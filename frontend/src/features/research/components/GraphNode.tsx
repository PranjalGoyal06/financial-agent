import React from 'react';
import { Handle, Position, NodeProps, Node } from '@xyflow/react';
import { Play, CheckCircle2, XCircle, AlertCircle, AlertTriangle, Clock, Sparkles, FastForward } from 'lucide-react';

export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'warning' | 'blocked' | 'skipped';

export type GraphNodeData = Record<string, unknown> & {
  label: string;
  status: NodeStatus;
  duration?: string;
  ghosted?: boolean;
  informational?: boolean;
  onNodeClick?: (id: string) => void;
  onToggleCollapse?: (id: string) => void;
  collapsed?: boolean;
};

export type AppNode = Node<GraphNodeData, 'customNode' | 'group'>;

const statusConfig = {
  pending: {
    icon: Clock,
    modifier: 'pending'
  },
  running: {
    icon: Play,
    modifier: 'running'
  },
  completed: {
    icon: CheckCircle2,
    modifier: 'completed'
  },
  failed: {
    icon: XCircle,
    modifier: 'failed'
  },
  warning: {
    icon: AlertTriangle,
    modifier: 'warning'
  },
  blocked: {
    icon: AlertCircle,
    modifier: 'blocked'
  },
  skipped: {
    icon: FastForward,
    modifier: 'skipped'
  }
};

export function GraphNode({ id, data }: NodeProps<AppNode>) {
  const config = statusConfig[data.status || 'pending'];
  const Icon = config.icon;

  let classes = `graph-node graph-node--${config.modifier}`;
  if (data.ghosted) classes += ' graph-node--ghosted';
  if (data.informational) classes += ' graph-node--informational';

  return (
    <div
      className={classes}
      onClick={() => data.onNodeClick?.(id)}
    >
      <Handle type="target" position={(data.targetPosition as Position) || Position.Top} style={{ opacity: 0 }} />
      
      <div className="graph-node__icon">
        <Icon size={18} />
      </div>
      
      <div className="graph-node__content">
        <span className="graph-node__label">{data.label}</span>
        {data.status && (
          <span className="graph-node__status">
            {data.status} {data.duration && `• ${data.duration}`}
          </span>
        )}
      </div>

      <Handle type="source" position={(data.sourcePosition as Position) || Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}
