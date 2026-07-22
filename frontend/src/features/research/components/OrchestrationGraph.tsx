import React, { useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { GraphNode, AppNode } from './GraphNode';

const nodeTypes = {
  customNode: GraphNode,
};

type OrchestrationGraphProps = {
  nodes: AppNode[];
  edges: Edge[];
  onNodeClick: (id: string) => void;
};

export function OrchestrationGraph({ nodes, edges, onNodeClick }: OrchestrationGraphProps) {
  // Inject the onNodeClick handler into the node data
  const nodesWithHandlers = useMemo(() => {
    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        onNodeClick,
      },
    }));
  }, [nodes, onNodeClick]);

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodesWithHandlers}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background color="var(--line-strong)" gap={24} size={2} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
