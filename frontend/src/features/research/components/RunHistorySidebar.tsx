import React, { useState } from 'react';
import { CheckCircle2, Play, Clock, XCircle, AlertCircle, PanelLeftClose, PanelLeftOpen } from 'lucide-react';

export type RunHistoryItem = {
  id: string;
  topic: string;
  date: string;
  status: 'running' | 'completed' | 'failed' | 'blocked' | 'pending';
  duration?: string;
};

type RunHistorySidebarProps = {
  runs: RunHistoryItem[];
  selectedRunId?: string;
  onSelectRun: (id: string) => void;
};

const statusIconMap = {
  running: <Play size={16} color="var(--blue)" />,
  completed: <CheckCircle2 size={16} color="var(--green)" />,
  failed: <XCircle size={16} color="var(--red)" />,
  blocked: <AlertCircle size={16} color="#F59E0B" />,
  pending: <Clock size={16} color="var(--muted)" />,
};

export function RunHistorySidebar({ runs, selectedRunId, onSelectRun }: RunHistorySidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (isCollapsed) {
    return (
      <div className="research-sidebar research-sidebar--collapsed" style={{ width: '56px', transition: 'width 0.2s' }}>
        <div className="research-sidebar__header" style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
          <button className="research-panel__close" onClick={() => setIsCollapsed(false)} title="Expand sidebar">
            <PanelLeftOpen size={18} />
          </button>
        </div>
        <ul className="research-sidebar__list" style={{ overflowX: 'hidden' }}>
          {runs.map((run) => (
             <li key={run.id} style={{ display: 'flex', justifyContent: 'center', padding: '12px 0' }}>
                <button 
                  onClick={() => onSelectRun(run.id)} 
                  title={run.topic}
                  style={{ background: 'transparent', border: 'none', cursor: 'pointer' }}
                >
                   {statusIconMap[run.status]}
                </button>
             </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="research-sidebar" style={{ transition: 'width 0.2s' }}>
      <div className="research-sidebar__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="research-sidebar__title">Prior Runs</h2>
        <button className="research-panel__close" onClick={() => setIsCollapsed(true)} title="Collapse sidebar">
          <PanelLeftClose size={18} />
        </button>
      </div>
      
      <ul className="research-sidebar__list">
        {runs.length === 0 ? (
          <li style={{ padding: '16px', color: 'var(--muted)', fontSize: '14px', textAlign: 'center' }}>
            No previous runs found.
          </li>
        ) : (
          runs.map((run) => {
            const isSelected = run.id === selectedRunId;
            return (
              <li key={run.id}>
                <button
                  onClick={() => onSelectRun(run.id)}
                  className={`research-sidebar__item ${isSelected ? 'research-sidebar__item--selected' : ''}`}
                >
                  <div className="research-sidebar__item-icon">
                    {statusIconMap[run.status]}
                  </div>
                  <div style={{ minWidth: 0, overflow: 'hidden' }}>
                    <div className="research-sidebar__item-title">
                      {run.topic}
                    </div>
                    <div className="research-sidebar__item-meta">
                      <span>{run.date}</span>
                      {run.duration && (
                        <>
                          <span style={{ margin: '0 4px' }}>&bull;</span>
                          <span>{run.duration}</span>
                        </>
                      )}
                    </div>
                  </div>
                </button>
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}
