from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from app.db import AsyncSessionLocal
from app.models import ResearchRunEventModel

logger = logging.getLogger(__name__)


# Global dictionary of active SSE queues keyed by run_id
_SSE_QUEUES: dict[str, asyncio.Queue] = {}


class ResearchRunLogger:
    """System-level (Tier-1) logger for a deep research run.
    
    Writes structured events to the database and pushes to an active SSE Queue.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id

    async def _async_db_write(self, event_dict: dict[str, Any]) -> None:
        try:
            async with AsyncSessionLocal() as session:
                db_event = ResearchRunEventModel(
                    run_id=event_dict["run_id"],
                    node=event_dict["node"],
                    target=event_dict.get("target"),
                    event_type=event_dict["event_type"],
                    level=event_dict["level"],
                    summary=event_dict["summary"],
                    payload_json=event_dict["payload"],
                )
                session.add(db_event)
                await session.commit()
        except Exception as exc:
            logger.error(f"Failed writing Tier-1 research log for run {self.run_id} to DB: {exc}")

    def log_event(
        self,
        node: str,
        event_type: Literal["node_start", "node_complete", "llm_call", "api_traffic", "triage_gate", "drift_report", "exception", "run_completed", "run_failed"],
        summary: str,
        payload: dict[str, Any] | None = None,
        level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO",
        target: str | None = None,
    ) -> None:
        """Write a structured event to the run's DB table and SSE queue."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "node": node,
            "target": target,
            "level": level,
            "event_type": event_type,
            "summary": summary,
            "payload": payload or {},
        }

        # 1. Push to SSE Queue if exists
        queue = _SSE_QUEUES.get(self.run_id)
        if queue is not None:
            try:
                queue.put_nowait(event)
            except Exception as e:
                logger.error(f"Failed to push event to SSE queue for run {self.run_id}: {e}")

        # 2. Write to DB asynchronously in the background
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._async_db_write(event))
        except RuntimeError:
            # If no running loop, we can't write to DB in the background like this.
            # This shouldn't happen during a FastAPI request/background task.
            logger.error(f"No running event loop to write DB event for run {self.run_id}")

    def log_llm_call(
        self,
        node: str,
        model_name: str,
        prompt_preview: str,
        response_preview: str,
        latency_ms: float | None = None,
        status: Literal["SUCCESS", "FAILED", "FALLBACK"] = "SUCCESS",
        metadata: dict[str, Any] | None = None,
        target: str | None = None,
    ) -> None:
        """Log an internal LLM call trace."""
        payload = {
            "model_name": model_name,
            "prompt_preview": prompt_preview[:500] if prompt_preview else "",
            "response_preview": response_preview[:500] if response_preview else "",
            "latency_ms": latency_ms,
            "status": status,
        }
        if metadata:
            payload.update(metadata)
            
        level = "WARNING" if status == "FALLBACK" else ("ERROR" if status == "FAILED" else "INFO")
        self.log_event(
            node=node,
            event_type="llm_call",
            summary=f"LLM Call ({model_name}) -> {status}",
            payload=payload,
            level=level,
            target=target,
        )

    def log_api_traffic(
        self,
        node: str,
        provider: str,
        target_or_query: str,
        items_count_or_status: Any,
        latency_ms: float | None = None,
        target: str | None = None,
    ) -> None:
        """Log market data or search engine API traffic."""
        payload = {
            "provider": provider,
            "target_or_query": target_or_query,
            "items_count_or_status": items_count_or_status,
            "latency_ms": latency_ms,
        }
        self.log_event(
            node=node,
            event_type="api_traffic",
            summary=f"API Call [{provider}] for '{target_or_query}'",
            payload=payload,
            level="INFO",
            target=target,
        )

    def log_exception(self, node: str, exception: Exception, context: str = "", target: str | None = None) -> None:
        """Log an exception trace."""
        payload = {
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": context,
        }
        self.log_event(
            node=node,
            event_type="exception",
            summary=f"Exception in node {node}: {exception}",
            payload=payload,
            level="ERROR",
            target=target,
        )


# Registry of active loggers per run_id to avoid redundant object creation
_LOGGERS: dict[str, ResearchRunLogger] = {}


def get_run_logger(run_id: str) -> ResearchRunLogger:
    """Retrieve or create a ResearchRunLogger instance for a specific run_id."""
    if run_id not in _LOGGERS:
        _LOGGERS[run_id] = ResearchRunLogger(run_id)
    return _LOGGERS[run_id]


def get_sse_queue(run_id: str) -> asyncio.Queue:
    """Retrieve or create an SSE Queue for a specific run_id."""
    if run_id not in _SSE_QUEUES:
        _SSE_QUEUES[run_id] = asyncio.Queue()
    return _SSE_QUEUES[run_id]


def cleanup_sse_queue(run_id: str) -> None:
    """Remove the SSE Queue for a run_id to free memory."""
    _SSE_QUEUES.pop(run_id, None)

