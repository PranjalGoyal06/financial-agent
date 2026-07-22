import React, { useState, useCallback } from 'react';
import { Edge } from '@xyflow/react';
import { RunHistorySidebar, RunHistoryItem } from './components/RunHistorySidebar';
import { OrchestrationGraph } from './components/OrchestrationGraph';
import { EvidenceDrawer, EvidenceItem } from './components/EvidenceDrawer';
import { NodeDetailsPanel } from './components/NodeDetailsPanel';
import { AppNode, GraphNodeData } from './components/GraphNode';
import { FileText, Plus } from 'lucide-react';
import './research.css';

// Mock Data for demonstration
const mockRuns: RunHistoryItem[] = [
  { id: '1', topic: 'Market Analysis Q3', date: 'Oct 26, 2026', status: 'running', duration: '14m 20s' },
  { id: '2', topic: 'Competitor Scrape v1', date: 'Oct 25, 2026', status: 'completed', duration: '45m 0s' },
];

const initialNodes: AppNode[] = [
  { id: 'start', position: { x: 250, y: 50 }, data: { label: 'Start Research', status: 'completed' }, type: 'customNode' },
  { id: 'scrape', position: { x: 250, y: 150 }, data: { label: 'Web Scrape', status: 'completed' }, type: 'customNode' },
  { id: 'extract', position: { x: 500, y: 150 }, data: { label: 'Text Extraction', status: 'completed' }, type: 'customNode' },
  { id: 'summarize', position: { x: 250, y: 250 }, data: { label: 'Summarization', status: 'completed' }, type: 'customNode' },
  { id: 'insight', position: { x: 500, y: 250 }, data: { label: 'Insight Generation', status: 'running' }, type: 'customNode' },
  { id: 'report', position: { x: 500, y: 350 }, data: { label: 'Report Generation', status: 'pending' }, type: 'customNode' },
];

const initialEdges: Edge[] = [
  { id: 'e1', source: 'start', target: 'scrape', animated: true },
  { id: 'e2', source: 'scrape', target: 'extract', animated: true },
  { id: 'e3', source: 'scrape', target: 'summarize', animated: true },
  { id: 'e4', source: 'summarize', target: 'insight', animated: true },
  { id: 'e5', source: 'insight', target: 'report', animated: false },
];

const mockEvidence: EvidenceItem[] = [
  { id: 'e1', type: 'url', title: 'Q3 Market Earnings Report', urlOrPath: 'https://example.com/q3', status: 'useful', snippet: 'The market saw a 12% increase...' },
  { id: 'e2', type: 'document', title: 'Competitor PDF', urlOrPath: '#', status: 'discarded', reason: '404 Not Found' }
];

export function ResearchLayout() {
  const [selectedRunId, setSelectedRunId] = useState<string>('1');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [isEvidenceDrawerOpen, setEvidenceDrawerOpen] = useState(false);

  const selectedNode = initialNodes.find(n => n.id === selectedNodeId)?.data || null;

  const handleNodeClick = useCallback((id: string) => {
    setSelectedNodeId(id);
  }, []);

  return (
    <div className="research-layout">
      <RunHistorySidebar
        runs={mockRuns}
        selectedRunId={selectedRunId}
        onSelectRun={setSelectedRunId}
      />
      
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
    </div>
  );
}
