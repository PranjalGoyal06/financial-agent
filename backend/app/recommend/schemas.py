from pydantic import BaseModel, Field

class RecommendIntent(BaseModel):
    ticker: str = Field(..., description="The stock ticker symbol the user wants a recommendation for. (e.g. HDFCBANK, RELIANCE)")

class RecommendationCard(BaseModel):
    ticker: str
    recommendation: str
    rationale: str
    confidence_score: float | None = None
    based_on_prior_research: bool = False
    run_id: str | None = None

class RecommendEnvelope(BaseModel):
    type: str = "recommendation_card"
    card: RecommendationCard
