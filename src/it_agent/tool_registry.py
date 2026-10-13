from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import ActionSafety, ToolResult


ToolHandler = Callable[[dict[str, Any]], ToolResult]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    safety: ActionSafety
    handler: ToolHandler


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool is not registered: {name}")
        return self._tools[name]

    def run(self, name: str, args: dict[str, Any]) -> ToolResult:
        return self.get(name).handler(args)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

