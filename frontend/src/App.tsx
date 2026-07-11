import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { marked } from "marked";

// ── Markdown ───────────────────────────────────────────────────────────────────

function Markdown({ content }: { content: string }) {
  const rawHtml = marked.parse(content, { async: false }) as string;
  return (
    <div className="message-content" dangerouslySetInnerHTML={{ __html: rawHtml }} />
  );
}

// ── Tool call card ─────────────────────────────────────────────────────────────

type ToolCallBlock = {
  type: "tool_call";
  name: string;
  summary: string;
  input: Record<string, unknown>;
  output?: string;
  status: "running" | "done" | "failed";
};

function ToolCallCard({ block }: { block: ToolCallBlock }) {
  const label = block.name.replace(/_tool$/, "").replace(/_/g, " ");
  const isRunning = block.status === "running";
  const isFailed = block.status === "failed";
  const icon = isRunning ? "⟳" : isFailed ? "⚠" : "✓";

  return (
    <details
      className={`tool-card${isRunning ? " tool-card--running" : ""}${
        isFailed ? " tool-card--failed" : ""
      }`}
    >
      <summary className="tool-card__summary">
        <span className="tool-card__icon">{icon}</span>
        <span className="tool-card__label">{label}</span>
        {block.summary && !isRunning && (
          <span className="tool-card__result">{block.summary}</span>
        )}
      </summary>
      <div className="tool-card__body">
        <div className="tool-card__section">
          <p className="tool-card__section-label">Request</p>
          <pre className="tool-card__code">{JSON.stringify(block.input, null, 2)}</pre>
        </div>
        {block.output !== undefined && (
          <div className="tool-card__section">
            <p className="tool-card__section-label">Response</p>
            <pre className="tool-card__code">{formatToolOutput(block.output)}</pre>
          </div>
        )}
      </div>
    </details>
  );
}

function formatToolOutput(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

// ── Types ──────────────────────────────────────────────────────────────────────

type TextBlock = { type: "text"; text: string };
type ContentBlock = TextBlock | ToolCallBlock;

type Message = {
  id: number;
  role: "user" | "assistant" | "system" | "error";
  // user/system/error use plain content string; assistant uses blocks
  content?: string;
  blocks?: ContentBlock[];
};

type StreamEvent =
  | { event: "run_start"; data: { stage: string; user_id: string; timestamp: string } }
  | { event: "token"; data: { token: string } }
  | { event: "error"; data: { message: string } }
  | { event: "tool_call"; data: { name: string; status: string; summary: string; input: Record<string, unknown> } }
  | { event: "tool_result"; data: { name: string; status: "done" | "failed"; summary: string; output?: string } }
  | { event: "final"; data: { model: string; timestamp: string } };

type Holding = {
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
};

type PortfolioResponse = {
  user_id: string;
  portfolio_id: string;
  holdings: Holding[];
  total_holdings: number;
  updated_at: string;
};

type PortfolioUploadError = { row: number; field: string; message: string };
type PortfolioUploadFailure = { message: string; errors: PortfolioUploadError[] };

// ── SSE parser ─────────────────────────────────────────────────────────────────

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

  if (!eventName || !data) return null;
  try {
    return { event: eventName, data: JSON.parse(data) } as StreamEvent;
  } catch {
    return null;
  }
}

// ── Block reducer helpers ──────────────────────────────────────────────────────

function appendToken(blocks: ContentBlock[], token: string): ContentBlock[] {
  const last = blocks[blocks.length - 1];
  if (last?.type === "text") {
    return [...blocks.slice(0, -1), { type: "text", text: last.text + token }];
  }
  return [...blocks, { type: "text", text: token }];
}

function pushToolCall(
  blocks: ContentBlock[],
  name: string,
  input: Record<string, unknown>
): ContentBlock[] {
  return [
    ...blocks,
    { type: "tool_call", name, summary: "", input, status: "running" },
  ];
}

function resolveToolResult(
  blocks: ContentBlock[],
  name: string,
  summary: string,
  output: string,
  status: "done" | "failed"
): ContentBlock[] {
  const idx = [...blocks].reverse().findIndex(
    (b) => b.type === "tool_call" && b.name === name && b.status === "running"
  );
  if (idx === -1) return blocks;
  const realIdx = blocks.length - 1 - idx;
  return blocks.map((b, i) =>
    i === realIdx
      ? ({ ...b, status, summary, output } as ToolCallBlock)
      : b
  );
}

// ── Message renderer ───────────────────────────────────────────────────────────

