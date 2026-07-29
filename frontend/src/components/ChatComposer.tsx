import React, { useState, useRef, useEffect, ChangeEvent, FormEvent } from "react";
import { AVAILABLE_MODELS, getSelectedModelConfig } from "../models";

type MentionItem = {
  id: string;
  label: string;
  type: "command" | "ticker" | "watchlist" | "artifact";
  replacement: string;
};

type RecognizedMention = { type: string; id: string; label: string };

interface ChatComposerProps {
  onSubmit: (msg: string, mentions: RecognizedMention[]) => void;
  isStreaming: boolean;
  onStop?: () => void;
  placeholder?: string;
  initialValue?: string;
}

// Module-level cache so we don't re-fetch on every keystroke
let _mentionCache: MentionItem[] | null = null;

async function loadMentionCache(): Promise<MentionItem[]> {
  if (_mentionCache) return _mentionCache;
  try {
    const [wlRes, artRes] = await Promise.all([
      fetch("/api/watchlists"),
      fetch("/api/artifacts"),
    ]);
    const combined: MentionItem[] = [];
    if (wlRes.ok) {
      const wlData = await wlRes.json();
      if (Array.isArray(wlData.watchlists)) {
        combined.push(
          ...wlData.watchlists.map((wl: any) => ({
            id: wl.slug,
            label: wl.name,
            type: "watchlist" as const,
            replacement: wl.slug,
          }))
        );
      }
    }
    if (artRes.ok) {
      const artData = await artRes.json();
      if (Array.isArray(artData.artifacts)) {
        combined.push(
          ...artData.artifacts.map((art: any) => ({
            id: art.id,
            label: art.title,
            type: "artifact" as const,
            replacement: art.title.replace(/\s+/g, "_"),
          }))
        );
      }
    }
    _mentionCache = combined;
    return combined;
  } catch {
    return [];
  }
}

