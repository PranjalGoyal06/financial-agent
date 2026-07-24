import json
import logging
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent
from app.db import AsyncSessionLocal
from app.models import Artifact, AuditEventModel
from app.llm.provider import get_chat_model, get_structured_model
from app.create_artifact.state import CreateArtifactState
from app.create_artifact.schemas import ArtifactIntent, ArtifactCard
from app.compare.schemas import CardEnvelope
from app.graph import AGENT_TOOLS

logger = logging.getLogger(__name__)

async def interpret_request_node(state: CreateArtifactState, config: RunnableConfig) -> dict:
    llm = get_structured_model(ArtifactIntent, temperature=0.1)
    
    messages = state.get("messages", [])
    if not messages:
        raise ValueError("No messages in state")
        
    last_msg = messages[-1].content
    # Remove the command prefix
    if last_msg.startswith("/create-artifact"):
        last_msg = last_msg.replace("/create-artifact", "").strip()

    sys_prompt = """You are parsing a request to create a financial artifact (markdown document).
    Determine if the request requires fetching fresh market data/news, or if it can be fulfilled just by summarizing the existing conversation context.
    Also, generate a suitable title and filename.
    
    CRITICAL INSTRUCTION: You must call the provided tool/function to output the extracted JSON result. Do not output conversational text.
    """
    
    res = await llm.ainvoke([SystemMessage(content=sys_prompt), HumanMessage(content=last_msg)])
    return {"intent": res}

async def gather_evidence_node(state: CreateArtifactState, config: RunnableConfig) -> dict:
    intent = state.get("intent")
    if not intent or not intent.needs_fresh_grounding:
        return {"evidence_pack": {}}
        
    llm = get_chat_model(temperature=0.1, streaming=False)
    
    sys_prompt = """You are a financial research assistant gathering data for a report.
    Use your tools to execute the provided search queries and gather the necessary financial data.
    Do not write the final report, just gather the data using tools and output a summary of your findings.
    """
    
    agent = create_react_agent(llm, tools=AGENT_TOOLS, prompt=SystemMessage(content=sys_prompt))
    
    # Run the agent with the search queries
    queries = "\n".join([f"- {q}" for q in intent.search_queries])
    msg = f"Gather data for the following queries:\n{queries}"
    
    res = await agent.ainvoke({"messages": [HumanMessage(content=msg)]}, config)
    
    # Extract tool outputs or agent summary as the evidence pack
    last_message = res["messages"][-1].content
    return {"evidence_pack": {"agent_summary": last_message}}

async def generate_content_node(state: CreateArtifactState, config: RunnableConfig) -> dict:
    intent = state.get("intent")
    evidence_pack = state.get("evidence_pack", {})
    messages = state.get("messages", [])
    
    llm = get_chat_model(temperature=0.4, streaming=False)
    
    sys_prompt = f"""You are generating a markdown artifact titled '{intent.title}'.
    Format the output strictly as Markdown. Do not include markdown code block wrappers (like ```markdown), just output the raw markdown.
    """
    
    # Provide the context
    context_msg = "Here is the existing conversation context:\n"
    for m in messages[:-1]:  # Exclude the actual command
        if isinstance(m, HumanMessage):
            context_msg += f"User: {m.content}\n"
        elif isinstance(m, AIMessage):
            context_msg += f"Assistant: {m.content}\n"
            
    if evidence_pack:
        context_msg += "\nHere is fresh evidence gathered:\n" + str(evidence_pack)
        
    last_msg = messages[-1].content.replace("/create-artifact", "").strip()
    
    res = await llm.ainvoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=context_msg),
        HumanMessage(content=f"Please write the artifact for the request: {last_msg}")
    ])
    
    return {"markdown_content": res.content}

async def validate_citations_node(state: CreateArtifactState, config: RunnableConfig) -> dict:
    # In a full implementation, we'd extract [id] tags and check against the evidence pack.
    # For now, we'll just pass through.
    return {}

async def persist_file_node(state: CreateArtifactState, config: RunnableConfig) -> dict:
    intent = state.get("intent")
    markdown_content = state.get("markdown_content")
    request_id = state.get("request_id", "local_run")
    llm_provider = state.get("llm_provider", "default")
    llm_model = state.get("llm_model", "default")
    
    async with AsyncSessionLocal() as db:
        artifact = Artifact(
            source_type="chat_create",
            source_ref_id=request_id,
            title=intent.title,
            content_markdown=markdown_content,
            metadata_json=json.dumps({
                "filename": intent.filename,
                "evidence_pack_json": state.get("evidence_pack", {})
            }),
        )
        db.add(artifact)
        
        # Also log the audit event
        audit = AuditEventModel(
            request_id=request_id,
            command="create_artifact",
            model_provider=llm_provider,
            model_name=llm_model,
            run_mode="interactive",
            payload_json=json.dumps({"filename": intent.filename, "title": intent.title}),
        )
        db.add(audit)
        
        await db.commit()
        
    return {}

async def render_card_node(state: CreateArtifactState, config: RunnableConfig) -> dict:
    intent = state.get("intent")
    markdown_content = state.get("markdown_content")
    request_id = state.get("request_id", "local_run")
    llm_provider = state.get("llm_provider", "default")
    llm_model = state.get("llm_model", "default")
    
    preview = markdown_content[:200] + "..." if len(markdown_content) > 200 else markdown_content
    
    card = ArtifactCard(
        filename=intent.filename,
        title=intent.title,
        content_preview=preview,
        full_content_ref=f"db://research_artifacts/{request_id}",
        created_at=datetime.utcnow().isoformat(),
        evidence_ids=[],
        source_context="fresh_analysis" if intent.needs_fresh_grounding else "conversation_summary"
    )
    
    envelope = CardEnvelope(
        command="create_artifact",
        request_id=request_id,
        generated_at=datetime.utcnow().isoformat(),
        model_provider=llm_provider,
        model_name=llm_model,
        run_mode="interactive",
        payload=card.model_dump()
    )
    
    return {"envelope": envelope}
