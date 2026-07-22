import React from 'react';
import { ExternalLink, Check, Trash2, FileText, ChevronRight } from 'lucide-react';

export type EvidenceItem = {
  id: string;
  type: 'url' | 'document';
  title: string;
  urlOrPath: string;
  status: 'useful' | 'discarded';
  reason?: string; 
  snippet?: string;
};

type EvidenceDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  evidence: EvidenceItem[];
};

export function EvidenceDrawer({ isOpen, onClose, evidence }: EvidenceDrawerProps) {
  if (!isOpen) return null;

  const usefulEvidence = evidence.filter((e) => e.status === 'useful');
  const discardedEvidence = evidence.filter((e) => e.status === 'discarded');

  return (
    <div className="research-panel">
      <div className="research-panel__header">
        <h2 className="research-panel__title">
          <FileText size={16} color="var(--blue)" />
          Evidence Drawer
        </h2>
        <button className="research-panel__close" onClick={onClose}>
          <ChevronRight size={18} />
        </button>
      </div>

      <div className="research-panel__body">
        {/* Useful Evidence Section */}
        <div className="evidence-section">
          <h3 className="evidence-section__title">
            <Check size={14} color="var(--green)" />
            Included in Research ({usefulEvidence.length})
          </h3>
          <div>
            {usefulEvidence.length === 0 ? (
              <p style={{ fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>
                No useful evidence collected yet.
              </p>
            ) : (
              usefulEvidence.map((item) => (
                <div key={item.id} className="evidence-card">
                  <div className="evidence-card__header">
                    <span className="evidence-card__title">{item.title}</span>
                    <a
                      href={item.urlOrPath}
                      target="_blank"
                      rel="noreferrer"
                      className="evidence-card__link"
                    >
                      <ExternalLink size={14} />
                    </a>
                  </div>
                  {item.snippet && (
                    <p className="evidence-card__snippet">
                      "{item.snippet}"
                    </p>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Discarded Evidence Section */}
        <div className="evidence-section">
          <h3 className="evidence-section__title">
            <Trash2 size={14} color="var(--muted)" />
            Discarded ({discardedEvidence.length})
          </h3>
          <div>
            {discardedEvidence.map((item) => (
              <div key={item.id} className="evidence-card evidence-card--discarded">
                <div className="evidence-card__header">
                  <span className="evidence-card__title">{item.title}</span>
                </div>
                {item.reason && (
                  <p className="evidence-card__reason">
                    Reason: {item.reason}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
