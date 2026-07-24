import React from 'react';
import { FileText, Clock, ExternalLink, Activity, FolderOpen } from 'lucide-react';

export function ArtifactCardRender({ envelope }: { envelope: any }) {
  if (envelope?.command !== "create_artifact") return null;
  
  const payload = envelope.payload;
  if (!payload) return null;
  
  const isFresh = payload.source_context === "fresh_analysis";
  
  return (
    <div className="artifact-render">
      <div className="artifact-render__header">
        <div className="artifact-render__title-wrap">
          <FileText size={18} className="artifact-render__icon" />
          <h3 className="artifact-render__title">{payload.title}</h3>
        </div>
        <div className={`artifact-render__badge ${isFresh ? 'artifact-render__badge--fresh' : 'artifact-render__badge--summary'}`}>
          {isFresh ? (
            <><Activity size={12} /> Fresh Analysis</>
          ) : (
            <><FolderOpen size={12} /> Chat Summary</>
          )}
        </div>
      </div>
      
      <div className="artifact-render__body">
        <p className="artifact-render__preview">
          {payload.content_preview}
        </p>
      </div>
      
      <div className="artifact-render__footer">
        <div className="artifact-render__meta">
          <span className="meta-item"><Clock size={12} /> {new Date(payload.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
          <span className="meta-item filename-tag">{payload.filename}</span>
        </div>
        
        <button 
          className="artifact-render__button"
          onClick={() => {
            // Future: Open in artifacts tab or modal
            console.log("Opening artifact:", payload.full_content_ref);
            alert(`Opening artifact: ${payload.filename}`);
          }}
        >
          <span>View Full Document</span>
          <ExternalLink size={14} />
        </button>
      </div>
    </div>
  );
}
