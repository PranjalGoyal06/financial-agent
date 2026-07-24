import React, { useState } from "react";
import {
  TrendingUp,
  BarChart3,
  PieChart,
  Globe,
  Briefcase,
  Cpu,
  Terminal,
  ChevronDown,
  Check,
  Copy,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Code,
  FileText,
  Zap,
} from "lucide-react";

export type ToolCallBlock = {
  type: "tool_call";
  name: string;
  summary: string;
  input: Record<string, unknown>;
  output?: string;
  status: "running" | "done" | "failed";
};

// ── Tool Category Metadata ───────────────────────────────────────────────────

type ToolCategory = {
  icon: React.ElementType;
  title: string;
  themeClass: string;
};

function getToolCategory(name: string): ToolCategory {
  const cleanName = name.replace(/_tool$/, "").toLowerCase();

  if (cleanName.includes("quote")) {
    return { icon: TrendingUp, title: "Market Quote", themeClass: "tool-theme--quote" };
  }
  if (cleanName.includes("historical") || cleanName.includes("chart")) {
    return { icon: BarChart3, title: "Historical Data", themeClass: "tool-theme--historical" };
  }
  if (
    cleanName.includes("fundamental") ||
    cleanName.includes("ratio") ||
    cleanName.includes("metric")
  ) {
    return { icon: PieChart, title: "Fundamentals", themeClass: "tool-theme--fundamentals" };
  }
  if (cleanName.includes("search") || cleanName.includes("web") || cleanName.includes("news")) {
    return { icon: Globe, title: "Web Search", themeClass: "tool-theme--search" };
  }
  if (cleanName.includes("portfolio") || cleanName.includes("holding")) {
    return { icon: Briefcase, title: "Portfolio", themeClass: "tool-theme--portfolio" };
  }
  if (cleanName.includes("analysis") || cleanName.includes("ta")) {
    return { icon: Cpu, title: "Analysis", themeClass: "tool-theme--analysis" };
  }

  const formattedLabel = cleanName
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

  return { icon: Terminal, title: formattedLabel, themeClass: "tool-theme--default" };
}

// ── Summary Parser ────────────────────────────────────────────────────────────

interface ParsedSummary {
  ticker?: string;
  tag?: string;
  value?: string;
  change?: { text: string; isPositive: boolean; isNegative: boolean };
  pills?: Array<{ label: string; value: string }>;
  rawText?: string;
}

function parseSummary(summary: string): ParsedSummary | null {
  if (!summary || !summary.trim()) return null;

  // 1. Try JSON parse
  try {
    const data = JSON.parse(summary);
    if (typeof data === "object" && data !== null) {
      const pills: Array<{ label: string; value: string }> = [];
      const ticker = data.ticker || data.symbol || data.canonical_ticker;

      if (data.pe_ratio !== undefined)
        pills.push({ label: "P/E", value: Number(data.pe_ratio).toFixed(1) });
      if (data.pb_ratio !== undefined)
        pills.push({ label: "P/B", value: Number(data.pb_ratio).toFixed(1) });
      if (data.peg_ratio !== undefined)
        pills.push({ label: "PEG", value: Number(data.peg_ratio).toFixed(1) });
      if (data.ps_ratio !== undefined)
        pills.push({ label: "P/S", value: Number(data.ps_ratio).toFixed(1) });
      if (data.exchange) pills.push({ label: "Exch", value: String(data.exchange) });

      if (pills.length > 0 || ticker) {
        return { ticker: ticker ? String(ticker) : undefined, pills };
      }
    }
  } catch {
    // Not JSON
  }

  // 2. Match Quote format: "RELIANCE.NS: ₹1,272.20 (-1.27%)"
  const quoteMatch = summary.match(
    /^([A-Z0-9.]+):\s*([^(\n]+)(?:\(([-+]?\d+(?:\.\d+)?%?)\))?/i
  );
  if (quoteMatch) {
    const [, ticker, valStr, chgStr] = quoteMatch;
    let changeObj;
    if (chgStr) {
      const isNeg = chgStr.includes("-");
      const isPos = chgStr.includes("+") || (!isNeg && parseFloat(chgStr) > 0);
      changeObj = { text: chgStr, isPositive: isPos, isNegative: isNeg };
    }
    return {
      ticker: ticker.trim(),
      value: valStr.trim(),
      change: changeObj,
    };
  }

  // 3. Match Historical format: "RELIANCE.NS (1y): -10.01%"
  const histMatch = summary.match(
    /^([A-Z0-9.]+)\s*\(([^)]+)\):\s*([-+]?\d+(?:\.\d+)?%?)/i
  );
  if (histMatch) {
    const [, ticker, tag, chgStr] = histMatch;
    const isNeg = chgStr.includes("-");
    const isPos = chgStr.includes("+") || (!isNeg && parseFloat(chgStr) > 0);
    return {
      ticker: ticker.trim(),
      tag: tag.trim(),
      change: { text: chgStr.trim(), isPositive: isPos, isNegative: isNeg },
    };
  }

  return { rawText: summary };
}

