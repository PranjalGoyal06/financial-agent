import React, { useState, useRef, useEffect, ChangeEvent, FormEvent } from "react";

interface ChatComposerProps {
  onSubmit: (msg: string) => void;
  isStreaming: boolean;
  onStop?: () => void;
  placeholder?: string;
  initialValue?: string;
}

export function ChatComposer({ onSubmit, isStreaming, onStop, placeholder, initialValue = "" }: ChatComposerProps) {
  const [input, setInput] = useState(initialValue);
  
  // ── Mentions State ─────────────────────────────────────────────────────────────
  const [triggerState, setTriggerState] = useState<{ activeTrigger: '/' | '$' | '@' | null, query: string, startIndex: number }>({ activeTrigger: null, query: "", startIndex: -1 });
  const [suggestions, setSuggestions] = useState<{ id: string, label: string }[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recognizedMentions, setRecognizedMentions] = useState<Map<string, { type: string, id: string, label: string }>>(new Map());

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

  // Async Mentions Search
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
        { id: 'research', label: '/research' },
        { id: 'goal', label: '/goal' },
        { id: 'schedule', label: '/schedule' },
      ];
      setSuggestions(allCommands.filter(c => c.label.toLowerCase().includes(query)));
      setSelectedIndex(0);
    } else if (triggerState.activeTrigger === '$') {
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
      fetch('/api/portfolio')
        .then(res => res.json())
        .then(data => {
          // just mock empty for now if no endpoint
          setSuggestions([]);
        })
        .catch(err => {
          setSuggestions([]);
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
      onStop?.();
      return;
    }
    
    if (triggerState.activeTrigger && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % suggestions.length);
        return;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
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

  function insertMention(sugg: { id: string, label: string }) {
    if (triggerState.startIndex === -1 || !textareaRef.current) return;
    
    const before = input.slice(0, triggerState.startIndex);
    const after = input.slice(textareaRef.current.selectionStart);
    
    const replacement = `${triggerState.activeTrigger}${sugg.id} `;
    setInput(before + replacement + after);
    
    setRecognizedMentions(prev => {
      const next = new Map(prev);
      next.set(replacement.trim(), { 
        type: triggerState.activeTrigger === '/' ? 'command' : (triggerState.activeTrigger === '$' ? 'ticker' : 'watchlist'), 
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

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSubmit(input);
    setInput("");
    if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer-input-wrapper">
        <div className="composer-overlay">
          {renderOverlay(input)}
        </div>
        <textarea
          ref={textareaRef}
          className="composer__input"
          aria-label="Message"
          value={input}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || "Message PAISA..."}
          rows={1}
        />
        {triggerState.activeTrigger && suggestions.length > 0 && (
          <div className="suggestion-popup">
            {suggestions.map((sugg, i) => (
              <div 
                key={sugg.id} 
                className={`suggestion-item ${i === selectedIndex ? 'active' : ''}`}
                onMouseDown={(e) => {
                  e.preventDefault(); // prevent blur
                  insertMention(sugg);
                }}
              >
                {sugg.label}
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
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        )}
      </button>
    </form>
  );
}
