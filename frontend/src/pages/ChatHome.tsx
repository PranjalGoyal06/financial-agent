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
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto', justifyContent: 'center' }}>
      
      <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
        <h2 style={{ marginBottom: '8px', color: 'var(--ink)', textAlign: 'center' }}>How can I help you today?</h2>
        <p style={{ marginBottom: '32px', color: 'var(--text-light)', textAlign: 'center' }}>
          Ask PAISA about your portfolio or any Indian equity.
        </p>
        <ChatComposer 
          onSubmit={(msg) => { setInput(msg); handleStartChat(msg); }}
          isStreaming={isStarting}
          placeholder="Ask PAISA about your portfolio..."
          initialValue={input}
        />
      </div>
    </div>
  );
}
