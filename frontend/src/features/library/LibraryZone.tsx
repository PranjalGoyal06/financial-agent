import React, { useState, useEffect } from 'react';
import { Search, X, Plus, UploadCloud } from 'lucide-react';
import { marked } from 'marked';
import { ArtifactCard, Artifact, ArtifactType } from './ArtifactCard';
import './library-styles.css';

const CATEGORIES: { label: string; value: string }[] = [
  { label: 'All Artifacts', value: 'all' },
  { label: 'Reports', value: 'report' },
  { label: 'Charts & Analysis', value: 'chart' },
  { label: 'Data Extracts', value: 'data' },
  { label: 'Transcripts', value: 'transcript' },
  { label: 'User Uploads', value: 'user_upload' }
];

export function LibraryZone() {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  
  // Upload Modal State
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadContent, setUploadContent] = useState('');
  const [uploadType, setUploadType] = useState<string>('report');
  const [isUploading, setIsUploading] = useState(false);

  const fetchArtifacts = async () => {
    try {
      const res = await fetch('http://localhost:8000/artifacts');
      if (res.ok) {
        const data = await res.json();
        const mapped = data.artifacts.map((a: any) => {
          // Find type from tags or fallback to source_type
          let type = a.source_type;
          const typeTag = a.tags.find((t: string) => t.startsWith('type:'));
          if (typeTag) {
            type = typeTag.split(':')[1];
          } else if (a.metadata_json?.artifact_type) {
            type = a.metadata_json.artifact_type;
          }

          return {
            id: a.id,
            title: a.title,
            excerpt: a.content_markdown.substring(0, 150) + '...',
            type: type,
            date: a.created_at ? new Date(a.created_at).toLocaleDateString() : 'Unknown Date',
            content: a.content_markdown,
            source_type: a.source_type
          };
        });
        setArtifacts(mapped);
      }
    } catch (e) {
      console.error("Failed to fetch artifacts", e);
    }
  };

  useEffect(() => {
    fetchArtifacts();
  }, []);

  const handleUpload = async () => {
    if (!uploadTitle.trim() || !uploadContent.trim()) return;
    setIsUploading(true);
    try {
      const payload = {
        title: uploadTitle,
        content_markdown: uploadContent,
        tags: [`type:${uploadType}`],
        source_type: 'user_upload',
        metadata_json: { artifact_type: uploadType }
      };
      
      const res = await fetch('http://localhost:8000/artifacts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        setIsUploadOpen(false);
        setUploadTitle('');
        setUploadContent('');
        fetchArtifacts();
      }
    } catch (e) {
      console.error("Upload failed", e);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (artifact: Artifact) => {
    if (!window.confirm(`Are you sure you want to delete "${artifact.title}"?`)) return;
    try {
      const res = await fetch(`http://localhost:8000/artifacts/${artifact.id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchArtifacts();
      }
    } catch (e) {
      console.error("Delete failed", e);
    }
  };

  const handleRename = async (artifact: Artifact) => {
    const newTitle = window.prompt('Enter new title for artifact:', artifact.title);
    if (!newTitle || newTitle.trim() === '' || newTitle === artifact.title) return;
    
    try {
      const res = await fetch(`http://localhost:8000/artifacts/${artifact.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (res.ok) {
        fetchArtifacts();
      }
    } catch (e) {
      console.error("Rename failed", e);
    }
  };

  const filteredArtifacts = artifacts.filter(a => {
    // category match
    let matchesCategory = false;
    if (activeCategory === 'all') matchesCategory = true;
    else if (activeCategory === 'user_upload') matchesCategory = a.source_type === 'user_upload';
    else matchesCategory = a.type === activeCategory;

    // search match
    const searchLower = searchQuery.toLowerCase();
    const matchesSearch = a.title.toLowerCase().includes(searchLower) || a.excerpt.toLowerCase().includes(searchLower);

    return matchesCategory && matchesSearch;
  });

  return (
    <div className="library-zone">
      <header className="library-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <h1>The Archive</h1>
          <button 
            className="library-action-btn primary"
            onClick={() => setIsUploadOpen(true)}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}
          >
            <UploadCloud size={18} />
            Upload
          </button>
        </div>
        <div className="library-search-container">
          <Search className="library-search-icon" />
          <input 
            type="text" 
            className="library-search-input" 
            placeholder="Search artifacts..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </header>

      <div className="library-filters">
        {CATEGORIES.map(cat => (
          <button 
            key={cat.value}
            className={`library-filter-btn ${activeCategory === cat.value ? 'active' : ''}`}
            onClick={() => setActiveCategory(cat.value)}
          >
            {cat.label}
          </button>
        ))}
      </div>

      <div className="library-grid">
        {filteredArtifacts.map((artifact, index) => (
          <ArtifactCard 
            key={artifact.id} 
            artifact={artifact} 
            index={index} 
            onClick={setSelectedArtifact}
            onDelete={handleDelete}
            onRename={handleRename}
          />
        ))}
        {filteredArtifacts.length === 0 && (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '40px', color: 'var(--ink-light)' }}>
            No artifacts found.
          </div>
        )}
      </div>

      {/* Slide-out Preview */}
      <div className={`artifact-preview-overlay ${selectedArtifact ? 'open' : ''}`} onClick={() => setSelectedArtifact(null)}>
        <div className="artifact-preview-panel" onClick={(e) => e.stopPropagation()}>
          {selectedArtifact && (
            <>
              <div className="preview-header">
                <div>
                  <span className="artifact-type-badge">{selectedArtifact.type}</span>
                  <h2 className="preview-title">{selectedArtifact.title}</h2>
                  <div className="preview-meta">{selectedArtifact.date} {selectedArtifact.source_type === 'user_upload' ? '(User Uploaded)' : ''}</div>
                </div>
                <button className="preview-close" onClick={() => setSelectedArtifact(null)}>
                  <X size={24} />
                </button>
              </div>
              <div className="preview-content message-content">
                <div dangerouslySetInnerHTML={{ __html: marked.parse(selectedArtifact.content) as string }} />
              </div>
            </>
          )}
        </div>
      </div>

      {/* Upload Modal */}
      {isUploadOpen && (
        <div className="artifact-preview-overlay open" onClick={() => setIsUploadOpen(false)} style={{ alignItems: 'center', justifyContent: 'center' }}>
          <div className="artifact-preview-panel" onClick={(e) => e.stopPropagation()} style={{ width: '600px', maxWidth: '90vw', height: 'auto', maxHeight: '80vh', borderRadius: '12px', right: 'auto', display: 'flex', flexDirection: 'column' }}>
            <div className="preview-header">
              <h2 className="preview-title">Upload Artifact</h2>
              <button className="preview-close" onClick={() => setIsUploadOpen(false)}>
                <X size={24} />
              </button>
            </div>
            <div className="preview-content" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>Title</label>
                <input 
                  type="text" 
                  value={uploadTitle}
                  onChange={e => setUploadTitle(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--surface-hover)', background: 'var(--app-bg)', color: 'var(--ink)' }}
                  placeholder="e.g., Q4 Analysis"
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>Type</label>
                <select 
                  value={uploadType}
                  onChange={e => setUploadType(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--surface-hover)', background: 'var(--app-bg)', color: 'var(--ink)' }}
                >
                  <option value="report">Report</option>
                  <option value="chart">Chart</option>
                  <option value="data">Data</option>
                  <option value="transcript">Transcript</option>
                </select>
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>Content (Markdown)</label>
                <textarea 
                  value={uploadContent}
                  onChange={e => setUploadContent(e.target.value)}
                  style={{ width: '100%', height: '200px', padding: '10px', borderRadius: '6px', border: '1px solid var(--surface-hover)', background: 'var(--app-bg)', color: 'var(--ink)', resize: 'vertical' }}
                  placeholder="Write or paste your markdown content here..."
                />
              </div>
              <button 
                onClick={handleUpload}
                disabled={isUploading || !uploadTitle.trim() || !uploadContent.trim()}
                style={{ alignSelf: 'flex-end', padding: '10px 24px', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500, opacity: isUploading ? 0.7 : 1 }}
              >
                {isUploading ? 'Uploading...' : 'Save Artifact'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