function AssistantBlocks({
  blocks,
  isStreaming,
}: {
  blocks: ContentBlock[];
  isStreaming?: boolean;
}) {
  return (
    <div className={`assistant-turn${isStreaming ? " assistant-turn--streaming" : ""}`}>
      {blocks.map((block, i) =>
        block.type === "text" ? (
          <Markdown key={i} content={block.text} />
        ) : (
          <ToolCallCard key={i} block={block} />
        )
      )}
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────────────────────

export function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      role: "system",
      content: "PAISA is ready. Ask about your portfolio or any Indian equity.",
    },
  ]);
  const [input, setInput] = useState("");
  const [draftBlocks, setDraftBlocks] = useState<ContentBlock[]>([]);
  const [status, setStatus] = useState("Checking backend...");
  const [isStreaming, setIsStreaming] = useState(false);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [portfolioStatus, setPortfolioStatus] = useState("Loading portfolio...");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadErrors, setUploadErrors] = useState<PortfolioUploadError[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const nextId = useRef(2);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // ── Health check ─────────────────────────────────────────────────────────────

  useEffect(() => {
    fetch("/health")
      .then((r) => {
        if (!r.ok) throw new Error(`Backend returned ${r.status}`);
        return r.json();
      })
      .then((p: { runtime: string; user_id: string }) => {
        setStatus(`Connected · ${p.user_id}`);
      })
      .catch((e: unknown) => {
        setStatus(e instanceof Error ? e.message : "Backend unavailable");
      });
  }, []);

  useEffect(() => {
    void loadPortfolio();
  }, []);

  // Auto-scroll on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, draftBlocks]);

  // ── Portfolio ─────────────────────────────────────────────────────────────────

  async function loadPortfolio() {
    try {
      const r = await fetch("/portfolio");
      if (!r.ok) throw new Error(`Portfolio returned ${r.status}`);
      const p = (await r.json()) as PortfolioResponse;
      setPortfolio(p);
      setPortfolioStatus(
        p.total_holdings ? `${p.total_holdings} holdings` : "No holdings"
      );
    } catch (e: unknown) {
      setPortfolioStatus(e instanceof Error ? e.message : "Unavailable");
    }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setUploadErrors([]);
  }

  async function uploadPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setUploadErrors([]);
    setPortfolioStatus("Uploading…");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const r = await fetch("/portfolio/upload", { method: "POST", body: formData });
      const payload = await r.json();

      if (!r.ok) {
        const failure = payload as PortfolioUploadFailure;
        setUploadErrors(failure.errors ?? []);
        throw new Error(failure.message || `Upload failed (${r.status})`);
      }

      setPortfolioStatus(`${Number(payload.imported_count ?? 0)} holdings imported`);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadPortfolio();
    } catch (e: unknown) {
      setPortfolioStatus(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  // ── Composer auto-grow ────────────────────────────────────────────────────────

  function handleInputChange(e: ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  // ── Chat stream ───────────────────────────────────────────────────────────────

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isStreaming) return;

    setMessages((cur) => [
      ...cur,
      { id: nextId.current++, role: "user", content: message },
    ]);
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    setDraftBlocks([]);
    setIsStreaming(true);
    setStatus("Thinking…");

    try {
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ message }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Chat request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let blocks: ContentBlock[] = [];
      let hasError = false;

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const rawEvents = buffer.split("\n\n");
        buffer = rawEvents.pop() ?? "";

        for (const rawEvent of rawEvents) {
          const parsed = parseSseEvent(rawEvent);
          if (!parsed) continue;

          if (parsed.event === "run_start") {
            setStatus("Thinking…");
          }

          if (parsed.event === "token") {
            blocks = appendToken(blocks, parsed.data.token);
            setDraftBlocks([...blocks]);
          }

          if (parsed.event === "tool_call") {
            blocks = pushToolCall(blocks, parsed.data.name, parsed.data.input ?? {});
            setDraftBlocks([...blocks]);
            setStatus(`Calling ${parsed.data.name.replace(/_tool$/, "")}…`);
          }

          if (parsed.event === "tool_result") {
            const outputStr = parsed.data.output ?? parsed.data.summary ?? "";
            blocks = resolveToolResult(
              blocks,
              parsed.data.name,
              parsed.data.summary,
              outputStr,
              parsed.data.status
            );
            setDraftBlocks([...blocks]);
          }

          if (parsed.event === "error") {
            setMessages((cur) => [
              ...cur,
              { id: nextId.current++, role: "error", content: parsed.data.message },
            ]);
            setDraftBlocks([]);
            setStatus("Stream failed");
            hasError = true;
            break;
          }

          if (parsed.event === "final") {
            setStatus(`Completed · ${parsed.data.model}`);
          }
        }

        if (done || hasError) break;
      }

      if (blocks.length > 0 && !hasError) {
        setMessages((cur) => [
          ...cur,
          { id: nextId.current++, role: "assistant", blocks },
        ]);
        setDraftBlocks([]);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Chat stream failed";
      setStatus(msg);
      setMessages((cur) => [
        ...cur,
        { id: nextId.current++, role: "error", content: msg },
      ]);
    } finally {
      setIsStreaming(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <main className="app-shell">

      {/* ── Portfolio sidebar ── */}
      <aside className="portfolio-panel" aria-label="Portfolio">
        <header className="portfolio-header">
          <div className="portfolio-header__text">
            <p className="eyebrow">Portfolio</p>
            <span className="portfolio-stat">{portfolio?.total_holdings ?? 0} holdings</span>
          </div>
          <span className={`portfolio-status-dot${portfolio?.total_holdings ? " portfolio-status-dot--ok" : ""}`} />
        </header>

        <form className="upload-row" onSubmit={uploadPortfolio}>
          <input
            ref={fileInputRef}
            aria-label="Portfolio CSV"
            accept=".csv,text/csv"
            onChange={selectFile}
            type="file"
          />
          <button disabled={!selectedFile || isUploading} type="submit">
            {isUploading ? "…" : "Upload"}
          </button>
        </form>

        <p className="portfolio-status-text">{portfolioStatus}</p>

        {uploadErrors.length > 0 && (
          <div className="upload-errors" role="alert">
            <p className="upload-errors__title">Rejected rows</p>
            <ul>
              {uploadErrors.map((err) => (
                <li key={`${err.row}-${err.field}`}>
                  Row {err.row} · {err.field}: {err.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="holdings-table-wrap">
          {portfolio?.holdings.length ? (
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Qty</th>
                  <th>Avg ₹</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((h) => (
                  <tr key={h.id}>
                    <td>
                      <span className="ticker-badge">{h.canonical_ticker}</span>
                    </td>
                    <td>{formatNumber(h.quantity)}</td>
                    <td>{formatNumber(h.avg_cost)}</td>
                    <td>{h.purchase_date ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-holdings">No holdings · upload a CSV</div>
          )}
        </div>
      </aside>

      {/* ── Chat workbench ── */}
      <section className="chat-workbench" aria-label="Chat">
        <header className="chat-header">
          <div>
            <p className="eyebrow">Investment intelligence</p>
            <h1>PAISA</h1>
          </div>
          <span className="status-pill">{status}</span>
        </header>

        <div className="message-list" aria-live="polite">

          {messages.map((msg) => {
            if (msg.role === "user") {
              return (
                <div key={msg.id} className="turn turn--user">
                  <div className="bubble bubble--user">
                    <Markdown content={msg.content ?? ""} />
                  </div>
                </div>
              );
            }
            if (msg.role === "system") {
              return (
                <div key={msg.id} className="turn turn--system">
                  <p className="system-notice">{msg.content}</p>
                </div>
              );
            }
            if (msg.role === "error") {
              return (
                <div key={msg.id} className="turn turn--assistant">
                  <div className="error-bubble">
                    <span className="error-bubble__icon">⚠</span>
                    {msg.content}
                  </div>
                </div>
              );
            }
            // assistant
            return (
              <div key={msg.id} className="turn turn--assistant">
                <AssistantBlocks blocks={msg.blocks ?? []} />
              </div>
            );
          })}

          {/* Streaming draft */}
          {draftBlocks.length > 0 && (
            <div className="turn turn--assistant">
              <AssistantBlocks blocks={draftBlocks} isStreaming />
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* ── Composer ── */}
        <form className="composer" onSubmit={sendMessage}>
          <div className="composer__inner">
            <textarea
              ref={textareaRef}
              className="composer__input"
              aria-label="Message"
              value={input}
              disabled={isStreaming}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your portfolio… (Enter to send, Shift+Enter for newline)"
              rows={1}
            />
            <button
              className="composer__send"
              disabled={isStreaming || !input.trim()}
              type="submit"
              aria-label="Send"
            >
              {isStreaming ? (
                <span className="composer__spinner">⟳</span>
              ) : (
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 8L14 8M8 2L14 8L8 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              )}
            </button>
          </div>
          <p className="composer__hint">Shift+Enter for newline</p>
        </form>
      </section>
    </main>
  );
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}
