import React from 'react';
import { X, Terminal } from 'lucide-react';
import { GraphNodeData } from './GraphNode';

type NodeDetailsPanelProps = {
  nodeData: GraphNodeData | null;
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

export function NodeDetailsPanel({ nodeData, onClose }: NodeDetailsPanelProps) {
  if (!nodeData) return null;

  const summary = NODE_SUMMARIES[nodeData.id as string] || 'Executes specialized analysis tasks for the research pipeline.';

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

        {/* Terminal / Logs View */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: '300px' }}>
          <h3 className="evidence-section__title" style={{ marginBottom: '8px' }}>
            <Terminal size={14} />
            Execution Logs
          </h3>
          <div className="node-logs">
            <div className="node-logs__line node-logs__line--system">[System] Node execution started...</div>
            <div className="node-logs__line">Loading required context...</div>
            
            {nodeData.status === 'running' && (
              <div className="node-logs__line" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#4C6FB7' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#4C6FB7', animation: 'pulse 2s infinite' }}></span>
                Processing task...
              </div>
            )}
            
            {nodeData.status === 'completed' && (
              <div className="node-logs__line node-logs__line--success">[System] Execution completed successfully.</div>
            )}
            
            {nodeData.status === 'failed' && (
              <div className="node-logs__line node-logs__line--error">[Error] Execution terminated unexpectedly.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
