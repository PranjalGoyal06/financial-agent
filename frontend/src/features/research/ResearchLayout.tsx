import React, { useState, useCallback } from 'react';
import { Edge } from '@xyflow/react';
import { RunHistorySidebar, RunHistoryItem } from './components/RunHistorySidebar';
import { OrchestrationGraph } from './components/OrchestrationGraph';
import { EvidenceDrawer, EvidenceItem } from './components/EvidenceDrawer';
import { NodeDetailsPanel } from './components/NodeDetailsPanel';
import { DiscoveryThesisView, DiscoveredTicker } from './components/DiscoveryThesisView';
import { AppNode, GraphNodeData } from './components/GraphNode';
import { FileText, Plus, Search, Activity, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import './research.css';

// ── Mock Data ─────────────────────────────────────────────────────────────────

const mockRuns: RunHistoryItem[] = [
  { id: '1', topic: 'Market Analysis Q3', date: 'Oct 26, 2026', status: 'running', duration: '14m 20s' },
  { id: '2', topic: 'Competitor Scrape v1', date: 'Oct 25, 2026', status: 'completed', duration: '45m 0s' },
];

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

const initialNodes: AppNode[] = [
  { id: 'plan_macro_sector', position: { x: 250, y: 50 }, data: { label: 'plan_macro_sector', status: 'completed' }, type: 'customNode' },
  { id: 'collect_macro_sector', position: { x: 250, y: 150 }, data: { label: 'collect_macro_sector', status: 'completed' }, type: 'customNode' },
  { id: 'discover_screen', position: { x: 250, y: 250 }, data: { label: 'discover_screen', status: 'completed' }, type: 'customNode' },
  { id: 'plan_tickers', position: { x: 250, y: 350 }, data: { label: 'plan_tickers', status: 'completed' }, type: 'customNode' },
  { id: 'collect_tickers_round1', position: { x: 250, y: 450 }, data: { label: 'collect_tickers_round1', status: 'completed' }, type: 'customNode' },
  { id: 'evidence_triage', position: { x: 250, y: 550 }, data: { label: 'evidence_triage', status: 'completed' }, type: 'customNode' },
  { id: 'collect_tickers_round2', position: { x: 250, y: 650 }, data: { label: 'collect_tickers_round2', status: 'completed', ghosted: true }, type: 'customNode' },
  { id: 'macro_synthesis', position: { x: 250, y: 750 }, data: { label: 'macro_synthesis', status: 'completed' }, type: 'customNode' },
  { id: 'sector_synthesis', position: { x: 250, y: 850 }, data: { label: 'sector_synthesis', status: 'completed' }, type: 'customNode' },
  
  // Grouped Node: ticker_synthesis
  { 
    id: 'ticker_synthesis', 
    position: { x: 200, y: 950 }, 
    data: { label: 'ticker_synthesis', status: 'running' },
    style: { width: 300, height: 480, backgroundColor: 'rgba(255, 255, 255, 0.05)', border: '1px dashed var(--line-strong)', borderRadius: '12px' },
    type: 'group' // default react flow group
  },
  { id: 'ts_draft', position: { x: 25, y: 40 }, data: { label: 'draft', status: 'completed', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_critique', position: { x: 25, y: 120 }, data: { label: 'critique', status: 'completed', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_revise', position: { x: 25, y: 200 }, data: { label: 'revise', status: 'completed', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_cio', position: { x: 25, y: 280 }, data: { label: 'CIO judgment', status: 'completed', llmTier: 'tier-frontier' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_validate', position: { x: 25, y: 360 }, data: { label: 'validate_citations', status: 'running', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },

  { id: 'reconcile', position: { x: 250, y: 1500 }, data: { label: 'reconcile_with_prior', status: 'pending', informational: true }, type: 'customNode' },
  { id: 'portfolio_synthesis', position: { x: 250, y: 1600 }, data: { label: 'portfolio_synthesis', status: 'pending' }, type: 'customNode' },
  { id: 'persist', position: { x: 250, y: 1700 }, data: { label: 'persist', status: 'pending' }, type: 'customNode' },
];

const initialEdges: Edge[] = [
  { id: 'e1', source: 'plan_macro_sector', target: 'collect_macro_sector', animated: true },
  { id: 'e2', source: 'collect_macro_sector', target: 'discover_screen', animated: true },
  { id: 'e3', source: 'discover_screen', target: 'plan_tickers', animated: true },
  { id: 'e4', source: 'plan_tickers', target: 'collect_tickers_round1', animated: true },
  { id: 'e5', source: 'collect_tickers_round1', target: 'evidence_triage', animated: true },
  { id: 'e6', source: 'evidence_triage', target: 'collect_tickers_round2', animated: true },
  { id: 'e7', source: 'collect_tickers_round2', target: 'macro_synthesis', animated: true },
  { id: 'e8', source: 'macro_synthesis', target: 'sector_synthesis', animated: true },
  { id: 'e9', source: 'sector_synthesis', target: 'ticker_synthesis', animated: true },
  
  // Group internal edges
  { id: 'e_ts1', source: 'ts_draft', target: 'ts_critique', animated: true },
  { id: 'e_ts2', source: 'ts_critique', target: 'ts_revise', animated: true },
  { id: 'e_ts3', source: 'ts_revise', target: 'ts_cio', animated: true },
  { id: 'e_ts4', source: 'ts_cio', target: 'ts_validate', animated: true },

  // Group to reconcile (with edge label)
  { 
    id: 'e_ts_out', 
    source: 'ticker_synthesis', 
    target: 'reconcile', 
    animated: true,
    label: '⚠ Flipped to BUY (Upgraded conviction)',
    labelStyle: { fill: 'var(--ink)', fontWeight: 600, fontSize: 11 },
    labelBgStyle: { fill: 'var(--surface)', stroke: 'var(--blue)', strokeWidth: 1, rx: 4, ry: 4 },
    labelBgPadding: [8, 4]
  },
  { id: 'e10', source: 'reconcile', target: 'portfolio_synthesis', animated: false },
  { id: 'e11', source: 'portfolio_synthesis', target: 'persist', animated: false },
];

const mockEvidence: EvidenceItem[] = [
  { id: 'e1', type: 'url', title: 'Q3 Market Earnings Report', urlOrPath: 'https://example.com/q3', status: 'useful', snippet: 'The market saw a 12% increase...' },
  { id: 'e2', type: 'document', title: 'Competitor PDF', urlOrPath: '#', status: 'discarded', reason: '404 Not Found' }
];

export function ResearchLayout() {
  const [activeTab, setActiveTab] = useState<'runs' | 'discovery'>('runs');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  
  // State for Runs view
  const [selectedRunId, setSelectedRunId] = useState<string>('1');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isEvidenceDrawerOpen, setEvidenceDrawerOpen] = useState(false);

  // State for Discovery view
  const [selectedDiscoveryId, setSelectedDiscoveryId] = useState<string>('d1');

  const selectedNode = initialNodes.find(n => n.id === selectedNodeId)?.data || null;
  const selectedDiscovery = mockDiscoveries.find(d => d.id === selectedDiscoveryId) || null;

  const handleNodeClick = useCallback((id: string) => {
    setSelectedNodeId(id);
  }, []);

  return (
    <div className="research-layout">
      
      {/* Unified Sidebar Container */}
      <div className={`research-sidebar ${isSidebarCollapsed ? 'research-sidebar--collapsed' : ''}`} style={{ width: isSidebarCollapsed ? '56px' : '280px', transition: 'width 0.2s', display: 'flex', flexDirection: 'column', flexShrink: 0, borderRight: '1px solid var(--line)', background: 'var(--surface)' }}>
        
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
              {mockRuns.map((run) => (
                <li key={run.id}>
                  <button
                    onClick={() => setSelectedRunId(run.id)}
                    className={`research-sidebar__item ${run.id === selectedRunId ? 'research-sidebar__item--selected' : ''}`}
                    style={{ justifyContent: isSidebarCollapsed ? 'center' : 'flex-start', padding: isSidebarCollapsed ? '16px 0' : '12px 16px' }}
                    title={run.topic}
                  >
                    <div className="research-sidebar__item-icon">
                      {run.status === 'running' ? <Activity size={16} color="var(--blue)" /> : <FileText size={16} color="var(--green)" />}
                    </div>
                    {!isSidebarCollapsed && (
                      <div style={{ minWidth: 0, overflow: 'hidden', textAlign: 'left' }}>
                        <div className="research-sidebar__item-title">{run.topic}</div>
                        <div className="research-sidebar__item-meta">
                          <span>{run.date}</span>
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
              <span className="research-badge">Running</span>
            </div>
            
            <div className="research-header__actions">
              <button 
                onClick={() => setEvidenceDrawerOpen(!isEvidenceDrawerOpen)}
                className="research-btn"
              >
                <FileText size={16} />
                Evidence
              </button>
              <button className="research-btn research-btn--primary">
                <Plus size={16} />
                New Run
              </button>
            </div>
          </header>

          {/* Graph Area */}
          <div className="research-graph-container" style={{ display: 'flex', position: 'relative', overflow: 'hidden' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <OrchestrationGraph
                nodes={initialNodes}
                edges={initialEdges}
                onNodeClick={handleNodeClick}
              />
              
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
