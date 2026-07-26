import React, { useState, useCallback, useEffect } from 'react';
import { RunHistorySidebar, RunHistoryItem } from './components/RunHistorySidebar';
import { OrchestrationGraph } from './components/OrchestrationGraph';
import { EvidenceDrawer, EvidenceItem } from './components/EvidenceDrawer';
import { NodeDetailsPanel } from './components/NodeDetailsPanel';
import { DiscoveryThesisView, DiscoveredTicker } from './components/DiscoveryThesisView';
import { AppNode, GraphNodeData } from './components/GraphNode';
import { FileText, Plus, Search, Activity, PanelLeftClose, PanelLeftOpen, Clock } from 'lucide-react';
import './research.css';

import { api, ResearchRun } from './api';
import { useResearchRun } from './useResearchRun';

// ── Mock Data ─────────────────────────────────────────────────────────────────

const mockDiscoveries: DiscoveredTicker[] = [
  { 
    id: 'd1', 
    ticker: 'ZOMATO', 
    companyName: 'Zomato Ltd', 
    date: 'Oct 26, 2026',
    discoveryVector: 'Spillover from Swiggy IPO analysis indicated massive market share consolidation.',
    thesis: 'Zomato has demonstrated sustained profitability over the last 3 quarters. The upcoming Swiggy IPO is bringing significant attention to the food delivery duopoly, where Zomato currently holds the edge in Blinkit (quick commerce) execution.\n\nKey drivers:\n1. Quick commerce achieving EBITDA break-even.\n2. Platform fee hikes driving pure margin expansion.\n3. Rationalized discount structures.'
  },
  { 
    id: 'd2', 
    ticker: 'SUZLON', 
    companyName: 'Suzlon Energy', 
    date: 'Oct 25, 2026',
    discoveryVector: 'Macro sector rotation into renewable energy infrastructure detected.',
    thesis: 'Debt restructuring is complete and the order book is at a multi-year high. Policy tailwinds for wind energy make this a strong turnaround candidate.'
  }
];

const mockEvidence: EvidenceItem[] = [
  { id: 'e1', type: 'url', title: 'Q3 Market Earnings Report', urlOrPath: 'https://example.com/q3', status: 'useful', snippet: 'The market saw a 12% increase...' },
  { id: 'e2', type: 'document', title: 'Competitor PDF', urlOrPath: '#', status: 'discarded', reason: '404 Not Found' }
];

