from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .agent import ItHelpdeskAgent
from .models import ActionSafety, Ticket


DEFAULT_MODEL = "gpt-4.1-mini"


def main() -> None:
    client = _openai_client()
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)

    print("External IT Helpdesk Agent with OpenAI conversation")
    print("Type an IT issue in natural language. Type /exit to quit.")
    print()

    while True:
        user_text = input("User: ").strip()
        if user_text.lower() in {"/exit", "exit", "quit"}:
            break
        if not user_text:
            continue

        ticket = _extract_ticket(client, model, user_text)
        result = ItHelpdeskAgent().handle_ticket(ticket, approved=False)

        if _has_pending_approval(result):
            print("Agent: I found one or more risky actions that require approval.")
            approval = input("Approve risky actions for this ticket? [y/N]: ").strip().lower()
            if approval == "y":
                result = ItHelpdeskAgent().handle_ticket(ticket, approved=True)

        answer = _explain_result(client, model, user_text, asdict(result))
        print(f"Agent: {answer}")
        print()


def _openai_client() -> Any:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set. In PowerShell, run: $env:OPENAI_API_KEY = \"your-key\"")
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError("OpenAI SDK is not installed. Run: pip install openai") from error
    return OpenAI()


def _extract_ticket(client: Any, model: str, user_text: str) -> Ticket:
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Convert the user's IT helpdesk request into a JSON ticket. "
                    "Return only valid JSON with these fields: id, requester, requester_email, "
                    "title, description, affected_service. "
                    "Use INC-CHAT plus the current UTC timestamp for id if no id is provided. "
                    "If requester is unknown, use End User. "
                    "If requester_email is unknown, use alex@contoso.example for demo purposes. "
                    "affected_service should be one short value such as identity, vpn, email, device, "
                    "finance-app, or knowledge-base."
                ),
            },
            {"role": "user", "content": user_text},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty ticket extraction response.")

    data = json.loads(content)
    data.setdefault("id", f"INC-CHAT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    data.setdefault("requester", "End User")
    data.setdefault("requester_email", "alex@contoso.example")
    data.setdefault("affected_service", "unknown")
    return Ticket.from_dict(data)


def _explain_result(client: Any, model: str, user_text: str, result: dict[str, Any]) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a concise IT helpdesk assistant. Explain the local IT agent result "
                    "in friendly language. Do not claim completed actions that were skipped. "
                    "If approval is required, say that clearly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Original user request:\n{user_text}\n\n"
                    f"Local agent result JSON:\n{json.dumps(result, indent=2, default=str)}"
                ),
            },
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty explanation response.")
    return content.strip()


def _has_pending_approval(result: Any) -> bool:
    approval_actions = {action.name for action in result.actions if action.safety == ActionSafety.APPROVAL_REQUIRED}
    skipped = {tool.name for tool in result.tool_results if not tool.success and tool.data.get("approval_required")}
    return bool(approval_actions & skipped)


if __name__ == "__main__":
    main()

