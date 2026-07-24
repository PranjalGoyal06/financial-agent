import { useState, useEffect } from "react";
import { AVAILABLE_MODELS, getSelectedModelConfig } from "./models";

export function SettingsZone() {
  const [isDarkMode, setIsDarkMode] = useState(
    document.documentElement.getAttribute("data-theme") === "dark"
  );
  
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

  const [streamResponses, setStreamResponses] = useState(() => {
    return localStorage.getItem("paisa_stream_responses") !== "false";
  });

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem("paisa_theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem("paisa_theme", "light");
    }
  }, [isDarkMode]);

  useEffect(() => {
    const config = getSelectedModelConfig(selectedModelId);
    localStorage.setItem("paisa_llm_provider", config.provider);
    localStorage.setItem("paisa_llm_model", config.model);
  }, [selectedModelId]);

  useEffect(() => {
    localStorage.setItem("paisa_stream_responses", String(streamResponses));
  }, [streamResponses]);

  return (
    <div className="settings-zone">
      <div className="settings-header">
        <h1>Preferences</h1>
        <p>Customize your PAISA experience</p>
      </div>

      <div className="settings-grid">
        {/* Appearance Group */}
        <section className="settings-card">
          <div className="settings-card__icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
          </div>
          <div className="settings-card__content">
            <h3>Appearance</h3>
            <div className="setting-row">
              <div className="setting-info">
                <label>Dark Mode</label>
                <span>Toggle dark theme across the app</span>
              </div>
              <div className="toggle-switch">
                <input 
                  type="checkbox" 
                  id="dark-mode-toggle"
                  checked={isDarkMode}
                  onChange={(e) => setIsDarkMode(e.target.checked)}
                />
                <label htmlFor="dark-mode-toggle" className="toggle-slider"></label>
              </div>
            </div>
          </div>
        </section>

        {/* AI & Model Group */}
        <section className="settings-card">
          <div className="settings-card__icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
          </div>
          <div className="settings-card__content">
            <h3>AI Configuration</h3>
            
            <div className="setting-row">
              <div className="setting-info">
                <label>LLM Model & Provider</label>
                <span>Choose the model engine for chat</span>
              </div>
              <div className="custom-select-wrapper">
                <select 
                  className="custom-select"
                  value={selectedModelId}
                  onChange={(e) => setSelectedModelId(e.target.value)}
                >
                  <optgroup label="Google Gemini">
                    <option value="gemini:gemini-3.6-flash">Gemini 3.6 Flash</option>
                    <option value="gemini:gemini-3.5-flash-lite">Gemini 3.5 Flash Lite</option>
                  </optgroup>
                  <optgroup label="Ollama Cloud">
                    <option value="ollama_cloud:gemma4:31b-cloud">Gemma 4 31B (Cloud)</option>
                    <option value="ollama_cloud:nemotron-3-super:cloud">Nemotron 3 Super (Cloud)</option>
                  </optgroup>
                  <optgroup label="Groq">
                    <option value="groq:llama-3.3-70b-versatile">Groq (Llama 3.3 70B)</option>
                  </optgroup>
                  <optgroup label="Ollama Local">
                    <option value="ollama:qwen3.5:latest">Qwen 3.5 (Local)</option>
                  </optgroup>
                </select>
                <div className="select-arrow">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"></polyline></svg>
                </div>
              </div>
            </div>

            <div className="setting-row">
              <div className="setting-info">
                <label>Stream Responses</label>
                <span>Show text as it's generated</span>
              </div>
              <div className="toggle-switch">
                <input 
                  type="checkbox" 
                  id="stream-toggle"
                  checked={streamResponses}
                  onChange={(e) => setStreamResponses(e.target.checked)}
                />
                <label htmlFor="stream-toggle" className="toggle-slider"></label>
              </div>
            </div>
          </div>
        </section>

        {/* Danger Zone or Data Options */}
        <section className="settings-card settings-card--danger">
          <div className="settings-card__icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </div>
          <div className="settings-card__content">
            <h3>Data Management</h3>
            <div className="setting-row">
              <div className="setting-info">
                <label className="text-danger">Clear Local Data</label>
                <span>Reset all local preferences and history</span>
              </div>
              <button 
                className="btn btn--danger"
                onClick={() => {
                  if (confirm("Are you sure? This will clear all settings.")) {
                    localStorage.clear();
                    window.location.reload();
                  }
                }}
              >
                Reset Data
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
