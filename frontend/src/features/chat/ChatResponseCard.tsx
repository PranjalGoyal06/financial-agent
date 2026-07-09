import type { ChatResponseCard as ChatResponseCardType } from "../../lib/types";
import { CitationList } from "./CitationList";
import { stableListKey } from "./renderKeys";

function badgeTone(value: string): string {
  const normalised = value.toLowerCase();
  if (["high", "good", "ok"].includes(normalised)) {
    return "good";
  }
  if (["medium", "limited", "degraded", "stale"].includes(normalised)) {
    return "watch";
  }
  if (["low", "critical_failure", "insufficient"].includes(normalised)) {
    return "risk";
  }
  return "neutral";
}

function formatBadge(value: string): string {
  return value.replace(/_/g, " ").toUpperCase();
}

type TextListProps = {
  title: string;
  items: string[];
};

function TextList({ title, items }: TextListProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <section className="chat-response__section">
      <h4>{title}</h4>
      <ul>
        {items.map((item, index) => (
          <li key={stableListKey(title, item, index)}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

type ChatResponseCardProps = {
  response: ChatResponseCardType;
};

export function ChatResponseCard({ response }: ChatResponseCardProps) {
  return (
    <article className="chat-response">
      <header className="chat-response__header">
        <div>
          <span className="chat-response__eyebrow">Recommendation</span>
          <h3>{response.recommendation}</h3>
        </div>
        <div className="chat-response__badges" aria-label="Response quality">
          <span className={`chat-badge chat-badge--${badgeTone(response.confidence_tier)}`}>
            Confidence {formatBadge(response.confidence_tier)}
          </span>
          <span className={`chat-badge chat-badge--${badgeTone(response.data_quality)}`}>
            Data {formatBadge(response.data_quality)}
          </span>
        </div>
      </header>

      <p className="chat-response__summary">{response.summary}</p>

      <div className="chat-response__grid">
        <section className="chat-response__section chat-response__section--risk">
          <h4>Downside First</h4>
          <p>{response.bear_case}</p>
          {response.expected_drawdown ? (
            <p className="chat-response__drawdown">{response.expected_drawdown}</p>
          ) : null}
        </section>

        {response.portfolio_impact ? (
          <section className="chat-response__section">
            <h4>Portfolio Impact</h4>
            <p>{response.portfolio_impact}</p>
          </section>
        ) : null}

        {response.upside_case ? (
          <section className="chat-response__section">
            <h4>Upside Case</h4>
            <p>{response.upside_case}</p>
          </section>
        ) : null}

        {response.no_action_case ? (
          <section className="chat-response__section">
            <h4>No-Action Case</h4>
            <p>{response.no_action_case}</p>
          </section>
        ) : null}
      </div>

      <TextList title="Key Risks" items={response.key_risks} />
      <TextList title="Assumptions" items={response.assumptions} />
      <TextList title="Principle Conflicts" items={response.principle_conflicts ?? []} />
      <TextList title="Next Steps" items={response.next_steps ?? []} />

      <CitationList citations={response.citations} />
    </article>
  );
}
