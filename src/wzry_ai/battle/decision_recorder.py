"""JSONL recorder for decision data collection."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any, Iterable

from wzry_ai.utils.logging_utils import get_logger

logger = get_logger(__name__)


class DecisionRecorder:
    """Best-effort recorder for future behavior cloning datasets."""

    def __init__(self, base_dir: str | Path | None = None, enabled=None):
        if base_dir is None:
            base_dir = os.environ.get("WZRY_DECISION_RECORD_DIR", "logs/decision_records")
        self.base_dir = Path(base_dir)
        self.enabled = enabled
        self._failure_count = 0

    def is_enabled(self) -> bool:
        if self.enabled is not None:
            return bool(self.enabled)
        value = os.environ.get("WZRY_DECISION_RECORDING", "0").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def record(
        self,
        *,
        state: Any,
        actions: Iterable[Any],
        executed_action: Any | None,
        selected_action: Any | None = None,
        fallback_action: Any | None = None,
        action_source: str = "rule",
        model_confidence: float | None = None,
        source: str = "rule_v1",
    ) -> None:
        if not self.is_enabled():
            return

        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now()
            event = {
                "schema_version": 1,
                "timestamp": now.isoformat(timespec="milliseconds"),
                "source": source,
                "action_source": action_source,
                "state": self._serialize(state),
                "actions": [self._serialize(action) for action in actions],
                "fallback_action": self._serialize(fallback_action),
                "selected_action": self._serialize(selected_action),
                "executed_action": self._serialize(executed_action),
                "model_confidence": model_confidence,
            }
            path = self.base_dir / f"{now:%Y-%m-%d}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
        except (OSError, TypeError, ValueError) as exc:
            self._failure_count += 1
            if self._failure_count == 1 or self._failure_count % 100 == 0:
                logger.warning(
                    "decision record failed (%s): %s",
                    self._failure_count,
                    exc,
                )
            else:
                logger.debug("decision record skipped: %s", exc)

    def _serialize(self, value: Any) -> Any:
        if value is None:
            return None
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, tuple):
            return [self._serialize(item) for item in value]
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._serialize(item) for key, item in value.items()}
        return value
