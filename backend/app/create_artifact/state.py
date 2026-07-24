from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from app.create_artifact.schemas import ArtifactIntent, ArtifactCard


def merge_messages(left: list[BaseMessage], right: list[BaseMessage] | None) -> list[BaseMessage]:
    if not right:
        return left
    return left + right


class CreateArtifactState(TypedDict):
    messages: Annotated[list[BaseMessage], merge_messages]
    request_id: str
    llm_provider: str
    llm_model: str
    
    # Intent parsing
    intent: ArtifactIntent | None
    
    # Evidence gathering
    evidence_pack: dict | None
    
    # Generation
    markdown_content: str | None
    
    # Final Output
    envelope: ArtifactCard | None
    error: str | None
