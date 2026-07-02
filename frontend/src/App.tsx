import { FormEvent, useEffect, useRef, useState } from "react";

type Message = {
  id: number;
  role: "user" | "assistant" | "system";
  content: string;
};

type StreamEvent =
  | { event: "run_start"; data: { stage: string; user_id: string; timestamp: string } }
  | { event: "token"; data: { token: string } }
  | {
      event: "final";
      data: {
        message: string;
        model: string;
        used_local_response: boolean;
        timestamp: string;
      };
    };

function parseSseEvent(rawEvent: string): StreamEvent | null {
  const eventName = rawEvent
    .split("\n")
    .find((line) => line.startsWith("event:"))
    ?.slice(6)
    .trim();
  const data = rawEvent
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");

  if (!eventName || !data) {
    return null;
  }

  try {
    return { event: eventName, data: JSON.parse(data) } as StreamEvent;
  } catch {
    return null;
  }
}

export function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "system",
      content:
        "SCALE Finance Agent is ready. Type a message to start a streamed chat.",
    },
  ]);
  const [input, setInput] = useState("");
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState("Checking backend...");
  const [isStreaming, setIsStreaming] = useState(false);
  const nextId = useRef(2);

  useEffect(() => {
    fetch("/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Backend returned ${response.status}`);
        }
        return response.json();
      })
      .then((payload: { runtime: string; user_id: string }) => {
        setStatus(`Connected as ${payload.user_id}`);
      })
      .catch((error: unknown) => {
        setStatus(error instanceof Error ? error.message : "Backend unavailable");
      });
  }, []);

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isStreaming) {
      return;
    }

    setMessages((current) => [
      ...current,
      { id: nextId.current++, role: "user", content: message },
    ]);
    setInput("");
    setDraft("");
    setIsStreaming(true);
    setStatus("Streaming response...");

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ message }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Chat request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantText = "";

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const rawEvents = buffer.split("\n\n");
        buffer = rawEvents.pop() ?? "";

        for (const rawEvent of rawEvents) {
          const parsed = parseSseEvent(rawEvent);
          if (!parsed) {
            continue;
          }

          if (parsed.event === "run_start") {
            setStatus("Preparing response...");
          }

          if (parsed.event === "token") {
            assistantText += parsed.data.token;
            setDraft(assistantText);
          }

          if (parsed.event === "final") {
            setStatus(
              parsed.data.used_local_response
                ? `Completed with ${parsed.data.model}`
                : `Completed with ${parsed.data.model}`
            );
          }
        }

        if (done) {
          break;
        }
      }

      if (assistantText) {
        setMessages((current) => [
          ...current,
          { id: nextId.current++, role: "assistant", content: assistantText },
        ]);
        setDraft("");
      }
    } catch (error: unknown) {
      setStatus(error instanceof Error ? error.message : "Chat stream failed");
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="chat-workbench" aria-label="Chat">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Investment intelligence</p>
            <h1>SCALE Finance Agent</h1>
          </div>
          <span className="status-pill">{status}</span>
        </header>

        <div className="message-list" aria-live="polite">
          {messages.map((message) => (
            <article className={`message message--${message.role}`} key={message.id}>
              <span>{message.role}</span>
              <p>{message.content}</p>
            </article>
          ))}
          {draft ? (
            <article className="message message--assistant message--streaming">
              <span>assistant</span>
              <p>{draft}</p>
            </article>
          ) : null}
        </div>

        <form className="composer" onSubmit={sendMessage}>
          <input
            aria-label="Message"
            value={input}
            disabled={isStreaming}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask the agent a question..."
          />
          <button disabled={isStreaming || !input.trim()} type="submit">
            {isStreaming ? "Streaming" : "Send"}
          </button>
        </form>
      </section>
    </main>
  );
}
