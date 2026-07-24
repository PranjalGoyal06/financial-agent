const fs = require('fs');
const path = './src/App.tsx';
let content = fs.readFileSync(path, 'utf8');

// 1. Add States
const stateTarget = `  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadErrors, setUploadErrors] = useState<PortfolioUploadError[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  
  const nextId = useRef(2);`;

const stateReplacement = `  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadErrors, setUploadErrors] = useState<PortfolioUploadError[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  
  // ── Mentions State ─────────────────────────────────────────────────────────────
  const [triggerState, setTriggerState] = useState<{ activeTrigger: '/' | '$' | '@' | null, query: string, startIndex: number }>({ activeTrigger: null, query: "", startIndex: -1 });
  const [suggestions, setSuggestions] = useState<{ id: string, label: string }[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [recognizedMentions, setRecognizedMentions] = useState<Map<string, { type: string, id: string, label: string }>>(new Map());

  // ── Async Mentions Search ──────────────────────────────────────────────────────
  useEffect(() => {
    if (triggerState.activeTrigger !== '$') return;
    
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(\`/api/search/stocks?q=\${encodeURIComponent(triggerState.query)}\`);
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        if (Array.isArray(data)) {
          setSuggestions(data.map((d: any) => ({ id: \`$\${d.symbol}\`, label: \`\${d.symbol} - \${d.name}\` })));
        }
      } catch (err) {
        console.error(err);
      }
    }, 200);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [triggerState]);

  const nextId = useRef(2);`;

content = content.replace(stateTarget, stateReplacement);

// 2. Add handlers
const handlersTarget = `  function handleInputChange(e: ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = \`\${el.scrollHeight}px\`;
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape" && isStreaming) {
      e.preventDefault();
      stopStreaming();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }`;

const handlersReplacement = `  function handleInputChange(e: ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setInput(val);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = \`\${el.scrollHeight}px\`;
    
    const cursor = el.selectionStart;
    const textBeforeCursor = val.slice(0, cursor);
    const match = textBeforeCursor.match(/(?:^|\\s)([\\/$@])([a-zA-Z0-9_-]*)$/);
    if (match) {
      const trigger = match[1] as '/' | '$' | '@';
      const query = match[2];
      const startIndex = match.index! + (match[0].startsWith(' ') || match[0].startsWith('\\n') ? 1 : 0);
      setTriggerState({ activeTrigger: trigger, query, startIndex });
      setSelectedIndex(0);
      
      if (trigger === '/') {
        const cmds = ['/new', '/clear', '/help'];
        setSuggestions(cmds.filter(c => c.startsWith(\`/\${query}\`)).map(c => ({ id: c, label: c })));
      } else if (trigger === '@') {
        const arts = ['@report', '@summary', '@portfolio'];
        setSuggestions(arts.filter(a => a.startsWith(\`@\${query}\`)).map(a => ({ id: a, label: a })));
      }
    } else {
      setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
      setSuggestions([]);
    }
  }

  function insertMention(suggestion: { id: string, label: string }) {
    if (!triggerState.activeTrigger) return;
    const trigger = triggerState.activeTrigger;
    const type = trigger === '/' ? 'command' : trigger === '$' ? 'ticker' : 'artifact';
    
    const before = input.slice(0, triggerState.startIndex);
    const replacement = \`\${suggestion.id} \`;
    const after = input.slice(triggerState.startIndex + trigger.length + triggerState.query.length);
    
    const newText = before + replacement + after;
    setInput(newText);
    
    setRecognizedMentions(prev => {
      const next = new Map(prev);
      next.set(suggestion.id, { type, id: suggestion.id, label: suggestion.label });
      return next;
    });
    
    setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
    
    setTimeout(() => {
      if (textareaRef.current) {
        textareaRef.current.focus();
        const newCursorPos = before.length + replacement.length;
        textareaRef.current.setSelectionRange(newCursorPos, newCursorPos);
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = \`\${textareaRef.current.scrollHeight}px\`;
      }
    }, 0);
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (triggerState.activeTrigger && suggestions.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % suggestions.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setTriggerState({ activeTrigger: null, query: "", startIndex: -1 });
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        insertMention(suggestions[selectedIndex]);
        return;
      }
    }

    if (e.key === "Escape" && isStreaming) {
      e.preventDefault();
      stopStreaming();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      e.currentTarget.form?.requestSubmit();
    }
  }

  function renderOverlay(text: string) {
    if (recognizedMentions.size === 0) return text;
    const escapedKeys = Array.from(recognizedMentions.keys()).map(k => k.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&'));
    if (escapedKeys.length === 0) return text;
    const regex = new RegExp(\`(\${escapedKeys.join('|')})(?=\\\\s|$)\`, 'g');
    const parts = text.split(regex);
    return parts.map((part, i) => {
      if (recognizedMentions.has(part)) {
        return <span key={i} className={\`mention highlight-\${recognizedMentions.get(part)!.type}\`}>{part}</span>;
      }
      return <span key={i}>{part}</span>;
    });
  }`;

content = content.replace(handlersTarget, handlersReplacement);


// 3. Update Send Message Payload
const sendMessageTarget = `    try {
      const activeConfig = getSelectedModelConfig(selectedModelId);
      const response = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ 
          message,
          llm_provider: activeConfig.provider,
          llm_model: activeConfig.model,
        }),`;
const sendMessageReplacement = `    const activeMentions = Array.from(recognizedMentions.values()).filter(m => message.includes(m.id));

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
        }),`;
content = content.replace(sendMessageTarget, sendMessageReplacement);


// 4. Wrap textarea with overlay and suggestions
const textareaTarget = `            <form className="composer" onSubmit={sendMessage}>
              <textarea
                ref={textareaRef}
                className="composer__input"
                aria-label="Message"
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                placeholder={isStreaming ? "Ask a new prompt to interrupt..." : "Ask PAISA about your portfolio..."}
                rows={1}
              />`;

const textareaReplacement = `            <form className="composer" onSubmit={sendMessage}>
              <div className="composer-input-wrapper">
                <div className="composer-overlay">
                  {renderOverlay(input)}
                  {input.endsWith('\\n') ? <br /> : null}
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
                        className={\`suggestion-item \${i === selectedIndex ? 'active' : ''}\`}
                        onClick={() => insertMention(sugg)}
                      >
                        {sugg.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>`;

content = content.replace(textareaTarget, textareaReplacement);

fs.writeFileSync(path, content);
console.log('App.tsx patched successfully.');
