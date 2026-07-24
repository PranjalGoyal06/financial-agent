import {
  ChangeEvent,
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { marked } from "marked";
import { User, Sparkles, Copy, Check } from "lucide-react";
import { BriefingZone } from "./BriefingZone";
import { PortfolioZone } from "./PortfolioZone";
import { ResearchLayout } from "./features/research/ResearchLayout";
import { SettingsZone } from "./SettingsZone";
import { LibraryZone } from "./features/library/LibraryZone";
import { StockSearch } from "./components/StockSearch";
import {
  ToolCallCard,
  ToolCallGroup,
  ToolCallBlock,
} from "./components/ToolCallCard";
import { ComparisonCardRender } from "./components/ComparisonCardRender";
import { ArtifactCardRender } from "./components/ArtifactCardRender";

// ── Markdown ───────────────────────────────────────────────────────────────────

function Markdown({ content }: { content: string }) {
  const rawHtml = marked.parse(content, { async: false }) as string;
  return (
    <div className="message-content" dangerouslySetInnerHTML={{ __html: rawHtml }} />
  );
}

// ── Types ──────────────────────────────────────────────────────────────────────

type TextBlock = { type: "text"; text: string };
type CardBlock = { type: "card_render"; payload: any };
type ContentBlock = TextBlock | ToolCallBlock | CardBlock;

type Message = {
  id: number;
  role: "user" | "assistant" | "system" | "error";
  content?: string;
  blocks?: ContentBlock[];
};

type StreamEvent =
  | { event: "run_start"; data: { stage: string; user_id: string; timestamp: string } }
  | { event: "token"; data: { token: string } }
  | { event: "error"; data: { message: string } }
  | { event: "tool_call"; data: { name: string; status: string; summary: string; input: Record<string, unknown> } }
  | { event: "tool_result"; data: { name: string; status: "done" | "failed"; summary: string; output?: string } }
  | { event: "card_render"; data: any }
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
  realized_pnl?: number;
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
  // Group contiguous tool_call blocks
  const groupedBlocks: Array<
    | { type: "text"; text: string }
    | { type: "tool_group"; items: ToolCallBlock[] }
    | { type: "card_render"; payload: any }
  > = [];

  for (const block of blocks) {
    if (block.type === "text") {
      groupedBlocks.push(block);
    } else if (block.type === "card_render") {
      groupedBlocks.push(block as any);
    } else {
      const last = groupedBlocks[groupedBlocks.length - 1];
      if (last && last.type === "tool_group") {
        last.items.push(block);
      } else {
        groupedBlocks.push({ type: "tool_group", items: [block] });
      }
    }
  }

  return (
    <div className={`assistant-turn${isStreaming ? " assistant-turn--streaming" : ""}`}>
      {groupedBlocks.map((item: any, i) =>
        item.type === "text" ? (
          <Markdown key={i} content={item.text} />
        ) : item.type === "card_render" ? (
          item.payload.command === "create_artifact" ? (
            <ArtifactCardRender key={i} envelope={item.payload} />
          ) : item.payload.command === "compare" ? (
            <ComparisonCardRender key={i} envelope={item.payload} />
          ) : null
        ) : (
          <ToolCallGroup key={i} blocks={item.items} isStreaming={isStreaming} />
        )
      )}
    </div>
  );
}

// ── Icons ──────────────────────────────────────────────────────────────────────

const HomeIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
    <polyline points="9 22 9 12 15 12 15 22"></polyline>
  </svg>
);

const ExchangeIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="16 3 21 3 21 8"></polyline>
    <line x1="4" y1="14" x2="21" y2="3"></line>
    <polyline points="8 21 3 21 3 16"></polyline>
    <line x1="20" y1="10" x2="3" y2="21"></line>
  </svg>
);

const WalletIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"></path>
    <path d="M3 5v14a2 2 0 0 0 2 2h16v-5"></path>
    <path d="M18 12a2 2 0 0 0 0 4h4v-4Z"></path>
  </svg>
);

const SearchIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"></circle>
    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
  </svg>
);

const UserIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
    <circle cx="12" cy="7" r="4"></circle>
  </svg>
);

const SquareIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2" />
  </svg>
);

// ── App ────────────────────────────────────────────────────────────────────────

import { AVAILABLE_MODELS, getSelectedModelConfig } from "./models";

export function App() {
  const [activeTab, setActiveTab] = useState<'chat' | 'research' | 'portfolio' | 'settings' | 'library'>('chat');
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
  const [healthData, setHealthData] = useState<any>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  function stopStreaming() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }
  
  const [selectedModelId, setSelectedModelId] = useState(() => {
    const p = localStorage.getItem("paisa_llm_provider") || "groq";
    const m = localStorage.getItem("paisa_llm_model");
    if (m) {
      const match = AVAILABLE_MODELS.find((opt) => opt.provider === p && opt.model === m);
      if (match) return match.id;
    }
    const matchProvider = AVAILABLE_MODELS.find((opt) => opt.provider === p);
    return matchProvider ? matchProvider.id : AVAILABLE_MODELS[0].id;
  });

  useEffect(() => {
    const config = getSelectedModelConfig(selectedModelId);
    localStorage.setItem("paisa_llm_provider", config.provider);
    localStorage.setItem("paisa_llm_model", config.model);
  }, [selectedModelId]);

  const handleModelChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedModelId(e.target.value);
  };

  // Portfolio state
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [portfolioStatus, setPortfolioStatus] = useState("Loading portfolio...");
  const [isPortfolioOpen, setIsPortfolioOpen] = useState(false);
  const [livePrices, setLivePrices] = useState<Record<string, any>>({});
  const [isRefreshingPrices, setIsRefreshingPrices] = useState(false);
  
  // Upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadErrors, setUploadErrors] = useState<PortfolioUploadError[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  
  // ── Mentions State ─────────────────────────────────────────────────────────────
  const [triggerState, setTriggerState] = useState<{ activeTrigger: '/' | '$' | '@' | null, query: string, startIndex: number }>({ activeTrigger: null, query: "", startIndex: -1 });
  const [suggestions, setSuggestions] = useState<{ id: string, label: string }[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recognizedMentions, setRecognizedMentions] = useState<Map<string, { type: string, id: string, label: string }>>(new Map());

  // ── Async Mentions Search ──────────────────────────────────────────────────────
  useEffect(() => {
    if (triggerState.activeTrigger === null) {
      setSuggestions([]);
      return;
    }
    
    const query = triggerState.query.toLowerCase();
    
    if (triggerState.activeTrigger === '/') {
      const allCommands = [
        { id: 'compare', label: '/compare' },
        { id: 'create-artifact', label: '/create-artifact' },
        { id: 'recommend', label: '/recommend' },
        { id: 'research', label: '/research' }
      ];
      setSuggestions(allCommands.filter(c => c.label.toLowerCase().includes(query)));
      setSelectedIndex(0);
    } else if (triggerState.activeTrigger === '$') {
      // Fetch from backend
      fetch(`/api/search/stocks?q=${encodeURIComponent(query)}`)
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) {
            setSuggestions(data.map(stock => ({
              id: stock.symbol,
              label: `${stock.symbol} - ${stock.name}`
            })));
            setSelectedIndex(0);
          }
        })
        .catch(err => {
          console.error("Failed to fetch stocks", err);
          setSuggestions([]);
        });
    } else if (triggerState.activeTrigger === '@') {
      const allArtifacts = [
        { id: 'research_notes', label: 'Research Notes' },
        { id: 'q1_earnings', label: 'Q1 Earnings Draft' },
        { id: 'tradebook', label: 'Tradebook CSV' }
      ];
      setSuggestions(allArtifacts.filter(a => a.id.toLowerCase().includes(query) || a.label.toLowerCase().includes(query)));
      setSelectedIndex(0);
    }
  }, [triggerState]);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const nextId = useRef(2);

  // ── Health check ─────────────────────────────────────────────────────────────

  useEffect(() => {
    fetch("/health")
      .then((r) => {
        if (!r.ok) throw new Error(`Backend returned ${r.status}`);
        return r.json();
      })
      .then((p: any) => {
        setHealthData(p);
        if (p.status === "healthy") setStatus("Connected");
        else if (p.status === "degraded") setStatus("Degraded");
        else setStatus("Unhealthy");
      })
      .catch((e: unknown) => {
        const msg = e instanceof Error ? e.message : "Backend unavailable";
        setStatus(msg);
        setHealthData({
          status: "error",
          checks: { backend: { ok: false, message: msg } }
        });
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
        p.total_holdings ? `${p.total_holdings} holdings` : "No tradebook uploaded yet"
      );
    } catch (e: unknown) {
      setPortfolioStatus(e instanceof Error ? e.message : "Unavailable");
    }
  }

  async function refreshPrices() {
    if (isRefreshingPrices) return;
    setIsRefreshingPrices(true);
    try {
      const r = await fetch("/portfolio/quotes");
      if (!r.ok) throw new Error("Failed to fetch quotes");
      const data = await r.json();
      setLivePrices(data);
    } catch (e: unknown) {
      console.error("Price refresh error:", e);
    } finally {
      setIsRefreshingPrices(false);
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
      // Auto-open portfolio on success
      setIsPortfolioOpen(true);
    } catch (e: unknown) {
      setPortfolioStatus(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }

  // ── Composer auto-grow ────────────────────────────────────────────────────────

  function handlePreFillChat(query: string) {
    setInput(query);
    if (textareaRef.current) {
      textareaRef.current.focus();
      setTimeout(() => {
        if (textareaRef.current) {
          textareaRef.current.style.height = "auto";
          textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
      }, 0);
    }
  }

  function handleInputChange(e: ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setInput(val);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
    
    const cursor = el.selectionStart;
    const textBeforeCursor = val.slice(0, cursor);
    const match = textBeforeCursor.match(/(?:^|\s)([\/$@])([a-zA-Z0-9_-]*)$/);
    if (match) {
      const trigger = match[1] as '/' | '$' | '@';
      const query = match[2];
      setTriggerState({ activeTrigger: trigger, query, startIndex: cursor - query.length - 1 });
    } else {
      setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
      setSuggestions([]);
    }
  }


  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape" && isStreaming) {
      e.preventDefault();
      stopStreaming();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      if (triggerState.activeTrigger && suggestions.length > 0) {
        e.preventDefault();
        insertMention(suggestions[selectedIndex]);
        return;
      }
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
    
    if (triggerState.activeTrigger && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % suggestions.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
      } else if (e.key === "Escape") {
        e.preventDefault();
        setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
        setSuggestions([]);
      }
    }
  }

  function insertMention(sugg: { id: string, label: string }) {
    if (triggerState.startIndex === -1 || !textareaRef.current) return;
    
    const before = input.slice(0, triggerState.startIndex);
    const after = input.slice(textareaRef.current.selectionStart);
    
    const replacement = `${triggerState.activeTrigger}${sugg.id} `;
    setInput(before + replacement + after);
    
    setRecognizedMentions(prev => {
      const next = new Map(prev);
      next.set(replacement.trim(), { 
        type: triggerState.activeTrigger === '/' ? 'command' : (triggerState.activeTrigger === '$' ? 'ticker' : 'artifact'), 
        id: sugg.id, 
        label: sugg.label 
      });
      return next;
    });
    
    setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
    setSuggestions([]);
    
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
      }
    }, 0);
  }

  function renderOverlay(text: string) {
    if (recognizedMentions.size === 0) return <span>{text}</span>;
    const keys = Array.from(recognizedMentions.keys());
    const escaped = keys.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
    const regex = new RegExp(`(${escaped.join('|')})(?=\\s|$)`, 'g');
    const parts = text.split(regex);
    return (
      <>
        {parts.map((part, i) => {
          if (recognizedMentions.has(part)) {
            const m = recognizedMentions.get(part)!;
            return <span key={i} className={`highlight highlight--${m.type}`}>{part}</span>;
          }
          return <span key={i}>{part}</span>;
        })}
      </>
    );
  }

  // ── Chat stream ───────────────────────────────────────────────────────────────

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = input.trim();
    if (!message) return;

    if (isStreaming) {
      stopStreaming();
    }

    const controller = new AbortController();
    abortControllerRef.current = controller;

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

    let blocks: ContentBlock[] = [];
    let hasError = false;
    let wasAborted = false;

    const activeMentions = Array.from(recognizedMentions.values()).filter(m => message.includes(m.id));

    try {
      const activeConfig = getSelectedModelConfig(selectedModelId);
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ 
          message,
          mentions: activeMentions,
          llm_provider: activeConfig.provider,
          llm_model: activeConfig.model,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Chat request failed (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        if (controller.signal.aborted) {
          wasAborted = true;
          break;
        }
        const { value, done } = await reader.read();
        if (controller.signal.aborted) {
          wasAborted = true;
          break;
        }
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

          if (parsed.event === "card_render") {
            blocks = [...blocks, { type: "card_render", payload: parsed.data }];
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
            setStatus(`Connected`);
          }
        }

        if (done || hasError) break;
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") {
        wasAborted = true;
      } else {
        const msg = e instanceof Error ? e.message : "Chat stream failed";
        setStatus(msg);
        setMessages((cur) => [
          ...cur,
          { id: nextId.current++, role: "error", content: msg },
        ]);
      }
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      setIsStreaming(false);

      if (wasAborted) {
        setStatus("Interrupted");
      }

      if (blocks.length > 0 && !hasError) {
        const finalBlocks = blocks.map((b) =>
          b.type === "tool_call" && b.status === "running"
            ? { ...b, status: "failed" as const, summary: "Interrupted", output: "Tool execution interrupted by user." }
            : b
        );

        setMessages((cur) => [
          ...cur,
          { id: nextId.current++, role: "assistant", blocks: finalBlocks },
        ]);
        setDraftBlocks([]);
      }
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────────

  return (
    <div className={`app-shell ${isPortfolioOpen ? 'app-shell--portfolio-open' : ''}`}>
      
      {/* ── Left Sidebar (Navigation) ── */}
      <aside className="sidebar" aria-label="Navigation">
        <div className="sidebar__logo">
          <div className="sidebar__logo-icon">P</div>
          <div className="sidebar__logo-text">PAISA</div>
        </div>
        
        <nav className="nav-section">
          <p className="nav-section__title">Main Menu</p>
          <a href="#" className={`nav-item ${activeTab === 'chat' ? 'nav-item--active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('chat'); }}>
            <HomeIcon />
            Home
          </a>
          <a href="#" className={`nav-item ${activeTab === 'portfolio' ? 'nav-item--active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('portfolio'); setIsPortfolioOpen(false); }}>
            <WalletIcon />
            Portfolio
          </a>
          <a href="#" className="nav-item">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2-2z"></path></svg>
            Chat
          </a>
          <a href="#" className={`nav-item ${activeTab === 'research' ? 'nav-item--active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('research'); }}>
            <ExchangeIcon />
            Research
          </a>
          <a href="#" className={`nav-item ${activeTab === 'library' ? 'nav-item--active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('library'); setIsPortfolioOpen(false); }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            Artifacts
          </a>
          <a href="#" className={`nav-item ${activeTab === 'settings' ? 'nav-item--active' : ''}`} onClick={(e) => { e.preventDefault(); setActiveTab('settings'); }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
            Settings
          </a>
        </nav>

        <form className="upload-box" onSubmit={uploadPortfolio}>
          <p className="upload-box__title">Tradebook</p>
          <p className="upload-box__desc">{portfolioStatus}</p>
          {portfolio?.updated_at && (
            <p className="upload-box__desc" style={{ fontSize: '10px', marginTop: '-12px' }}>
              Last updated: {formatUpdatedDate(portfolio.updated_at)}
            </p>
          )}
          <input
            ref={fileInputRef}
            aria-label="Portfolio CSV"
            accept=".csv,text/csv"
            onChange={selectFile}
            type="file"
          />
          {!selectedFile ? (
            <button
              className="upload-box__btn"
              disabled={isUploading}
              type="button"
              onClick={() => fileInputRef.current?.click()}
            >
              Upload CSV
            </button>
          ) : (
            <button 
              className="upload-box__btn" 
              type="submit" 
              disabled={isUploading}
              style={{ background: "var(--green)", color: "#FFF" }}
            >
              {isUploading ? "Uploading…" : "Confirm Upload"}
            </button>
          )}
          
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
        </form>
        
        <div className="sidebar__footer">
          <div className="service-status-container">
            <div className={`status-dot ${
              status === "Connected" ? "status-dot--ok" : 
              status === "Degraded" ? "status-dot--degraded" : 
              "status-dot--error"
            }`} />
            <span className="sidebar__status-text">{status}</span>
            
            {healthData && healthData.checks && Object.keys(healthData.checks).length > 0 && (
              <div className="service-status-tooltip">
                {Object.entries(healthData.checks).map(([key, info]: [string, any]) => (
                  <div key={key} className="service-status-item">
                    <div className="service-status-item-left">
                      <div className={`status-dot ${info.ok ? "status-dot--ok" : "status-dot--error"}`} />
                      <span className="service-status-item-name">{key.replace('_', ' ')}</span>
                    </div>
                    <span className="service-status-item-meta">
                      {info.latency_ms ? `${info.latency_ms}ms` : info.message ? info.message : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* ── Main Content Area ── */}
      <section className="main-content flex flex-col h-full relative" style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        
        {/* ── Top Header ── */}
        <header className="top-header">
          <StockSearch 
            onSelect={(symbol, name) => {
              setActiveTab('chat');
              handlePreFillChat(`Analyze ${name} (${symbol}), including recent news and financial health.`);
            }}
          />
          <div className="header-actions">
            <button 
              className="portfolio-toggle-btn" 
              onClick={() => setIsPortfolioOpen(!isPortfolioOpen)}
            >
              Portfolio ({portfolio?.total_holdings ?? 0})
            </button>
            <div className="user-profile">
              <div className="user-profile__info">
                <span className="user-profile__name">Trader</span>
                <span className="user-profile__email">Pro Member</span>
              </div>
              <div className="user-profile__avatar">
                <UserIcon />
              </div>
            </div>
          </div>
        </header>

        {activeTab === 'portfolio' ? (
          <PortfolioZone />
        ) : activeTab === 'research' ? (
          <ResearchLayout />
        ) : activeTab === 'settings' ? (
          <SettingsZone />
        ) : activeTab === 'library' ? (
          <LibraryZone />
        ) : (
          <>
            <div className="message-list" aria-live="polite" style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
              {messages.map((msg) => {
                if (msg.role === "user") {
                  return (
                    <div key={msg.id} className="turn turn--user">
                      <div className="turn-avatar turn-avatar--user">
                        <User size={18} />
                      </div>
                      <div className="turn-content-wrapper">
                        <div className="turn-content">
                          <Markdown content={msg.content ?? ""} />
                        </div>
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
                      <div className="turn-avatar turn-avatar--error">
                        <Sparkles size={18} />
                      </div>
                      <div className="turn-content-wrapper">
                        <div className="error-bubble">
                          <span className="error-bubble__icon">⚠</span>
                          {msg.content}
                        </div>
                        <div className="end-of-message-indicator" />
                      </div>
                    </div>
                  );
                }
                // assistant
                return (
                  <div key={msg.id} className="turn turn--assistant">
                    <div className="turn-avatar turn-avatar--assistant">
                      <Sparkles size={18} />
                    </div>
                    <div className="turn-content-wrapper">
                      <AssistantBlocks blocks={msg.blocks ?? []} />
                      <div className="end-of-message-indicator" />
                    </div>
                  </div>
                );
              })}

              {/* Streaming draft */}
              {draftBlocks.length > 0 && (
                <div className="turn turn--assistant">
                  <div className="turn-avatar turn-avatar--assistant">
                    <Sparkles size={18} />
                  </div>
                  <div className="turn-content-wrapper">
                    <AssistantBlocks blocks={draftBlocks} isStreaming />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* ── Composer ── */}
            <div className="composer-wrap">
              <div style={{ display: 'flex', justifyContent: 'flex-start', padding: '0 16px 8px' }}>
                <select 
                  value={selectedModelId}
                  onChange={handleModelChange}
                  style={{
                    background: 'transparent',
                    border: '1px solid var(--border-light)',
                    borderRadius: '4px',
                    color: 'var(--text-light)',
                    fontSize: '12px',
                    padding: '2px 8px',
                    cursor: 'pointer',
                    outline: 'none'
                  }}
                >
                  <optgroup label="Google Gemini">
                    <option value="gemini:gemini-3.6-flash">Gemini 3.6 Flash</option>
                    <option value="gemini:gemini-3.5-flash-lite">Gemini 3.5 Flash Lite</option>
                  </optgroup>
                  <optgroup label="Ollama Cloud">
                    <option value="ollama_cloud:gemma4:31b-cloud">Gemma 4 31B (Cloud)</option>
                    <option value="ollama_cloud:nemotron-3-super:cloud">Nemotron 3 Super (Cloud)</option>
                  </optgroup>
                  <optgroup label="Groq">
                    <option value="groq:llama-3.3-70b-versatile">Groq (Llama 3.3 70B)</option>
                  </optgroup>
                  <optgroup label="Ollama Local">
                    <option value="ollama:qwen3.5:latest">Qwen 3.5 (Local)</option>
                  </optgroup>
                </select>
              </div>
            <form className="composer" onSubmit={sendMessage}>
              <div className="composer-input-wrapper">
                <div className="composer-overlay">
                  {renderOverlay(input)}
                  {input.endsWith('\n') ? <br /> : null}
                </div>
                <textarea
                  ref={textareaRef}
                  className="composer__input"
                  aria-label="Message"
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={isStreaming ? "Ask a new prompt to interrupt..." : "Ask PAISA about your portfolio..."}
                  rows={1}
                />
                
                {triggerState.activeTrigger && suggestions.length > 0 && (
                  <div className="suggestion-popup">
                    {suggestions.map((sugg, i) => (
                      <div 
                        key={sugg.id} 
                        className={`suggestion-item ${i === selectedIndex ? 'active' : ''}`}
                        onClick={() => insertMention(sugg)}
                      >
                        {sugg.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {isStreaming ? (
                <button
                  className="composer__send composer__send--stop"
                  type="button"
                  onClick={stopStreaming}
                  aria-label="Stop generating"
                  title="Stop generating (Esc)"
                >
                  <SquareIcon />
                </button>
              ) : (
                <button
                  className="composer__send"
                  disabled={!input.trim()}
                  type="submit"
                  aria-label="Send"
                  title="Send message"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"></line>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
                </button>
              )}
            </form>
          </div>
        </>
        )}
      </section>

      {/* ── Right Sidebar (Portfolio) ── */}
      <aside className="right-sidebar">
        <div className="right-sidebar__inner">
          <div className="right-sidebar__header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 className="right-sidebar__title">Your Holdings</h2>
              <button 
                className="refresh-btn" 
                onClick={refreshPrices} 
                disabled={isRefreshingPrices}
                aria-label="Refresh live prices"
                title="Refresh live prices"
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--text-tertiary)', display: 'flex', padding: '4px'
                }}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ animation: isRefreshingPrices ? 'spin 1s linear infinite' : 'none' }}>
                  <polyline points="23 4 23 10 17 10"></polyline>
                  <polyline points="1 20 1 14 7 14"></polyline>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
                </svg>
              </button>
            </div>
          <button className="right-sidebar__close" onClick={() => setIsPortfolioOpen(false)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        <div className="portfolio-list">
          {portfolio?.holdings.length ? (
            portfolio.holdings.map((h) => {
              // Note: Since we don't have real-time PnL per stock right now,
              // we can mock the UI elements or just show static info
              // For a real app, this logic would use `h.current_price` etc.
              return (
                <div key={h.id} className="portfolio-card">
                  <div className="portfolio-card__header">
                    <div>
                      <h3 className="portfolio-card__ticker">{h.canonical_ticker}</h3>
                      <p className="portfolio-card__name">{h.exchange} • {h.asset_class}</p>
                    </div>
                    {/* Live P&L Badge & Line Graph */}
                    {(() => {
                      const quote = livePrices[h.canonical_ticker];
                      if (!quote) return null;
                      if (quote.error) {
                        return <span className="portfolio-card__pnl portfolio-card__pnl--negative" title={quote.error}>⚠ Err</span>;
                      }
                      if (quote.price) {
                        const totalInvested = h.avg_cost * h.quantity;
                        const currentValue = quote.price * h.quantity;
                        const pnlAmount = currentValue - totalInvested;
                        const pnlPct = totalInvested > 0 ? (pnlAmount / totalInvested) * 100 : 0;
                        const isPositive = pnlPct >= 0;
                        const sign = isPositive ? "+" : "";
                        return (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {quote.sparkline && quote.sparkline.length > 1 && (
                              <Sparkline data={quote.sparkline} />
                            )}
                            <div className={`portfolio-card__pnl ${isPositive ? 'portfolio-card__pnl--positive' : 'portfolio-card__pnl--negative'}`}>
                              {sign}{pnlPct.toFixed(2)}%
                            </div>
                          </div>
                        );
                      }
                      return null;
                    })()}
                  </div>
                  <div className="portfolio-card__metrics">
                    <div className="portfolio-card__metric">
                      <span className="portfolio-card__metric-label">Shares</span>
                      <span className="portfolio-card__metric-value">{formatNumber(h.quantity)}</span>
                    </div>
                    <div className="portfolio-card__metric" style={{alignItems: 'flex-end'}}>
                      <span className="portfolio-card__metric-label">Avg Cost</span>
                      <span className="portfolio-card__metric-value">₹{formatNumber(h.avg_cost)}</span>
                    </div>
                  </div>
                  {/* Total Value Row if live price exists */}
                  {livePrices[h.canonical_ticker] && !livePrices[h.canonical_ticker].error && (
                    <div className="portfolio-card__metrics" style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--border-color)'}}>
                      <div className="portfolio-card__metric">
                        <span className="portfolio-card__metric-label">Live Price</span>
                        <span className="portfolio-card__metric-value">₹{formatNumber(livePrices[h.canonical_ticker].price)}</span>
                      </div>
                      <div className="portfolio-card__metric" style={{alignItems: 'flex-end'}}>
                        <span className="portfolio-card__metric-label">Total P&L</span>
                        <span className="portfolio-card__metric-value" style={{
                           color: (livePrices[h.canonical_ticker].price * h.quantity - h.avg_cost * h.quantity) >= 0 ? 'var(--green)' : 'var(--red)'
                        }}>
                          ₹{formatNumber(livePrices[h.canonical_ticker].price * h.quantity - h.avg_cost * h.quantity)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="empty-state">
              No holdings available. Upload your tradebook to see your portfolio cards.
            </div>
          )}
          </div>
        </div>
      </aside>

    </div>
  );
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value);
}

function formatUpdatedDate(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleString("en-IN", { 
      day: "numeric", month: "short", hour: "numeric", minute: "2-digit" 
    });
  } catch {
    return "";
  }
}

function Sparkline({ data, isPositive: customIsPositive, width = 64, height = 24 }: { data: number[]; isPositive?: boolean; width?: number; height?: number }) {
  if (!data || data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = 2;
  const effHeight = height - padding * 2;

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - padding - ((val - min) / range) * effHeight;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const isPositive = customIsPositive !== undefined ? customIsPositive : data[data.length - 1] >= data[0];
  const strokeColor = isPositive ? "var(--green)" : "var(--red)";

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: "visible" }}>
      <polyline
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points.join(" ")}
      />
    </svg>
  );
}


