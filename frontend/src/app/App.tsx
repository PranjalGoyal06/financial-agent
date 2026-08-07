import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  BrainCircuit,
  ChevronRight,
  CircleDot,
  Download,
  FileText,
  FolderOpen,
  Gauge,
  History,
  LockKeyhole,
  MessageSquareText,
  Moon,
  PanelRightOpen,
  Pencil,
  Plus,
  RefreshCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Trash2,
  Upload,
  WalletCards,
  X,
} from "lucide-react";
import { ChatPanel } from "../features/chat";
import { downloadCsv, holdingsToCsv } from "../features/portfolio/exportCsv";
import type {
  ArtifactDetail,
  ArtifactSummary,
  Holding,
  PortfolioImportResponse,
  PortfolioValuation,
} from "../lib/types";

type SessionResponse = {
  session_id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
  message_count: number;
  metadata: Record<string, unknown>;
};

type ChatSessionsResponse = {
  sessions: SessionResponse[];
};

type HoldingsResponse = {
  holdings: Holding[];
};

type PortfolioValuationResponse = PortfolioValuation;

type ArtifactsResponse = {
  artifacts: ArtifactSummary[];
};

type ThemeMode = "light" | "dark";
type RouteId = "dashboard" | "portfolio" | "chat" | "proactive-research";

type PromptIntent = {
  id: number;
  text: string;
};

type AllocationRow = {
  label: string;
  value: number;
  weight: number;
};

type ChatSessionSummary = {
  id: string;
  title: string;
  group: "Today" | "Previous 7 Days" | "Older";
  metadata: string[];
  updatedAt: string;
  messageCount: number;
};

type HoldingDetailSelection = {
  holding: Holding;
};

type WelcomeMessageSource = {
  message: string;
  source: "briefing" | "fallback";
};

const ROUTE_PATHS: Record<RouteId, string> = {
  dashboard: "/",
  portfolio: "/portfolio",
  chat: "/chat",
  "proactive-research": "/proactive-research",
};

const NAV_ITEMS: Array<{ route: RouteId; label: string; icon: typeof Gauge }> = [
  { route: "dashboard", label: "Dashboard", icon: Gauge },
  { route: "portfolio", label: "Portfolio", icon: WalletCards },
  { route: "chat", label: "Chat", icon: MessageSquareText },
  { route: "proactive-research", label: "Proactive Research", icon: BrainCircuit },
];

const WELCOME_MESSAGES = [
  "Welcome back. Your portfolio overview is ready for review, with risk, exposure, and research context available from one workspace.",
  "Good to see you. Start with the portfolio summary, review current evidence, or ask the agent a follow-up question.",
  "Your finance workspace is ready. Import holdings, inspect concentration, and use the agent for advisory analysis before taking action.",
  "Welcome. The agent is prepared to help reason through holdings, risks, evidence, and next steps without executing trades.",
];

const ASSET_FILTERS = ["All", "Equity", "ETF", "Mutual Fund", "Debt", "Gold", "Other"];

function routeFromPath(pathname: string): RouteId {
  if (pathname.startsWith("/portfolio")) {
    return "portfolio";
  }
  if (pathname.startsWith("/chat")) {
    return "chat";
  }
  if (pathname.startsWith("/proactive-research")) {
    return "proactive-research";
  }
  return "dashboard";
}

function sessionIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/chat\/([^/]+)$/);
  return match?.[1] ? decodeURIComponent(match[1]) : null;
}

function chatPath(sessionId: string): string {
  return `/chat/${encodeURIComponent(sessionId)}`;
}

function sessionGroup(value: string): ChatSessionSummary["group"] {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Older";
  }

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfSessionDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const ageMs = startOfToday.getTime() - startOfSessionDay.getTime();

  if (ageMs <= 0) {
    return "Today";
  }
  if (ageMs <= 7 * 24 * 60 * 60 * 1000) {
    return "Previous 7 Days";
  }
  return "Older";
}

function chatSessionSummary(session: SessionResponse): ChatSessionSummary {
  const timestamp = session.last_message_at || session.updated_at || session.created_at;
  const title = session.title?.trim() || "New chat";
  const metadata = [
    session.message_count ? `${session.message_count} msg${session.message_count === 1 ? "" : "s"}` : "empty",
    formatDateTime(timestamp),
  ];

  return {
    id: session.session_id,
    title,
    group: sessionGroup(timestamp),
    metadata,
    updatedAt: timestamp,
    messageCount: session.message_count,
  };
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
  }).format(value);
}

function formatCurrency(value: number, currency = "INR"): string {
  try {
    return new Intl.NumberFormat("en-IN", {
      currency,
      maximumFractionDigits: 0,
      style: "currency",
    }).format(value);
  } catch {
    return `${currency || "INR"} ${formatNumber(value)}`;
  }
}

