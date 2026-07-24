import React from 'react';
import { Check } from 'lucide-react';

export function ComparisonCardRender({ envelope }: { envelope: any }) {
  if (envelope?.command !== "compare") return null;
  
  const payload = envelope.payload;
  if (!payload || !payload.tickers || payload.tickers.length !== 2) return null;
  
  const tickerA = payload.tickers[0];
  const tickerB = payload.tickers[1];
  
  return (
    <div className="comparison-render">
      <div className="comparison-render__header">
        <div className="comparison-render__title">
          <span className="ticker-badge">{tickerA}</span>
          <span className="vs-text">vs</span>
          <span className="ticker-badge">{tickerB}</span>
        </div>
        <div className={`confidence-badge confidence-badge--${payload.confidence_tier}`}>
          {payload.confidence_tier} confidence
        </div>
      </div>
      
      <div className="comparison-table-wrapper">
        <table className="comparison-table">
          <thead>
            <tr>
              <th className="dim-col">Dimension</th>
              <th className="val-col">{tickerA}</th>
              <th className="val-col">{tickerB}</th>
              <th className="note-col">Analysis</th>
            </tr>
          </thead>
          <tbody>
            {payload.rows.map((row: any, i: number) => {
              const aWins = row.lean === 'A';
              const bWins = row.lean === 'B';
              return (
                <tr key={i}>
                  <td className="dim-col font-medium">{row.dimension}</td>
                  <td className={`val-col ${aWins ? 'winner-cell' : ''}`}>
                    {aWins && <Check size={14} className="winner-icon" />}
                    {row.value_a || '-'}
                  </td>
                  <td className={`val-col ${bWins ? 'winner-cell' : ''}`}>
                    {bWins && <Check size={14} className="winner-icon" />}
                    {row.value_b || '-'}
                  </td>
                  <td className="note-col text-muted">{row.note}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      
      <div className="comparison-summary">
        <strong>Summary:</strong> {payload.overall_summary}
      </div>
    </div>
  );
}
