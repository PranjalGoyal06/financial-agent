import React, { useState } from 'react';
import { X, Terminal, Activity, FileJson } from 'lucide-react';
import { GraphNodeData } from './GraphNode';
import { ResearchRunEvent } from '../api';

type NodeDetailsPanelProps = {
  runId: string;
  nodeData: GraphNodeData & { id?: string } | null;
  events?: ResearchRunEvent[];
  onClose: () => void;
};

const NODE_SUMMARIES: Record<string, string> = {
  plan_macro_sector: 'Resolves the initial watchlist targets and categorizes them by industry sectors.',
  collect_macro_sector: 'Gathers broad economic data and sector-specific news to establish market context.',
  macro_synthesis: 'Analyzes market-wide evidence to build a foundational view of current macroeconomic conditions.',
  sector_synthesis: 'Synthesizes sector evidence to identify prevailing tailwinds, headwinds, and thematic trends.',
  discover_screen: 'Scans the market using screener constraints and sector spillovers to uncover new investment candidates.',
  plan_tickers: 'Finalizes the complete list of target tickers, merging user holdings with newly discovered candidates.',
  collect_tickers_round1: 'Scours real-time web sources and financial APIs to collect news, filings, and price action data for selected assets.',
  ticker_synthesis: 'Evaluates the gathered evidence for each ticker to construct a baseline investment thesis.',
  ts_draft: 'Drafts the initial investment thesis and evidence summary for the ticker.',
  ts_critique: 'Critiques the drafted thesis, checking for bias, logic gaps, or omitted evidence.',
  ts_revise: 'Revises the draft thesis based on the local critique to strengthen the argument.',
  ts_cio: 'Submits the revised thesis to the frontier model for high-level CIO judgment and approval.',
  ts_validate: 'Validates all citations and data points in the final thesis against raw evidence.',
  reconcile: 'Compares current findings with previous research runs to detect major shifts or thesis drifts.',
  evidence_triage: 'Identifies gaps in the current research and formulates highly specific follow-up queries.',
  collect_tickers_round2: 'Executes targeted follow-up searches to patch missing evidence and resolve ambiguities.',
  ticker_synthesis_round2: 'Re-evaluates the ticker thesis by incorporating the newly gathered follow-up evidence.',
  portfolio_synthesis: 'Aggregates all insights to produce the final CIO-level briefing and cross-asset correlation analysis.',
  persist: 'Saves the comprehensive research pack and generated artifacts securely to the database.'
};

