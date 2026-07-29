import React, { useState, useEffect, useRef, FormEvent, ChangeEvent } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { marked } from "marked";
import { User, Sparkles, Square } from "lucide-react";
import { ChatComposer } from "../components/ChatComposer";
import { ToolCallGroup, ToolCallBlock } from "../components/ToolCallCard";
import { ArtifactCardRender } from "../components/ArtifactCardRender";
import { ComparisonCardRender } from "../components/ComparisonCardRender";
import { RecommendationCardRender } from "../components/RecommendationCardRender";
import { AVAILABLE_MODELS, getSelectedModelConfig } from "../models";

// Reusing types from App.tsx conceptually
type TextBlock = { type: "text"; text: string };
type CardBlock = { type: "card_render"; payload: any };
type ContentBlock = TextBlock | ToolCallBlock | CardBlock;

type Message = {
  id: number | string;
  role: "user" | "assistant" | "system" | "error" | "tool";
  content?: string;
  blocks?: ContentBlock[];
};

type StreamEvent =
  | { event: "run_start"; data: { stage: string; user_id: string; timestamp: string; thread_id?: string } }
  | { event: "token"; data: { token: string } }
  | { event: "error"; data: { message: string } }
  | { event: "tool_call"; data: { name: string; status: string; summary: string; input: Record<string, unknown> } }
  | { event: "tool_result"; data: { name: string; status: "done" | "failed"; summary: string; output?: string } }
  | { event: "card_render"; data: any }
  | { event: "final"; data: { model: string; timestamp: string } };

function Markdown({ content }: { content: string }) {
  const rawHtml = marked.parse(content, { async: false }) as string;
  return <div className="message-content" dangerouslySetInnerHTML={{ __html: rawHtml }} />;
}

function parseSseEvent(rawEvent: string): StreamEvent | null {
  const eventName = rawEvent.split("\n").find((line) => line.startsWith("event:"))?.slice(6).trim();
  const data = rawEvent.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
  if (!eventName || !data) return null;
  try { return { event: eventName, data: JSON.parse(data) } as StreamEvent; } catch { return null; }
}

function appendToken(blocks: ContentBlock[], token: string): ContentBlock[] {
  const last = blocks[blocks.length - 1];
  if (last?.type === "text") {
    return [...blocks.slice(0, -1), { type: "text", text: last.text + token }];
  }
  return [...blocks, { type: "text", text: token }];
}

function pushToolCall(blocks: ContentBlock[], name: string, input: Record<string, unknown>): ContentBlock[] {
  return [...blocks, { type: "tool_call", name, summary: "", input, status: "running" }];
}

function resolveToolResult(blocks: ContentBlock[], name: string, summary: string, output: string, status: "done" | "failed"): ContentBlock[] {
  const idx = [...blocks].reverse().findIndex(b => b.type === "tool_call" && b.name === name && b.status === "running");
  if (idx === -1) return blocks;
  const realIdx = blocks.length - 1 - idx;
  return blocks.map((b, i) => i === realIdx ? ({ ...b, status, summary, output } as ToolCallBlock) : b);
}

function AssistantBlocks({ blocks, isStreaming }: { blocks: ContentBlock[]; isStreaming?: boolean }) {
  const groupedBlocks: any[] = [];
  for (const block of blocks) {
    if (block.type === "text" || block.type === "card_render") {
      groupedBlocks.push(block);
    } else {
      const last = groupedBlocks[groupedBlocks.length - 1];
      if (last && last.type === "tool_group") last.items.push(block);
      else groupedBlocks.push({ type: "tool_group", items: [block] });
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
          ) : item.payload.type === "recommendation_card" ? (
            <RecommendationCardRender key={i} envelope={item.payload} />
          ) : null
        ) : (
          <ToolCallGroup key={i} blocks={item.items} isStreaming={isStreaming} />
        )
      )}
    </div>
  );
}

const SquareIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <rect x="4" y="4" width="16" height="16" rx="2" />
  </svg>
);

