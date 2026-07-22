import React from 'react';
import { X, Terminal } from 'lucide-react';
import { GraphNodeData } from './GraphNode';

type NodeDetailsPanelProps = {
  nodeData: GraphNodeData | null;
  onClose: () => void;
};

export function NodeDetailsPanel({ nodeData, onClose }: NodeDetailsPanelProps) {
  if (!nodeData) return null;

  return (
    <div className="research-panel">
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
