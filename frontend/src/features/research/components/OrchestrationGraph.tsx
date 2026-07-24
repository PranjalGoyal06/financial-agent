import React, { useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  Edge,
  NodeChange,
  EdgeChange,
  applyNodeChanges,
  applyEdgeChanges,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { GraphNode, AppNode } from './GraphNode';
import { GroupNode } from './GroupNode';

const nodeTypes = {
  customNode: GraphNode,
  group: GroupNode,
};

type OrchestrationGraphProps = {
  nodes: AppNode[];
  edges: Edge[];
  onNodeClick: (id: string) => void;
};

export function OrchestrationGraph({ nodes: initialNodes, edges: initialEdges, onNodeClick }: OrchestrationGraphProps) {
  const [nodes, setNodes] = React.useState<AppNode[]>(initialNodes);
  const [edges, setEdges] = React.useState<Edge[]>(initialEdges);

  const onNodesChange = React.useCallback(
    (changes: NodeChange<AppNode>[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = React.useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const handleToggleCollapse = React.useCallback((groupId: string) => {
    setNodes((nds) => {
      const groupNode = nds.find((n) => n.id === groupId);
      if (!groupNode) return nds;

      const isCollapsed = !groupNode.data.collapsed;
      
      return nds.map((node) => {
        if (node.id === groupId) {
          return {
            ...node,
            data: { ...node.data, collapsed: isCollapsed },
            style: { 
              ...node.style, 
              height: isCollapsed ? 60 : 420,
              width: isCollapsed ? 200 : 300,
            }
          };
        }
        if (node.parentId === groupId) {
          return {
            ...node,
            hidden: isCollapsed
          };
        }
        return node;
      });
    });
  }, []);

  const nodesWithHandlers = useMemo(() => {
    return nodes.map((node) => ({
      ...node,
      data: {
        ...node.data,
        onNodeClick,
        onToggleCollapse: handleToggleCollapse
      },
    }));
  }, [nodes, onNodeClick, handleToggleCollapse]);

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ReactFlow
        nodes={nodesWithHandlers}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
      >
        <Background color="var(--line-strong)" gap={24} size={2} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
