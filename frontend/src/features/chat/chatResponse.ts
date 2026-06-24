import type { ChatMessage, ChatResponseCard, Citation, DataQualityStatus } from "../../lib/types";

const EMPTY_CARD: ChatResponseCard = {
  recommendation: "Insufficient Data",
  confidence_tier: "insufficient",
  data_quality: "limited",
  summary: "The assistant did not return a structured summary.",
  bear_case: "No bear case was returned.",
  expected_drawdown: null,
  key_risks: [],
  portfolio_impact: "Portfolio impact was not provided.",
  upside_case: null,
  no_action_case: "No no-action case was provided.",
  assumptions: [],
  principle_conflicts: [],
  claims: [],
  next_steps: [],
  citations: [],
};

function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
}

function parseJsonObject(content: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(content);
    return asRecord(parsed);
  } catch {
    return {};
  }
}

function citationsFromSources(sources: unknown): Citation[] {
  return asStringArray(sources).map((source) => ({
    evidence_id: source,
    title: source,
  }));
}

function citationsFromEvidencePack(value: unknown): Citation[] {
  const evidencePack = asRecord(value);
  const items = Array.isArray(evidencePack.items) ? evidencePack.items : [];

  return items
    .map((item) => asRecord(item))
    .map((item) => ({
      evidence_id: asString(item.evidence_id ?? item.id ?? item.document_id, "evidence"),
      title: asOptionalString(item.title ?? item.heading),
      source: asOptionalString(item.source ?? item.publisher),
      url: asOptionalString(item.url),
      excerpt: asOptionalString(item.excerpt ?? item.text ?? item.content),
    }))
    .filter((citation) => citation.evidence_id !== "evidence");
}

function dataQualityFromMetadata(message: ChatMessage, response: Record<string, unknown>): DataQualityStatus {
  const direct = asString(response.data_quality);
  if (direct) {
    return direct;
  }

  const responseQuality = asRecord(response.data_quality);
  const responseVerdict = asString(responseQuality.verdict);
  if (responseVerdict) {
    return responseVerdict;
  }

  const dataQuality = asRecord(message.metadata?.data_quality);
  return asString(dataQuality.verdict, EMPTY_CARD.data_quality);
}

export function normaliseChatResponse(message: ChatMessage): ChatResponseCard {
  const envelope = asRecord(message.metadata?.response);
  const cardPayload = asRecord(envelope.card_payload);
  const finalResponse = asRecord(message.metadata?.final_response);
  const recommendationMetadata = asRecord(message.metadata?.recommendation);
  const parsedContent = parseJsonObject(message.content);
  const response: Record<string, unknown> = {
    ...parsedContent,
    ...recommendationMetadata,
    ...finalResponse,
    ...cardPayload,
    confidence_tier:
      cardPayload.confidence_tier ??
      envelope.confidence_tier ??
      finalResponse.confidence_tier ??
      recommendationMetadata.confidence_tier,
    data_quality:
      cardPayload.data_quality ??
      envelope.data_quality ??
      finalResponse.data_quality,
  };

  const action = asString(response.recommendation ?? response.action, EMPTY_CARD.recommendation);
  const summary = asString(response.summary, message.content || EMPTY_CARD.summary);
  const sources = response.sources ?? response.citations;
  const evidenceCitations = citationsFromEvidencePack(response.evidence_pack);
  const sourceCitations = citationsFromSources(sources);
  const envelopeEvidence = asStringArray(envelope.evidence_ids).map((id) => ({
    evidence_id: id,
    title: id,
  }));

  return {
    recommendation: titleCase(action),
    confidence_tier: asString(
      response.confidence_tier ?? response.confidence,
      EMPTY_CARD.confidence_tier,
    ),
    data_quality: dataQualityFromMetadata(message, response),
    summary,
    bear_case: asString(response.bear_case, EMPTY_CARD.bear_case),
    expected_drawdown:
      response.expected_drawdown === null
        ? null
        : asOptionalString(response.expected_drawdown),
    key_risks: asStringArray(response.key_risks),
    portfolio_impact: asString(response.portfolio_impact, EMPTY_CARD.portfolio_impact),
    upside_case:
      response.upside_case === null ? null : asOptionalString(response.upside_case),
    no_action_case: asString(response.no_action_case, EMPTY_CARD.no_action_case),
    assumptions: asStringArray(response.assumptions),
    principle_conflicts: asStringArray(response.principle_conflicts),
    claims: Array.isArray(response.claims) ? (response.claims as ChatResponseCard["claims"]) : [],
    next_steps: asStringArray(response.next_steps),
    citations:
      evidenceCitations.length > 0
        ? evidenceCitations
        : sourceCitations.length > 0
          ? sourceCitations
          : envelopeEvidence,
  };
}
