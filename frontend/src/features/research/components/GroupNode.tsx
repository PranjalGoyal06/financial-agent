import React from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { AppNode } from './GraphNode';
import { ChevronDown, ChevronRight, Activity } from 'lucide-react';

export function GroupNode({ id, data }: NodeProps<AppNode>) {
  // We'll manage local collapse state for visual indication, 
  // but true collapsing requires filtering the nodes array in the parent component.
  // For this UI mockup, we'll just show the toggle button.
  
  const isCollapsed = data.collapsed === true;
  
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <div 
        style={{ 
          position: 'absolute', 
          top: -12, 
          left: 12, 
          background: 'var(--surface)', 
          padding: '4px 12px',
          borderRadius: '4px',
          border: '1px solid var(--line-strong)',
          fontSize: '12px',
          fontWeight: 600,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          zIndex: 10,
          boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
        }}
        onClick={(e) => {
          e.stopPropagation();
          data.onToggleCollapse?.(id);
        }}
      >
        {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        <Activity size={14} color="var(--blue)" />
        {data.label}
      </div>
      
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}
