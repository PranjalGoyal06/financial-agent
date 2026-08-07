import type { ReactiveResponseEnvelope, ToolCallTrace } from "../../lib/types";
import { normaliseChatResponse } from "./chatResponse";
import { ChatResponseCard } from "./ChatResponseCard";
import type { ChatMessage } from "../../lib/types";

type ReactiveResponseProps = {
  message: ChatMessage;
};

function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function asTextList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function responseLabel(responseType: string): string {
  if (responseType === "portfolio_snapshot") {
    return "Portfolio Snapshot";
  }
  if (responseType === "insufficient_data") {
    return "Insufficient Data";
  }
  if (responseType === "research_run_status") {
    return "Research Run";
  }
  return titleCase(responseType);
}

function formatToolArgs(args: Record<string, unknown> | undefined): string {
  if (!args || Object.keys(args).length === 0) {
    return "";
  }
  return JSON.stringify(args);
}

function ToolTrace({ toolCalls }: { toolCalls?: ToolCallTrace[] }) {
  if (!toolCalls?.length) {
    return null;
  }

  return (
    <details className="chat-disclosure chat-tool-disclosure">
      <summary>Tool calls</summary>
      <ol>
        {toolCalls.map((toolCall, index) => (
          <li key={toolCall.tool_call_id || `${toolCall.name}-${index}`}>
            <strong>{toolCall.name}</strong>
            {formatToolArgs(toolCall.args) ? (
              <code>{formatToolArgs(toolCall.args)}</code>
            ) : null}
            {toolCall.summary ? <span>{toolCall.summary}</span> : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

function Disclosure({ response }: { response: ReactiveResponseEnvelope }) {
  const deterministic = response.retrieval_disclosure?.deterministic ?? [];
  const planned = response.retrieval_disclosure?.llm_planned ?? [];
  const unavailable = response.retrieval_disclosure?.unavailable ?? [];
  const hasDisclosure = deterministic.length || planned.length || unavailable.length;

  if (!hasDisclosure && response.evidence_ids.length === 0) {
    return null;
  }

  return (
    <details className="chat-disclosure">
      <summary>Evidence and retrieval</summary>
      {deterministic.length ? (
        <section>
          <h4>Baseline</h4>
          <ul>
            {deterministic.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {planned.length ? (
        <section>
          <h4>Retrieved</h4>
          <ul>
            {planned.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {unavailable.length ? (
        <section>
          <h4>Unavailable</h4>
          <ul>
            {unavailable.map((item) => (
              <li key={`${item.item}-${item.reason}`}>
                {item.item}
                {item.reason ? `: ${item.reason}` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {response.evidence_ids.length ? (
        <section>
          <h4>Evidence IDs</h4>
          <ul>
            {response.evidence_ids.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </details>
  );
}

function GenericCard({ response }: { response: ReactiveResponseEnvelope }) {
  const payload = asRecord(response.card_payload);
  const risks = asTextList(payload.risks ?? payload.key_risks ?? payload.risk_notes);
  const caveats = asTextList(payload.caveats ?? payload.warnings);
  const assumptions = response.assumptions.length
    ? response.assumptions
    : asTextList(payload.assumptions);
  const nextSteps = asTextList(payload.next_steps ?? payload.suggested_prompts);
  const summary =
    typeof payload.summary === "string" && payload.summary.trim()
      ? payload.summary
      : response.bubble_text;

  return (
    <article className="chat-response chat-response--generic">
      <header className="chat-response__header">
        <div>
          <span className="chat-response__eyebrow">
            {responseLabel(response.response_type)}
          </span>
          <h3>{summary}</h3>
        </div>
        <div className="chat-response__badges" aria-label="Response quality">
          <span className="chat-badge chat-badge--neutral">
            Confidence {response.confidence_tier.replace(/_/g, " ").toUpperCase()}
          </span>
          <span className="chat-badge chat-badge--neutral">
            Data {response.data_quality.replace(/_/g, " ").toUpperCase()}
          </span>
        </div>
      </header>

      {risks.length ? (
        <section className="chat-response__section">
          <h4>Risk Notes</h4>
          <ul>
            {risks.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {caveats.length ? (
        <section className="chat-response__section">
          <h4>Caveats</h4>
          <ul>
            {caveats.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {assumptions.length ? (
        <section className="chat-response__section">
          <h4>Assumptions</h4>
          <ul>
            {assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {nextSteps.length ? (
        <section className="chat-response__section">
          <h4>Suggested Follow-ups</h4>
          <ul>
            {nextSteps.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <Disclosure response={response} />
    </article>
  );
}

export function ReactiveResponse({ message }: ReactiveResponseProps) {
  const response = message.metadata?.response;
  const toolCalls = message.metadata?.tool_calls;

  if (!response) {
    return <ChatResponseCard response={normaliseChatResponse(message)} />;
  }

  if (response.response_type === "plain_chat" || !response.card_payload) {
    return (
      <div className="chat-message__stack">
        <div className="chat-message__bubble">{response.bubble_text}</div>
        <ToolTrace toolCalls={toolCalls} />
        <Disclosure response={response} />
      </div>
    );
  }

  if (response.response_type === "recommendation") {
    return (
      <div className="chat-message__stack chat-message__stack--wide">
        <ChatResponseCard response={normaliseChatResponse(message)} />
        <ToolTrace toolCalls={toolCalls} />
      </div>
    );
  }

  return (
    <div className="chat-message__stack chat-message__stack--wide">
      <GenericCard response={response} />
      <ToolTrace toolCalls={toolCalls} />
    </div>
  );
}