function formatSignedCurrency(value: number, currency = "INR"): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatCurrency(value, currency)}`;
}

function assetLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
  }).format(date);
}

function holdingCost(holding: Holding): number {
  return holding.quantity * holding.avg_buy_price;
}

function riskTone(score: number): "muted" | "good" | "watch" | "bad" {
  if (score === 0) {
    return "muted";
  }
  if (score < 4.2) {
    return "good";
  }
  if (score < 7) {
    return "watch";
  }
  return "bad";
}

function riskLabel(score: number): string {
  if (score === 0) {
    return "Awaiting portfolio";
  }
  if (score < 4.2) {
    return "Balanced";
  }
  if (score < 7) {
    return "Moderate";
  }
  return "Elevated";
}

function buildAllocation(holdings: Holding[], totalValue: number): AllocationRow[] {
  const byAsset = new Map<string, number>();

  for (const holding of holdings) {
    const label = assetLabel(holding.asset_class);
    byAsset.set(label, (byAsset.get(label) ?? 0) + holdingCost(holding));
  }

  return [...byAsset.entries()]
    .map(([label, value]) => ({
      label,
      value,
      weight: totalValue > 0 ? (value / totalValue) * 100 : 0,
    }))
    .sort((first, second) => second.value - first.value);
}

function estimateRiskScore(holdings: Holding[], allocation: AllocationRow[]): number {
  if (holdings.length === 0) {
    return 0;
  }

  const total = allocation.reduce((sum, item) => sum + item.value, 0);
  const largestHoldingWeight =
    holdings.reduce((maxWeight, holding) => {
      const value = holdingCost(holding);
      return total > 0 ? Math.max(maxWeight, (value / total) * 100) : maxWeight;
    }, 0) / 10;
  const largestAssetWeight = allocation[0]?.weight ? allocation[0].weight / 16 : 0;
  const diversificationOffset = Math.min(2.2, holdings.length / 8);

  return Math.min(9.4, Math.max(2.6, 4.7 + largestHoldingWeight + largestAssetWeight - diversificationOffset));
}

function isResearchLikeArtifact(artifact: ArtifactSummary): boolean {
  const text = `${artifact.title} ${artifact.filename} ${artifact.artifact_type}`.toLowerCase();
  return ["research", "brief", "briefing", "report", "analysis", "proactive"].some((term) =>
    text.includes(term),
  );
}

async function parseJsonError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    return payload.detail || fallback;
  } catch {
    return fallback;
  }
}

export function App() {
  const [activeRoute, setActiveRoute] = useState<RouteId>(() => routeFromPath(window.location.pathname));
  const [sessionId, setSessionId] = useState<string | null>(() => sessionIdFromPath(window.location.pathname));
  const [chatSessions, setChatSessions] = useState<SessionResponse[]>([]);
  const [isChatSessionsLoading, setIsChatSessionsLoading] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [portfolioValuation, setPortfolioValuation] = useState<PortfolioValuation | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactSummary[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactDetail | null>(null);
  const [selectedHolding, setSelectedHolding] = useState<HoldingDetailSelection | null>(null);
  const [portfolioFile, setPortfolioFile] = useState<File | null>(null);
  const [artifactFile, setArtifactFile] = useState<File | null>(null);
  const [portfolioStatus, setPortfolioStatus] = useState<string | null>(null);
  const [artifactStatus, setArtifactStatus] = useState<string | null>(null);
  const [portfolioError, setPortfolioError] = useState<string | null>(null);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [isPortfolioUploading, setIsPortfolioUploading] = useState(false);
  const [isArtifactUploading, setIsArtifactUploading] = useState(false);
  const [chatPrompt, setChatPrompt] = useState<PromptIntent | null>(null);
  const [portfolioQuery, setPortfolioQuery] = useState("");
  const [assetFilter, setAssetFilter] = useState("All");
  const [chatSessionQuery, setChatSessionQuery] = useState("");
  const [fallbackWelcome] = useState(() => WELCOME_MESSAGES[Math.floor(Math.random() * WELCOME_MESSAGES.length)]);
  const [theme, setTheme] = useState<ThemeMode>(() => {
    const storedTheme = localStorage.getItem("paisa-theme");
    if (storedTheme === "light" || storedTheme === "dark") {
      return storedTheme;
    }
    return "dark";
  });

  const portfolioValue = useMemo(
    () => holdings.reduce((sum, holding) => sum + holdingCost(holding), 0),
    [holdings],
  );
  const allocation = useMemo(() => buildAllocation(holdings, portfolioValue), [holdings, portfolioValue]);
  const riskScore = useMemo(() => estimateRiskScore(holdings, allocation), [holdings, allocation]);
  const topHoldings = useMemo(
    () => [...holdings].sort((first, second) => holdingCost(second) - holdingCost(first)).slice(0, 7),
    [holdings],
  );
  const filteredHoldings = useMemo(() => {
    const normalisedQuery = portfolioQuery.trim().toLowerCase();
    return holdings.filter((holding) => {
      const matchesFilter = assetFilter === "All" || assetLabel(holding.asset_class) === assetFilter;
      const searchText = `${holding.raw_ticker} ${holding.canonical_ticker} ${holding.exchange} ${assetLabel(
        holding.asset_class,
      )}`.toLowerCase();
      return matchesFilter && (!normalisedQuery || searchText.includes(normalisedQuery));
    });
  }, [assetFilter, holdings, portfolioQuery]);
  const holdingCount = holdings.length;
  const portfolioCurrency = portfolioValuation?.currency || holdings[0]?.currency || "INR";
  const hasCurrentValuation = portfolioValuation?.current_value !== null && portfolioValuation?.current_value !== undefined;
  const hasTodayPnl = portfolioValuation?.today_pnl !== null && portfolioValuation?.today_pnl !== undefined;
  const valuationCoverage =
    portfolioValuation && holdingCount
      ? `${portfolioValuation.priced_holdings}/${holdingCount} holdings priced${
          portfolioValuation.is_stale ? " from cache" : ""
        }`
      : "Quotes load after import";
  const importSchema = "ticker, exchange, asset_class, quantity, avg_buy_price, currency, purchase_date";
  const latestImportDate = holdings
    .map((holding) => holding.created_at)
    .filter(Boolean)
    .sort()
    .at(-1);
  const dominantAllocation = allocation[0];
  const riskToneName = riskTone(riskScore);
  const welcomeMessage: WelcomeMessageSource = useMemo(() => {
    const briefing = artifacts.find(isResearchLikeArtifact);
    if (!briefing) {
      return { message: fallbackWelcome, source: "fallback" };
    }
    return {
      message: `${briefing.title}: ${briefing.preview || "A recent research briefing is available for review."}`,
      source: "briefing",
    };
  }, [artifacts, fallbackWelcome]);
  const filteredChatSessions = useMemo(() => {
    const query = chatSessionQuery.trim().toLowerCase();
    return chatSessions
      .map(chatSessionSummary)
      .filter((session) => !query || session.title.toLowerCase().includes(query));
  }, [chatSessionQuery, chatSessions]);
  const activeChatSummary = useMemo(() => {
    const activeSession = chatSessions.find((session) => session.session_id === sessionId);
    return activeSession ? chatSessionSummary(activeSession) : null;
  }, [chatSessions, sessionId]);

  const loadChatSessions = useCallback(async () => {
    const response = await fetch("/api/v1/chat/sessions");
    if (!response.ok) {
      throw new Error(`Failed to load chat sessions (${response.status})`);
    }
    const payload = (await response.json()) as ChatSessionsResponse;
    setChatSessions(payload.sessions);
    return payload.sessions;
  }, []);

  const createChatSession = useCallback(
    async (openInChat = true) => {
      const response = await fetch("/api/v1/chat/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "New chat" }),
      });

      if (!response.ok) {
        throw new Error(`Session creation failed (${response.status})`);
      }

      const payload = (await response.json()) as SessionResponse;
      setChatSessions((current) => [
        payload,
        ...current.filter((session) => session.session_id !== payload.session_id),
      ]);
      setSessionId(payload.session_id);
      setSessionError(null);

      if (openInChat) {
        window.history.pushState({}, "", chatPath(payload.session_id));
        setActiveRoute("chat");
      }

      return payload;
    },
    [],
  );

  useEffect(() => {
    function syncRoute() {
      const route = routeFromPath(window.location.pathname);
      setActiveRoute(route);
      if (route === "chat") {
        const routedSessionId = sessionIdFromPath(window.location.pathname);
        if (routedSessionId) {
          setSessionId(routedSessionId);
        }
      }
    }

    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function initialiseChatSessions() {
      setIsChatSessionsLoading(true);
      try {
        const sessions = await loadChatSessions();
        if (cancelled) {
          return;
        }

        const routedSessionId = sessionIdFromPath(window.location.pathname);
        if (routedSessionId) {
          setSessionId(routedSessionId);
          setSessionError(null);
          return;
        }

        if (sessions.length > 0) {
          setSessionId((current) => current || sessions[0].session_id);
          setSessionError(null);
          return;
        }

        await createChatSession(routeFromPath(window.location.pathname) === "chat");
      } catch (error) {
        if (!cancelled) {
          setSessionError(error instanceof Error ? error.message : "Session creation failed");
        }
      } finally {
        if (!cancelled) {
          setIsChatSessionsLoading(false);
        }
      }
    }

    void initialiseChatSessions();

    return () => {
      cancelled = true;
    };
  }, [createChatSession, loadChatSessions]);

  useEffect(() => {
    void loadHoldings();
    void loadArtifacts();
  }, []);

  useEffect(() => {
    localStorage.setItem("paisa-theme", theme);
  }, [theme]);

  function navigate(route: RouteId) {
    const path = route === "chat" && sessionId ? chatPath(sessionId) : ROUTE_PATHS[route];
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }
    setActiveRoute(route);
  }

  function openChatSession(nextSessionId: string) {
    setSessionId(nextSessionId);
    window.history.pushState({}, "", chatPath(nextSessionId));
    setActiveRoute("chat");
  }

  async function handleNewChat() {
    try {
      setSessionError(null);
      await createChatSession(true);
    } catch (error) {
      setSessionError(error instanceof Error ? error.message : "Session creation failed");
    }
  }

  async function handleRenameChat(targetSession: ChatSessionSummary) {
    const title = window.prompt("Rename chat", targetSession.title)?.trim();
    if (!title || title === targetSession.title) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/chat/sessions/${targetSession.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });

      if (!response.ok) {
        throw new Error(`Rename failed (${response.status})`);
      }

      const updated = (await response.json()) as SessionResponse;
      setChatSessions((current) =>
        current.map((session) => (session.session_id === updated.session_id ? updated : session)),
      );
    } catch (error) {
      setSessionError(error instanceof Error ? error.message : "Rename failed");
    }
  }

  async function handleDeleteChat(targetSession: ChatSessionSummary) {
    const confirmed = window.confirm(`Delete "${targetSession.title}"?`);
    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/chat/sessions/${targetSession.id}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error(`Delete failed (${response.status})`);
      }

      const remaining = chatSessions.filter((session) => session.session_id !== targetSession.id);
      setChatSessions(remaining);

      if (sessionId === targetSession.id) {
        const nextSession = remaining[0] ?? (await createChatSession(false));
        openChatSession(nextSession.session_id);
      }
    } catch (error) {
      setSessionError(error instanceof Error ? error.message : "Delete failed");
    }
  }

  async function loadHoldings() {
    setPortfolioError(null);
    try {
      const [holdingsResponse, valuationResponse] = await Promise.all([
        fetch("/api/v1/portfolio/holdings"),
        fetch("/api/v1/portfolio/valuation"),
      ]);

      if (!holdingsResponse.ok) {
        setPortfolioError(`Failed to load holdings (${holdingsResponse.status})`);
        return;
      }
      const payload = (await holdingsResponse.json()) as HoldingsResponse;
      setHoldings(payload.holdings);

      if (valuationResponse.ok) {
        setPortfolioValuation((await valuationResponse.json()) as PortfolioValuationResponse);
      } else {
        setPortfolioValuation(null);
        setPortfolioError(`Failed to load valuation (${valuationResponse.status})`);
      }
    } catch (error) {
      setPortfolioValuation(null);
      setPortfolioError(error instanceof Error ? error.message : "Failed to load holdings");
    }
  }

  async function loadArtifacts() {
    setArtifactError(null);
    try {
      const response = await fetch("/api/v1/artifacts");
      if (!response.ok) {
        setArtifactError(`Failed to load artifacts (${response.status})`);
        return;
      }
      const payload = (await response.json()) as ArtifactsResponse;
      setArtifacts(payload.artifacts);
    } catch (error) {
      setArtifactError(error instanceof Error ? error.message : "Failed to load artifacts");
    }
  }

  async function handlePortfolioUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!portfolioFile) {
      setPortfolioError("Choose a portfolio CSV before uploading.");
      return;
    }

    const form = new FormData();
    form.append("file", portfolioFile);
    setIsPortfolioUploading(true);
    setPortfolioError(null);
    setPortfolioStatus(null);

    try {
      const response = await fetch("/api/v1/portfolio/imports", {
        method: "POST",
        body: form,
      });

      if (!response.ok) {
        throw new Error(await parseJsonError(response, `Import failed (${response.status})`));
      }

      const payload = (await response.json()) as PortfolioImportResponse;
      await loadHoldings();
      setPortfolioStatus(
        `${payload.imported} holding${payload.imported === 1 ? "" : "s"} imported` +
          (payload.rejected.length ? `, ${payload.rejected.length} rejected` : ""),
      );
    } catch (error) {
      setPortfolioError(error instanceof Error ? error.message : "Portfolio import failed");
    } finally {
      setIsPortfolioUploading(false);
    }
  }

  async function handleArtifactUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!artifactFile) {
      setArtifactError("Choose a .txt or .md file before uploading.");
      return;
    }

    const form = new FormData();
    form.append("file", artifactFile);
    setIsArtifactUploading(true);
    setArtifactError(null);
    setArtifactStatus(null);

    try {
      const response = await fetch("/api/v1/artifacts", {
        method: "POST",
        body: form,
      });

      if (!response.ok) {
        throw new Error(await parseJsonError(response, `Upload failed (${response.status})`));
      }

      const detail = (await response.json()) as ArtifactDetail;
      await loadArtifacts();
      setSelectedArtifact(detail);
      setArtifactStatus(`${detail.filename} uploaded`);
    } catch (error) {
      setArtifactError(error instanceof Error ? error.message : "Artifact upload failed");
    } finally {
      setIsArtifactUploading(false);
    }
  }

  async function openArtifact(artifactId: string) {
    setArtifactError(null);
    const response = await fetch(`/api/v1/artifacts/${artifactId}`);
    if (!response.ok) {
      setArtifactError(await parseJsonError(response, `Artifact load failed (${response.status})`));
      return;
    }
    setSelectedArtifact((await response.json()) as ArtifactDetail);
  }

  function handleExportHoldings() {
    if (!holdings.length) {
      setPortfolioError("Import holdings before exporting a CSV.");
      return;
    }

    downloadCsv("portfolio-holdings.csv", holdingsToCsv(holdings));
  }

  function sendPrompt(text: string, route: RouteId = activeRoute) {
    setChatPrompt({ id: Date.now(), text });
    if (route === "chat") {
      navigate("chat");
    }
  }

  function renderChatPanel(className?: string) {
    if (sessionError) {
      return <div className="app-error">{sessionError}</div>;
    }
    if (!sessionId || isChatSessionsLoading) {
      return <div className="app-loading">Loading chat sessions...</div>;
    }
    return (
      <ChatPanel
        className={className}
        sessionId={sessionId}
        suggestedPrompt={chatPrompt}
        onMessageSent={async () => {
          await loadChatSessions();
        }}
      />
    );
  }

  function renderUploadPanel(compact = false) {
    return (
      <section className={compact ? "import-panel import-panel--compact" : "import-panel"} aria-label="Portfolio import">
        <form className="upload-strip" onSubmit={handlePortfolioUpload}>
          <label>
            <span>Portfolio CSV</span>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => setPortfolioFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button type="submit" disabled={isPortfolioUploading}>
            <Upload size={16} aria-hidden="true" />
            {isPortfolioUploading ? "Uploading" : "Import"}
          </button>
        </form>
        <p className="schema-note">{importSchema}</p>
        {portfolioStatus ? <p className="status-line status-line--good">{portfolioStatus}</p> : null}
        {portfolioError ? <p className="status-line status-line--bad">{portfolioError}</p> : null}
      </section>
    );
  }

  function renderDashboard() {
    return (
      <>
        <section className="dashboard-hero" aria-label="Portfolio summary">
          <div className="hero-copy">
            <p className="eyebrow">{welcomeMessage.source === "briefing" ? "Latest briefing" : "Welcome"}</p>
            <h1>{welcomeMessage.message}</h1>
          </div>

          <div className="hero-metrics">
            <article className="metric-tile metric-tile--anchor">
              <span>Total portfolio cost</span>
              <strong>{formatCurrency(portfolioValue)}</strong>
              <small>{holdingCount ? `${holdingCount} holdings imported` : "Import CSV to begin"}</small>
            </article>
            <article className="metric-tile">
              <span>Current value</span>
              <strong>
                {hasCurrentValuation
                  ? formatCurrency(portfolioValuation?.current_value ?? 0, portfolioCurrency)
                  : holdingCount
                    ? "Quote unavailable"
                    : "Import CSV"}
              </strong>
              <small>{holdingCount ? valuationCoverage : "Upload holdings to request market quotes"}</small>
            </article>
            <article className="metric-tile">
              <span>Today&apos;s P&L</span>
              <strong>
                {hasTodayPnl
                  ? formatSignedCurrency(portfolioValuation?.today_pnl ?? 0, portfolioCurrency)
                  : holdingCount
                    ? "Quote unavailable"
                    : "Import CSV"}
              </strong>
              <small>{hasTodayPnl ? "Based on latest quote change" : "Daily quote change unavailable"}</small>
            </article>
            <article className={`metric-tile metric-tile--${riskToneName}`}>
              <span>Portfolio risk score</span>
              <strong>{riskScore ? `${riskScore.toFixed(1)} / 10` : "Pending"}</strong>
              <small>{riskLabel(riskScore)}</small>
            </article>
          </div>
        </section>

        <section className="dashboard-grid" aria-label="Dashboard zones">
          <section className="portfolio-zone" aria-labelledby="portfolio-zone-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Zone 1</p>
                <h2 id="portfolio-zone-title">Portfolio reality</h2>
              </div>
              <div className="heading-actions">
                <button className="quiet-button" type="button" onClick={() => void loadHoldings()}>
                  <RefreshCcw size={16} aria-hidden="true" />
                  Refresh holdings
                </button>
                <button className="quiet-button" type="button" onClick={() => navigate("portfolio")}>
                  <PanelRightOpen size={16} aria-hidden="true" />
                  View all holdings
                </button>
              </div>
            </div>

            <div className="portfolio-layout">
              {renderUploadPanel(true)}

              <section className="exposure-panel" aria-label="Allocation">
                <div className="panel-title-row">
                  <h3>Exposure map</h3>
                  <span>{dominantAllocation ? `${dominantAllocation.label} leads` : "Awaiting holdings"}</span>
                </div>
                {allocation.length ? (
                  <div className="allocation-list">
                    {allocation.map((item) => (
                      <div className="allocation-row" key={item.label}>
                        <div>
                          <span>{item.label}</span>
                          <strong>{formatCurrency(item.value)}</strong>
                        </div>
                        <div className="allocation-track" aria-hidden="true">
                          <span style={{ width: `${Math.max(4, item.weight)}%` }} />
                        </div>
                        <small>{item.weight.toFixed(1)}%</small>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state empty-state--compact">
                    <FolderOpen size={22} aria-hidden="true" />
                    <p>Import holdings to see allocation by asset class.</p>
                  </div>
                )}
              </section>
            </div>

            <section className="holdings-panel" aria-label="Top holdings">
              <div className="panel-title-row">
                <h3>Top holdings by imported cost</h3>
                <button
                  className="link-button"
                  type="button"
                  onClick={() => sendPrompt("Analyse concentration risk across my top holdings.", "chat")}
                >
                  Ask about concentration
                  <ChevronRight size={14} aria-hidden="true" />
                </button>
              </div>

              {topHoldings.length ? (
                <div className="holdings-table-wrap">
                  <table className="holdings-table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Asset</th>
                        <th>Qty</th>
                        <th>Avg buy</th>
                        <th>Invested amount</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {topHoldings.map((holding) => {
                        const value = holdingCost(holding);
                        const weight = portfolioValue > 0 ? (value / portfolioValue) * 100 : 0;
                        return (
                          <tr
                            key={holding.holding_id}
                            onClick={() => setSelectedHolding({ holding })}
                          >
                            <td>
                              <strong>{holding.raw_ticker}</strong>
                              <small>{holding.exchange}</small>
                            </td>
                            <td>{assetLabel(holding.asset_class)}</td>
                            <td>{formatNumber(holding.quantity)}</td>
                            <td>{formatCurrency(holding.avg_buy_price, holding.currency || "INR")}</td>
                            <td>
                              {formatCurrency(value, holding.currency || "INR")}
                              <small>{weight.toFixed(1)}% weight</small>
                            </td>
                            <td>
                              <span className="table-chip">Imported lot</span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="empty-state">
                  <FolderOpen size={24} aria-hidden="true" />
                  <h3>No portfolio uploaded</h3>
                  <p>Upload a CSV with holdings to generate portfolio analysis.</p>
                </div>
              )}
            </section>
          </section>

          <section className="intelligence-zone" aria-labelledby="intelligence-zone-title">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Zone 2</p>
                <h2 id="intelligence-zone-title">Intelligence briefing</h2>
              </div>
            </div>

            <article className="briefing-panel">
              <div className="briefing-header">
                <BrainCircuit size={18} aria-hidden="true" />
                <div>
                  <h3>Latest research briefing</h3>
                  <p>Proactive Research turns portfolio context, evidence, and risk checks into reusable reports.</p>
                </div>
              </div>
              <div className="briefing-list">
                <button
                  type="button"
                  onClick={() => sendPrompt("Analyse my portfolio risk and list the evidence behind each concern.", "chat")}
                >
                  <AlertTriangle size={16} aria-hidden="true" />
                  <span>
                    <strong>{dominantAllocation ? `${dominantAllocation.label} concentration` : "Portfolio not imported"}</strong>
                    <small>
                      {dominantAllocation
                        ? `${dominantAllocation.weight.toFixed(1)}% of imported cost sits in one asset class.`
                        : "Risk analysis needs holdings before it can reason."}
                    </small>
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => sendPrompt("Which holdings need better evidence before I make a decision?", "chat")}
                >
                  <ShieldCheck size={16} aria-hidden="true" />
                  <span>
                    <strong>Evidence required</strong>
                    <small>Advisory outputs should cite sources and show confidence before action.</small>
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => sendPrompt("What should I do next without executing any trade?", "chat")}
                >
                  <LockKeyhole size={16} aria-hidden="true" />
                  <span>
                    <strong>No execution boundary</strong>
                    <small>The agent can explain, compare, and recommend. It cannot place trades.</small>
                  </span>
                </button>
              </div>
            </article>

            <article className="freshness-panel">
              <div className="panel-title-row">
                <h3>Data freshness</h3>
                <span className="status-chip status-chip--neutral">Transparent state</span>
              </div>
              <dl className="freshness-list">
                <div>
                  <dt>Portfolio</dt>
                  <dd>{latestImportDate ? `Imported ${formatDateTime(latestImportDate)}` : "No import yet"}</dd>
                </div>
                <div>
                  <dt>Quotes</dt>
                  <dd>Awaiting market data</dd>
                </div>
                <div>
                  <dt>News</dt>
                  <dd>Evidence retrieval available when research artefacts are present</dd>
                </div>
              </dl>
            </article>

            {renderArtifactsPanel()}
          </section>

          <aside className="chat-zone" aria-label="Portfolio chat">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Zone 3</p>
                <h2>Chat with Agent</h2>
              </div>
              <button className="icon-button" type="button" aria-label="Continue in Chat" onClick={() => navigate("chat")}>
                <PanelRightOpen size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="prompt-strip">
              {[
                "Analyse my portfolio risk.",
                "What evidence is missing?",
                "Compare my top two holdings.",
              ].map((prompt) => (
                <button key={prompt} type="button" onClick={() => sendPrompt(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>

            {renderChatPanel()}
          </aside>
        </section>
      </>
    );
  }

  function renderPortfolioPage() {
    return (
      <section className="page-shell portfolio-page" aria-labelledby="portfolio-page-title">
        <div className="page-header">
          <div>
            <p className="eyebrow">Portfolio</p>
            <h1 id="portfolio-page-title">Holdings dashboard</h1>
            <p>Review positions, inspect exposure, and open holding-level analysis.</p>
          </div>
          <div className="heading-actions">
            <button className="quiet-button" type="button" onClick={() => void loadHoldings()}>
              <RefreshCcw size={16} aria-hidden="true" />
              Refresh holdings
            </button>
            <button
              className="quiet-button"
              type="button"
              disabled={!holdings.length}
              onClick={handleExportHoldings}
            >
              <Download size={16} aria-hidden="true" />
              Export CSV
            </button>
            <button className="quiet-button" type="button" aria-label="Column settings">
              <SlidersHorizontal size={16} aria-hidden="true" />
              Columns
            </button>
          </div>
        </div>

        <section className="summary-strip" aria-label="Portfolio summary">
          <article>
            <span>Invested amount</span>
            <strong>{formatCurrency(portfolioValue)}</strong>
          </article>
          <article>
            <span>Current value</span>
            <strong>
              {hasCurrentValuation
                ? formatCurrency(portfolioValuation?.current_value ?? 0, portfolioCurrency)
                : holdingCount
                  ? "Quote unavailable"
                  : "No import yet"}
            </strong>
          </article>
          <article>
            <span>Unrealised P&L</span>
            <strong>
              {portfolioValuation?.unrealized_pnl !== null && portfolioValuation?.unrealized_pnl !== undefined
                ? formatSignedCurrency(portfolioValuation.unrealized_pnl, portfolioCurrency)
                : holdingCount
                  ? "Quote unavailable"
                  : "No import yet"}
            </strong>
          </article>
          <article>
            <span>Holdings</span>
            <strong>{holdingCount}</strong>
          </article>
          <article>
            <span>Last updated</span>
            <strong>{latestImportDate ? formatDateTime(latestImportDate) : "No import yet"}</strong>
          </article>
        </section>

        <div className="portfolio-toolbar">
          <label className="filter-search">
            <Search size={16} aria-hidden="true" />
            <input
              value={portfolioQuery}
              placeholder="Filter by ticker or exchange..."
              onChange={(event) => setPortfolioQuery(event.target.value)}
            />
          </label>
          <div className="filter-chips" aria-label="Asset class filters">
            {ASSET_FILTERS.map((filter) => (
              <button
                key={filter}
                className={assetFilter === filter ? "filter-chip filter-chip--active" : "filter-chip"}
                type="button"
                onClick={() => setAssetFilter(filter)}
              >
                {filter}
              </button>
            ))}
          </div>
        </div>

        {renderUploadPanel(true)}

        <section className="holdings-panel holdings-panel--full" aria-label="All holdings">
          {filteredHoldings.length ? (
            <div className="holdings-table-wrap">
              <table className="holdings-table holdings-table--full">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th>Exchange</th>
                    <th>Asset Class</th>
                    <th>Quantity</th>
                    <th>Average Buy</th>
                    <th>Invested Amount</th>
                    <th>Weight</th>
                    <th>AI Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredHoldings.map((holding) => {
                    const value = holdingCost(holding);
                    const weight = portfolioValue > 0 ? (value / portfolioValue) * 100 : 0;
                    return (
                      <tr key={holding.holding_id} onClick={() => setSelectedHolding({ holding })}>
                        <td>
                          <strong>{holding.raw_ticker}</strong>
                          <small>{holding.canonical_ticker}</small>
                        </td>
                        <td>{holding.exchange}</td>
                        <td>{assetLabel(holding.asset_class)}</td>
                        <td>{formatNumber(holding.quantity)}</td>
                        <td>{formatCurrency(holding.avg_buy_price, holding.currency || "INR")}</td>
                        <td>{formatCurrency(value, holding.currency || "INR")}</td>
                        <td>
                          <div className="weight-cell">
                            <span>{weight.toFixed(1)}%</span>
                            <div className="allocation-track" aria-hidden="true">
                              <span style={{ width: `${Math.max(4, weight)}%` }} />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="table-chip">Awaiting analysis</span>
                        </td>
                        <td>
                          <button
                            className="row-action"
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              sendPrompt(`Analyse ${holding.canonical_ticker} in the context of my portfolio.`, "chat");
                            }}
                          >
                            Analyse
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={5}>Total imported cost</td>
                    <td>{formatCurrency(portfolioValue)}</td>
                    <td>100%</td>
                    <td colSpan={2}>{holdingCount} holdings</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <FolderOpen size={24} aria-hidden="true" />
              <h3>No holdings found</h3>
              <p>Upload a CSV with your holdings to generate a portfolio dashboard and agent analysis.</p>
            </div>
          )}
        </section>

        <section className="allocation-grid" aria-label="Allocation charts">
          <article className="exposure-panel">
            <div className="panel-title-row">
              <h3>Asset allocation</h3>
              <span>{allocation.length} groups</span>
            </div>
            <div className="allocation-list">
              {allocation.map((item) => (
                <div className="allocation-row" key={item.label}>
                  <div>
                    <span>{item.label}</span>
                    <strong>{formatCurrency(item.value)}</strong>
                  </div>
                  <div className="allocation-track" aria-hidden="true">
                    <span style={{ width: `${Math.max(4, item.weight)}%` }} />
                  </div>
                  <small>{item.weight.toFixed(1)}%</small>
                </div>
              ))}
            </div>
          </article>
          <article className="exposure-panel">
            <div className="panel-title-row">
              <h3>Top holding weights</h3>
              <span>Imported cost basis</span>
            </div>
            <div className="allocation-list">
              {topHoldings.map((holding) => {
                const value = holdingCost(holding);
                const weight = portfolioValue > 0 ? (value / portfolioValue) * 100 : 0;
                return (
                  <div className="allocation-row" key={holding.holding_id}>
                    <div>
                      <span>{holding.raw_ticker}</span>
                      <strong>{formatCurrency(value, holding.currency || "INR")}</strong>
                    </div>
                    <div className="allocation-track" aria-hidden="true">
                      <span style={{ width: `${Math.max(4, weight)}%` }} />
                    </div>
                    <small>{weight.toFixed(1)}%</small>
                  </div>
                );
              })}
            </div>
          </article>
        </section>
      </section>
    );
  }

  function renderChatPage() {
    const groupedSessions = ["Today", "Previous 7 Days", "Older"].map((group) => ({
      group,
      sessions: filteredChatSessions.filter((session) => session.group === group),
    }));

    return (
      <section className="chat-page" aria-label="Full chat">
        <aside className="chat-session-sidebar" aria-label="Chat sessions">
          <button className="primary-action" type="button" onClick={() => void handleNewChat()}>
            <Plus size={16} aria-hidden="true" />
            New chat
          </button>
          <label className="filter-search">
            <Search size={16} aria-hidden="true" />
            <input
              value={chatSessionQuery}
              placeholder="Search chats..."
              onChange={(event) => setChatSessionQuery(event.target.value)}
            />
          </label>

          <div className="session-groups">
            {isChatSessionsLoading ? <div className="sidebar-empty">Loading chats...</div> : null}
            {groupedSessions.map(({ group, sessions }) => (
              <section key={group} className="session-group">
                <h2>{group}</h2>
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    className={session.id === sessionId ? "session-row session-row--active" : "session-row"}
                  >
                    <button type="button" onClick={() => openChatSession(session.id)}>
                      <strong>{session.title}</strong>
                      <span>
                        {session.metadata.map((item) => (
                          <small key={item}>{item}</small>
                        ))}
                      </span>
                    </button>
                    <div className="session-row__actions">
                      <button
                        type="button"
                        aria-label={`Rename ${session.title}`}
                        title="Rename chat"
                        onClick={() => void handleRenameChat(session)}
                      >
                        <Pencil size={14} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        aria-label={`Delete ${session.title}`}
                        title="Delete chat"
                        onClick={() => void handleDeleteChat(session)}
                      >
                        <Trash2 size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </div>
                ))}
                {!isChatSessionsLoading && sessions.length === 0 ? (
                  <div className="sidebar-empty sidebar-empty--compact">No chats here.</div>
                ) : null}
              </section>
            ))}
          </div>
        </aside>

        <section className="chat-main">
          <div className="page-header page-header--compact">
            <div>
              <p className="eyebrow">Chat</p>
              <h1>{activeChatSummary?.title || "Portfolio conversation"}</h1>
              <p>Ask about holdings, risks, news, evidence, or Proactive Research outputs.</p>
            </div>
            {sessionId ? (
              <div className="heading-actions">
                <button
                  className="quiet-button"
                  type="button"
                  onClick={() => {
                    if (activeChatSummary) {
                      void handleRenameChat(activeChatSummary);
                    }
                  }}
                >
                  <Pencil size={16} aria-hidden="true" />
                  Rename
                </button>
              </div>
            ) : null}
          </div>
          <div className="prompt-strip prompt-strip--large">
            {[
              "What is my biggest risk?",
              "Should I rebalance?",
              "Compare my top two holdings.",
              "Explain my sector exposure.",
              "Run downside analysis.",
            ].map((prompt) => (
              <button key={prompt} type="button" onClick={() => sendPrompt(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
          {renderChatPanel("chat-panel--full")}
        </section>
      </section>
    );
  }

  function renderProactiveResearchPage() {
    return (
      <section className="page-shell proactive-page" aria-labelledby="proactive-title">
        <div className="page-header">
          <div>
            <p className="eyebrow">Proactive Research</p>
            <h1 id="proactive-title">Proactive Agent workspace</h1>
            <p>
              Start portfolio-level or ticker-level research and save outputs as reusable reports for future analysis.
            </p>
          </div>
          <span className="status-chip status-chip--neutral">Service unavailable</span>
        </div>

        <section className="research-layout">
          <article className="research-launcher">
            <div className="briefing-header">
              <Sparkles size={18} aria-hidden="true" />
              <div>
                <h3>Proactive Research launcher</h3>
                <p>Analyse holdings, watchlist ideas, prior notes, and concentration risk.</p>
              </div>
            </div>
            <div className="segmented-list">
              <span>Full Portfolio</span>
              <span>Watchlist</span>
              <span>Specific Tickers</span>
              <span>Single Holding</span>
            </div>
            <div className="research-options">
              {[
                "Portfolio Review",
                "Watchlist Analysis",
                "Concentration Risk Review",
                "Downside Stress Test",
                "News Impact Review",
                "Fundamental Review",
              ].map((item) => (
                <button key={item} type="button">
                  {item}
                </button>
              ))}
            </div>
            <button className="primary-action" type="button" disabled>
              Start research
            </button>
          </article>

          <article className="research-timeline">
            <div className="panel-title-row">
              <h3>Research run status</h3>
              <span>Awaiting service</span>
            </div>
            {[
              "Create research run",
              "Load portfolio context",
              "Fetch market data",
              "Retrieve evidence",
              "Analyse holdings",
              "Create report",
              "Save artefact",
            ].map((step, index) => (
              <div className="timeline-step" key={step}>
                <span>{index + 1}</span>
                <p>{step}</p>
              </div>
            ))}
          </article>
        </section>

        <section className="artifacts-panel">
          <div className="panel-title-row">
            <h3>Saved research outputs</h3>
            <span>{artifacts.length} artefacts</span>
          </div>
          <div className="artifact-stack">
            {artifacts.length ? (
              artifacts.map((artifact) => (
                <button
                  key={artifact.artifact_id}
                  className="artifact-row"
                  type="button"
                  onClick={() => void openArtifact(artifact.artifact_id)}
                >
                  <FileText size={17} aria-hidden="true" />
                  <span>
                    <strong>{artifact.title}</strong>
                    <small>{artifact.preview || artifact.filename}</small>
                  </span>
                </button>
              ))
            ) : (
              <div className="empty-state empty-state--compact">
                <FileText size={22} aria-hidden="true" />
                <p>No research artefacts saved yet.</p>
              </div>
            )}
          </div>
        </section>
      </section>
    );
  }

  function renderArtifactsPanel() {
    return (
      <article className="artifacts-panel">
        <div className="panel-title-row">
          <h3>Research artefacts</h3>
          <span>{artifacts.length} saved</span>
        </div>

        <form className="artifact-upload" onSubmit={handleArtifactUpload}>
          <label>
            <span>Upload .txt or .md evidence</span>
            <input
              type="file"
              accept=".txt,.md,text/plain,text/markdown"
              onChange={(event) => setArtifactFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button type="submit" disabled={isArtifactUploading}>
            <Upload size={15} aria-hidden="true" />
            {isArtifactUploading ? "Uploading" : "Save"}
          </button>
        </form>
        {artifactStatus ? <p className="status-line status-line--good">{artifactStatus}</p> : null}
        {artifactError ? <p className="status-line status-line--bad">{artifactError}</p> : null}

        <div className="artifact-stack" aria-label="Uploaded artifacts">
          {artifacts.length ? (
            artifacts.slice(0, 4).map((artifact) => (
              <button
                key={artifact.artifact_id}
                className="artifact-row"
                type="button"
                onClick={() => void openArtifact(artifact.artifact_id)}
              >
                <FileText size={17} aria-hidden="true" />
                <span>
                  <strong>{artifact.title}</strong>
                  <small>{artifact.preview || artifact.filename}</small>
                </span>
              </button>
            ))
          ) : (
            <div className="empty-state empty-state--compact">
              <FileText size={22} aria-hidden="true" />
              <p>No research artefacts saved yet.</p>
            </div>
          )}
        </div>

        {selectedArtifact ? (
          <article className="artifact-preview">
            <p className="eyebrow">{selectedArtifact.artifact_type}</p>
            <h4>{selectedArtifact.title}</h4>
            <pre>{selectedArtifact.content}</pre>
          </article>
        ) : null}
      </article>
    );
  }

  function renderHoldingDrawer() {
    if (!selectedHolding) {
      return null;
    }

    const { holding } = selectedHolding;
    const invested = holdingCost(holding);
    const weight = portfolioValue > 0 ? (invested / portfolioValue) * 100 : 0;

    return (
      <aside className="holding-drawer" aria-label="Holding details">
        <div className="drawer-header">
          <div>
            <p className="eyebrow">{holding.exchange}</p>
            <h2>{holding.raw_ticker}</h2>
            <span>{holding.canonical_ticker}</span>
          </div>
          <button className="icon-button" type="button" aria-label="Close details" onClick={() => setSelectedHolding(null)}>
            <X size={17} aria-hidden="true" />
          </button>
        </div>

        <section className="drawer-section">
          <h3>Your position</h3>
          <dl className="detail-grid">
            <div>
              <dt>Quantity</dt>
              <dd>{formatNumber(holding.quantity)}</dd>
            </div>
            <div>
              <dt>Average buy</dt>
              <dd>{formatCurrency(holding.avg_buy_price, holding.currency || "INR")}</dd>
            </div>
            <div>
              <dt>Invested amount</dt>
              <dd>{formatCurrency(invested, holding.currency || "INR")}</dd>
            </div>
            <div>
              <dt>Portfolio weight</dt>
              <dd>{weight.toFixed(1)}%</dd>
            </div>
          </dl>
        </section>

        <section className="drawer-section">
          <h3>AI view</h3>
          <p>Awaiting holding-level analysis. Ask the agent to generate a risk-first view with evidence.</p>
          <div className="prompt-strip">
            {[
              `Should I add more ${holding.raw_ticker}?`,
              `What is the bear case for ${holding.raw_ticker}?`,
              `Compare ${holding.raw_ticker} with sector peers.`,
              `What would change the recommendation for ${holding.raw_ticker}?`,
            ].map((prompt) => (
              <button key={prompt} type="button" onClick={() => sendPrompt(prompt, "chat")}>
                {prompt}
              </button>
            ))}
          </div>
        </section>

        <section className="drawer-section">
          <h3>Evidence</h3>
          <p>
            Market quotes, news, and uploaded research artefacts will be cited when available. Current position data comes
            from the imported portfolio lot.
          </p>
        </section>
      </aside>
    );
  }

  return (
    <main className="app-shell" data-theme={theme}>
      <aside className="sidebar" aria-label="Primary navigation">
        <button className="brand-lockup" type="button" onClick={() => navigate("dashboard")}>
          <div className="brand-mark" aria-hidden="true">
            P
          </div>
          <div>
            <strong>PAISA</strong>
            <span>AI Agent for Finance</span>
          </div>
        </button>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.route}
                className={activeRoute === item.route ? "nav-item nav-item--active" : "nav-item"}
                type="button"
                title={item.label}
                onClick={() => navigate(item.route)}
              >
                <Icon size={17} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <button className="research-cta" type="button" onClick={() => navigate("proactive-research")}>
          <BrainCircuit size={17} aria-hidden="true" />
          <span>Start Proactive Research</span>
        </button>
      </aside>

      <div className="app-frame">
        <header className="topbar">
          <div className="command-search" aria-label="Search placeholder">
            <Search size={16} aria-hidden="true" />
            <span>Search holdings, reports, evidence, or ask the agent...</span>
          </div>

          <div className="topbar-actions">
            <button className="status-chip status-chip--neutral" type="button">
              <CircleDot size={10} aria-hidden="true" />
              Market data awaiting refresh
            </button>
            <button className="status-chip status-chip--neutral" type="button">
              <Activity size={15} aria-hidden="true" />
              Agent service status unknown
            </button>
            <button className="icon-button" type="button" aria-label="Notifications">
              <Bell size={17} aria-hidden="true" />
            </button>
            <button
              className="icon-button"
              type="button"
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
            >
              {theme === "dark" ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
            </button>
          </div>
        </header>

        {activeRoute === "dashboard" ? renderDashboard() : null}
        {activeRoute === "portfolio" ? renderPortfolioPage() : null}
        {activeRoute === "chat" ? renderChatPage() : null}
        {activeRoute === "proactive-research" ? renderProactiveResearchPage() : null}

        <footer className="audit-footer">
          <span>
            <Activity size={14} aria-hidden="true" />
            Advisory only
          </span>
          <span>
            <History size={14} aria-hidden="true" />
            Recommendation history retained when backend support is available
          </span>
          <span>
            <ShieldCheck size={14} aria-hidden="true" />
            Human approval required for every investment action
          </span>
        </footer>
      </div>

      {renderHoldingDrawer()}
    </main>
  );
}
