import React, { useState, useMemo } from 'react';
import { Clock, Calendar, X } from 'lucide-react';

interface ScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSchedule: (cronExpression: string) => Promise<void>;
  selectedWatchlistName?: string;
}

type FrequencyType = 'daily' | 'weekdays' | 'weekly' | 'monthly' | 'custom';

const DAYS_OF_WEEK = [
  { label: 'Monday', value: 1 },
  { label: 'Tuesday', value: 2 },
  { label: 'Wednesday', value: 3 },
  { label: 'Thursday', value: 4 },
  { label: 'Friday', value: 5 },
  { label: 'Saturday', value: 6 },
  { label: 'Sunday', value: 0 },
];

export const ScheduleModal: React.FC<ScheduleModalProps> = ({
  isOpen,
  onClose,
  onSchedule,
  selectedWatchlistName
}) => {
  const [frequency, setFrequency] = useState<FrequencyType>('weekdays');
  const [hour, setHour] = useState<number>(17); // Default 5 PM (17:00)
  const [minute, setMinute] = useState<number>(0);
  const [dayOfWeek, setDayOfWeek] = useState<number>(1); // Monday
  const [customCron, setCustomCron] = useState<string>('0 17 * * 1-5');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Compute Cron Expression & Human Description
  const { cronExpression, humanDescription } = useMemo(() => {
    if (frequency === 'custom') {
      const parts = customCron.trim().split(/\s+/);
      const isValid = parts.length === 5;
      return {
        cronExpression: customCron.trim(),
        humanDescription: isValid ? `Custom schedule: "${customCron.trim()}"` : 'Invalid cron expression format (requires 5 fields)'
      };
    }

    const pad = (n: number) => n.toString().padStart(2, '0');
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const timeStr = `${displayHour}:${pad(minute)} ${ampm}`;

    if (frequency === 'daily') {
      return {
        cronExpression: `${minute} ${hour} * * *`,
        humanDescription: `Runs every day at ${timeStr}`
      };
    }

    if (frequency === 'weekdays') {
      return {
        cronExpression: `${minute} ${hour} * * 1-5`,
        humanDescription: `Runs every weekday (Monday through Friday) at ${timeStr}`
      };
    }

    if (frequency === 'weekly') {
      const dayName = DAYS_OF_WEEK.find(d => d.value === dayOfWeek)?.label || 'Monday';
      return {
        cronExpression: `${minute} ${hour} * * ${dayOfWeek}`,
        humanDescription: `Runs every ${dayName} at ${timeStr}`
      };
    }

    if (frequency === 'monthly') {
      return {
        cronExpression: `${minute} ${hour} 1 * *`,
        humanDescription: `Runs on the 1st day of every month at ${timeStr}`
      };
    }

    return { cronExpression: '0 17 * * 1-5', humanDescription: 'Weekdays at 5:00 PM' };
  }, [frequency, hour, minute, dayOfWeek, customCron]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!cronExpression) return;

    try {
      setIsSubmitting(true);
      await onSchedule(cronExpression);
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to schedule run');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="schedule-modal-overlay" onClick={onClose}>
      <div className="schedule-modal" onClick={e => e.stopPropagation()}>
        <div className="schedule-modal__header">
          <div className="schedule-modal__header-title">
            <Clock size={20} className="schedule-modal__icon" />
            <div>
              <h3>Schedule Automated Research</h3>
              {selectedWatchlistName && (
                <p className="schedule-modal__subtitle">Target: <strong>{selectedWatchlistName}</strong></p>
              )}
            </div>
          </div>
          <button type="button" className="schedule-modal__close-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="schedule-modal__body">
          {/* Frequency Selector */}
          <div className="schedule-modal__section">
            <label className="schedule-modal__label">Frequency</label>
            <div className="schedule-modal__presets">
              <button
                type="button"
                className={`schedule-modal__preset-btn ${frequency === 'weekdays' ? 'active' : ''}`}
                onClick={() => setFrequency('weekdays')}
              >
                Weekdays (Mon-Fri)
              </button>
              <button
                type="button"
                className={`schedule-modal__preset-btn ${frequency === 'daily' ? 'active' : ''}`}
                onClick={() => setFrequency('daily')}
              >
                Every Day
              </button>
              <button
                type="button"
                className={`schedule-modal__preset-btn ${frequency === 'weekly' ? 'active' : ''}`}
                onClick={() => setFrequency('weekly')}
              >
                Weekly
              </button>
              <button
                type="button"
                className={`schedule-modal__preset-btn ${frequency === 'monthly' ? 'active' : ''}`}
                onClick={() => setFrequency('monthly')}
              >
                Monthly
              </button>
              <button
                type="button"
                className={`schedule-modal__preset-btn ${frequency === 'custom' ? 'active' : ''}`}
                onClick={() => setFrequency('custom')}
              >
                Custom Cron
              </button>
            </div>
          </div>

          {/* Time & Day Selectors */}
          {frequency !== 'custom' ? (
            <div className="schedule-modal__time-row">
              {frequency === 'weekly' && (
                <div className="schedule-modal__field">
                  <label className="schedule-modal__label">Day of Week</label>
                  <select
                    className="schedule-modal__select"
                    value={dayOfWeek}
                    onChange={e => setDayOfWeek(Number(e.target.value))}
                  >
                    {DAYS_OF_WEEK.map(day => (
                      <option key={day.value} value={day.value}>{day.label}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="schedule-modal__field">
                <label className="schedule-modal__label">Time</label>
                <div className="schedule-modal__time-inputs">
                  <select
                    className="schedule-modal__select"
                    value={hour}
                    onChange={e => setHour(Number(e.target.value))}
                  >
                    {Array.from({ length: 24 }).map((_, h) => {
                      const ampm = h >= 12 ? 'PM' : 'AM';
                      const displayH = h === 0 ? 12 : h > 12 ? h - 12 : h;
                      return (
                        <option key={h} value={h}>
                          {displayH}:00 {ampm} ({h.toString().padStart(2, '0')}:00)
                        </option>
                      );
                    })}
                  </select>
                  <select
                    className="schedule-modal__select"
                    value={minute}
                    onChange={e => setMinute(Number(e.target.value))}
                  >
                    <option value={0}>:00</option>
                    <option value={15}>:15</option>
                    <option value={30}>:30</option>
                    <option value={45}>:45</option>
                  </select>
                </div>
              </div>
            </div>
          ) : (
            <div className="schedule-modal__section">
              <label className="schedule-modal__label">Cron Expression (5 fields)</label>
              <input
                type="text"
                className="schedule-modal__input"
                value={customCron}
                onChange={e => setCustomCron(e.target.value)}
                placeholder="e.g. 0 17 * * 1-5"
              />
              <span className="schedule-modal__hint">
                Format: <code>minute hour day-of-month month day-of-week</code>
              </span>
            </div>
          )}

          {/* Schedule Preview */}
          <div className="schedule-modal__preview">
            <Calendar size={16} className="schedule-modal__preview-icon" />
            <div className="schedule-modal__preview-content">
              <span className="schedule-modal__preview-text">{humanDescription}</span>
              <span className="schedule-modal__preview-cron">Cron: <code>{cronExpression}</code></span>
            </div>
          </div>

          {error && <div className="schedule-modal__error">{error}</div>}

          {/* Actions */}
          <div className="schedule-modal__footer">
            <button
              type="button"
              className="research-btn"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="research-btn research-btn--primary"
              disabled={isSubmitting || !cronExpression}
            >
              {isSubmitting ? 'Scheduling...' : 'Save Schedule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
