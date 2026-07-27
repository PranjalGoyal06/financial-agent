import React, { useEffect, useState } from "react";
import { NavLink, useNavigate, useParams } from "react-router-dom";
import { MessageSquare, Plus, Pencil, Trash2, MoreHorizontal } from "lucide-react";

type ChatSession = {
  id: string;
  title: string;
  created_at: string;
};

export function ChatSidebar() {
  const navigate = useNavigate();
  const { session_id } = useParams<{ session_id: string }>();
  
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  useEffect(() => {
    fetch("/api/chat/sessions")
      .then((res) => res.json())
      .then((data) => {
        setSessions(data.sessions || []);
      })
      .catch((err) => console.error("Error fetching sessions:", err))
      .finally(() => setLoading(false));
  }, []);

  async function handleDelete(e: React.MouseEvent, id: string) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this chat?")) return;
    
    try {
      const res = await fetch(`/api/chat/sessions/${id}`, { method: "DELETE" });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== id));
        if (session_id === id) {
          navigate("/chat");
        }
      }
    } catch (err) {
      console.error("Failed to delete", err);
    }
  }

  function startEdit(e: React.MouseEvent, session: ChatSession) {
    e.preventDefault();
    e.stopPropagation();
    setEditingId(session.id);
    setEditTitle(session.title);
  }

  async function saveEdit(id: string) {
    if (!editTitle.trim()) {
      setEditingId(null);
      return;
    }
    
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title: editTitle } : s));
    setEditingId(null);
    
    try {
      await fetch(`/api/chat/sessions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: editTitle })
      });
    } catch (err) {
      console.error("Failed to rename", err);
    }
  }

  return (
    <div style={{
      width: '260px',
      borderRight: '1px solid var(--border-light)',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--surface)'
    }}>
      <div style={{ padding: '16px' }}>
        <NavLink 
          to="/chat"
          end
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '12px',
            background: 'var(--surface-hover)',
            borderRadius: '8px',
            color: 'var(--ink)',
            textDecoration: 'none',
            fontWeight: 500
          }}
        >
          <Plus size={18} />
          New Chat
        </NavLink>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 16px 16px' }}>
        <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Recent
        </div>
        {loading ? (
          <div style={{ fontSize: '14px', color: 'var(--text-light)' }}>Loading...</div>
        ) : sessions.length === 0 ? (
          <div style={{ fontSize: '14px', color: 'var(--text-light)' }}>No previous chats</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {sessions.map((session) => (
              <div key={session.id} className="chat-sidebar-item-wrapper" style={{ position: 'relative' }}>
                <NavLink
                  to={`/chat/${session.id}`}
                  style={({ isActive }) => ({
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    textDecoration: 'none',
                    fontSize: '14px',
                    color: isActive ? 'var(--ink)' : 'var(--text-light)',
                    background: isActive ? 'var(--surface-hover)' : 'transparent',
                    position: 'relative'
                  })}
                  className="chat-sidebar-item"
                >
                  <MessageSquare size={16} style={{ flexShrink: 0 }} />
                  
                  {editingId === session.id ? (
                    <input 
                      autoFocus
                      value={editTitle}
                      onChange={e => setEditTitle(e.target.value)}
                      onBlur={() => saveEdit(session.id)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') saveEdit(session.id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      style={{
                        flex: 1,
                        background: 'var(--surface)',
                        border: '1px solid var(--border-light)',
                        color: 'var(--ink)',
                        borderRadius: '4px',
                        padding: '2px 6px',
                        outline: 'none',
                        fontSize: '14px'
                      }}
                      onClick={e => e.preventDefault()}
                    />
                  ) : (
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                      {session.title || 'New Chat'}
                    </span>
                  )}

                  {editingId !== session.id && (
                    <div className="chat-sidebar-item-actions" style={{ display: 'flex', gap: '4px' }}>
                      <button 
                        onClick={(e) => startEdit(e, session)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-light)', cursor: 'pointer', padding: '4px' }}
                        title="Rename"
                      >
                        <Pencil size={14} />
                      </button>
                      <button 
                        onClick={(e) => handleDelete(e, session.id)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--text-light)', cursor: 'pointer', padding: '4px' }}
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  )}
                </NavLink>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
