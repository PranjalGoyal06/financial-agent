import { useEffect, useState } from "react";

type PortfolioValuedRow = {
  id: string;
  raw_ticker: string;
  canonical_ticker: string;
  exchange: string;
  asset_class: string;
  quantity: number;
  avg_cost: number;
  currency: string;
  purchase_date: string | null;
  created_at: string;
  
  market_value: number | null;
  unrealized_pnl_pct: number | null;
  recommendation: "buy" | "add" | "hold" | "reduce" | "watch" | "no_action" | "insufficient_data" | null;
  confidence_score: number | null;
  last_updated: string | null;
  run_id: string | null;
};

type PortfolioValuedResponse = {
  summary: {
    total_market_value: number;
    total_unrealized_pnl: number;
    realized_pnl: number;
  };
  holdings: PortfolioValuedRow[];
};

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}

function getRecommendationPillStyle(rec: string | null): React.CSSProperties {
  if (rec === "buy" || rec === "add") {
    return { backgroundColor: "rgba(34, 197, 94, 0.2)", color: "#4ade80", border: "1px solid rgba(34, 197, 94, 0.4)" };
  }
  if (rec === "reduce") {
    return { backgroundColor: "rgba(239, 68, 68, 0.2)", color: "#f87171", border: "1px solid rgba(239, 68, 68, 0.4)" };
  }
  if (rec === "hold" || rec === "watch" || rec === "no_action") {
    return { backgroundColor: "rgba(234, 179, 8, 0.2)", color: "#facc15", border: "1px solid rgba(234, 179, 8, 0.4)" };
  }
  return { backgroundColor: "rgba(156, 163, 175, 0.2)", color: "#9ca3af", border: "1px solid rgba(156, 163, 175, 0.4)" };
}

