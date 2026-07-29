import React, { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { OrchestrationGraph } from './components/OrchestrationGraph';
import { NodeDetailsPanel } from './components/NodeDetailsPanel';
import { FileText, Plus, Activity, PanelLeftClose, PanelLeftOpen, Clock, Calendar, MoreVertical, Edit2, Trash2 } from 'lucide-react';
import './research.css';
import { ScheduleModal } from './ScheduleModal';
import { ActiveSchedulesModal } from './ActiveSchedulesModal';

import { api, ResearchRun } from './api';
import { useResearchRun } from './useResearchRun';

function formatTime(isoStr: string) {
  try {
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return isoStr;
  }
}

export function ResearchLayout() {
  const { runId } = useParams();
  const navigate = useNavigate();

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  
  // State for Runs view
  const selectedRunId = runId || null;
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const [runsList, setRunsList] = useState<ResearchRun[]>([]);
  const [activeMenuRunId, setActiveMenuRunId] = useState<string | null>(null);

  const { nodes, edges, runStatus, events } = useResearchRun(selectedRunId ?? null);

  // State for Watchlists
  const [watchlists, setWatchlists] = useState<import('./api').Watchlist[]>([]);
  const [selectedWatchlistId, setSelectedWatchlistId] = useState<string>('');
  // State for Schedules
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [isActiveSchedulesModalOpen, setIsActiveSchedulesModalOpen] = useState(false);
  const [schedulesCount, setSchedulesCount] = useState<number>(0);

  const fetchSchedulesCount = useCallback(async () => {
    try {
      const res = await api.getSchedules();
      setSchedulesCount(res.schedules.length);
    } catch (e) {
      console.error("Failed to fetch schedules count", e);
    }
  }, []);

  useEffect(() => {
    fetchSchedulesCount();
  }, [fetchSchedulesCount]);

  const fetchRuns = useCallback(async () => {
    try {
      const runsData = await api.getRuns();
      setRunsList(runsData.runs);
      return runsData.runs;
    } catch (err) {
      console.error("Failed to fetch runs", err);
      return [];
    }
  }, []);

  // Re-fetch when the actively viewed run finishes
  useEffect(() => {
    if (runStatus === 'completed' || runStatus === 'failed' || runStatus === 'cancelled') {
      fetchRuns();
    }
  }, [runStatus, fetchRuns]);

  // Poll every 15s if ANY run in the sidebar is 'running'
  useEffect(() => {
    const hasRunning = runsList.some(r => r.status === 'running');
    if (!hasRunning) return;
    
    const interval = setInterval(() => {
      fetchRuns();
    }, 15000);
    return () => clearInterval(interval);
  }, [runsList, fetchRuns]);

  useEffect(() => {
    // Fetch initial runs and watchlists
    Promise.all([fetchRuns(), api.getWatchlists()])
      .then(([runs, watchlistsData]) => {
        if (runs.length > 0 && !runId) {
          navigate(`/research/${runs[0].id}`, { replace: true });
        }
        setWatchlists(watchlistsData.watchlists);
        const portfolioWl = watchlistsData.watchlists.find(w => w.type === 'portfolio');
        if (portfolioWl) {
          setSelectedWatchlistId(portfolioWl.id);
        } else if (watchlistsData.watchlists.length > 0) {
          setSelectedWatchlistId(watchlistsData.watchlists[0].id);
        }
      })
      .catch(err => console.error("Failed to fetch initial data", err));
  }, [runId, navigate, fetchRuns]);

  const handleTriggerNewRun = useCallback(async () => {
    setIsTriggering(true);
    try {
      const targetId = selectedWatchlistId || undefined;
      const asyncExecution = localStorage.getItem("paisa_async_research") !== "false";
      const data = await api.triggerRun(targetId, asyncExecution);
      const newRun: ResearchRun = {
        id: data.run_id,
        status: 'running',
        started_at: new Date().toISOString(),
        completed_at: null,
      };
      setRunsList(prev => [newRun, ...prev]);
      navigate(`/research/${data.run_id}`);
    } catch (e) {
      console.error('Failed to trigger research run', e);
    } finally {
      setIsTriggering(false);
    }
  }, [selectedWatchlistId, navigate]);

  const handleRename = async (e: React.MouseEvent, id: string, currentTitle?: string | null) => {
    e.stopPropagation();
    setActiveMenuRunId(null);
    const defaultName = currentTitle || `Run ${id.slice(-6)}`;
    const newTitle = prompt('Enter new run title:', defaultName);
    if (newTitle !== null && newTitle.trim() !== '') {
      try {
        await api.renameRun(id, newTitle.trim());
        await fetchRuns();
      } catch (err) {
        alert('Failed to rename run');
      }
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setActiveMenuRunId(null);
    if (confirm('Are you sure you want to delete this run?')) {
      try {
        await api.deleteRun(id);
        setRunsList(prev => prev.filter(r => r.id !== id));
        if (selectedRunId === id) {
          navigate('/research');
        }
      } catch (err) {
        alert('Failed to delete run');
      }
    }
  };

  const selectedNode = nodes.find(n => n.id === selectedNodeId)?.data || null;

  const handleNodeClick = useCallback((id: string) => {
    setSelectedNodeId(id);
  }, []);

  const prevNodesRef = React.useRef<typeof nodes>([]);
  const prevRunIdRef = React.useRef<string | null>(null);

  // Auto-switch on node status change
  useEffect(() => {
    if (runStatus === 'running') {
      const prevNodes = prevNodesRef.current;
      
      if (prevRunIdRef.current !== selectedRunId) {
         const runningNode = nodes.find(n => n.data.status === 'running' && n.id !== 'ticker_synthesis');
         if (runningNode) setSelectedNodeId(runningNode.id);
      } else {
        let changedNode = null;
        for (const node of nodes) {
          const prevNode = prevNodes.find(n => n.id === node.id);
          if (prevNode && prevNode.data.status !== node.data.status) {
            changedNode = node;
            if (node.data.status === 'running') {
              break;
            }
          }
        }
        
        if (changedNode && changedNode.id !== 'ticker_synthesis') {
          setSelectedNodeId(changedNode.id);
        }
      }
    }
    
    prevNodesRef.current = nodes;
    prevRunIdRef.current = selectedRunId;
  }, [nodes, runStatus, selectedRunId]);

  return (
    <div className="research-layout" onClick={() => setActiveMenuRunId(null)}>
      
      {/* Unified Sidebar Container */}
      <div className={`research-sidebar ${isSidebarCollapsed ? 'research-sidebar--collapsed' : ''}`} style={{ width: isSidebarCollapsed ? '56px' : '280px', transition: 'width 0.2s', display: 'flex', flexDirection: 'column', flexShrink: 0, borderRight: '1px solid var(--line)', background: 'var(--surface)', position: 'relative', zIndex: 10 }}>
        
        {/* Sidebar Header & Collapse Toggle */}
        <div style={{ display: 'flex', justifyContent: isSidebarCollapsed ? 'center' : 'space-between', alignItems: 'center', padding: '16px', borderBottom: '1px solid var(--line)' }}>
          {!isSidebarCollapsed && <h2 className="research-sidebar__title">Research Hub</h2>}
          <button className="research-panel__close" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)} title="Toggle sidebar">
            {isSidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        {/* List Content */}
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          <ul className="research-sidebar__list">
            {runsList.map((run) => (
              <li key={run.id} style={{ position: 'relative' }}>
                <div 
                  role="button"
                  tabIndex={0}
                  onClick={() => navigate(`/research/${run.id}`)}
                  className={`research-sidebar__item ${run.id === selectedRunId ? 'research-sidebar__item--selected' : ''}`}
                  style={{ background: 'transparent', border: 'none', width: '100%', textAlign: 'left', padding: isSidebarCollapsed ? '12px' : '12px 16px', display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer', borderBottom: '1px solid var(--line)' }}
                  title={run.title || `Run ${run.id.slice(0,8)}`}
                >
                  <div className="research-sidebar__item-icon">
                    {run.status === 'running' ? <Activity size={16} color="var(--blue)" /> : (run.status === 'failed' ? <FileText size={16} color="var(--red)" /> : <FileText size={16} color="var(--green)" />)}
                  </div>
                  {!isSidebarCollapsed && (
                    <div style={{ minWidth: 0, overflow: 'hidden', textAlign: 'left', flex: 1 }}>
                      <div className="research-sidebar__item-title">{run.title || `Run ${run.id.slice(-6)}`}</div>
                      <div className="research-sidebar__item-meta">
                        <span>{formatTime(run.started_at)}</span>
                      </div>
                    </div>
                  )}
                  {!isSidebarCollapsed && (
                    <div className="research-sidebar__item-actions" onClick={e => e.stopPropagation()}>
                      <button 
                        className="research-btn-icon" 
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveMenuRunId(activeMenuRunId === run.id ? null : run.id);
                        }}
                      >
                        <MoreVertical size={14} />
                      </button>
                      {activeMenuRunId === run.id && (
                        <div className="research-menu-dropdown" style={{ position: 'absolute', right: '16px', top: '40px', background: 'var(--surface-raised)', border: '1px solid var(--line)', borderRadius: '6px', padding: '4px', zIndex: 100, boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
                          <button onClick={(e) => handleRename(e, run.id, run.title)} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', width: '100%', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '13px', color: 'var(--foreground)', textAlign: 'left' }}>
                            <Edit2 size={14} /> Rename
                          </button>
                          <button onClick={(e) => handleDelete(e, run.id)} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', width: '100%', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '13px', color: 'var(--red)', textAlign: 'left' }}>
                            <Trash2 size={14} /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>
      
      <main className="research-main">
        {/* Header Controls */}
        <header className="research-header">
          <div className="research-header__title">
            Research Orchestrator
            <span className={`research-badge ${runStatus === 'running' ? 'research-badge--running' : ''}`}>
              {runStatus === 'running' ? 'Running...' : (runStatus === 'failed' ? 'Failed' : 'Completed')}
            </span>
          </div>
          
          <div className="research-header__actions">
            {watchlists.length > 0 && (
              <select 
                value={selectedWatchlistId} 
                onChange={e => setSelectedWatchlistId(e.target.value)}
                className="research-select"
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--line)',
                  background: 'var(--surface)',
                  color: 'var(--foreground)',
                  fontSize: '13px',
                  fontWeight: 500,
                  marginRight: '8px'
                }}
              >
                {watchlists.map(wl => (
                  <option key={wl.id} value={wl.id}>
                    {wl.name}
                  </option>
                ))}
              </select>
            )}
            <button 
              onClick={() => setIsScheduleModalOpen(true)}
              className="research-btn"
            >
              <Clock size={16} />
              Schedule
            </button>
            <button
              onClick={() => setIsActiveSchedulesModalOpen(true)}
              className="research-btn"
              title="View active scheduled runs"
            >
              <Calendar size={16} />
              Schedules {schedulesCount > 0 && `(${schedulesCount})`}
            </button>
            <button 
              onClick={handleTriggerNewRun}
              disabled={isTriggering}
              className="research-btn research-btn--primary"
            >
              <Plus size={16} />
              {isTriggering ? 'Starting...' : 'New Run'}
            </button>
            {runStatus === 'running' && (
              <button
                onClick={async () => {
                  if (!selectedRunId) return;
                  try {
                    await api.cancelRun(selectedRunId);
                  } catch (e) {
                    alert('Failed to cancel run.');
                  }
                }}
                className="research-btn"
                style={{ color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.3)' }}
              >
                Stop Run
              </button>
            )}
          </div>
        </header>

        {/* Graph Area */}
        <div className="research-graph-container" style={{ display: 'flex', position: 'relative', overflow: 'hidden' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            {selectedRunId ? (
              <OrchestrationGraph
                nodes={nodes}
                edges={edges}
                onNodeClick={handleNodeClick}
              />
            ) : (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--muted)' }}>
                No run selected.
              </div>
            )}
            
            {selectedNodeId && (
              <NodeDetailsPanel
                runId={selectedRunId || ''}
                nodeData={{ ...selectedNode, id: selectedNodeId } as any}
                events={events}
                onClose={() => setSelectedNodeId(null)}
              />
            )}
          </div>
        </div>
      </main>

      <ScheduleModal
        isOpen={isScheduleModalOpen}
        onClose={() => setIsScheduleModalOpen(false)}
        selectedWatchlistName={watchlists.find(w => w.id === selectedWatchlistId)?.name}
        onSchedule={async (cronExpression: string) => {
          await api.scheduleRun(cronExpression, selectedWatchlistId || undefined);
          fetchSchedulesCount();
          alert('Run scheduled successfully!');
        }}
      />

      <ActiveSchedulesModal
        isOpen={isActiveSchedulesModalOpen}
        onClose={() => setIsActiveSchedulesModalOpen(false)}
        onSchedulesUpdated={fetchSchedulesCount}
      />
    </div>
  );
}
