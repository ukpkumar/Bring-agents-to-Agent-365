from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .agent import ItHelpdeskAgent
from .models import Ticket


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the external IT helpdesk agent.")
    parser.add_argument("--ticket", required=True, help="Path to a JSON ticket file.")
    parser.add_argument("--approve", action="store_true", help="Approve actions marked approval_required.")
    args = parser.parse_args()

    ticket_path = Path(args.ticket)
    ticket = Ticket.from_dict(json.loads(ticket_path.read_text(encoding="utf-8")))
    result = ItHelpdeskAgent().handle_ticket(ticket, approved=args.approve)
    print(json.dumps(_json_safe(asdict(result)), indent=2, sort_keys=True))


def _json_safe(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value

