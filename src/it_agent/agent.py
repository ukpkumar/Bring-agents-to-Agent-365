from __future__ import annotations

from .models import ActionSafety, AgentResult, Classification, PlannedAction, Severity, Ticket, TicketCategory, ToolResult
from .telemetry import Agent365TelemetryAdapter
from .tool_registry import ToolRegistry
from .tools import default_registry


class ItHelpdeskAgent:
    def __init__(self, registry: ToolRegistry | None = None, telemetry: Agent365TelemetryAdapter | None = None) -> None:
        self.registry = registry or default_registry()
        self.telemetry = telemetry or Agent365TelemetryAdapter()

    def handle_ticket(self, ticket: Ticket, approved: bool = False) -> AgentResult:
        self.telemetry.emit("ticket.received", {"ticket_id": ticket.id, "requester": ticket.requester_email})

        classification = self._classify(ticket)
        self.telemetry.emit(
            "ticket.classified",
            {
                "ticket_id": ticket.id,
                "category": classification.category.value,
                "severity": classification.severity.value,
                "risk_score": classification.risk_score,
            },
        )

        actions = self._plan(ticket, classification)
        tool_results = self._execute(ticket, actions, approved)
        response = self._compose_response(classification, actions, tool_results, approved)

        self.telemetry.emit("ticket.completed", {"ticket_id": ticket.id, "tool_results": len(tool_results)})
        return AgentResult(ticket.id, classification, actions, tool_results, response, self.telemetry.event_count)

    def _classify(self, ticket: Ticket) -> Classification:
        text = f"{ticket.title} {ticket.description} {ticket.affected_service or ''}".lower()

        if any(term in text for term in ["phish", "malware", "suspicious", "compromised"]):
            return Classification(TicketCategory.SECURITY, Severity.HIGH, 85, "Potential security incident indicators found.")
        if any(term in text for term in ["mfa", "authenticator", "locked out", "sign in", "login", "password"]):
            return Classification(TicketCategory.IDENTITY, Severity.MEDIUM, 55, "Identity or authentication issue.")
        if any(term in text for term in ["vpn", "network", "latency", "connectivity"]):
            return Classification(TicketCategory.NETWORK, Severity.MEDIUM, 45, "Network access or VPN issue.")
        if any(term in text for term in ["device", "laptop", "compliance", "intune"]):
            return Classification(TicketCategory.DEVICE, Severity.MEDIUM, 50, "Device health or compliance issue.")
        if any(term in text for term in ["access", "permission", "role", "application"]):
            return Classification(TicketCategory.ACCESS, Severity.MEDIUM, 60, "Application access request.")
        if any(term in text for term in ["email", "outlook", "mailbox"]):
            return Classification(TicketCategory.EMAIL, Severity.LOW, 30, "Email productivity issue.")
        return Classification(TicketCategory.UNKNOWN, Severity.LOW, 20, "No strong category signal found.")

    def _plan(self, ticket: Ticket, classification: Classification) -> list[PlannedAction]:
        base_note = PlannedAction(
            "create_ticket_note",
            ActionSafety.SAFE,
            "Document agent triage decision for IT analyst review.",
            {"ticket_id": ticket.id, "note": f"Classified as {classification.category.value}; severity {classification.severity.value}."},
        )

        if classification.category == TicketCategory.IDENTITY:
            return [
                PlannedAction("check_user_status", ActionSafety.SAFE, "Verify account and MFA state.", {"email": ticket.requester_email}),
                PlannedAction("check_service_health", ActionSafety.SAFE, "Check identity service health.", {"service": "identity"}),
                PlannedAction("reset_mfa", ActionSafety.APPROVAL_REQUIRED, "MFA reset changes user authentication state.", {"email": ticket.requester_email}),
                base_note,
            ]
        if classification.category == TicketCategory.NETWORK:
            return [
                PlannedAction("check_service_health", ActionSafety.SAFE, "Check VPN service health.", {"service": "vpn"}),
                base_note,
            ]
        if classification.category == TicketCategory.SECURITY:
            return [
                PlannedAction("check_user_status", ActionSafety.SAFE, "Check reporter identity context.", {"email": ticket.requester_email}),
                PlannedAction("quarantine_message", ActionSafety.APPROVAL_REQUIRED, "Quarantine affects mailbox content and requires analyst approval.", {"ticket_id": ticket.id}),
                base_note,
            ]
        if classification.category == TicketCategory.DEVICE:
            return [
                PlannedAction("check_user_status", ActionSafety.SAFE, "Check device compliance posture.", {"email": ticket.requester_email}),
                base_note,
            ]
        return [base_note]

    def _execute(self, ticket: Ticket, actions: list[PlannedAction], approved: bool) -> list[ToolResult]:
        results: list[ToolResult] = []
        for action in actions:
            if action.safety == ActionSafety.APPROVAL_REQUIRED and not approved:
                result = ToolResult(action.name, False, "Skipped because approval was not provided.", {"approval_required": True})
                results.append(result)
                self.telemetry.emit("tool.skipped", {"ticket_id": ticket.id, "tool": action.name, "reason": "approval_required"})
                continue

            tool = self.registry.get(action.name)
            if action.safety != tool.safety:
                raise ValueError(f"Action safety mismatch for {action.name}: planned {action.safety}, registry {tool.safety}")

            self.telemetry.emit("tool.invocation.started", {"ticket_id": ticket.id, "tool": action.name, "safety": action.safety.value})
            result = self.registry.run(action.name, action.args)
            results.append(result)
            self.telemetry.emit("tool.invocation.completed", {"ticket_id": ticket.id, "tool": action.name, "success": result.success})
        return results

    def _compose_response(
        self,
        classification: Classification,
        actions: list[PlannedAction],
        results: list[ToolResult],
        approved: bool,
    ) -> str:
        blocked = [action.name for action in actions if action.safety == ActionSafety.APPROVAL_REQUIRED and not approved]
        successful = [result.name for result in results if result.success]
        response = (
            f"Ticket classified as {classification.category.value}/{classification.severity.value}. "
            f"Completed: {', '.join(successful) if successful else 'none'}."
        )
        if blocked:
            response += f" Waiting for approval before running: {', '.join(blocked)}."
        return response

