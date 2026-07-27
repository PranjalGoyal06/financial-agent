import React from 'react';
import { Target, Activity, CheckCircle, AlertTriangle, AlertCircle } from 'lucide-react';

export function RecommendationCardRender({ envelope }: { envelope: any }) {
  if (envelope?.type !== "recommendation_card") return null;
  
  const payload = envelope.card;
  if (!payload || !payload.ticker) return null;
  
  const rec = (payload.recommendation || "Hold").toLowerCase();
  
  let recClass = "rec-hold";
  let Icon = Activity;
  if (rec.includes("buy")) {
    recClass = "rec-buy";
    Icon = CheckCircle;
  } else if (rec.includes("sell") || rec.includes("avoid")) {
    recClass = "rec-sell";
    Icon = AlertTriangle;
  }
  
  const confPercent = payload.confidence_score ? Math.round(payload.confidence_score * 100) : null;
  
  return (
    <div className={`recommendation-render ${recClass}`}>
      <div className="recommendation-render__header">
        <div className="recommendation-render__title">
          <Target className="title-icon" size={18} />
          <span className="ticker-badge">{payload.ticker}</span>
          <span className="live-stance-text">Live Stance</span>
        </div>
        {confPercent !== null && (
          <div className="confidence-badge">
            {confPercent}% Conviction
          </div>
        )}
      </div>
      
      <div className="recommendation-render__body">
        <div className="rec-stance">
          <Icon size={24} className="stance-icon" />
          <span className="stance-text">{payload.recommendation.toUpperCase()}</span>
        </div>
        
        <div className="rec-rationale">
          {payload.rationale}
        </div>
      </div>
      
      {payload.based_on_prior_research && (
        <div className="rec-footer">
          <AlertCircle size={14} className="footer-icon" />
          <span>Grounded in deep research (Run ID: {payload.run_id?.substring(0,8) || 'unknown'})</span>
        </div>
      )}
    </div>
  );
}
