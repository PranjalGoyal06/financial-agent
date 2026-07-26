export interface ResearchRun {
  id: string;
  status: 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at: string | null;
}

export interface ResearchRunEvent {
  timestamp: string;
  node: string;
  target?: string | null;
  event_type: string;
  level: string;
  summary: string;
  payload: any;
}

export interface ResearchSchedule {
  id: string;
  cron_expression: string;
  is_active: boolean;
}

export const api = {
  async triggerRun(): Promise<{ run_id: string; status: string }> {
    const res = await fetch('/research/trigger', { method: 'POST' });
    if (!res.ok) throw new Error('Failed to trigger run');
    return res.json();
  },

  async getRuns(): Promise<{ runs: ResearchRun[] }> {
    const res = await fetch('/research/runs');
    if (!res.ok) throw new Error('Failed to fetch runs');
    return res.json();
  },

  async scheduleRun(cron_expression: string): Promise<ResearchSchedule> {
    const res = await fetch(`/research/schedule?cron_expression=${encodeURIComponent(cron_expression)}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to schedule run');
    return res.json();
  },

  async getArtifact(runId: string, artifactType: string, target?: string): Promise<any> {
    let url = `/research/artifact/${runId}/${artifactType}`;
    if (target) {
      url += `?target=${encodeURIComponent(target)}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch artifact');
    return res.json();
  }
};