function formatRecommendation(rec: string | null): string {
  if (!rec) return "Unknown";
  return rec.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

export function PortfolioZone() {
  const [data, setData] = useState<PortfolioValuedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/portfolio/valued")
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load portfolio valuation");
        return r.json();
      })
      .then((d: PortfolioValuedResponse) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="portfolio-zone" style={{ padding: "40px", display: "flex", justifyContent: "center" }}>
        <div style={{ color: "var(--text-secondary)" }}>Loading portfolio data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="portfolio-zone" style={{ padding: "40px" }}>
        <div style={{ color: "var(--red)" }}>{error}</div>
      </div>
    );
  }

  if (!data || data.holdings.length === 0) {
    return (
      <div className="portfolio-zone" style={{ padding: "40px", textAlign: "center" }}>
        <h2 style={{ fontSize: "24px", color: "var(--text-primary)", marginBottom: "16px" }}>Your Portfolio</h2>
        <p style={{ color: "var(--text-secondary)" }}>No holdings found. Upload your tradebook via the sidebar to get started.</p>
      </div>
    );
  }

  return (
    <div className="portfolio-zone" style={{ padding: "40px", overflowY: "auto", height: "100%" }}>
      <h2 style={{ fontSize: "24px", color: "var(--text-primary)", marginBottom: "24px", fontWeight: "600" }}>Portfolio Dashboard</h2>
      
      {/* Summary Strip */}
      <div style={{ 
        display: "flex", 
        gap: "24px", 
        marginBottom: "32px",
        flexWrap: "wrap"
      }}>
        <div style={{ 
          background: "var(--surface-sunken)", 
          padding: "20px", 
          borderRadius: "12px",
          minWidth: "200px",
          flex: 1
        }}>
          <div style={{ color: "var(--text-tertiary)", fontSize: "14px", marginBottom: "8px" }}>Total Market Value</div>
          <div style={{ fontSize: "28px", color: "var(--text-primary)", fontWeight: "bold" }}>
            ₹{formatNumber(data.summary.total_market_value)}
          </div>
        </div>

        <div style={{ 
          background: "var(--surface-sunken)", 
          padding: "20px", 
          borderRadius: "12px",
          minWidth: "200px",
          flex: 1
        }}>
          <div style={{ color: "var(--text-tertiary)", fontSize: "14px", marginBottom: "8px" }}>Unrealized P&L</div>
          <div style={{ 
            fontSize: "28px", 
            fontWeight: "bold",
            color: data.summary.total_unrealized_pnl >= 0 ? "var(--green)" : "var(--red)" 
          }}>
            {data.summary.total_unrealized_pnl >= 0 ? "+" : ""}
            ₹{formatNumber(data.summary.total_unrealized_pnl)}
          </div>
        </div>

        <div style={{ 
          background: "var(--surface-sunken)", 
          padding: "20px", 
          borderRadius: "12px",
          minWidth: "200px",
          flex: 1
        }}>
          <div style={{ color: "var(--text-tertiary)", fontSize: "14px", marginBottom: "8px" }}>Realized P&L</div>
          <div style={{ 
            fontSize: "28px", 
            fontWeight: "bold",
            color: data.summary.realized_pnl >= 0 ? "var(--green)" : "var(--red)" 
          }}>
            {data.summary.realized_pnl >= 0 ? "+" : ""}
            ₹{formatNumber(data.summary.realized_pnl)}
          </div>
        </div>
      </div>

      {/* Holdings Table */}
      <div style={{ background: "var(--surface)", borderRadius: "12px", overflow: "hidden", border: "1px solid var(--border-color)" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
          <thead>
            <tr style={{ background: "var(--surface-sunken)", color: "var(--text-secondary)", fontSize: "13px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              <th style={{ padding: "16px", fontWeight: "500" }}>Ticker</th>
              <th style={{ padding: "16px", fontWeight: "500", textAlign: "right" }}>Qty</th>
              <th style={{ padding: "16px", fontWeight: "500", textAlign: "right" }}>Avg ₹</th>
              <th style={{ padding: "16px", fontWeight: "500", textAlign: "right" }}>Value ₹</th>
              <th style={{ padding: "16px", fontWeight: "500", textAlign: "right" }}>P&L %</th>
              <th style={{ padding: "16px", fontWeight: "500", textAlign: "center" }}>AI Stance</th>
              <th style={{ padding: "16px", fontWeight: "500", textAlign: "center" }}>Confidence</th>
              <th style={{ padding: "16px", fontWeight: "500", textAlign: "right" }}>Research Age</th>
            </tr>
          </thead>
          <tbody>
            {data.holdings.map((h) => {
              const pnlColor = h.unrealized_pnl_pct && h.unrealized_pnl_pct >= 0 ? "var(--green)" : "var(--red)";
              const isStale = h.last_updated && (new Date().getTime() - new Date(h.last_updated).getTime()) > 48 * 60 * 60 * 1000;
              
              return (
                <tr 
                  key={h.id} 
                  style={{ borderTop: "1px solid var(--border-color)", cursor: h.run_id ? "pointer" : "default" }}
                  onClick={() => {
                    if (h.run_id) {
                      console.log("Navigating to research artifact:", h.run_id);
                    }
                  }}
                  onMouseEnter={(e) => {
                    if (h.run_id) e.currentTarget.style.backgroundColor = "var(--surface-hover)";
                  }}
                  onMouseLeave={(e) => {
                    if (h.run_id) e.currentTarget.style.backgroundColor = "transparent";
                  }}
                >
                  <td style={{ padding: "16px", color: "var(--text-primary)", fontWeight: "500" }}>
                    {h.canonical_ticker}
                  </td>
                  <td style={{ padding: "16px", color: "var(--text-secondary)", textAlign: "right" }}>
                    {formatNumber(h.quantity)}
                  </td>
                  <td style={{ padding: "16px", color: "var(--text-secondary)", textAlign: "right" }}>
                    {formatNumber(h.avg_cost)}
                  </td>
                  <td style={{ padding: "16px", color: "var(--text-primary)", textAlign: "right", fontWeight: "500" }}>
                    {h.market_value ? formatNumber(h.market_value) : "-"}
                  </td>
                  <td style={{ padding: "16px", color: pnlColor, textAlign: "right", fontWeight: "500" }}>
                    {h.unrealized_pnl_pct ? `${h.unrealized_pnl_pct > 0 ? "+" : ""}${h.unrealized_pnl_pct.toFixed(2)}%` : "-"}
                  </td>
                  <td style={{ padding: "16px", textAlign: "center" }}>
                    <span style={{ 
                      padding: "4px 10px", 
                      borderRadius: "12px", 
                      fontSize: "12px", 
                      fontWeight: "600",
                      ...getRecommendationPillStyle(h.recommendation)
                    }}>
                      {formatRecommendation(h.recommendation)}
                    </span>
                  </td>
                  <td style={{ padding: "16px", textAlign: "center", color: "var(--text-primary)" }}>
                    {h.confidence_score ? (
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px" }}>
                        <div style={{ width: "40px", height: "4px", background: "var(--surface-sunken)", borderRadius: "2px", overflow: "hidden" }}>
                          <div style={{ height: "100%", width: `${h.confidence_score}%`, background: "var(--text-primary)" }} />
                        </div>
                        <span style={{ fontSize: "13px" }}>{h.confidence_score}</span>
                      </div>
                    ) : "-"}
                  </td>
                  <td style={{ padding: "16px", color: isStale ? "var(--red)" : "var(--text-tertiary)", textAlign: "right", fontSize: "13px" }}>
                    {h.last_updated ? (
                      isStale ? "Stale" : new Date(h.last_updated).toLocaleDateString("en-IN")
                    ) : (
                      "No Data"
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
