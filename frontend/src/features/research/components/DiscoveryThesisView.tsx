import React from 'react';
import { Plus, XCircle } from 'lucide-react';

export type DiscoveredTicker = {
  id: string;
  ticker: string;
  companyName: string;
  discoveryVector: string;
  thesis: string;
  date: string;
};

type DiscoveryThesisViewProps = {
  ticker: DiscoveredTicker | null;
  onAddToWatchlist: (id: string) => void;
  onDismiss: (id: string) => void;
};

export function DiscoveryThesisView({ ticker, onAddToWatchlist, onDismiss }: DiscoveryThesisViewProps) {
  if (!ticker) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--muted)' }}>
        Select a discovered ticker to view the full thesis.
      </div>
    );
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--app-bg)' }}>
      {/* Header */}
      <header className="research-header">
        <div className="research-header__title">
          <div>
            <span style={{ fontSize: '20px', fontWeight: 700, marginRight: '8px' }}>{ticker.ticker}</span>
            <span style={{ fontSize: '14px', color: 'var(--muted)', fontWeight: 400 }}>{ticker.companyName}</span>
          </div>
          <span className="research-badge" style={{ background: 'var(--blue)', color: '#fff', borderColor: 'var(--blue)' }}>🔍 NEW DISCOVERY</span>
        </div>
        
        <div className="research-header__actions">
          <button 
            className="research-btn"
            onClick={() => onDismiss(ticker.id)}
          >
            <XCircle size={16} color="var(--red)" />
            Dismiss
          </button>
          <button 
            className="research-btn research-btn--primary"
            onClick={() => onAddToWatchlist(ticker.id)}
          >
            <Plus size={16} />
            Add to Watchlist
          </button>
        </div>
      </header>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '32px' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto', background: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--line-strong)', padding: '32px' }}>
          <h3 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--muted)', letterSpacing: '0.5px', marginBottom: '8px' }}>Discovery Vector</h3>
          <p style={{ fontSize: '16px', fontWeight: 500, color: 'var(--ink)', marginBottom: '32px', paddingLeft: '12px', borderLeft: '3px solid var(--blue)' }}>
            {ticker.discoveryVector}
          </p>

          <h3 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--muted)', letterSpacing: '0.5px', marginBottom: '16px' }}>Investment Thesis</h3>
          <div style={{ fontSize: '14px', lineHeight: 1.6, color: 'var(--ink-secondary)', whiteSpace: 'pre-wrap' }}>
            {ticker.thesis}
          </div>
        </div>
      </div>
    </div>
  );
}
