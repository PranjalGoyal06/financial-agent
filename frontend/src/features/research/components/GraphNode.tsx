import React from 'react';
import { Handle, Position, NodeProps, Node } from '@xyflow/react';
import { Play, CheckCircle2, XCircle, AlertCircle, Clock } from 'lucide-react';

export type NodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'blocked';

export type GraphNodeData = Record<string, unknown> & {
  label: string;
  status: NodeStatus;
  duration?: string;
  onNodeClick?: (id: string) => void;
};

export type AppNode = Node<GraphNodeData, 'customNode'>;

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
  blocked: {
    icon: AlertCircle,
    modifier: 'blocked'
  },
};

export function GraphNode({ id, data }: NodeProps<AppNode>) {
  const config = statusConfig[data.status || 'pending'];
  const Icon = config.icon;

  return (
    <div
      className={`graph-node graph-node--${config.modifier}`}
      onClick={() => data.onNodeClick?.(id)}
    >
      <Handle type="target" position={Position.Top} />
      
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

      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
