import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ChatComposer } from "../components/ChatComposer";

export function ChatHome() {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [isStarting, setIsStarting] = useState(false);

  async function handleStartChat(messageContent: string) {
    if (!messageContent.trim() || isStarting) return;
    setIsStarting(true);
    
    try {
      const res = await fetch("/api/chat/sessions", { method: "POST" });
      if (!res.ok) throw new Error("Failed to create session");
      const data = await res.json();
      navigate(`/chat/${data.id}`, { state: { initialMessage: messageContent } });
    } catch (e) {
      console.error(e);
      setIsStarting(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '24px' }}>
        <h2 style={{ marginBottom: '8px', color: 'var(--ink)', textAlign: 'center' }}>How can I help you today?</h2>
        <p style={{ color: 'var(--text-light)', textAlign: 'center' }}>
          Ask PAISA about your portfolio or any Indian equity.
        </p>
      </div>
      
      <div style={{ width: '100%', flexShrink: 0, background: 'var(--app-bg)' }}>
        <div style={{ padding: '24px 24px 96px 24px', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
          <ChatComposer 
            onSubmit={(msg) => { setInput(msg); handleStartChat(msg); }}
            isStreaming={isStarting}
            placeholder="Ask anything, @ to mention artifacts, $ to mention stocks, / for commands"
            initialValue={input}
          />
        </div>
      </div>
    </div>
  );
}