function formatJson(raw: unknown): string {
  if (typeof raw === "string") {
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
      return raw;
    }
  }
  return JSON.stringify(raw, null, 2);
}

// ── Single Tool Card Component ────────────────────────────────────────────────

export function ToolCallCard({ block }: { block: ToolCallBlock }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<"request" | "response">("response");
  const [copiedTab, setCopiedTab] = useState<"request" | "response" | null>(null);

  const { icon: CategoryIcon, title, themeClass } = getToolCategory(block.name);
  const parsedSummary = parseSummary(block.summary);

  const isRunning = block.status === "running";
  const isFailed = block.status === "failed";

  const handleCopy = (e: React.MouseEvent, type: "request" | "response") => {
    e.stopPropagation();
    const content =
      type === "request"
        ? formatJson(block.input)
        : formatJson(block.output ?? "");
    navigator.clipboard.writeText(content);
    setCopiedTab(type);
    setTimeout(() => setCopiedTab(null), 2000);
  };

  return (
    <div
      className={`tool-card ${themeClass} ${isRunning ? "tool-card--running" : ""} ${
        isFailed ? "tool-card--failed" : ""
      } ${isOpen ? "tool-card--expanded" : ""}`}
    >
      {/* Header Summary Row */}
      <button
        type="button"
        className="tool-card__header"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <div className="tool-card__header-left">
          <div className="tool-card__icon-badge">
            {isRunning ? (
              <Loader2 className="tool-card__spinner" size={14} />
            ) : (
              <CategoryIcon size={14} />
            )}
          </div>

          <div className="tool-card__meta">
            <span className="tool-card__title">{title}</span>

            {/* Smart Summary Badges */}
            {!isRunning && parsedSummary && (
              <div className="tool-card__summary-pills">
                {parsedSummary.ticker && (
                  <span className="tool-pill tool-pill--ticker">
                    {parsedSummary.ticker}
                  </span>
                )}
                {parsedSummary.tag && (
                  <span className="tool-pill tool-pill--tag">
                    {parsedSummary.tag}
                  </span>
                )}
                {parsedSummary.value && (
                  <span className="tool-pill tool-pill--value">
                    {parsedSummary.value}
                  </span>
                )}
                {parsedSummary.change && (
                  <span
                    className={`tool-pill tool-pill--change ${
                      parsedSummary.change.isPositive
                        ? "tool-pill--pos"
                        : parsedSummary.change.isNegative
                        ? "tool-pill--neg"
                        : ""
                    }`}
                  >
                    {parsedSummary.change.text}
                  </span>
                )}
                {parsedSummary.pills?.map((p, idx) => (
                  <span key={idx} className="tool-pill tool-pill--metric">
                    <span className="tool-pill__key">{p.label}:</span>
                    <span className="tool-pill__val">{p.value}</span>
                  </span>
                ))}
                {parsedSummary.rawText && (
                  <span className="tool-pill tool-pill--text">
                    {parsedSummary.rawText}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="tool-card__header-right">
          {/* Status Indicator */}
          <div className="tool-card__status">
            {isRunning ? (
              <span className="status-badge status-badge--running">
                <span className="status-dot" />
                Running
              </span>
            ) : isFailed ? (
              <span className="status-badge status-badge--failed">
                <AlertCircle size={12} />
                Failed
              </span>
            ) : (
              <span className="status-badge status-badge--done">
                <CheckCircle2 size={12} />
                Done
              </span>
            )}
          </div>

          <div className="tool-card__chevron">
            <ChevronDown size={14} />
          </div>
        </div>
      </button>

      {/* Expanded Content Drawer */}
      {isOpen && (
        <div className="tool-card__drawer">
          <div className="tool-card__drawer-nav">
            <div className="tool-card__tabs">
              <button
                type="button"
                className={`tool-card__tab ${
                  activeTab === "response" ? "tool-card__tab--active" : ""
                }`}
                onClick={() => setActiveTab("response")}
              >
                <FileText size={12} />
                Output Result
              </button>
              <button
                type="button"
                className={`tool-card__tab ${
                  activeTab === "request" ? "tool-card__tab--active" : ""
                }`}
                onClick={() => setActiveTab("request")}
              >
                <Code size={12} />
                Input Parameters
              </button>
            </div>

            <button
              type="button"
              className="tool-card__copy-btn"
              onClick={(e) => handleCopy(e, activeTab)}
              title="Copy to clipboard"
            >
              {copiedTab === activeTab ? (
                <>
                  <Check size={12} className="tool-card__copy-check" />
                  Copied
                </>
              ) : (
                <>
                  <Copy size={12} />
                  Copy JSON
                </>
              )}
            </button>
          </div>

          <div className="tool-card__code-wrapper">
            <pre className="tool-card__code">
              {activeTab === "request"
                ? formatJson(block.input)
                : block.output !== undefined
                ? formatJson(block.output)
                : "No response output recorded."}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Grouped Tool Calls Container ─────────────────────────────────────────────

export function ToolCallGroup({
  blocks,
  isStreaming,
}: {
  blocks: ToolCallBlock[];
  isStreaming?: boolean;
}) {
  // If only 1 block, render clean card directly
  if (blocks.length === 1) {
    return <ToolCallCard block={blocks[0]} />;
  }

  const [isGroupOpen, setIsGroupOpen] = useState(true);

  const runningCount = blocks.filter((b) => b.status === "running").length;
  const failedCount = blocks.filter((b) => b.status === "failed").length;
  const doneCount = blocks.filter((b) => b.status === "done").length;

  // Extract distinct category titles for header badge
  const categoryTitles = Array.from(
    new Set(blocks.map((b) => getToolCategory(b.name).title))
  ).join(" • ");

  return (
    <div className="tool-group">
      <button
        type="button"
        className="tool-group__header"
        onClick={() => setIsGroupOpen(!isGroupOpen)}
      >
        <div className="tool-group__header-left">
          <div className="tool-group__icon">
            {runningCount > 0 ? (
              <Loader2 className="tool-group__spinner" size={14} />
            ) : (
              <Zap size={14} />
            )}
          </div>
          <div className="tool-group__info">
            <span className="tool-group__title">
              Executed {blocks.length} Tool Actions
            </span>
            <span className="tool-group__categories">{categoryTitles}</span>
          </div>
        </div>

        <div className="tool-group__header-right">
          <div className="tool-group__stats">
            {runningCount > 0 && (
              <span className="group-stat group-stat--running">
                {runningCount} Running
              </span>
            )}
            {doneCount > 0 && (
              <span className="group-stat group-stat--done">
                {doneCount} Done
              </span>
            )}
            {failedCount > 0 && (
              <span className="group-stat group-stat--failed">
                {failedCount} Failed
              </span>
            )}
          </div>
          <div className={`tool-group__chevron ${isGroupOpen ? "is-open" : ""}`}>
            <ChevronDown size={14} />
          </div>
        </div>
      </button>

      {isGroupOpen && (
        <div className="tool-group__list">
          {blocks.map((block, idx) => (
            <div key={idx} className="tool-group__item">
              <ToolCallCard block={block} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
