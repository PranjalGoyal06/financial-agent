export interface ModelConfig {
  id: string;
  provider: string;
  model: string;
  label: string;
  group: string;
}

export const AVAILABLE_MODELS: ModelConfig[] = [
  // Google Gemini
  {
    id: "gemini:gemini-3.6-flash",
    provider: "gemini",
    model: "gemini-3.6-flash",
    label: "Gemini 3.6 Flash",
    group: "Google Gemini",
  },
  {
    id: "gemini:gemini-3.5-flash-lite",
    provider: "gemini",
    model: "gemini-3.5-flash-lite",
    label: "Gemini 3.5 Flash Lite",
    group: "Google Gemini",
  },
  // Ollama Cloud
  {
    id: "ollama_cloud:gemma4:31b-cloud",
    provider: "ollama_cloud",
    model: "gemma4:31b-cloud",
    label: "Gemma 4 31B (Cloud)",
    group: "Ollama Cloud",
  },
  {
    id: "ollama_cloud:nemotron-3-super:cloud",
    provider: "ollama_cloud",
    model: "nemotron-3-super:cloud",
    label: "Nemotron 3 Super (Cloud)",
    group: "Ollama Cloud",
  },
  // Groq
  {
    id: "groq:llama-3.3-70b-versatile",
    provider: "groq",
    model: "llama-3.3-70b-versatile",
    label: "Groq (Llama 3.3 70B)",
    group: "Groq",
  },
  // Ollama Local
  {
    id: "ollama:qwen3.5:latest",
    provider: "ollama",
    model: "qwen3.5:latest",
    label: "Qwen 3.5 (Local)",
    group: "Ollama Local",
  },
];

export function getSelectedModelConfig(selectedId: string): ModelConfig {
  const found = AVAILABLE_MODELS.find((m) => m.id === selectedId);
  if (found) return found;

  // Fallback check by provider name
  const byProvider = AVAILABLE_MODELS.find((m) => m.provider === selectedId);
  if (byProvider) return byProvider;

  return AVAILABLE_MODELS[0];
}
