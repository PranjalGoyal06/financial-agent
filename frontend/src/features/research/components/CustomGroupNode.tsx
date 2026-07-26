import React from 'react';
import { NodeProps, Node } from '@xyflow/react';
import { ChevronDown, ChevronRight, Activity, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { GraphNodeData } from './GraphNode';

export type GroupNode = Node<GraphNodeData, 'customGroup'>;

const statusConfig = {
  pending: { icon: Clock, color: 'var(--muted)' },
  running: { icon: Activity, color: 'var(--blue)' },
  completed: { icon: CheckCircle2, color: 'var(--green)' },
  failed: { icon: XCircle, color: 'var(--red)' },
  blocked: { icon: Clock, color: '#F59E0B' },
};

export function CustomGroupNode({ id, data }: NodeProps<GroupNode>) {
  const config = statusConfig[data.status || 'pending'];
  const Icon = config.icon;
  const isCollapsed = data.collapsed;

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        backgroundColor: 'rgba(255, 255, 255, 0.03)',
        border: `1px dashed ${data.status === 'running' ? 'var(--blue)' : 'var(--line-strong)'}`,
        borderRadius: '12px',
        position: 'relative',
      }}
      onClick={(e) => {
        // Prevent click from propagating to React Flow pane
        e.stopPropagation();
        data.onNodeClick?.(id);
      }}
    >
      <div 
        style={{
          position: 'absolute',
          top: '-12px',
          left: '12px',
          background: 'var(--app-bg)',
          padding: '2px 8px',
          borderRadius: '4px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          border: '1px solid var(--line-strong)',
          fontSize: '11px',
          fontWeight: 600,
          color: 'var(--ink)',
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }}
      >
        <Icon size={12} color={config.color} />
        {data.label}
        <button 
          onClick={(e) => {
            e.stopPropagation();
            data.onToggleCollapse?.(id);
          }}
          style={{
            background: 'transparent',
            border: 'none',
            display: 'flex',
            alignItems: 'center',
            cursor: 'pointer',
            padding: '2px',
            marginLeft: '4px',
            color: 'var(--muted)'
          }}
        >
          {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </button>
      </div>
    </div>
  );
}
