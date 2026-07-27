import React, { useState, useEffect } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { BriefingZone } from "../BriefingZone";
import { ChatComposer } from "../components/ChatComposer";

export function Home() {
  const navigate = useNavigate();
  const location = useLocation();
  const [input, setInput] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [recentSessions, setRecentSessions] = useState<any[]>([]);

  useEffect(() => {
    fetch("/api/chat/sessions")
      .then(res => res.json())
      .then(data => {
        if (data && data.sessions) {
          setRecentSessions(data.sessions.slice(0, 4));
        }
      })
      .catch(err => console.error("Failed to load recent sessions", err));
  }, []);

  useEffect(() => {
    if (location.state?.prefill) {
      setInput(location.state.prefill);
      window.history.replaceState({}, '');
    }
  }, [location]);

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

  function handlePreFillChat(query: string) {
    setInput(query);
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto' }}>
      <BriefingZone 
        onPreFillChat={handlePreFillChat} 
        onNavigateToAsset={(ticker) => {
          navigate('/research?ticker=' + ticker);
        }} 
      />
      
      <div style={{ padding: '24px', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
        <h3 style={{ marginBottom: '16px', color: 'var(--text-light)' }}>Start a new conversation</h3>
        <ChatComposer 
          onSubmit={(msg) => { setInput(msg); handleStartChat(msg); }}
          isStreaming={isStarting}
          placeholder="Ask PAISA about your portfolio..."
          initialValue={input}
        />
        <div className="prompt-chips-container">
          <button className="prompt-chip" onClick={() => handleStartChat("Analyze my portfolio risk")}>Analyze my portfolio risk</button>
          <button className="prompt-chip" onClick={() => handleStartChat("What are the latest tech tailwinds?")}>What are the latest tech tailwinds?</button>
          <button className="prompt-chip" onClick={() => handleStartChat("Review my asset allocation")}>Review my asset allocation</button>
        </div>
      </div>

      {recentSessions.length > 0 && (
        <div className="recent-conversations-container" style={{ maxWidth: '800px', margin: '0 auto 40px auto', width: '100%' }}>
          <h3 className="recent-conversations-title">Recent Conversations</h3>
          <div className="recent-conversations-grid">
            {recentSessions.map(s => (
              <Link to={`/chat/${s.id}`} key={s.id} className="chat-session-item" style={{ border: '1px solid var(--line)', background: 'var(--surface)' }}>
                <span className="chat-session-title">{s.title || "New Chat"}</span>
                <span className="chat-session-time">{new Date(s.updated_at).toLocaleDateString()}</span>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
