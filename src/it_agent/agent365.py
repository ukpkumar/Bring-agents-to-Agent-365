from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class Agent365SdkClient(Protocol):
    def emit_event(self, event: dict[str, Any]) -> None:
        ...


@dataclass(frozen=True)
class Agent365Config:
    agent_name: str
    agent_id: str | None
    tenant_id: str | None
    enabled: bool
    sdk_module: str
    log_path: Path

    @classmethod
    def from_env(cls) -> "Agent365Config":
        return cls(
            agent_name=os.getenv("AGENT365_AGENT_NAME", "external-it-helpdesk-agent"),
            agent_id=os.getenv("AGENT365_AGENT_ID"),
            tenant_id=os.getenv("AGENT365_TENANT_ID"),
            enabled=_env_bool("AGENT365_ENABLED"),
            sdk_module=os.getenv("AGENT365_SDK_MODULE", "agent365"),
            log_path=Path(os.getenv("AGENT365_LOG_PATH", "logs/agent365-telemetry.jsonl")),
        )

    def validate_for_sdk(self) -> None:
        missing = []
        if not self.agent_id:
            missing.append("AGENT365_AGENT_ID")
        if not self.tenant_id:
            missing.append("AGENT365_TENANT_ID")
        if missing:
            raise RuntimeError(f"Agent 365 SDK mode is enabled, but missing: {', '.join(missing)}")


class OptionalAgent365SdkBridge:
    def __init__(self, config: Agent365Config) -> None:
        self.config = config
        self._client: Agent365SdkClient | None = None
        if self.config.enabled:
            self.config.validate_for_sdk()
            self._client = self._load_client()

    def emit_event(self, event: dict[str, Any]) -> None:
        if self._client is not None:
            self._client.emit_event(event)

    def _load_client(self) -> Agent365SdkClient:
        try:
            module = importlib.import_module(self.config.sdk_module)
        except ImportError as error:
            raise RuntimeError(
                f"Agent 365 SDK mode is enabled, but Python module '{self.config.sdk_module}' is not installed. "
                "Install the Agent 365 SDK package or set AGENT365_SDK_MODULE to your SDK adapter module."
            ) from error

        if hasattr(module, "create_client"):
            client = module.create_client(agent_id=self.config.agent_id, tenant_id=self.config.tenant_id)
            if not hasattr(client, "emit_event"):
                raise RuntimeError("Agent 365 SDK client returned by create_client does not expose emit_event(event).")
            return client

        if hasattr(module, "emit_event"):
            return _ModuleFunctionClient(module)

        raise RuntimeError(
            f"Agent 365 SDK module '{self.config.sdk_module}' must expose create_client(...) or emit_event(event)."
        )


class _ModuleFunctionClient:
    def __init__(self, module: Any) -> None:
        self.module = module

    def emit_event(self, event: dict[str, Any]) -> None:
        self.module.emit_event(event)


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

