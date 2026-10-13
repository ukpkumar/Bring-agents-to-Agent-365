from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent365 import Agent365Config, OptionalAgent365SdkBridge


class Agent365TelemetryAdapter:
    """Telemetry adapter that logs locally and can forward events to an Agent 365 SDK bridge."""

    def __init__(self, log_path: Path | None = None, config: Agent365Config | None = None) -> None:
        self.config = config or Agent365Config.from_env()
        self.log_path = log_path or self.config.log_path
        self.sdk_bridge = OptionalAgent365SdkBridge(self.config)
        self.event_count = 0

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_name": event_name,
            "agent_name": self.config.agent_name,
            "agent_id": self.config.agent_id,
            "tenant_id": self.config.tenant_id,
            "payload": payload,
        }
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, sort_keys=True) + "\n")
        self.sdk_bridge.emit_event(event)
        self.event_count += 1