export function NodeDetailsPanel({ runId, nodeData, events = [], onClose }: NodeDetailsPanelProps) {
  if (!nodeData) return null;

  // Use nodeData.id or fallback to nodeData.label, since the label usually matches the key
  const nodeId = (nodeData.id || nodeData.label || '') as string;
  const summary = NODE_SUMMARIES[nodeId] || 'Executes specialized analysis tasks for the research pipeline.';

  // Filter events strictly for this node. (The node ID is the source of truth).
  const nodeEvents = events.filter(e => e.node === nodeId);
  
  const [terminalLogs, setTerminalLogs] = useState<any[]>([]);
  const [isFetchingLogs, setIsFetchingLogs] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);

  const fetchDetailedLogs = async () => {
    if (!runId || !nodeId) return;
    setIsFetchingLogs(true);
    setLogsError(null);
    try {
      const res = await fetch(`/api/research/logs/${runId}?node=${nodeId}`);
      if (!res.ok) throw new Error('Failed to fetch detailed logs');
      const data = await res.json();
      setTerminalLogs(data);
    } catch (err) {
      setLogsError(String(err));
    } finally {
      setIsFetchingLogs(false);
    }
  };

  return (
    <div className="research-panel" style={{ position: 'absolute', top: 0, right: 0, bottom: 0 }}>
      <div className="research-panel__header">
        <div>
          <h2 className="research-panel__title">{nodeData.label}</h2>
          <span style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--muted)', fontWeight: 500 }}>
            Status: <span style={{ color: 'var(--blue)' }}>{nodeData.status}</span>
          </span>
        </div>
        <button className="research-panel__close" onClick={onClose}>
          <X size={18} />
        </button>
      </div>

      <div className="research-panel__body" style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%' }}>
        <div style={{ background: 'var(--surface-hover)', padding: '12px', borderRadius: '6px', fontSize: '13px', color: 'var(--text)', border: '1px solid var(--line)' }}>
          {summary}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--line)', paddingBottom: '8px', fontSize: '13px', fontWeight: 500, color: 'var(--text)' }}>
          <Activity size={14} /> Node Events & Logs
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '300px', gap: '12px' }}>
          <div className="node-logs" style={{ flex: 1 }}>
            <div className="node-logs__line node-logs__line--system">[System] Node execution started...</div>
            {nodeEvents.length === 0 && (
              <div className="node-logs__line">Loading required context...</div>
            )}
            
            {nodeEvents.map((e, i) => (
              <div key={i} className={`node-logs__line ${e.level === 'ERROR' ? 'node-logs__line--error' : ''}`}>
                <span style={{ color: 'var(--muted)' }}>{new Date(e.timestamp).toLocaleTimeString()}</span>{' '}
                {e.event_type === 'api_traffic' ? <span style={{ color: 'var(--blue)' }}>[API]</span> : null}
                {e.event_type === 'llm_call' ? <span style={{ color: 'var(--purple)' }}>[LLM]</span> : null}
                {e.event_type === 'triage_gate' ? <span style={{ color: 'var(--orange)' }}>[Triage]</span> : null}
                {e.event_type === 'console' ? <span style={{ color: 'var(--green)' }}>[Log]</span> : null}
                {' '}{e.summary}
              </div>
            ))}
            
            {nodeData.status === 'running' && (
              <div className="node-logs__line" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#4C6FB7', marginTop: '8px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#4C6FB7', animation: 'pulse 2s infinite' }}></span>
                Processing task...
              </div>
            )}
            
            {nodeData.status === 'completed' && (
              <div className="node-logs__line node-logs__line--success" style={{ marginTop: '8px' }}>[System] Execution completed successfully.</div>
            )}
            
            {nodeData.status === 'failed' && (
              <div className="node-logs__line node-logs__line--error" style={{ marginTop: '8px' }}>[Error] Execution terminated unexpectedly.</div>
            )}

            {terminalLogs.length > 0 && (
              <div style={{ marginTop: '16px', borderTop: '1px dashed var(--line)', paddingTop: '16px' }}>
                <div className="node-logs__line node-logs__line--system" style={{ marginBottom: '8px' }}>
                  --- RAW JSON PAYLOADS ---
                </div>
                {terminalLogs.map((log, i) => (
                  <div key={i} style={{ marginBottom: '16px' }}>
                    <div style={{ color: 'var(--muted)', fontSize: '11px', marginBottom: '4px' }}>
                      {new Date(log.timestamp).toLocaleTimeString()} - {log.action}
                    </div>
                    <pre style={{ margin: 0, padding: '12px', background: '#0a0a0a', borderRadius: '4px', overflowX: 'auto', fontSize: '11px', color: '#a0aec0', fontFamily: 'monospace' }}>
                      {JSON.stringify(log.details, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          <button 
            className="research-btn research-btn--secondary" 
            onClick={fetchDetailedLogs}
            disabled={isFetchingLogs}
            style={{ alignSelf: 'flex-start' }}
          >
            <FileJson size={14} />
            {isFetchingLogs ? 'Fetching...' : 'Fetch Detailed Payloads'}
          </button>
          {logsError && <div style={{ color: 'var(--red)', fontSize: '12px' }}>{logsError}</div>}
        </div>
      </div>
    </div>
  );
}
