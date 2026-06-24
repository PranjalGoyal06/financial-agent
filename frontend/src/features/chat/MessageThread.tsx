import type { ChatMessage } from "../../lib/types";
import { ReactiveResponse } from "./ReactiveResponse";

type MessageThreadProps = {
  messages: ChatMessage[];
  isLoading?: boolean;
};

export function MessageThread({ messages, isLoading = false }: MessageThreadProps) {
  if (isLoading) {
    return <div className="chat-empty">Loading conversation...</div>;
  }

  if (messages.length === 0) {
    return (
      <div className="chat-empty">
        <h3>Start with the portfolio risk you want to understand.</h3>
        <p>Ask about downside, concentration, no-action cases, or a ticker in context.</p>
      </div>
    );
  }

  return (
    <div className="chat-thread" aria-live="polite">
      {messages.map((message) => (
        <div
          key={message.message_id}
          className={`chat-message chat-message--${message.role}`}
        >
          {message.role === "assistant" ? (
            <ReactiveResponse message={message} />
          ) : (
            <div className="chat-message__bubble">{message.content}</div>
          )}
        </div>
      ))}
    </div>
  );
}
