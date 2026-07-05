import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

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

type PortfolioUploadError = {
  row: number;
  field: string;
  message: string;
};

type PortfolioUploadFailure = {
  message: string;
  errors: PortfolioUploadError[];
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
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [portfolioStatus, setPortfolioStatus] = useState("Loading portfolio...");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadErrors, setUploadErrors] = useState<PortfolioUploadError[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const nextId = useRef(2);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  useEffect(() => {
    void loadPortfolio();
  }, []);

  async function loadPortfolio() {
    try {
      const response = await fetch("/portfolio");
      if (!response.ok) {
        throw new Error(`Portfolio returned ${response.status}`);
      }
      const payload = (await response.json()) as PortfolioResponse;
      setPortfolio(payload);
      setPortfolioStatus(
        payload.total_holdings
          ? `${payload.total_holdings} holdings loaded`
          : "No holdings imported"
      );
    } catch (error: unknown) {
      setPortfolioStatus(error instanceof Error ? error.message : "Portfolio unavailable");
    }
  }

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setUploadErrors([]);
  }

  async function uploadPortfolio(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile || isUploading) {
      return;
    }

    setIsUploading(true);
    setUploadErrors([]);
    setPortfolioStatus("Uploading portfolio...");

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("/portfolio/upload", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();

      if (!response.ok) {
        const failure = payload as PortfolioUploadFailure;
        setUploadErrors(failure.errors ?? []);
        throw new Error(failure.message || `Upload failed (${response.status})`);
      }

      const importedCount = Number(payload.imported_count ?? 0);
      setPortfolioStatus(`${importedCount} holdings imported`);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      await loadPortfolio();
    } catch (error: unknown) {
      setPortfolioStatus(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }

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
      <section className="portfolio-panel" aria-label="Portfolio">
        <header className="portfolio-header">
          <div>
            <p className="eyebrow">Data foundation</p>
            <h2>Portfolio</h2>
          </div>
          <div className="holding-count">
            <span>Holdings</span>
            <strong>{portfolio?.total_holdings ?? 0}</strong>
          </div>
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
            {isUploading ? "Uploading" : "Upload CSV"}
          </button>
        </form>

        <p className="portfolio-status">{portfolioStatus}</p>

        {uploadErrors.length ? (
          <div className="upload-errors" role="alert">
            <h3>Rejected rows</h3>
            <ul>
              {uploadErrors.map((error) => (
                <li key={`${error.row}-${error.field}-${error.message}`}>
                  Row {error.row}, {error.field}: {error.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="holdings-table-wrap">
          {portfolio?.holdings.length ? (
            <table className="holdings-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Exchange</th>
                  <th>Asset</th>
                  <th>Qty</th>
                  <th>Avg cost</th>
                  <th>Currency</th>
                  <th>Purchase date</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((holding) => (
                  <tr key={holding.id}>
                    <td>{holding.canonical_ticker}</td>
                    <td>{holding.exchange}</td>
                    <td>{holding.asset_class}</td>
                    <td>{formatNumber(holding.quantity)}</td>
                    <td>{formatNumber(holding.avg_cost)}</td>
                    <td>{holding.currency}</td>
                    <td>{holding.purchase_date ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="empty-holdings">No holdings</div>
          )}
        </div>
      </section>

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

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(value);
}
