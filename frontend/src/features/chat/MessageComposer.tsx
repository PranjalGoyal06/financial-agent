import { FormEvent, useEffect, useState } from "react";

type SuggestedPrompt = {
  id: number;
  text: string;
};

type MessageComposerProps = {
  disabled?: boolean;
  suggestedPrompt?: SuggestedPrompt | null;
  onSubmit: (content: string) => void;
};

export function MessageComposer({
  disabled = false,
  suggestedPrompt = null,
  onSubmit,
}: MessageComposerProps) {
  const [content, setContent] = useState("");
  const canSubmit = content.trim().length > 0 && !disabled;

  useEffect(() => {
    if (suggestedPrompt?.text) {
      setContent(suggestedPrompt.text);
    }
  }, [suggestedPrompt]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    onSubmit(content.trim());
    setContent("");
  }

  return (
    <form className="chat-composer" onSubmit={handleSubmit}>
      <label htmlFor="chat-message-input">Message</label>
      <textarea
        id="chat-message-input"
        value={content}
        disabled={disabled}
        rows={3}
        placeholder="Ask the agent about risk, downside, allocation, evidence, or what to do next."
        onChange={(event) => setContent(event.target.value)}
      />
      <button type="submit" disabled={!canSubmit}>
        Send
      </button>
    </form>
  );
}
