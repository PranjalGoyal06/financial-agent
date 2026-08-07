from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from app.agents.reactive.graph import (
    BUILD_EVIDENCE_PACK,
    COMPLIANCE_CHECK,
    DATA_QUALITY_GATE,
    EXECUTE_RETRIEVAL,
    FINAL_REASONING,
    FORMAT_RESPONSE,
    INITIALISE_TURN,
    LOAD_BASELINE_CONTEXT,
    NODE_FUNCTIONS,
    PARSE_VALIDATE_OUTPUT,
    PERSIST_TURN,
    PLAN_RETRIEVAL,
    VALIDATE_RETRIEVAL_PLAN,
    route_after_data_quality,
    route_after_plan_validation,
)
from app.agents.reactive.schemas import FinalResponse
from app.agents.reactive.state import ReactiveState
from app.agents.simple_tool_agent import run_simple_tool_agent
from app.config import settings
from app.db.repositories.chat_repository import (
    DEFAULT_CHAT_REPOSITORY,
    ChatMessageRecord,
    ChatRepository,
    ChatSessionRecord,
)
from app.schemas.api import (
    ChatMessageCreateRequest,
    ChatMessageHistoryResponse,
    ChatMessageResponse,
    ChatSessionCreateRequest,
    ChatSessionCreateResponse,
    ChatSessionListResponse,
    ChatSessionUpdateRequest,
)

router = APIRouter(prefix="/chat", tags=["chat"])
chat_repository: ChatRepository = DEFAULT_CHAT_REPOSITORY


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if hasattr(model, "dict"):
        return model.dict()
    return dict(model)


def _sse(event: str, data: dict[str, Any]) -> str:
    payload = json.dumps(
        {"event": event, "data": data}, default=_json_default, separators=(",", ":")
    )
    return f"event: {event}\ndata: {payload}\n\n"


def _session_response(session: ChatSessionRecord) -> ChatSessionCreateResponse:
    return ChatSessionCreateResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message_at=session.last_message_at,
        message_count=session.message_count,
        metadata=session.metadata,
    )


def _message_response(message: ChatMessageRecord) -> ChatMessageResponse:
    return ChatMessageResponse(
        message_id=message.message_id,
        session_id=message.session_id,
        role=message.role,  # type: ignore[arg-type]
        content=message.content,
        created_at=message.created_at,
        graph_run_id=message.graph_run_id,
        metadata=message.metadata,
    )


def _get_session(session_id: str) -> ChatSessionRecord:
    session = chat_repository.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found."
        )
    return session


