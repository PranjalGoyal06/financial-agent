import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import type {
  ChatFinalResponseEvent,
  ChatMessage,
  ChatMessageHistoryResponse,
  ChatStreamEvent,
  ToolCallTrace,
} from "../../lib/types";
import { MessageComposer } from "./MessageComposer";
import { MessageThread } from "./MessageThread";
import { PipelineStatus } from "./PipelineStatus";
import "./ChatPanel.css";

type SuggestedPrompt = {
  id: number;
  text: string;
};

type ChatPanelProps = {
  sessionId: string;
  apiBaseUrl?: string;
  className?: string;
  suggestedPrompt?: SuggestedPrompt | null;
  onMessageSent?: () => void | Promise<void>;
};

function apiUrl(apiBaseUrl: string, path: string): string {
  return `${apiBaseUrl.replace(/\/$/, "")}${path}`;
}

function temporaryUserMessage(sessionId: string, content: string): ChatMessage {
  const localId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

  return {
    message_id: `local-${localId}`,
    session_id: sessionId,
    role: "user",
    content,
    created_at: new Date().toISOString(),
  };
}

function parseSseEvent(rawEvent: string): ChatStreamEvent | null {
  const data = rawEvent
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");

  if (!data) {
    return null;
  }

  try {
    return JSON.parse(data) as ChatStreamEvent;
  } catch {
    return null;
  }
}

function appendFinalMessage(messages: ChatMessage[], event: ChatFinalResponseEvent): ChatMessage[] {
  const finalMessage = event.data.message;
  if (!finalMessage) {
    return messages;
  }

  const withoutDuplicate = messages.filter(
    (message) => message.message_id !== finalMessage.message_id,
  );
  return [...withoutDuplicate, finalMessage];
}

function upsertToolCallTrace(
  toolCalls: ToolCallTrace[],
  nextTrace: ToolCallTrace,
): ToolCallTrace[] {
  const key = nextTrace.tool_call_id || `${nextTrace.name}-${JSON.stringify(nextTrace.args ?? {})}`;
  const index = toolCalls.findIndex((trace) => {
    const traceKey = trace.tool_call_id || `${trace.name}-${JSON.stringify(trace.args ?? {})}`;
    return traceKey === key;
  });
  if (index === -1) {
    return [...toolCalls, nextTrace];
  }
  return toolCalls.map((trace, traceIndex) =>
    traceIndex === index ? { ...trace, ...nextTrace } : trace,
  );
}

function applyStreamEvent(
  event: ChatStreamEvent,
  setCompletedNodes: Dispatch<SetStateAction<string[]>>,
  setLiveToolCalls: Dispatch<SetStateAction<ToolCallTrace[]>>,
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>,
): boolean {
  if (event.event === "node_complete") {
    setCompletedNodes((current) => [...current, event.data.node_name]);
  }

  if (event.event === "tool_call") {
    setLiveToolCalls((current) => upsertToolCallTrace(current, event.data));
  }

  if (event.event === "final_response") {
    setMessages((current) => appendFinalMessage(current, event));
    return true;
  }

  if (event.event === "error") {
    throw new Error(event.data.message);
  }

  return false;
}

function toolStatusLabel(status: string): string {
  return status.replace(/_/g, " ").toUpperCase();
}

function ToolCallTracePanel({ toolCalls }: { toolCalls: ToolCallTrace[] }) {
  if (!toolCalls.length) {
    return null;
  }

  return (
    <div className="chat-tool-trace" aria-live="polite">
      <div className="chat-tool-trace__title">Tool calls</div>
      <ol>
        {toolCalls.map((toolCall, index) => (
          <li key={toolCall.tool_call_id || `${toolCall.name}-${index}`}>
            <span className={`chat-tool-trace__status chat-tool-trace__status--${toolCall.status}`}>
              {toolStatusLabel(toolCall.status)}
            </span>
            <span className="chat-tool-trace__name">{toolCall.name}</span>
            {toolCall.summary ? (
              <span className="chat-tool-trace__summary">{toolCall.summary}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ChatPanel({
  sessionId,
  apiBaseUrl = "/api/v1",
  className = "",
  suggestedPrompt = null,
  onMessageSent,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);
  const [liveToolCalls, setLiveToolCalls] = useState<ToolCallTrace[]>([]);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const historyUrl = useMemo(
    () => apiUrl(apiBaseUrl, `/chat/sessions/${sessionId}/messages`),
    [apiBaseUrl, sessionId],
  );

  const loadMessages = useCallback(
    async (signal?: AbortSignal) => {
      const response = await fetch(historyUrl, { signal });
      if (!response.ok) {
        throw new Error(`Failed to load chat history (${response.status})`);
      }

      const payload = (await response.json()) as ChatMessageHistoryResponse;
      setMessages(payload.messages);
    },
    [historyUrl],
  );

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    loadMessages(controller.signal)
      .catch((loadError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "Failed to load chat history");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [loadMessages]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  async function handleSubmit(content: string) {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setError(null);
    setIsProcessing(true);
    setCompletedNodes([]);
    setLiveToolCalls([]);
    setMessages((current) => [...current, temporaryUserMessage(sessionId, content)]);

    try {
      const response = await fetch(historyUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ content }),
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Message send failed (${response.status})`);
      }

      if (!response.body) {
        throw new Error("The chat endpoint did not return a stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalReceived = false;

      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

        const rawEvents = buffer.split("\n\n");
        buffer = rawEvents.pop() ?? "";

        for (const rawEvent of rawEvents) {
          const event = parseSseEvent(rawEvent);
          if (!event) {
            continue;
          }

          finalReceived =
            applyStreamEvent(event, setCompletedNodes, setLiveToolCalls, setMessages) ||
            finalReceived;
        }

        if (done) {
          break;
        }
      }

      const trailingEvent = parseSseEvent(buffer.trim());
      if (trailingEvent) {
        finalReceived =
          applyStreamEvent(trailingEvent, setCompletedNodes, setLiveToolCalls, setMessages) ||
          finalReceived;
      }

      if (finalReceived) {
        await loadMessages(controller.signal);
        await onMessageSent?.();
      }
    } catch (sendError: unknown) {
      if (!controller.signal.aborted) {
        setError(sendError instanceof Error ? sendError.message : "Message send failed");
      }
    } finally {
      if (!controller.signal.aborted) {
        setIsProcessing(false);
      }
    }
  }

  return (
    <section className={`chat-panel ${className}`} aria-label="Reactive chat">
      <header className="chat-panel__header">
        <div>
          <p className="chat-panel__kicker">Investment Agent</p>
          <h2>Portfolio conversation</h2>
        </div>
        <PipelineStatus
          isProcessing={isProcessing}
          completedNodes={completedNodes}
          error={error}
        />
      </header>

      <ToolCallTracePanel toolCalls={liveToolCalls} />
      <MessageThread messages={messages} isLoading={isLoading} />
      <MessageComposer
        disabled={isProcessing || isLoading}
        suggestedPrompt={suggestedPrompt}
        onSubmit={handleSubmit}
      />
    </section>
  );
}

export default ChatPanel;
