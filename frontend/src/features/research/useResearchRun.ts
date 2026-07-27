import { useState, useEffect } from 'react';
import { api, ResearchRunEvent, ResearchRun } from './api';
import { AppNode, NodeStatus } from './components/GraphNode';
import { Edge } from '@xyflow/react';

// Hardcoded initial DAG layout
export const initialNodes: AppNode[] = [
  { id: 'plan_macro_sector', position: { x: 50, y: 50 }, data: { label: 'plan_macro_sector', status: 'pending' }, type: 'customNode' },
  { id: 'collect_macro_sector', position: { x: 50, y: 150 }, data: { label: 'collect_macro_sector', status: 'pending' }, type: 'customNode' },
  { id: 'discover_screen', position: { x: 50, y: 250 }, data: { label: 'discover_screen', status: 'pending' }, type: 'customNode' },
  { id: 'plan_tickers', position: { x: 50, y: 350 }, data: { label: 'plan_tickers', status: 'pending' }, type: 'customNode' },
  { id: 'collect_tickers_round1', position: { x: 50, y: 450 }, data: { label: 'collect_tickers_round1', status: 'pending' }, type: 'customNode' },
  { id: 'evidence_triage', position: { x: 50, y: 550 }, data: { label: 'evidence_triage', status: 'pending' }, type: 'customNode' },
  { id: 'collect_tickers_round2', position: { x: 50, y: 650 }, data: { label: 'collect_tickers_round2', status: 'pending', sourcePosition: 'right' }, type: 'customNode' },

  { id: 'macro_synthesis', position: { x: 400, y: 650 }, data: { label: 'macro_synthesis', status: 'pending', targetPosition: 'left', sourcePosition: 'top' }, type: 'customNode' },
  { id: 'sector_synthesis', position: { x: 400, y: 550 }, data: { label: 'sector_synthesis', status: 'pending', targetPosition: 'bottom', sourcePosition: 'top' }, type: 'customNode' },
  
  // Grouped Node: ticker_synthesis
  { 
    id: 'ticker_synthesis', 
    position: { x: 400, y: 50 }, 
    data: { label: 'ticker_synthesis', status: 'pending', targetPosition: 'bottom', sourcePosition: 'right' },
    style: { width: 300, height: 480, backgroundColor: 'rgba(255, 255, 255, 0.05)', border: '1px dashed var(--line-strong)', borderRadius: '12px' },
    type: 'group' // will be rendered via CustomGroupNode
  },
  { id: 'ts_draft', position: { x: 25, y: 40 }, data: { label: 'draft', status: 'pending', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_critique', position: { x: 25, y: 120 }, data: { label: 'critique', status: 'pending', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_revise', position: { x: 25, y: 200 }, data: { label: 'revise', status: 'pending', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_cio', position: { x: 25, y: 280 }, data: { label: 'CIO judgment', status: 'pending', llmTier: 'tier-frontier' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },
  { id: 'ts_validate', position: { x: 25, y: 360 }, data: { label: 'validate_citations', status: 'pending', llmTier: 'tier-local' }, type: 'customNode', parentId: 'ticker_synthesis', extent: 'parent' },

  { id: 'reconcile', position: { x: 750, y: 50 }, data: { label: 'reconcile_with_prior', status: 'pending', informational: true, targetPosition: 'left', sourcePosition: 'bottom' }, type: 'customNode' },
  { id: 'portfolio_synthesis', position: { x: 750, y: 150 }, data: { label: 'portfolio_synthesis', status: 'pending', targetPosition: 'top', sourcePosition: 'bottom' }, type: 'customNode' },
  { id: 'persist', position: { x: 750, y: 250 }, data: { label: 'persist', status: 'pending', targetPosition: 'top', sourcePosition: 'bottom' }, type: 'customNode' },
];

export const initialEdges: Edge[] = [
  { id: 'e1', source: 'plan_macro_sector', target: 'collect_macro_sector', animated: true, type: 'smoothstep' },
  { id: 'e2', source: 'collect_macro_sector', target: 'discover_screen', animated: true, type: 'smoothstep' },
  { id: 'e3', source: 'discover_screen', target: 'plan_tickers', animated: true, type: 'smoothstep' },
  { id: 'e4', source: 'plan_tickers', target: 'collect_tickers_round1', animated: true, type: 'smoothstep' },
  { id: 'e5', source: 'collect_tickers_round1', target: 'evidence_triage', animated: true, type: 'smoothstep' },
  { id: 'e6', source: 'evidence_triage', target: 'collect_tickers_round2', animated: true, type: 'smoothstep' },
  { id: 'e7', source: 'collect_tickers_round2', target: 'macro_synthesis', animated: true, type: 'smoothstep' },
  { id: 'e8', source: 'macro_synthesis', target: 'sector_synthesis', animated: true, type: 'smoothstep' },
  { id: 'e9', source: 'sector_synthesis', target: 'ticker_synthesis', animated: true, type: 'smoothstep' },
  
  // Group internal edges
  { id: 'e_ts1', source: 'ts_draft', target: 'ts_critique', animated: true, type: 'smoothstep' },
  { id: 'e_ts2', source: 'ts_critique', target: 'ts_revise', animated: true, type: 'smoothstep' },
  { id: 'e_ts3', source: 'ts_revise', target: 'ts_cio', animated: true, type: 'smoothstep' },
  { id: 'e_ts4', source: 'ts_cio', target: 'ts_validate', animated: true, type: 'smoothstep' },

  { 
    id: 'e_ts_out', 
    source: 'ticker_synthesis', 
    target: 'reconcile', 
    animated: true,
    type: 'smoothstep'
  },
  { id: 'e10', source: 'reconcile', target: 'portfolio_synthesis', animated: false, type: 'smoothstep' },
  { id: 'e11', source: 'portfolio_synthesis', target: 'persist', animated: false, type: 'smoothstep' },
];

export function useResearchRun(runId: string | null) {
  const [nodes, setNodes] = useState<AppNode[]>(initialNodes);
  const [events, setEvents] = useState<ResearchRunEvent[]>([]);
  const [runStatus, setRunStatus] = useState<string>('pending');
  
  // Track node status map locally to quickly update `nodes`
  const [nodeStatusMap, setNodeStatusMap] = useState<Record<string, 'pending' | 'running' | 'completed' | 'failed'>>({});

  useEffect(() => {
    if (!runId) return;

    // Reset state for new run
    setNodes(initialNodes);
    setEvents([]);
    setRunStatus('running');
    setNodeStatusMap({});

    const eventSource = new EventSource(`/research/stream/${runId}`);
    
    eventSource.addEventListener('node_event', (e: MessageEvent) => {
      const data: ResearchRunEvent = JSON.parse(e.data);
      setEvents(prev => [...prev, data]);
      
      if (data.event_type === 'run_completed') {
        setRunStatus('completed');
        eventSource.close();
      } else if (data.event_type === 'run_failed') {
        setRunStatus('failed');
        eventSource.close();
      } else if (data.event_type === 'node_start') {
        setNodeStatusMap(prev => ({ ...prev, [data.node]: 'running' }));
      } else if (data.event_type === 'node_complete') {
        setNodeStatusMap(prev => ({ ...prev, [data.node]: 'completed' }));
      } else if (data.event_type === 'node_error') {
        setNodeStatusMap(prev => ({ ...prev, [data.node]: 'failed' }));
      }
    });

    eventSource.onerror = (err) => {
      console.error('SSE Error:', err);
      eventSource.close();
      // Optionally fallback to polling here
    };

    return () => {
      eventSource.close();
    };
  }, [runId]);

  // Sync nodeStatusMap -> nodes
  useEffect(() => {
    setNodes(prev => prev.map(node => {
      const newStatus = nodeStatusMap[node.id];
      if (newStatus && newStatus !== node.data.status) {
        return {
          ...node,
          data: {
            ...node.data,
            status: newStatus
          }
        };
      }
      // Expand nested status to parent group
      if (node.id === 'ticker_synthesis') {
        const anyRunning = Object.keys(nodeStatusMap).some(k => k.startsWith('ts_') && nodeStatusMap[k] === 'running');
        const anyFailed = Object.keys(nodeStatusMap).some(k => k.startsWith('ts_') && nodeStatusMap[k] === 'failed');
        const allCompleted = ['ts_draft', 'ts_critique', 'ts_revise', 'ts_cio', 'ts_validate'].every(k => nodeStatusMap[k] === 'completed');
        
        let s: NodeStatus = 'pending';
        if (anyFailed) s = 'failed';
        else if (anyRunning) s = 'running';
        else if (allCompleted) s = 'completed';
        
        if (s !== node.data.status) {
           return { ...node, data: { ...node.data, status: s } };
        }
      }
      return node;
    }));
  }, [nodeStatusMap]);

  return { nodes, edges: initialEdges, events, runStatus };
}
