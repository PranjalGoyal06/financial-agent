import React, { useEffect, useState, useRef } from "react";
import { Plus, Search, Trash2, Edit2, X, Check, BarChart2 } from "lucide-react";

export type Watchlist = { id: string; name: string; slug: string; type: string };

type StockResult = {
  symbol: string;
  name: string;
  exchange: string;
};

export function WatchlistsView() {
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [items, setItems] = useState<string[]>([]);
  const [newWlName, setNewWlName] = useState("");
  
  // Edit & Delete states
  const [editingWlId, setEditingWlId] = useState<string | null>(null);
  const [editingWlName, setEditingWlName] = useState("");

  // Search states
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<StockResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchWatchlists();
    
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchWatchlists = () => {
    fetch("/api/watchlists")
      .then(r => {
        if (!r.ok) throw new Error("Failed to load watchlists");
        return r.json();
      })
      .then(d => {
        setWatchlists(d.watchlists || []);
        if (d.watchlists && d.watchlists.length > 0 && !selectedId) {
          setSelectedId(d.watchlists[0].id);
        }
      })
      .catch(e => console.error(e));
  };

  useEffect(() => {
    if (selectedId) {
      fetch(`/api/watchlists/${selectedId}/items`)
        .then(r => {
          if (!r.ok) throw new Error("Failed to load items");
          return r.json();
        })
        .then(d => setItems(d.tickers || []))
        .catch(e => console.error(e));
    } else {
      setItems([]);
    }
  }, [selectedId]);

  // Debounced Search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setShowDropdown(false);
      return;
    }
    const timer = setTimeout(() => {
      setIsSearching(true);
      fetch(`/api/search/stocks?q=${encodeURIComponent(searchQuery)}`)
        .then(r => r.json())
        .then(d => {
          setSearchResults(d);
          setShowDropdown(true);
        })
        .catch(e => console.error(e))
        .finally(() => setIsSearching(false));
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWlName.trim()) return;
    try {
      const res = await fetch("/api/watchlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newWlName.trim() })
      });
      if (res.ok) {
        const wl = await res.json();
        setWatchlists([...watchlists, wl]);
        setNewWlName("");
        setSelectedId(wl.id);
      }
    } catch (err: any) {
      alert("Network error: " + err.message);
    }
  };

  const handleRename = async (id: string) => {
    if (!editingWlName.trim()) return;
    try {
      const res = await fetch(`/api/watchlists/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: editingWlName.trim() })
      });
      if (res.ok) {
        setWatchlists(watchlists.map(w => w.id === id ? { ...w, name: editingWlName.trim() } : w));
        setEditingWlId(null);
      }
    } catch (err: any) {
      alert("Network error: " + err.message);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this watchlist?")) return;
    try {
      const res = await fetch(`/api/watchlists/${id}`, { method: "DELETE" });
      if (res.ok) {
        setWatchlists(watchlists.filter(w => w.id !== id));
        if (selectedId === id) setSelectedId(watchlists[0]?.id || null);
      }
    } catch (err: any) {
      alert("Network error: " + err.message);
    }
  };

  const handleAddItem = async (ticker: string) => {
    if (!selectedId) return;
    if (items.includes(ticker)) {
      setSearchQuery("");
      setShowDropdown(false);
      return;
    }
    try {
      const res = await fetch(`/api/watchlists/${selectedId}/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker })
      });
      if (res.ok) {
        setItems([...items, ticker].sort());
        setSearchQuery("");
        setShowDropdown(false);
      }
    } catch (err: any) {
      alert("Network error: " + err.message);
    }
  };

  const handleRemove = async (ticker: string) => {
    if (!selectedId) return;
    const res = await fetch(`/api/watchlists/${selectedId}/items/${ticker}`, { method: "DELETE" });
    if (res.ok) {
      setItems(items.filter(i => i !== ticker));
    }
  };

  const activeWatchlist = watchlists.find(w => w.id === selectedId);

  return (
    <div style={{ display: "flex", gap: "24px", height: "calc(100vh - 160px)" }}>
      {/* Sidebar */}
      <div style={{ 
        width: "280px", 
        background: "var(--surface)", 
        borderRadius: "12px", 
        border: "1px solid var(--border-color)", 
        display: "flex",
        flexDirection: "column",
        overflow: "hidden"
      }}>
        <div style={{ padding: "20px", borderBottom: "1px solid var(--border-color)" }}>
          <h3 style={{ margin: 0, color: "var(--text-secondary)", fontSize: "13px", textTransform: "uppercase", letterSpacing: "0.5px", fontWeight: 600 }}>My Watchlists</h3>
        </div>
        
        <div style={{ flex: 1, overflowY: "auto", padding: "12px" }}>
          {watchlists.map(w => (
            <div 
              key={w.id} 
              onClick={() => { if (editingWlId !== w.id) setSelectedId(w.id); }}
              style={{ 
                padding: "12px", 
                cursor: "pointer", 
                background: selectedId === w.id ? "var(--surface-hover)" : "transparent",
                border: selectedId === w.id ? "1px solid var(--border-color)" : "1px solid transparent",
                borderRadius: "8px",
                marginBottom: "4px",
                color: selectedId === w.id ? "var(--text-primary)" : "var(--text-secondary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "all 0.2s ease",
                fontWeight: selectedId === w.id ? 600 : 400
              }}
              onMouseEnter={(e) => {
                if (selectedId !== w.id) e.currentTarget.style.background = "var(--surface-sunken)";
                const actions = e.currentTarget.querySelector('.wl-actions');
                if (actions) (actions as HTMLElement).style.opacity = '1';
              }}
              onMouseLeave={(e) => {
                if (selectedId !== w.id) e.currentTarget.style.background = "transparent";
                const actions = e.currentTarget.querySelector('.wl-actions');
                if (actions) (actions as HTMLElement).style.opacity = '0';
              }}
            >
              {editingWlId === w.id ? (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%" }}>
                  <input 
                    autoFocus
                    value={editingWlName}
                    onChange={e => setEditingWlName(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === "Enter") handleRename(w.id);
                      if (e.key === "Escape") setEditingWlId(null);
                    }}
                    style={{ flex: 1, background: "var(--bg)", border: "1px solid var(--text-primary)", color: "var(--text-primary)", padding: "4px 8px", borderRadius: "4px", fontSize: "14px" }}
                  />
                  <Check size={16} style={{ cursor: "pointer", color: "var(--green)" }} onClick={(e) => { e.stopPropagation(); handleRename(w.id); }} />
                  <X size={16} style={{ cursor: "pointer", color: "var(--text-tertiary)" }} onClick={(e) => { e.stopPropagation(); setEditingWlId(null); }} />
                </div>
              ) : (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", overflow: "hidden" }}>
                    <BarChart2 size={16} style={{ opacity: 0.7, flexShrink: 0 }} />
                    <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {w.name} {w.type === "portfolio" && <span style={{ opacity: 0.5, fontSize: "11px", fontWeight: 400, marginLeft: "4px", border: "1px solid var(--border-color)", padding: "2px 4px", borderRadius: "4px" }}>AUTO</span>}
                    </span>
                  </div>
                  
                  {w.type !== "portfolio" && (
                    <div className="wl-actions" style={{ display: "flex", gap: "8px", opacity: 0, transition: "opacity 0.2s" }}>
                      <Edit2 size={14} style={{ color: "var(--text-tertiary)", cursor: "pointer" }} onClick={(e) => { e.stopPropagation(); setEditingWlId(w.id); setEditingWlName(w.name); }} />
                      <Trash2 size={14} style={{ color: "var(--red)", cursor: "pointer" }} onClick={(e) => handleDelete(w.id, e)} />
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>

        <div style={{ padding: "16px", borderTop: "1px solid var(--border-color)", background: "var(--surface-sunken)" }}>
          <form onSubmit={handleCreate} style={{ display: "flex", gap: "8px" }}>
            <input 
              value={newWlName} 
              onChange={e => setNewWlName(e.target.value)}
              placeholder="Create watchlist..."
              style={{ flex: 1, padding: "10px", background: "var(--bg)", border: "1px solid var(--border-color)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "13px" }}
            />
            <button type="submit" disabled={!newWlName.trim()} style={{ padding: "10px", background: newWlName.trim() ? "var(--text-primary)" : "var(--surface)", color: "var(--bg)", borderRadius: "8px", border: "none", cursor: newWlName.trim() ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center", transition: "background 0.2s" }}>
              <Plus size={18} />
            </button>
          </form>
        </div>
      </div>
      
      {/* Main Content Area */}
      <div style={{ 
        flex: 1, 
        background: "var(--surface)", 
        borderRadius: "12px", 
        border: "1px solid var(--border-color)", 
        display: "flex",
        flexDirection: "column",
        overflow: "hidden"
      }}>
        {selectedId ? (
          <>
            <div style={{ padding: "24px 32px", borderBottom: "1px solid var(--border-color)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: "24px", fontWeight: 600, color: "var(--text-primary)" }}>{activeWatchlist?.name}</h2>
                <div style={{ fontSize: "13px", color: "var(--text-tertiary)", marginTop: "4px" }}>
                  {items.length} {items.length === 1 ? "instrument" : "instruments"}
                </div>
              </div>

              {activeWatchlist?.type !== "portfolio" && (
                <div ref={searchRef} style={{ position: "relative", width: "320px" }}>
                  <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
                    <Search size={16} style={{ position: "absolute", left: "12px", color: "var(--text-tertiary)" }} />
                    <input 
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      onFocus={() => setShowDropdown(true)}
                      placeholder="Search and add instruments..."
                      style={{ 
                        width: "100%", 
                        padding: "10px 12px 10px 36px", 
                        background: "var(--surface-sunken)", 
                        border: "1px solid var(--border-color)", 
                        borderRadius: "8px", 
                        color: "var(--text-primary)", 
                        fontSize: "14px",
                        outline: "none",
                        transition: "border-color 0.2s"
                      }}
                      onFocusCapture={(e) => e.currentTarget.style.borderColor = "var(--text-primary)"}
                      onBlurCapture={(e) => e.currentTarget.style.borderColor = "var(--border-color)"}
                    />
                  </div>
                  
                  {/* Autocomplete Dropdown */}
                  {showDropdown && searchQuery.trim().length > 0 && (
                    <div style={{ 
                      position: "absolute", 
                      top: "calc(100% + 8px)", 
                      left: 0, 
                      right: 0, 
                      background: "var(--surface)", 
                      border: "1px solid var(--border-color)", 
                      borderRadius: "8px", 
                      boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.3)",
                      maxHeight: "300px",
                      overflowY: "auto",
                      zIndex: 10
                    }}>
                      {isSearching ? (
                        <div style={{ padding: "16px", textAlign: "center", color: "var(--text-tertiary)", fontSize: "13px" }}>Searching...</div>
                      ) : searchResults.length > 0 ? (
                        <div style={{ padding: "8px 0" }}>
                          {searchResults.map(res => (
                            <div 
                              key={res.symbol}
                              onClick={() => handleAddItem(res.symbol)}
                              style={{ 
                                padding: "10px 16px", 
                                cursor: "pointer", 
                                display: "flex", 
                                justifyContent: "space-between", 
                                alignItems: "center",
                                transition: "background 0.2s"
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.background = "var(--surface-hover)"}
                              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                            >
                              <div style={{ display: "flex", flexDirection: "column" }}>
                                <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "14px" }}>{res.symbol}</span>
                                <span style={{ color: "var(--text-secondary)", fontSize: "12px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "200px" }}>{res.name}</span>
                              </div>
                              <span style={{ fontSize: "11px", color: "var(--text-tertiary)", border: "1px solid var(--border-color)", padding: "2px 6px", borderRadius: "4px" }}>
                                {res.exchange}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ padding: "16px", textAlign: "center", color: "var(--text-tertiary)", fontSize: "13px" }}>No instruments found</div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            <div style={{ padding: "32px", overflowY: "auto", flex: 1 }}>
              {items.length === 0 ? (
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-tertiary)" }}>
                  <BarChart2 size={48} style={{ opacity: 0.2, marginBottom: "16px" }} />
                  <p style={{ margin: 0, fontSize: "16px" }}>This watchlist is empty</p>
                  {activeWatchlist?.type !== "portfolio" && (
                    <p style={{ margin: "8px 0 0 0", fontSize: "14px", opacity: 0.7 }}>Search for instruments above to add them.</p>
                  )}
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "16px", alignContent: "flex-start" }}>
                  {items.map(t => (
                    <div 
                      key={t} 
                      className="ticker-card"
                      style={{ 
                        padding: "16px", 
                        background: "var(--surface-sunken)", 
                        borderRadius: "12px", 
                        border: "1px solid var(--border-color)", 
                        display: "flex", 
                        justifyContent: "space-between",
                        alignItems: "center",
                        transition: "all 0.2s ease",
                        position: "relative",
                        overflow: "hidden"
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.transform = "translateY(-2px)";
                        e.currentTarget.style.borderColor = "var(--text-secondary)";
                        const btn = e.currentTarget.querySelector('.remove-btn');
                        if (btn) (btn as HTMLElement).style.opacity = '1';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.transform = "translateY(0)";
                        e.currentTarget.style.borderColor = "var(--border-color)";
                        const btn = e.currentTarget.querySelector('.remove-btn');
                        if (btn) (btn as HTMLElement).style.opacity = '0';
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        <span style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "16px" }}>{t}</span>
                        <span style={{ color: "var(--text-tertiary)", fontSize: "12px", marginTop: "2px" }}>Equity</span>
                      </div>
                      
                      {activeWatchlist?.type !== "portfolio" && (
                        <button 
                          className="remove-btn"
                          onClick={() => handleRemove(t)}
                          style={{ 
                            background: "var(--surface)", 
                            border: "1px solid var(--border-color)", 
                            color: "var(--text-secondary)", 
                            width: "32px", 
                            height: "32px", 
                            borderRadius: "50%", 
                            display: "flex", 
                            alignItems: "center", 
                            justifyContent: "center",
                            cursor: "pointer",
                            opacity: 0,
                            transition: "all 0.2s ease",
                            position: "absolute",
                            right: "12px"
                          }}
                          onMouseEnter={(e) => { e.currentTarget.style.color = "var(--red)"; e.currentTarget.style.borderColor = "var(--red)"; }}
                          onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-secondary)"; e.currentTarget.style.borderColor = "var(--border-color)"; }}
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-tertiary)" }}>
            <BarChart2 size={48} style={{ opacity: 0.2, marginBottom: "16px" }} />
            <p style={{ margin: 0, fontSize: "16px" }}>Select a watchlist from the sidebar</p>
          </div>
        )}
      </div>
    </div>
  );
}
