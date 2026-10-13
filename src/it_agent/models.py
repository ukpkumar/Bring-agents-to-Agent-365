from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TicketCategory(str, Enum):
    ACCESS = "access"
    IDENTITY = "identity"
    NETWORK = "network"
    DEVICE = "device"
    EMAIL = "email"
    SECURITY = "security"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionSafety(str, Enum):
    SAFE = "safe"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Ticket:
    id: str
    requester: str
    requester_email: str
    title: str
    description: str
    affected_service: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Ticket":
        required = ["id", "requester", "requester_email", "title", "description"]
        missing = [key for key in required if not data.get(key)]
        if missing:
            raise ValueError(f"Ticket is missing required fields: {', '.join(missing)}")
        return cls(
            id=str(data["id"]),
            requester=str(data["requester"]),
            requester_email=str(data["requester_email"]),
            title=str(data["title"]),
            description=str(data["description"]),
            affected_service=data.get("affected_service"),
        )


@dataclass(frozen=True)
class Classification:
    category: TicketCategory
    severity: Severity
    risk_score: int
    rationale: str


@dataclass(frozen=True)
class PlannedAction:
    name: str
    safety: ActionSafety
    reason: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    name: str
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    ticket_id: str
    classification: Classification
    actions: list[PlannedAction]
    tool_results: list[ToolResult]
    response: str
    telemetry_events: int