function formatTime(isoStr: string) {
  try {
    return new Date(isoStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return isoStr;
  }
}

export function ResearchLayout() {
  const [activeTab, setActiveTab] = useState<'runs' | 'discovery'>('runs');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  
  // State for Runs view
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isEvidenceDrawerOpen, setEvidenceDrawerOpen] = useState(false);
  const [isTriggering, setIsTriggering] = useState(false);
  const [runsList, setRunsList] = useState<ResearchRun[]>([]);

  const { nodes, edges, events, runStatus } = useResearchRun(selectedRunId);

  useEffect(() => {
    // Fetch initial runs
    api.getRuns().then(data => {
      setRunsList(data.runs);
      if (data.runs.length > 0) {
        setSelectedRunId(data.runs[0].id);
      }
    }).catch(err => console.error("Failed to fetch runs", err));
  }, []);

  // State for Discovery view
  const [selectedDiscoveryId, setSelectedDiscoveryId] = useState<string>('d1');

  const handleTriggerNewRun = useCallback(async () => {
    setIsTriggering(true);
    try {
      const data = await api.triggerRun();
      const newRun: ResearchRun = {
        id: data.run_id,
        status: 'running',
        started_at: new Date().toISOString(),
        completed_at: null,
      };
      setRunsList(prev => [newRun, ...prev]);
      setSelectedRunId(data.run_id);
    } catch (e) {
      console.error('Failed to trigger research run', e);
    } finally {
      setIsTriggering(false);
    }
  }, []);

  const selectedNode = nodes.find(n => n.id === selectedNodeId)?.data || null;
  const selectedDiscovery = mockDiscoveries.find(d => d.id === selectedDiscoveryId) || null;

  const handleNodeClick = useCallback((id: string) => {
    setSelectedNodeId(id);
  }, []);

  return (
    <div className="research-layout">
      
      {/* Unified Sidebar Container */}
      <div className={`research-sidebar ${isSidebarCollapsed ? 'research-sidebar--collapsed' : ''}`} style={{ width: isSidebarCollapsed ? '56px' : '280px', transition: 'width 0.2s', display: 'flex', flexDirection: 'column', flexShrink: 0, borderRight: '1px solid var(--line)', background: 'var(--surface)', position: 'relative', zIndex: 10 }}>
        
        {/* Sidebar Header & Collapse Toggle */}
        <div style={{ display: 'flex', justifyContent: isSidebarCollapsed ? 'center' : 'space-between', alignItems: 'center', padding: '16px', borderBottom: '1px solid var(--line)' }}>
          {!isSidebarCollapsed && <h2 className="research-sidebar__title">Research Hub</h2>}
          <button className="research-panel__close" onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)} title="Toggle sidebar">
            {isSidebarCollapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        {/* Tab Switchers */}
        <div style={{ display: 'flex', flexDirection: isSidebarCollapsed ? 'column' : 'row', borderBottom: '1px solid var(--line)' }}>
          <button 
            onClick={() => setActiveTab('runs')}
            style={{ flex: 1, padding: '12px', background: activeTab === 'runs' ? 'var(--surface-hover)' : 'transparent', border: 'none', borderBottom: activeTab === 'runs' && !isSidebarCollapsed ? '2px solid var(--blue)' : '2px solid transparent', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', color: activeTab === 'runs' ? 'var(--blue)' : 'var(--muted)' }}
            title="Run History"
          >
            <Activity size={16} />
            {!isSidebarCollapsed && <span style={{ fontSize: '13px', fontWeight: 600 }}>Runs</span>}
          </button>
          <button 
            onClick={() => setActiveTab('discovery')}
            style={{ flex: 1, padding: '12px', background: activeTab === 'discovery' ? 'var(--surface-hover)' : 'transparent', border: 'none', borderBottom: activeTab === 'discovery' && !isSidebarCollapsed ? '2px solid var(--blue)' : '2px solid transparent', cursor: 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px', color: activeTab === 'discovery' ? 'var(--blue)' : 'var(--muted)' }}
            title="Discovery Desk"
          >
            <Search size={16} />
            {!isSidebarCollapsed && <span style={{ fontSize: '13px', fontWeight: 600 }}>Discovery</span>}
          </button>
        </div>

        {/* List Content */}
        <div style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          {activeTab === 'runs' ? (
            <ul className="research-sidebar__list">
              {runsList.map((run) => (
                <li key={run.id}>
                  <button
                    onClick={() => setSelectedRunId(run.id)}
                    className={`research-sidebar__item ${run.id === selectedRunId ? 'research-sidebar__item--selected' : ''}`}
                    style={{ justifyContent: isSidebarCollapsed ? 'center' : 'flex-start', padding: isSidebarCollapsed ? '16px 0' : '12px 16px' }}
                    title={`Run ${run.id.slice(0,8)}`}
                  >
                    <div className="research-sidebar__item-icon">
                      {run.status === 'running' ? <Activity size={16} color="var(--blue)" /> : (run.status === 'failed' ? <FileText size={16} color="var(--red)" /> : <FileText size={16} color="var(--green)" />)}
                    </div>
                    {!isSidebarCollapsed && (
                      <div style={{ minWidth: 0, overflow: 'hidden', textAlign: 'left' }}>
                        <div className="research-sidebar__item-title">Run {run.id.slice(-6)}</div>
                        <div className="research-sidebar__item-meta">
                          <span>{formatTime(run.started_at)}</span>
                        </div>
                      </div>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <ul className="research-sidebar__list">
              {mockDiscoveries.map((disc) => (
                <li key={disc.id}>
                  <button
                    onClick={() => setSelectedDiscoveryId(disc.id)}
                    className={`research-sidebar__item ${disc.id === selectedDiscoveryId ? 'research-sidebar__item--selected' : ''}`}
                    style={{ justifyContent: isSidebarCollapsed ? 'center' : 'flex-start', padding: isSidebarCollapsed ? '16px 0' : '12px 16px' }}
                    title={disc.ticker}
                  >
                    <div className="research-sidebar__item-icon">
                      <Search size={16} color={disc.id === selectedDiscoveryId ? 'var(--blue)' : 'var(--muted)'} />
                    </div>
                    {!isSidebarCollapsed && (
                      <div style={{ minWidth: 0, overflow: 'hidden', textAlign: 'left' }}>
                        <div className="research-sidebar__item-title">{disc.ticker}</div>
                        <div className="research-sidebar__item-meta">
                          <span>{disc.date}</span>
                        </div>
                      </div>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      
      {activeTab === 'runs' ? (
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
              <button 
                onClick={() => setEvidenceDrawerOpen(!isEvidenceDrawerOpen)}
                className="research-btn"
              >
                <FileText size={16} />
                Evidence
              </button>
              <button 
                onClick={async () => {
                  const cron = prompt('Enter a cron expression to schedule a daily run (e.g., "0 17 * * 1-5" for 5 PM weekdays):', '0 17 * * 1-5');
                  if (cron) {
                    try {
                      await api.scheduleRun(cron);
                      alert('Run scheduled successfully!');
                    } catch (e) {
                      alert('Failed to schedule run.');
                    }
                  }
                }}
                className="research-btn"
              >
                <Clock size={16} />
                Schedule
              </button>
              <button 
                onClick={handleTriggerNewRun}
                disabled={isTriggering}
                className="research-btn research-btn--primary"
              >
                <Plus size={16} />
                {isTriggering ? 'Starting...' : 'New Run'}
              </button>
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
                  nodeData={selectedNode}
                  onClose={() => setSelectedNodeId(null)}
                />
              )}
            </div>
            
            <EvidenceDrawer
              isOpen={isEvidenceDrawerOpen}
              onClose={() => setEvidenceDrawerOpen(false)}
              evidence={mockEvidence}
            />
          </div>
        </main>
      ) : (
        <DiscoveryThesisView 
          ticker={selectedDiscovery} 
          onAddToWatchlist={(id) => console.log('Added to watchlist', id)}
          onDismiss={(id) => console.log('Dismissed', id)}
        />
      )}
    </div>
  );
}

