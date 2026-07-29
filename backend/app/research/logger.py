from __future__ import annotations

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Literal

from app.db import AsyncSessionLocal
from app.models import ResearchRunEventModel

logger = logging.getLogger(__name__)

# Module-level set to maintain strong references to background asyncio tasks
_BACKGROUND_TASKS: set[asyncio.Task] = set()


# Global dictionary of active SSE queues keyed by run_id
# Now supports multiple subscribers per run (Broadcasting)
_SSE_QUEUES: dict[str, list[asyncio.Queue]] = {}

# Global queue for sequential DB writes to guarantee chronological ordering
_DB_QUEUE = asyncio.Queue()
_DB_WORKER_TASK: asyncio.Task | None = None

def _ensure_global_db_worker() -> None:
    global _DB_WORKER_TASK
    if _DB_WORKER_TASK is None:
        try:
            loop = asyncio.get_running_loop()
            
            async def global_db_worker():
                while True:
                    task_data = await _DB_QUEUE.get()
                    if task_data is None:
                        break
                    logger_instance, event = task_data
                    await logger_instance._async_db_write(event)
                    
                    # Push to SSE Queues strictly AFTER DB write to prevent race conditions
                    queues = _SSE_QUEUES.get(logger_instance.run_id, [])
                    for q in queues:
                        try:
                            q.put_nowait(event)
                        except Exception as e:
                            logger.error(f"Failed to push to SSE queue: {e}")
                            
                    _DB_QUEUE.task_done()
                    
            _DB_WORKER_TASK = loop.create_task(global_db_worker())
            _BACKGROUND_TASKS.add(_DB_WORKER_TASK)
            _DB_WORKER_TASK.add_done_callback(_BACKGROUND_TASKS.discard)
        except RuntimeError:
            logger.error("No running event loop to start global DB worker")

# Global queue for sequential JSONL file writes
_FILE_QUEUE = asyncio.Queue()
_FILE_WORKER_TASK: asyncio.Task | None = None

def _ensure_global_file_worker() -> None:
    global _FILE_WORKER_TASK
    if _FILE_WORKER_TASK is None:
        try:
            loop = asyncio.get_running_loop()
            
            async def global_file_worker():
                while True:
                    task_data = await _FILE_QUEUE.get()
                    if task_data is None:
                        break
                    run_id, event = task_data
                    
                    def write_to_file():
                        log_dir = "logs/runs"
                        os.makedirs(log_dir, exist_ok=True)
                        filepath = os.path.join(log_dir, f"{run_id}.jsonl")
                        with open(filepath, "a", encoding="utf-8") as f:
                            f.write(json.dumps(event) + "\n")
                            
                    try:
                        await asyncio.to_thread(write_to_file)
                    except Exception as e:
                        logger.error(f"Failed to write to JSONL log for run {run_id}: {e}")
                            
                    _FILE_QUEUE.task_done()
                    
            _FILE_WORKER_TASK = loop.create_task(global_file_worker())
            _BACKGROUND_TASKS.add(_FILE_WORKER_TASK)
            _FILE_WORKER_TASK.add_done_callback(_BACKGROUND_TASKS.discard)
        except RuntimeError:
            logger.error("No running event loop to start global FILE worker")

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
                    created_at=datetime.fromisoformat(event_dict["timestamp"]),
                )
                session.add(db_event)
                await session.commit()
        except Exception as exc:
            logger.error(f"Failed writing Tier-1 research log for run {self.run_id} to DB: {exc}")

    def log_event(
        self,
        node: str,
        event_type: Literal["node_start", "node_complete", "node_skipped", "node_error", "llm_call", "api_traffic", "triage_gate", "drift_report", "exception", "run_completed", "run_failed", "run_cancelled"],
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

        # 2. Write to DB sequentially in the background (which then pushes to SSE)
        _ensure_global_db_worker()
        _DB_QUEUE.put_nowait((self, event))

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
        self.log_event(
            node,
            "exception",
            f"{exception.__class__.__name__}: {str(exception)}",
            payload={"traceback": traceback.format_exc(), "context": context or ""},
            level="ERROR",
            target=target,
        )
        self.log_event(
            node=node,
            event_type="node_error",
            summary=f"Node {node} failed",
            level="ERROR",
            target=target,
        )

    def log_debug(
        self,
        node: str,
        action: str,
        details: dict[str, Any] | None = None
    ) -> None:
        """Tier-2 logging: Writes heavy payloads to JSONL and sends a lightweight console event to SSE."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # 1. Write massive payload to JSONL file
        file_event = {
            "timestamp": timestamp,
            "run_id": self.run_id,
            "node": node,
            "event_type": "debug",
            "action": action,
            "details": details or {}
        }
        _ensure_global_file_worker()
        _FILE_QUEUE.put_nowait((self.run_id, file_event))
        
        # 2. Push lightweight console event to SSE Queue directly
        console_event = {
            "timestamp": timestamp,
            "run_id": self.run_id,
            "node": node,
            "event_type": "console",
            "summary": action,
            "level": "DEBUG",
            "payload": {}
        }
        queues = _SSE_QUEUES.get(self.run_id, [])
        for q in queues:
            try:
                q.put_nowait(console_event)
            except Exception as e:
                logger.error(f"Failed to push console event to SSE queue: {e}")


# Registry of active loggers per run_id to avoid redundant object creation
_LOGGERS: dict[str, ResearchRunLogger] = {}


def get_run_logger(run_id: str) -> ResearchRunLogger:
    """Retrieve or create a ResearchRunLogger instance for a specific run_id."""
    if run_id not in _LOGGERS:
        _LOGGERS[run_id] = ResearchRunLogger(run_id)
    return _LOGGERS[run_id]


def get_new_sse_queue(run_id: str) -> asyncio.Queue:
    """Create and register a new SSE Queue for a specific run_id subscription."""
    if run_id not in _SSE_QUEUES:
        _SSE_QUEUES[run_id] = []
    q = asyncio.Queue()
    _SSE_QUEUES[run_id].append(q)
    return q


def remove_sse_queue(run_id: str, q: asyncio.Queue) -> None:
    """Remove a specific subscriber queue."""
    if run_id in _SSE_QUEUES:
        try:
            _SSE_QUEUES[run_id].remove(q)
        except ValueError:
            pass
        if not _SSE_QUEUES[run_id]:
            _SSE_QUEUES.pop(run_id)


def cleanup_sse_queue(run_id: str) -> None:
    """Remove all SSE Queues for a run_id to free memory."""
    _SSE_QUEUES.pop(run_id, None)

