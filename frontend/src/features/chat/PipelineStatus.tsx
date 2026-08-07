const PIPELINE_ORDER = [
  "load_context",
  "fetch_market_data",
  "semantic_retrieve",
  "validate_data_quality",
  "compress_context",
  "llm_reason",
  "parse_output",
  "compliance_check",
  "format_response",
];

function labelForNode(nodeName: string): string {
  return nodeName
    .replace(/^reactive\./, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function nextNodeAfter(nodeName: string | null): string | null {
  if (!nodeName) {
    return PIPELINE_ORDER[0];
  }

  const index = PIPELINE_ORDER.indexOf(nodeName);
  if (index === -1 || index === PIPELINE_ORDER.length - 1) {
    return null;
  }

  return PIPELINE_ORDER[index + 1];
}

type PipelineStatusProps = {
  isProcessing: boolean;
  completedNodes: string[];
  error?: string | null;
};

export function PipelineStatus({ isProcessing, completedNodes, error }: PipelineStatusProps) {
  const lastCompleted =
    completedNodes.length > 0 ? completedNodes[completedNodes.length - 1] : null;
  const runningNode = isProcessing ? nextNodeAfter(lastCompleted) : null;

  if (error) {
    return (
      <div className="chat-pipeline chat-pipeline--error" role="status">
        <span className="chat-pipeline__pulse" />
        <span>{error}</span>
      </div>
    );
  }

  if (!isProcessing) {
    return null;
  }

  return (
    <div className="chat-pipeline" role="status" aria-live="polite">
      <span className="chat-pipeline__pulse" />
      <span>
        {runningNode ? `Running ${labelForNode(runningNode)}` : "Finalising response"}
      </span>
      {lastCompleted ? (
        <span className="chat-pipeline__last">
          Completed {labelForNode(lastCompleted)}
        </span>
      ) : null}
    </div>
  );
}