def _append_message(
    *,
    session_id: str,
    role: str,
    content: str,
    graph_run_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ChatMessageRecord:
    return chat_repository.append_message(
        session_id=session_id,
        role=role,
        content=content,
        graph_run_id=graph_run_id,
        metadata=metadata,
    )


def _title_from_message(content: str) -> str:
    cleaned = " ".join(content.strip().split())
    if len(cleaned) <= 56:
        return cleaned or "New chat"
    return f"{cleaned[:53].rstrip()}..."


def _maybe_title_session(session: ChatSessionRecord, content: str) -> None:
    if session.message_count > 0:
        return
    if session.title and session.title not in {"New chat", "Portfolio conversation"}:
        return
    chat_repository.update_session(
        session.session_id,
        title=_title_from_message(content),
    )


def _initial_state(
    session: ChatSessionRecord, request: ChatMessageCreateRequest
) -> ReactiveState:
    recent_messages = [
        {
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        for message in chat_repository.list_messages(session.session_id)[-6:]
    ]
    user_id = request.user_id or session.user_id
    return {
        "session_id": session.session_id,
        "graph_run_id": "",
        "user_id": user_id,
        "user_query": request.content,
        "user_profile": {"user_id": user_id},
        "portfolio": {},
        "watchlist": [],
        "principles": [],
        "investment_principles": [],
        "recent_chat_context": recent_messages,
        "data_freshness_status": {},
        "retrieval_plan": {},
        "retrieval_disclosure": {},
        "relevant_tickers": [],
        "market_data": {},
        "retrieved_chunks": [],
        "evidence_pack": [],
        "prior_recommendations": [],
        "data_quality": {},
        "data_quality_verdict": "ok",
        "data_quality_passed": True,
        "data_quality_flags": [],
        "compressed_context": "",
        "principle_conflicts": [],
        "raw_analysis": "",
        "llm_raw_output": "",
        "parsed_output": {},
        "recommendation": {},
        "validation_errors": [],
        "final_response": {},
        "audit_events": [],
        "messages": [{"role": "user", "content": request.content}],
        "reasoning_trace": [],
    }


def _merge_state(state: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if key in {"messages", "reasoning_trace", "audit_events"} and isinstance(
            value, list
        ):
            existing = state.setdefault(key, [])
            if isinstance(existing, list):
                existing.extend(value)
                continue
        state[key] = value


def _normalise_graph_update(update: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    if not isinstance(update, dict):
        return

    for node_name, node_update in update.items():
        if node_name == "__end__":
            continue
        if isinstance(node_update, dict):
            yield node_name, node_update
        else:
            yield node_name, {}


def _run_manual_graph(
    initial_state: ReactiveState,
) -> Iterator[tuple[str, dict[str, Any]]]:
    state: dict[str, Any] = dict(initial_state)
    node_name = INITIALISE_TURN
    while True:
        update = NODE_FUNCTIONS[node_name](state)  # type: ignore[arg-type]
        update_dict = dict(update or {})
        _merge_state(state, update_dict)
        yield node_name, update_dict

        if node_name == INITIALISE_TURN:
            node_name = LOAD_BASELINE_CONTEXT
        elif node_name == LOAD_BASELINE_CONTEXT:
            node_name = PLAN_RETRIEVAL
        elif node_name == PLAN_RETRIEVAL:
            node_name = VALIDATE_RETRIEVAL_PLAN
        elif node_name == VALIDATE_RETRIEVAL_PLAN:
            node_name = route_after_plan_validation(state)  # type: ignore[assignment]
        elif node_name == EXECUTE_RETRIEVAL:
            node_name = BUILD_EVIDENCE_PACK
        elif node_name == BUILD_EVIDENCE_PACK:
            node_name = DATA_QUALITY_GATE
        elif node_name == DATA_QUALITY_GATE:
            node_name = route_after_data_quality(state)  # type: ignore[assignment]
        elif node_name == FINAL_REASONING:
            node_name = PARSE_VALIDATE_OUTPUT
        elif node_name == PARSE_VALIDATE_OUTPUT:
            node_name = COMPLIANCE_CHECK
        elif node_name == COMPLIANCE_CHECK:
            node_name = FORMAT_RESPONSE
        elif node_name == FORMAT_RESPONSE:
            node_name = PERSIST_TURN
        elif node_name == PERSIST_TURN:
            break
        else:
            break


def _stream_graph_updates(
    initial_state: ReactiveState,
) -> Iterator[tuple[str, dict[str, Any]]]:
    yield from _run_manual_graph(initial_state)


def _content_from_final_state(state: dict[str, Any]) -> str:
    final_response = state.get("final_response")
    if isinstance(final_response, dict) and final_response:
        if isinstance(final_response.get("bubble_text"), str):
            return final_response["bubble_text"]
        return json.dumps(final_response, default=_json_default)

    raw_analysis = state.get("raw_analysis") or state.get("llm_raw_output")
    if isinstance(raw_analysis, str) and raw_analysis.strip():
        return raw_analysis

    return "I could not produce a validated response for this message."


async def _message_event_stream(
    session: ChatSessionRecord,
    request: ChatMessageCreateRequest,
    graph_run_id: str,
) -> AsyncIterator[str]:
    if settings.chat_orchestration == "simple_llm_tools":
        async for event in _simple_message_event_stream(session, request, graph_run_id):
            yield event
        return

    state: dict[str, Any] = dict(_initial_state(session, request))
    state["graph_run_id"] = graph_run_id

    try:
        for node_name, update in _stream_graph_updates(state):  # type: ignore[arg-type]
            _merge_state(state, update)
            yield _sse(
                "node_complete",
                {
                    "node_name": node_name,
                    "timestamp": _utc_now().isoformat(),
                },
            )

        content = _content_from_final_state(state)
        final_response = state.get("final_response", {})
        if isinstance(final_response, dict) and final_response:
            response_metadata = dict(final_response)
        else:
            fallback = FinalResponse(
                response_type="error",
                bubble_text=content,
                card_payload={"message": content, "recoverable": True},
                confidence_tier="insufficient",
                data_quality="critical_failure",
                retrieval_disclosure={},
                evidence_ids=[],
                assumptions=[],
                principle_conflicts=[],
                graph_run_id=graph_run_id,
            )
            response_metadata = fallback.model_dump(mode="json")
        assistant_message = _append_message(
            session_id=session.session_id,
            role="assistant",
            content=content,
            graph_run_id=graph_run_id,
            metadata={
                "response": response_metadata,
                "validation_errors": state.get("validation_errors", []),
                "reasoning_trace": state.get("reasoning_trace", []),
            },
        )
        yield _sse(
            "final_response",
            {
                "message": _dump_model(_message_response(assistant_message)),
            },
        )
    except Exception as exc:  # noqa: BLE001
        yield _sse(
            "error",
            {
                "message": str(exc),
                "timestamp": _utc_now().isoformat(),
            },
        )


async def _simple_message_event_stream(
    session: ChatSessionRecord,
    request: ChatMessageCreateRequest,
    graph_run_id: str,
) -> AsyncIterator[str]:
    try:
        for event in run_simple_tool_agent(
            user_id=request.user_id or session.user_id,
            user_query=request.content,
            graph_run_id=graph_run_id,
        ):
            event_name = str(event.get("event", ""))
            event_data = event.get("data", {})
            if not isinstance(event_data, dict):
                event_data = {}

            if event_name in {"node_complete", "tool_call"}:
                payload = dict(event_data)
                payload.setdefault("timestamp", _utc_now().isoformat())
                yield _sse(event_name, payload)
                continue

            if event_name == "final":
                content = str(event_data.get("content") or "")
                response_metadata = event_data.get("response")
                if not isinstance(response_metadata, dict):
                    response_metadata = FinalResponse(
                        response_type="error",
                        bubble_text=(
                            content or "Simple tool mode did not return a response."
                        ),
                        card_payload={
                            "message": content
                            or "Simple tool mode did not return a response.",
                            "recoverable": True,
                        },
                        confidence_tier="insufficient",
                        data_quality="critical_failure",
                        retrieval_disclosure={},
                        evidence_ids=[],
                        assumptions=[],
                        principle_conflicts=[],
                        graph_run_id=graph_run_id,
                    ).model_dump(mode="json")
                assistant_message = _append_message(
                    session_id=session.session_id,
                    role="assistant",
                    content=content or str(response_metadata.get("bubble_text", "")),
                    graph_run_id=graph_run_id,
                    metadata={
                        "response": response_metadata,
                        "tool_calls": event_data.get("tool_calls", []),
                        "validation_errors": event_data.get("validation_errors", []),
                        "reasoning_trace": [],
                    },
                )
                yield _sse(
                    "final_response",
                    {
                        "message": _dump_model(_message_response(assistant_message)),
                    },
                )
                return
    except Exception as exc:  # noqa: BLE001
        yield _sse(
            "error",
            {
                "message": str(exc),
                "timestamp": _utc_now().isoformat(),
            },
        )


@router.post(
    "/sessions",
    response_model=ChatSessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    request: ChatSessionCreateRequest | None = None,
) -> ChatSessionCreateResponse:
    request = request or ChatSessionCreateRequest()
    session = chat_repository.create_session(
        user_id=request.user_id,
        title=request.title or "New chat",
        metadata=request.metadata,
    )
    return _session_response(session)


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_sessions(
    user_id: str = Query(default="demo-user", min_length=1),
) -> ChatSessionListResponse:
    sessions = chat_repository.list_sessions(user_id)
    return ChatSessionListResponse(
        sessions=[_session_response(session) for session in sessions]
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionCreateResponse)
def get_session(session_id: str) -> ChatSessionCreateResponse:
    return _session_response(_get_session(session_id))


@router.patch("/sessions/{session_id}", response_model=ChatSessionCreateResponse)
def update_session(
    session_id: str, request: ChatSessionUpdateRequest
) -> ChatSessionCreateResponse:
    session = chat_repository.update_session(
        session_id,
        title=request.title,
        metadata=request.metadata,
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found."
        )
    return _session_response(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str) -> Response:
    if not chat_repository.delete_session(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found."
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessions/{session_id}/messages")
def create_message(
    session_id: str,
    request: ChatMessageCreateRequest,
) -> StreamingResponse:
    session = _get_session(session_id)
    _maybe_title_session(session, request.content)
    graph_run_id = str(uuid4())
    _append_message(
        session_id=session.session_id,
        role="user",
        content=request.content,
        graph_run_id=graph_run_id,
        metadata=request.metadata,
    )
    return StreamingResponse(
        _message_event_stream(session, request, graph_run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageHistoryResponse,
)
def list_messages(session_id: str) -> ChatMessageHistoryResponse:
    _get_session(session_id)
    messages = chat_repository.list_messages(session_id)
    return ChatMessageHistoryResponse(
        session_id=session_id,
        messages=[_message_response(message) for message in messages],
    )
