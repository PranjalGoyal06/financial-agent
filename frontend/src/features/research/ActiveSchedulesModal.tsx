import React, { useState, useEffect, useCallback } from 'react';
import { Calendar, Clock, Trash2, X, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { api, ResearchSchedule } from './api';

interface ActiveSchedulesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSchedulesUpdated?: () => void;
}

function describeCron(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;

  const [min, hr, dom, mon, dow] = parts;
  const pad = (n: string) => n.padStart(2, '0');
  const hNum = parseInt(hr, 10);
  const mNum = parseInt(min, 10);
  const timeStr = isNaN(hNum) || isNaN(mNum)
    ? `${hr}:${min}`
    : `${hNum === 0 ? 12 : hNum > 12 ? hNum - 12 : hNum}:${pad(min)} ${hNum >= 12 ? 'PM' : 'AM'}`;

  if (dow === '1-5' && dom === '*' && mon === '*') {
    return `Weekdays (Mon-Fri) at ${timeStr}`;
  }
  if (dow === '*' && dom === '*' && mon === '*') {
    return `Every day at ${timeStr}`;
  }
  if (dom === '1' && dow === '*' && mon === '*') {
    return `1st of every month at ${timeStr}`;
  }
  const daysMap: Record<string, string> = { '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat' };
  if (daysMap[dow] && dom === '*' && mon === '*') {
    return `Every ${daysMap[dow]} at ${timeStr}`;
  }

  return `Cron: "${cron}" at ${timeStr}`;
}

function formatDateTime(isoStr?: string | null): string {
  if (!isoStr) return 'Not scheduled / Pending';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString([], {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return isoStr;
  }
}

export const ActiveSchedulesModal: React.FC<ActiveSchedulesModalProps> = ({
  isOpen,
  onClose,
  onSchedulesUpdated
}) => {
  const [schedules, setSchedules] = useState<ResearchSchedule[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchSchedules = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.getSchedules();
      setSchedules(data.schedules || []);
      if (onSchedulesUpdated) onSchedulesUpdated();
    } catch (err: any) {
      setError(err?.message || 'Failed to fetch active schedules');
    } finally {
      setIsLoading(false);
    }
  }, [onSchedulesUpdated]);

  useEffect(() => {
    if (isOpen) {
      fetchSchedules();
    }
  }, [isOpen, fetchSchedules]);

  const handleDelete = async (id: string) => {
    try {
      setDeletingId(id);
      await api.deleteSchedule(id);
      setSchedules(prev => prev.filter(s => s.id !== id));
      if (onSchedulesUpdated) onSchedulesUpdated();
    } catch (err: any) {
      alert('Failed to delete schedule: ' + (err?.message || 'Unknown error'));
    } finally {
      setDeletingId(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="schedule-modal-overlay" onClick={onClose}>
      <div className="schedule-modal schedule-modal--wide" onClick={e => e.stopPropagation()}>
        <div className="schedule-modal__header">
          <div className="schedule-modal__header-title">
            <Calendar size={20} className="schedule-modal__icon" />
            <div>
              <h3>Active Research Schedules</h3>
              <p className="schedule-modal__subtitle">Automated runs registered with background scheduler</p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              className="schedule-modal__close-btn"
              onClick={fetchSchedules}
              disabled={isLoading}
              title="Refresh schedules"
            >
              <RefreshCw size={16} className={isLoading ? 'spin-icon' : ''} />
            </button>
            <button className="schedule-modal__close-btn" onClick={onClose} aria-label="Close">
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="schedule-modal__body">
          {error && <div className="schedule-modal__error">{error}</div>}

          {isLoading && schedules.length === 0 ? (
            <div className="schedule-modal__empty">
              <RefreshCw size={24} className="spin-icon" />
              <p>Loading active schedules...</p>
            </div>
          ) : schedules.length === 0 ? (
            <div className="schedule-modal__empty">
              <Clock size={32} style={{ opacity: 0.4 }} />
              <p style={{ fontWeight: 500, margin: '8px 0 4px 0' }}>No Active Schedules Found</p>
              <span style={{ fontSize: '13px', color: 'var(--muted)' }}>
                Create a scheduled run using the "Schedule" button to automate daily or weekly research.
              </span>
            </div>
          ) : (
            <div className="active-schedules-list">
              {schedules.map(sched => (
                <div key={sched.id} className="active-schedule-card">
                  <div className="active-schedule-card__main">
                    <div className="active-schedule-card__title">
                      <CheckCircle2 size={16} className="active-schedule-card__status-icon" />
                      <span>{describeCron(sched.cron_expression)}</span>
                    </div>

                    <div className="active-schedule-card__meta">
                      <span className="active-schedule-card__badge">
                        Target: {sched.watchlist_name || 'Default Watchlist'}
                      </span>
                      <span className="active-schedule-card__next-time">
                        <Clock size={12} /> Next run: <strong>{formatDateTime(sched.next_run_time)}</strong>
                      </span>
                    </div>
                  </div>

                  <button
                    className="active-schedule-card__delete-btn"
                    onClick={() => handleDelete(sched.id)}
                    disabled={deletingId === sched.id}
                    title="Delete schedule"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="schedule-modal__system-note">
            <AlertCircle size={14} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>
              <strong>Note:</strong> Scheduled runs trigger automatically in the background while your local machine and application backend are running.
            </span>
          </div>

          <div className="schedule-modal__footer">
            <button type="button" className="research-btn" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
