from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Base directory for research log files
LOGS_DIR = Path("logs/research")


class ResearchRunLogger:
    """System-level (Tier-1) logger for a deep research run.
    
    Writes structured JSON Lines (.jsonl) events to `logs/research/{run_id}.jsonl`.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.log_file_path = LOGS_DIR / f"{run_id}.jsonl"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure the logs directory exists."""
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Could not create research logs directory {LOGS_DIR}: {e}")

    def log_event(
        self,
        node: str,
        event_type: Literal["node_start", "node_complete", "llm_call", "api_traffic", "triage_gate", "drift_report", "exception"],
        summary: str,
        payload: dict[str, Any] | None = None,
        level: Literal["INFO", "WARNING", "ERROR", "DEBUG"] = "INFO",
    ) -> None:
        """Write a structured event to the run's JSONL log file."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "node": node,
            "level": level,
            "event_type": event_type,
            "summary": summary,
            "payload": payload or {},
        }

        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as exc:
            logger.error(f"Failed writing Tier-1 research log for run {self.run_id}: {exc}")

    def log_llm_call(
        self,
        node: str,
        model_name: str,
        prompt_preview: str,
        response_preview: str,
        latency_ms: float | None = None,
        status: Literal["SUCCESS", "FAILED", "FALLBACK"] = "SUCCESS",
        metadata: dict[str, Any] | None = None,
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
        )

    def log_api_traffic(
        self,
        node: str,
        provider: str,
        target_or_query: str,
        items_count_or_status: Any,
        latency_ms: float | None = None,
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
        )

    def log_exception(self, node: str, exception: Exception, context: str = "") -> None:
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
        )


# Registry of active loggers per run_id to avoid redundant object creation
_LOGGERS: dict[str, ResearchRunLogger] = {}


def get_run_logger(run_id: str) -> ResearchRunLogger:
    """Retrieve or create a ResearchRunLogger instance for a specific run_id."""
    if run_id not in _LOGGERS:
        _LOGGERS[run_id] = ResearchRunLogger(run_id)
    return _LOGGERS[run_id]


def read_run_logs(run_id: str) -> list[dict[str, Any]]:
    """Reads and parses the JSONL log file for a run_id."""
    file_path = LOGS_DIR / f"{run_id}.jsonl"
    if not file_path.exists():
        return []

    events = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
    except Exception as exc:
        logger.error(f"Error reading Tier-1 log file for run {run_id}: {exc}")
    return events