export function ChatComposer({
  onSubmit,
  isStreaming,
  onStop,
  placeholder,
  initialValue = "",
}: ChatComposerProps) {
  const [input, setInput] = useState(initialValue);

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

  const handleModelChange = (e: ChangeEvent<HTMLSelectElement>) => {
    const newVal = e.target.value;
    setSelectedModelId(newVal);
    const config = getSelectedModelConfig(newVal);
    localStorage.setItem("paisa_llm_provider", config.provider);
    localStorage.setItem("paisa_llm_model", config.model);
  };

  const [triggerState, setTriggerState] = useState<{
    activeTrigger: "/" | "$" | "@" | null;
    query: string;
    startIndex: number;
  }>({ activeTrigger: null, query: "", startIndex: -1 });

  const [suggestions, setSuggestions] = useState<MentionItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recognizedMentions, setRecognizedMentions] = useState<
    Map<string, RecognizedMention>
  >(new Map());

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Sync initialValue
  useEffect(() => {
    if (initialValue && initialValue !== input) {
      setInput(initialValue);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
      }
    }
  }, [initialValue]);

  // Populate suggestions whenever trigger changes
  useEffect(() => {
    if (triggerState.activeTrigger === null) {
      setSuggestions([]);
      return;
    }

    const query = triggerState.query.toLowerCase();

    if (triggerState.activeTrigger === "/") {
      const allCommands: MentionItem[] = [
        { id: "compare", label: "/compare", type: "command", replacement: "compare" },
        { id: "create-artifact", label: "/create-artifact", type: "command", replacement: "create-artifact" },
        { id: "recommend", label: "/recommend", type: "command", replacement: "recommend" },
        { id: "research", label: "/research", type: "command", replacement: "research" },
      ];
      setSuggestions(
        allCommands.filter((c) => c.label.toLowerCase().includes(query))
      );
      setSelectedIndex(0);
    } else if (triggerState.activeTrigger === "$") {
      fetch(`/api/search/stocks?q=${encodeURIComponent(query)}`)
        .then((res) => res.json())
        .then((data) => {
          if (Array.isArray(data)) {
            setSuggestions(
              data.map((s: any) => ({
                id: s.symbol,
                label: `${s.symbol} — ${s.name}`,
                type: "ticker",
                replacement: s.symbol,
              }))
            );
            setSelectedIndex(0);
          }
        })
        .catch(() => setSuggestions([]));
    } else if (triggerState.activeTrigger === "@") {
      loadMentionCache().then((all) => {
        const filtered = all.filter(
          (item) =>
            item.replacement.toLowerCase().includes(query) ||
            item.label.toLowerCase().includes(query)
        );
        setSuggestions(filtered);
        setSelectedIndex(0);
      });
    }
  }, [triggerState]);

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
      const trigger = match[1] as "/" | "$" | "@";
      const query = match[2];
      setTriggerState({
        activeTrigger: trigger,
        query,
        startIndex: cursor - query.length - 1,
      });
    } else {
      setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
      setSuggestions([]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape" && isStreaming) {
      e.preventDefault();
      onStop?.();
      return;
    }

    if (triggerState.activeTrigger && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % suggestions.length);
        return;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(
          (prev) => (prev - 1 + suggestions.length) % suggestions.length
        );
        return;
      } else if (e.key === "Escape") {
        e.preventDefault();
        setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
        setSuggestions([]);
        return;
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        insertMention(suggestions[selectedIndex]);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  function insertMention(sugg: MentionItem) {
    if (triggerState.startIndex === -1 || !textareaRef.current) return;

    const before = input.slice(0, triggerState.startIndex);
    const after = input.slice(textareaRef.current.selectionStart);

    const replacementText = sugg.replacement;
    const token = `${triggerState.activeTrigger}${replacementText}`;
    const newInput = `${before}${token} ${after}`;
    setInput(newInput);

    setRecognizedMentions((prev) => {
      const next = new Map(prev);
      next.set(token, { type: sugg.type, id: sugg.id, label: sugg.label });
      return next;
    });

    setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
    setSuggestions([]);

    setTimeout(() => {
      if (textareaRef.current) {
        const pos = before.length + token.length + 1;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(pos, pos);
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
      }
    }, 0);
  }

  function renderOverlay(text: string) {
    if (recognizedMentions.size === 0) return <span>{text}</span>;
    const keys = Array.from(recognizedMentions.keys());
    // Sort longest first to avoid partial-match issues
    keys.sort((a, b) => b.length - a.length);
    const escaped = keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const regex = new RegExp(`(${escaped.join("|")})`, "g");
    const parts = text.split(regex);
    return (
      <>
        {parts.map((part, i) => {
          if (recognizedMentions.has(part)) {
            const m = recognizedMentions.get(part)!;
            return (
              <span key={i} className={`highlight highlight--${m.type}`}>
                {part}
              </span>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </>
    );
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const msg = input.trim();

    // Collect only the mentions that are actually present in the submitted message
    const activeMentions: RecognizedMention[] = [];
    recognizedMentions.forEach((mention, token) => {
      if (msg.includes(token)) {
        activeMentions.push(mention);
      }
    });

    onSubmit(msg, activeMentions);
    setInput("");
    setRecognizedMentions(new Map());
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  // type-badge for the suggestions dropdown
  const typeLabel: Record<string, string> = {
    command: "CMD",
    ticker: "$",
    watchlist: "List",
    artifact: "Doc",
  };

  return (
    <form className="composer" onSubmit={handleSubmit} style={{ flexDirection: 'column', padding: '12px 16px', gap: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', marginBottom: '4px' }}>
        <select 
          value={selectedModelId} 
          onChange={handleModelChange}
          className="model-switcher"
        >
          {Array.from(new Set(AVAILABLE_MODELS.map(m => m.group))).map(groupName => (
            <optgroup key={groupName} label={groupName}>
              {AVAILABLE_MODELS.filter(m => m.group === groupName).map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>
      <div style={{ display: 'flex', width: '100%', alignItems: 'flex-end', gap: '8px' }}>
        <div className="composer-input-wrapper">
          <div className="composer-overlay">{renderOverlay(input)}</div>
          <textarea
            ref={textareaRef}
            className="composer__input"
            aria-label="Message"
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || "Message PAISA… use / $ @ to trigger commands"}
            rows={1}
          />
          {triggerState.activeTrigger && suggestions.length > 0 && (
          <div className="suggestion-popup" role="listbox">
            {suggestions.map((sugg, i) => (
              <div
                key={`${sugg.type}-${sugg.id}`}
                role="option"
                aria-selected={i === selectedIndex}
                className={`suggestion-item ${i === selectedIndex ? "active" : ""}`}
                onMouseDown={(e) => {
                  e.preventDefault(); // keep textarea focused
                  insertMention(sugg);
                }}
              >
                <span className={`suggestion-badge suggestion-badge--${sugg.type}`}>
                  {typeLabel[sugg.type] ?? sugg.type}
                </span>
                <span className="suggestion-label">{sugg.label}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <button
        className="composer__send"
        disabled={!input.trim() || isStreaming}
        type="submit"
      >
        {isStreaming ? (
          <span className="spinner" />
        ) : (
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        )}
      </button>
      </div>
    </form>
  );
}