export function ChatPage() {
  const { session_id } = useParams<{ session_id: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [draftBlocks, setDraftBlocks] = useState<ContentBlock[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState("Connected");
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const nextId = useRef(Date.now());
  const abortControllerRef = useRef<AbortController | null>(null);

  const hasAutoSent = useRef(false);

  useEffect(() => {
    if (!session_id) return;
    
    // Bug 5: Reset state on session change
    setMessages([]);
    setDraftBlocks([]);
    setIsStreaming(false);
    setStatus("Connected");
    // Bug 4: Reset auto-send
    hasAutoSent.current = false;

    fetch(`/api/chat/sessions/${session_id}`)
      .then(res => res.json())
      .then(data => {
        let loaded: Message[] = [];
        if (data && data.messages) {
           loaded = data.messages.map((m: any) => ({
             id: m.id,
             role: m.role,
             content: m.content,
             // Bug 2: Read blocks_json
             blocks: m.blocks_json ? m.blocks_json : (m.role === 'assistant' ? [{ type: 'text', text: m.content }] : undefined)
           }));
        }
        
        // Handle auto-send from Home
        if (location.state?.initialMessage && !hasAutoSent.current) {
           const initialMsg = location.state.initialMessage;
           hasAutoSent.current = true;
           navigate(location.pathname, { replace: true, state: {} });
           
           // Bug 1: Inject user message synchronously before async sendMessageRaw
           const userMsg: Message = { id: nextId.current++, role: "user", content: initialMsg };
           setMessages([...loaded, userMsg]);
           sendMessageRaw(initialMsg, [], true);
        } else {
           setMessages(loaded);
        }
      })
      .catch(err => console.error("Failed to load session", err));
  }, [session_id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, draftBlocks]);

  function stopStreaming() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }

  async function sendMessageRaw(message: string, mentions: { type: string; id: string; label: string }[] = [], skipAddUserMsg: boolean = false) {
    if (!message.trim() || !session_id) return;
    
    if (isStreaming) stopStreaming();
    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (!skipAddUserMsg) {
      setMessages((cur) => [...cur, { id: nextId.current++, role: "user", content: message }]);
    }
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setDraftBlocks([]);
    setIsStreaming(true);
    setStatus("Thinking…");

    let blocks: ContentBlock[] = [];
    let hasError = false;
    let wasAborted = false;

    try {
      const p = localStorage.getItem("paisa_llm_provider") || "groq";
      const m = localStorage.getItem("paisa_llm_model");
      let activeConfig = AVAILABLE_MODELS[0];
      if (m) {
        const match = AVAILABLE_MODELS.find((opt) => opt.provider === p && opt.model === m);
        if (match) activeConfig = match;
      } else {
        const matchProvider = AVAILABLE_MODELS.find((opt) => opt.provider === p);
        if (matchProvider) activeConfig = matchProvider;
      }

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ 
          message,
          thread_id: session_id,
          mentions: mentions.map(m => ({ type: m.type, id: m.id, label: m.label })),
          llm_provider: activeConfig.provider,
          llm_model: activeConfig.model,
        }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) throw new Error(`Chat request failed (${response.status})`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        if (controller.signal.aborted) { wasAborted = true; break; }
        const { value, done } = await reader.read();
        if (controller.signal.aborted) { wasAborted = true; break; }
        
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
        const rawEvents = buffer.split("\n\n");
        buffer = rawEvents.pop() ?? "";

        for (const rawEvent of rawEvents) {
          const parsed = parseSseEvent(rawEvent);
          if (!parsed) continue;
          if (parsed.event === "run_start") setStatus("Thinking…");
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
            blocks = resolveToolResult(blocks, parsed.data.name, parsed.data.summary, parsed.data.output ?? "", parsed.data.status);
            setDraftBlocks([...blocks]);
          }
          if (parsed.event === "card_render") {
            blocks = [...blocks, { type: "card_render", payload: parsed.data }];
            setDraftBlocks([...blocks]);
          }
          if (parsed.event === "error") {
            setMessages((cur) => [...cur, { id: nextId.current++, role: "error", content: parsed.data.message }]);
            setDraftBlocks([]);
            setStatus("Stream failed");
            hasError = true;
            break;
          }
          if (parsed.event === "final") setStatus(`Connected`);
        }
        if (done || hasError) break;
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === "AbortError") wasAborted = true;
      else {
        const msg = e instanceof Error ? e.message : "Chat stream failed";
        setStatus(msg);
        setMessages((cur) => [...cur, { id: nextId.current++, role: "error", content: msg }]);
      }
    } finally {
      if (abortControllerRef.current === controller) abortControllerRef.current = null;
      setIsStreaming(false);
      if (wasAborted) setStatus("Interrupted");
      if (blocks.length > 0 && !hasError) {
        const finalBlocks = blocks.map((b) =>
          b.type === "tool_call" && b.status === "running"
            ? { ...b, status: "failed" as const, summary: "Interrupted", output: "Tool execution interrupted by user." }
            : b
        );
        setMessages((cur) => [...cur, { id: nextId.current++, role: "assistant", blocks: finalBlocks }]);
        setDraftBlocks([]);
      }
    }
  }

  function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendMessageRaw(input);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', flex: 1 }}>
      <div className="message-list" aria-live="polite" style={{ flex: 1, overflowY: "auto", padding: "24px" }}>
        {messages.map((msg) => {
          if (msg.role === "user") {
            return (
              <div key={msg.id} className="turn turn--user">
                <div className="turn-avatar turn-avatar--user"><User size={18} /></div>
                <div className="turn-content-wrapper"><div className="turn-content"><Markdown content={msg.content ?? ""} /></div></div>
              </div>
            );
          }
          if (msg.role === "error") {
            return (
              <div key={msg.id} className="turn turn--assistant">
                <div className="turn-avatar turn-avatar--error"><Sparkles size={18} /></div>
                <div className="turn-content-wrapper">
                  <div className="error-bubble"><span className="error-bubble__icon">⚠</span>{msg.content}</div>
                  <div className="end-of-message-indicator" />
                </div>
              </div>
            );
          }
          if (msg.role === "assistant") {
            return (
              <div key={msg.id} className="turn turn--assistant">
                <div className="turn-avatar turn-avatar--assistant"><Sparkles size={18} /></div>
                <div className="turn-content-wrapper">
                  <AssistantBlocks blocks={msg.blocks ?? []} />
                  <div className="end-of-message-indicator" />
                </div>
              </div>
            );
          }
          return null; // hide tool rows for now or render if we want them explicitly outside blocks
        })}

        {draftBlocks.length > 0 && (
          <div className="turn turn--assistant">
            <div className="turn-avatar turn-avatar--assistant"><Sparkles size={18} /></div>
            <div className="turn-content-wrapper"><AssistantBlocks blocks={draftBlocks} isStreaming /></div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="composer-wrap">
        <ChatComposer 
          onSubmit={(msg, mentions) => sendMessageRaw(msg, mentions)}
          isStreaming={isStreaming}
          onStop={stopStreaming}
          placeholder={isStreaming ? "Ask a new prompt to interrupt..." : "Type your message... (use / $ @ for commands)"}
        />
      </div>
    </div>
  );
}
