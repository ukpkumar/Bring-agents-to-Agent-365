from __future__ import annotations

from .models import ActionSafety, ToolResult
from .tool_registry import ToolDefinition, ToolRegistry


MOCK_USERS = {
    "alex@contoso.example": {
        "account_enabled": True,
        "mfa_registered": True,
        "mfa_locked": True,
        "device_compliant": True,
        "manager": "maya@contoso.example",
    },
    "sam@contoso.example": {
        "account_enabled": True,
        "mfa_registered": False,
        "mfa_locked": False,
        "device_compliant": False,
        "manager": "lee@contoso.example",
    },
}

MOCK_SERVICES = {
    "vpn": {"status": "degraded", "incident": "VPN-GW-1029 has elevated packet loss in UAE region."},
    "email": {"status": "healthy", "incident": None},
    "identity": {"status": "healthy", "incident": None},
}


def check_user_status(args: dict[str, object]) -> ToolResult:
    email = str(args["email"]).lower()
    user = MOCK_USERS.get(email)
    if not user:
        return ToolResult("check_user_status", False, f"No user record found for {email}.")
    return ToolResult("check_user_status", True, f"Found user state for {email}.", dict(user))


def check_service_health(args: dict[str, object]) -> ToolResult:
    service = str(args.get("service") or "identity").lower()
    state = MOCK_SERVICES.get(service)
    if not state:
        return ToolResult("check_service_health", False, f"No service health record found for {service}.")
    return ToolResult("check_service_health", True, f"{service} service status is {state['status']}.", dict(state))


def create_ticket_note(args: dict[str, object]) -> ToolResult:
    ticket_id = str(args["ticket_id"])
    note = str(args["note"])
    return ToolResult("create_ticket_note", True, f"Added note to ticket {ticket_id}.", {"note": note})


def reset_mfa(args: dict[str, object]) -> ToolResult:
    email = str(args["email"]).lower()
    return ToolResult("reset_mfa", True, f"MFA reset queued for {email}.", {"requires_user_reregistration": True})


def unlock_account(args: dict[str, object]) -> ToolResult:
    email = str(args["email"]).lower()
    return ToolResult("unlock_account", True, f"Account unlock queued for {email}.")


def quarantine_message(args: dict[str, object]) -> ToolResult:
    ticket_id = str(args["ticket_id"])
    return ToolResult("quarantine_message", True, f"Quarantine request recorded from ticket {ticket_id}.")


def default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition("check_user_status", "Read user identity and device posture.", ActionSafety.SAFE, check_user_status))
    registry.register(ToolDefinition("check_service_health", "Read mock service health.", ActionSafety.SAFE, check_service_health))
    registry.register(ToolDefinition("create_ticket_note", "Write a service desk ticket note.", ActionSafety.SAFE, create_ticket_note))
    registry.register(ToolDefinition("reset_mfa", "Reset a user's MFA registration.", ActionSafety.APPROVAL_REQUIRED, reset_mfa))
    registry.register(ToolDefinition("unlock_account", "Unlock a user account.", ActionSafety.APPROVAL_REQUIRED, unlock_account))
    registry.register(ToolDefinition("quarantine_message", "Quarantine a suspected phishing message.", ActionSafety.APPROVAL_REQUIRED, quarantine_message))
    return registry

