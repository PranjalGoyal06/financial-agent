import { useEffect, useState } from "react";

// Types matching the backend /briefing response
type GreetingData = {
  greeting: string;
  market_status: "open" | "closed";
  market_closed_relative_time: string;
  research_run_relative_time: string;
  tickers_analyzed: number;
};

type Metric = { price: number | null; day_change_pct: number | null };
type VixMetric = { value: number | null; tier: "low" | "moderate" | "elevated" | "high" | "unknown" };
type Breadth = { advancers: number; decliners: number; unchanged: number };
type PortfolioNetPnl = { amount: number; pct: number };

type ClimateData = {
  nifty50: Metric;
  india_vix: VixMetric;
  holdings_breadth: Breadth;
  portfolio_net_pnl: PortfolioNetPnl;
  fetched_at: string;
};

type ActionCard = {
  ticker: string;
  recommendation: string;
  confidence_score: number;
  confidence_tier: "high" | "moderate" | "low" | "unknown";
  headline: string;
  bear_case_snippet: string;
  change_context: string | null;
  run_id: string;
};

type ActionDeskData = {
  cards: ActionCard[];
  total_qualifying: number;
  has_overflow: boolean;
};

type NoActionData = { count: number; total_reviewed: number };
type NewsItem = {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  target: string;
  summary: string;
};

type BriefingResponse = {
  greeting: GreetingData;
  climate: ClimateData;
  action_desk: ActionDeskData;
  no_action: NoActionData;
  top_news: NewsItem[];
};

interface BriefingZoneProps {
  onPreFillChat: (query: string) => void;
}

function formatAmount(val: number): string {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(val);
}

export function BriefingZone({ onPreFillChat }: BriefingZoneProps) {
  const [data, setData] = useState<BriefingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchBriefing() {
      try {
        const res = await fetch("/briefing");
        if (!res.ok) throw new Error("Failed to load briefing");
        const json = await res.json();
        setData(json);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Error fetching briefing");
      } finally {
        setLoading(false);
      }
    }
    fetchBriefing();
  }, []);

  if (loading) {
    return <div className="briefing-loader">Gathering morning briefing...</div>;
  }
  if (error || !data) {
    return null; // silently fail or render nothing if backend is unreachable
  }

  const { greeting, climate, action_desk, no_action, top_news } = data;

  const handleCardClick = (ticker: string, recommendation: string) => {
    onPreFillChat(`Why is ${ticker} flagged as ${recommendation}?`);
  };

  return (
    <div className="briefing-zone">
      {/* Greeting Line */}
      <div className="briefing-greeting">
        {greeting.greeting}, Trader — markets{" "}
        {greeting.market_status === "closed"
          ? `closed ${greeting.market_closed_relative_time}`
          : "are currently open"}{" "}
        · overnight research ran {greeting.research_run_relative_time}
      </div>

      {/* Climate Strip */}
      <div className="climate-strip">
        <div className="climate-metric">
          <span className="climate-label">NIFTY 50</span>
          {climate.nifty50.price !== null ? (
            <span className="climate-val">
              {formatAmount(climate.nifty50.price)}{" "}
              <span
                className={
                  (climate.nifty50.day_change_pct ?? 0) >= 0 ? "text-green" : "text-red"
                }
              >
                ({(climate.nifty50.day_change_pct ?? 0) > 0 ? "+" : ""}
                {(climate.nifty50.day_change_pct ?? 0).toFixed(2)}%)
              </span>
            </span>
          ) : (
            <span className="climate-val">--</span>
          )}
        </div>
        <div className="climate-metric">
          <span className="climate-label">India VIX</span>
          <span className="climate-val">
            {climate.india_vix.value?.toFixed(2) ?? "--"} · {climate.india_vix.tier}
          </span>
        </div>
        <div className="climate-metric">
          <span className="climate-label">Breadth (Holdings)</span>
          <span className="climate-val">
            <span className="text-green">{climate.holdings_breadth.advancers} up</span> ·{" "}
            <span className="text-red">{climate.holdings_breadth.decliners} down</span>
          </span>
        </div>
        <div className="climate-metric">
          <span className="climate-label">Portfolio Net P&L</span>
          <span className="climate-val">
            <span className={climate.portfolio_net_pnl.amount >= 0 ? "text-green" : "text-red"}>
              ₹{formatAmount(Math.abs(climate.portfolio_net_pnl.amount))} (
              {climate.portfolio_net_pnl.pct > 0 ? "+" : ""}
              {climate.portfolio_net_pnl.pct.toFixed(2)}%)
            </span>
          </span>
        </div>
      </div>

      {/* Action Desk */}
      <div className="action-desk">
        <div className="action-desk-header">
          <h3 className="action-desk-title">Action Desk</h3>
          {action_desk.has_overflow && (
            <span className="action-overflow">
              Showing 5 of {action_desk.total_qualifying} alerts — <a href="#">View full research</a>
            </span>
          )}
        </div>
        
        {action_desk.cards.length === 0 ? (
          <div className="action-empty">Nothing crossed your threshold today.</div>
        ) : (
          <div className="action-cards">
            {action_desk.cards.map((card, i) => (
              <div
                key={i}
                className="action-card"
                onClick={() => handleCardClick(card.ticker, card.recommendation)}
              >
                <div className="action-card-header">
                  <span className="action-ticker">{card.ticker}</span>
                  <span className={`action-badge rec-${card.recommendation.toLowerCase().replace('_', '-')}`}>
                    {card.recommendation.toUpperCase()} · {card.confidence_tier} conf
                  </span>
                </div>
                {card.change_context && (
                  <div className="action-change-context">↗ {card.change_context}</div>
                )}
                <div className="action-headline">{card.headline}</div>
                <div className="action-bear-case">
                  <span className="bear-label">Bear Case:</span> {card.bear_case_snippet}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* No Action Summary */}
      {no_action.count > 0 && (
        <div className="no-action-line">
          {no_action.count} other holdings reviewed, no action needed — <a href="#">View all</a>
        </div>
      )}

      {/* Top News Carousel */}
      {top_news.length > 0 && (
        <div className="news-carousel-container">
          <h4 className="news-carousel-title">Latest Evidence</h4>
          <div className="news-carousel">
            {top_news.map((item, i) => (
              <a
                key={i}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="news-card"
              >
                <div className="news-card-tag">
                  <span className="news-target">{item.target}</span>
                  <span className="news-source">{item.source}</span>
                </div>
                <div className="news-title">{item.title}</div>
                <div className="news-summary">{item.summary}</div>
                <div className="news-time">{item.published_at}</div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
