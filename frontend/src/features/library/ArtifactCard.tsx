import React from 'react';
import { Eye, Download, Share2, Edit2, Trash2 } from 'lucide-react';

export type ArtifactType = 'report' | 'chart' | 'data' | 'transcript';

export interface Artifact {
  id: string;
  title: string;
  excerpt: string;
  type: ArtifactType;
  date: string;
  content: string; // Markdown or specific payload
  source_type?: string;
}

interface ArtifactCardProps {
  artifact: Artifact;
  onClick: (artifact: Artifact) => void;
  onDelete?: (artifact: Artifact) => void;
  onRename?: (artifact: Artifact) => void;
  index: number;
}

export function ArtifactCard({ artifact, onClick, onDelete, onRename, index }: ArtifactCardProps) {
  return (
    <div 
      className="artifact-card" 
      data-type={artifact.type}
      onClick={() => onClick(artifact)}
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      <span className="artifact-type-badge">{artifact.type}</span>
      <h3 className="artifact-title">{artifact.title}</h3>
      <p className="artifact-excerpt">{artifact.excerpt}</p>
      
      <div className="artifact-footer">
        <span>{artifact.date}</span>
        
        <div className="artifact-actions" onClick={(e) => e.stopPropagation()}>
          <button className="artifact-action-btn" title="View" onClick={() => onClick(artifact)}>
            <Eye size={14} />
          </button>
          {onRename && (
            <button className="artifact-action-btn" title="Rename" onClick={() => onRename(artifact)}>
              <Edit2 size={14} />
            </button>
          )}
          {onDelete && (
            <button className="artifact-action-btn" title="Delete" onClick={() => onDelete(artifact)} style={{ color: 'var(--down-color, #e57373)' }}>
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
