export type ChatRole = "user" | "assistant" | "system";

export type ConfidenceTier = "low" | "medium" | "high" | "insufficient" | string;

export type DataQualityStatus =
  | "good"
  | "ok"
  | "limited"
  | "degraded"
  | "stale"
  | "critical_failure"
  | string;

export type Claim = {
  text: string;
  claim_type: "data_supported" | "inference" | "assumption" | string;
  evidence_ids: string[];
};

export type Citation = {
  evidence_id: string;
  title?: string;
  source?: string;
  url?: string;
  excerpt?: string;
};

export type ChatResponseType =
  | "plain_chat"
  | "recommendation"
  | "news_digest"
  | "comparison"
  | "portfolio_snapshot"
  | "technical_analysis"
  | "fundamental_analysis"
  | "quant_analysis"
  | "research_run_status"
  | "insufficient_data"
  | "error"
  | string;

export type RetrievalDisclosure = {
  deterministic?: string[];
  llm_planned?: string[];
  unavailable?: Array<{
    item?: string;
    reason?: string;
  }>;
};

export type ToolCallTrace = {
  tool_call_id?: string;
  name: string;
  args?: Record<string, unknown>;
  status: "started" | "completed" | "failed" | string;
  summary?: string;
  timestamp?: string;
};

export type ReactiveResponseEnvelope = {
  graph_run_id: string;
  response_type: ChatResponseType;
  bubble_text: string;
  card_payload: Record<string, unknown> | null;
  confidence_tier: ConfidenceTier;
  data_quality: DataQualityStatus;
  retrieval_disclosure: RetrievalDisclosure;
  evidence_ids: string[];
  assumptions: string[];
  principle_conflicts: string[];
  advisory_only: boolean;
};

export type ChatResponseCard = {
  recommendation: string;
  confidence_tier: ConfidenceTier;
  data_quality: DataQualityStatus;
  summary: string;
  bear_case: string;
  expected_drawdown?: string | null;
  key_risks: string[];
  portfolio_impact?: string;
  upside_case?: string | null;
  no_action_case?: string;
  assumptions: string[];
  principle_conflicts?: string[];
  claims?: Claim[];
  next_steps?: string[];
  citations: Citation[];
};

export type ChatMessage = {
  message_id: string;
  session_id: string;
  role: ChatRole;
  content: string;
  created_at: string;
  graph_run_id?: string | null;
  metadata?: {
    response?: ReactiveResponseEnvelope;
    final_response?: Partial<ChatResponseCard> & Record<string, unknown>;
    recommendation?: Record<string, unknown>;
    data_quality?: Record<string, unknown>;
    validation_errors?: string[];
    reasoning_trace?: unknown[];
    tool_calls?: ToolCallTrace[];
    [key: string]: unknown;
  };
};

export type ChatMessageHistoryResponse = {
  session_id: string;
  messages: ChatMessage[];
};

export type ChatNodeCompleteEvent = {
  event: "node_complete";
  data: {
    node_name: string;
    timestamp: string;
  };
};

export type ChatToolCallEvent = {
  event: "tool_call";
  data: ToolCallTrace;
};

export type ChatFinalResponseEvent = {
  event: "final_response";
  data: {
    message: ChatMessage;
  };
};

export type ChatErrorEvent = {
  event: "error";
  data: {
    message: string;
    timestamp?: string;
  };
};

export type ChatStreamEvent =
  | ChatNodeCompleteEvent
  | ChatToolCallEvent
  | ChatFinalResponseEvent
  | ChatErrorEvent;

export type Holding = {
  holding_id: string;
  user_id?: string;
  portfolio_import_id?: string | null;
  raw_ticker: string;
  canonical_ticker: string;
  exchange: string;
  asset_class: string;
  quantity: number;
  avg_buy_price: number;
  currency: string;
  purchase_date: string;
  created_at: string;
};

export type PortfolioQuote = {
  holding_id: string;
  ticker: string;
  canonical_ticker: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  position_value: number | null;
  position_day_pnl: number | null;
  currency: string;
  source: string;
  is_stale: boolean;
  error: string | null;
};

export type PortfolioValuation = {
  invested_amount: number;
  current_value: number | null;
  unrealized_pnl: number | null;
  today_pnl: number | null;
  priced_holdings: number;
  unpriced_holdings: number;
  is_stale: boolean;
  currency: string;
  quotes: PortfolioQuote[];
};

export type PortfolioImportResponse = {
  import_id: string;
  source_filename?: string | null;
  imported: number;
  rejected: Array<{
    row: Record<string, string | number | null | undefined>;
    reason: string;
  }>;
  holdings: Holding[];
};

export type ArtifactSummary = {
  artifact_id: string;
  title: string;
  filename: string;
  artifact_type: string;
  created_at: string;
  preview: string;
};

export type ArtifactDetail = ArtifactSummary & {
  content: string;
};
