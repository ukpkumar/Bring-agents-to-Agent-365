---
title: "Lab Guide: Bringing a Third-Party Agent to Microsoft Agent 365"
description: "A practical walkthrough for registering, instrumenting, and validating a custom or third-party agent with Microsoft Agent 365."
date: 2026-10-13
tags:
  - Microsoft Agent 365
  - Entra Agent ID
  - OpenTelemetry
  - AI Agents
  - Governance
---

# Lab Guide: Bringing a Third-Party Agent to Microsoft Agent 365

AI agents are moving quickly from experiments to business-critical systems. That creates a new operational question for IT and security teams: how do we discover, govern, observe, and secure agents that were not originally built on Microsoft platforms?

Microsoft Agent 365 helps answer that question by bringing agents into a unified enterprise control plane. In this post, I walk through a practical step-by-step process for bringing a third-party or custom agent into Agent 365.

## Why bring agents to Microsoft Agent 365?

Organizations are beginning to use agents across IT, sales, finance, HR, engineering, and customer operations. Many of those agents are built outside Microsoft platforms, often using open-source frameworks, third-party SDKs, or custom code. Without a control plane, these agents can become difficult for IT and security teams to manage.

Bringing an agent to Agent 365 helps answer practical enterprise questions:

- Who owns this agent?
- What is the agent allowed to do?
- What tools can it call?
- What data can it access?
- Is the agent active, stale, or ownerless?
- Can security teams investigate its activity?
- Can risky actions be reviewed, blocked, or governed?
- Can the agent be managed through existing Microsoft Entra, Defender, Purview, and Microsoft 365 admin processes?

The goal is not just to make the agent work. The goal is to make the agent acceptable for enterprise deployment.

Agent 365 gives organizations a way to:

- Register agents as known enterprise assets
- Represent agents with Microsoft Entra-backed identities
- Apply governance and lifecycle controls
- Observe runtime activity and tool usage
- Support security investigation through Microsoft Defender
- Add data protection and compliance controls through Microsoft Purview
- Govern access to Microsoft 365 tools through Work IQ MCP capabilities

In short, Agent 365 helps move agents from isolated demos to governed, observable, and manageable enterprise systems.

The example scenario is an external IT helpdesk triage agent. The agent classifies support tickets, checks mock IT systems, separates safe actions from approval-required actions, and can use OpenAI for conversation. The same pattern applies to agents built with OpenAI Agents SDK, LangChain, CrewAI, LlamaIndex, custom Python or Node.js runtimes, and other third-party frameworks.

## Exercise overview

This walkthrough has two parts:

1. Build a simple local third-party agent.
2. Register and instrument that agent with Microsoft Agent 365.

The local agent is intentionally simple. It does not depend on Microsoft 365 data, real ticketing systems, or production identity. That makes it a safe starting point for learning the onboarding flow.

For this lab, the local agent is named:

```text
External IT Helpdesk Agent
```

Its project/package name is:

```text
external-it-agent
```

The agent simulates a common IT operations scenario: a helpdesk analyst receives a support ticket, and the agent triages it before a human takes action.

The agent does five things:

1. Reads a helpdesk ticket from JSON.
2. Classifies the issue, such as identity, VPN, device, email, access, or security.
3. Assigns severity and a basic risk score.
4. Plans actions using mock IT tools.
5. Blocks risky actions unless approval is explicitly provided.

Example use cases:

| Ticket type | What the agent does |
|---|---|
| MFA lockout | Checks user status and identity service health; recommends MFA reset only with approval |
| VPN issue | Checks mock VPN service health |
| Phishing report | Classifies as security and requires approval before quarantine-style actions |
| Device compliance issue | Checks mock user/device posture |
| Application access request | Classifies as access and records a triage note |

The agent has two types of actions:

| Action type | Meaning | Example |
|---|---|---|
| Safe action | Read-only or low-risk action the agent can run automatically | Check user status, check service health |
| Approval-required action | Action that changes user state, mailbox state, or security posture | Reset MFA, unlock account, quarantine message |

This behavior is important for Agent 365 because it demonstrates enterprise-friendly agent design:

- The agent has a clear owner and purpose.
- The agent has predictable tools.
- Risky actions are gated.
- Activity can be observed.
- The same design can later be governed through Agent 365.

In this lab, the mock tools do not touch real systems. They are intentionally local and safe.

The agent will:

- Accept a helpdesk ticket as JSON
- Classify the ticket
- Assign severity and risk
- Plan safe and approval-required actions
- Run mock IT tools
- Write local telemetry
- Later connect to Agent 365 registration and observability

## How to follow this lab

The lab uses several tools, and each command must be run in the right place. Unless a step says otherwise, use **Windows PowerShell**.

| Command type | Where to run it | What it affects |
|---|---|---|
| `mkdir`, `New-Item`, `python` | Inside the local agent project folder | The sample agent code on your machine |
| `pip install ...` | Inside the local agent project folder, ideally in a virtual environment | Python packages for this agent |
| `dotnet tool install --global ...` | Anywhere in PowerShell | Installs a user-level CLI tool |
| `winget install ...` | Anywhere in PowerShell | Installs a Windows application |
| `az login`, `az account show` | Anywhere in PowerShell | Signs you in to Azure and selects the subscription/tenant |
| `a365 ...` | Inside the local agent project folder | Registers/configures this specific agent project |
| `gh skill add ...` | Anywhere in PowerShell | Installs coding-assistant skills for your user profile |

Recommended local folder for this lab:

```text
C:\Agent365Labs\external-it-agent
```

If you use a different folder, replace that path in the commands.

## Part 1: Build a local third-party agent

Start by creating a small Python project. Run these commands in **Windows PowerShell**. This creates a local project only; it is not connected to Agent 365 yet.

```powershell
mkdir C:\Agent365Labs
cd C:\Agent365Labs
mkdir external-it-agent
cd external-it-agent
mkdir src\it_agent
mkdir examples
mkdir tests
```

Create a basic project file. Run this in **PowerShell** from the project root:

```powershell
New-Item pyproject.toml
notepad pyproject.toml
```

Paste the following content into `pyproject.toml`, then save and close Notepad:

```toml
[project]
name = "external-it-agent"
version = "0.1.0"
description = "External IT helpdesk agent sample for Agent 365 onboarding."
requires-python = ">=3.10"
dependencies = [
  "openai>=1.0.0",
]
```

### Define the ticket and result models

Create the file. Run this in **PowerShell** from the project root:

```powershell
New-Item src\it_agent\models.py
notepad src\it_agent\models.py
```

The agent needs a ticket input, a classification result, planned actions, and tool results.

Paste the following Python code into `src\it_agent\models.py`, then save and close Notepad:

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TicketCategory(str, Enum):
    IDENTITY = "identity"
    NETWORK = "network"
    DEVICE = "device"
    EMAIL = "email"
    SECURITY = "security"
    ACCESS = "access"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionSafety(str, Enum):
    SAFE = "safe"
    APPROVAL_REQUIRED = "approval_required"


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
        return cls(**{key: data.get(key) for key in cls.__dataclass_fields__})


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
```

### Add mock IT tools

Create the file. Run this in **PowerShell** from the project root:

```powershell
New-Item src\it_agent\tools.py
notepad src\it_agent\tools.py
```

Use mock tools so the exercise is safe to run locally.

Paste the following Python code into `src\it_agent\tools.py`, then save and close Notepad:

```python
from .models import ToolResult


MOCK_USERS = {
    "alex@contoso.example": {
        "account_enabled": True,
        "mfa_registered": True,
        "mfa_locked": True,
        "device_compliant": True,
    }
}

MOCK_SERVICES = {
    "identity": {"status": "healthy"},
    "vpn": {"status": "degraded", "incident": "VPN gateway packet loss."},
    "email": {"status": "healthy"},
}


def check_user_status(email: str) -> ToolResult:
    user = MOCK_USERS.get(email.lower())
    if not user:
        return ToolResult("check_user_status", False, f"No user found for {email}.")
    return ToolResult("check_user_status", True, f"Found user state for {email}.", dict(user))


def check_service_health(service: str) -> ToolResult:
    state = MOCK_SERVICES.get(service.lower())
    if not state:
        return ToolResult("check_service_health", False, f"No service found for {service}.")
    return ToolResult("check_service_health", True, f"{service} status is {state['status']}.", dict(state))


def reset_mfa(email: str) -> ToolResult:
    return ToolResult("reset_mfa", True, f"MFA reset queued for {email}.")


def create_ticket_note(ticket_id: str, note: str) -> ToolResult:
    return ToolResult("create_ticket_note", True, f"Added note to ticket {ticket_id}.", {"note": note})
```

### Add the agent logic

Create the file. Run this in **PowerShell** from the project root:

```powershell
New-Item src\it_agent\agent.py
notepad src\it_agent\agent.py
```

Paste the following Python code into `src\it_agent\agent.py`, then save and close Notepad:

```python
from .models import ActionSafety, Classification, PlannedAction, Severity, Ticket, TicketCategory
from .tools import check_service_health, check_user_status, create_ticket_note, reset_mfa


class ItHelpdeskAgent:
    def handle_ticket(self, ticket: Ticket, approved: bool = False) -> dict:
        classification = self._classify(ticket)
        actions = self._plan(ticket, classification)
        results = []

        for action in actions:
            if action.safety == ActionSafety.APPROVAL_REQUIRED and not approved:
                results.append({
                    "name": action.name,
                    "success": False,
                    "message": "Skipped because approval was not provided.",
                    "approval_required": True,
                })
                continue

            if action.name == "check_user_status":
                results.append(check_user_status(action.args["email"]))
            elif action.name == "check_service_health":
                results.append(check_service_health(action.args["service"]))
            elif action.name == "reset_mfa":
                results.append(reset_mfa(action.args["email"]))
            elif action.name == "create_ticket_note":
                results.append(create_ticket_note(action.args["ticket_id"], action.args["note"]))

        return {
            "ticket_id": ticket.id,
            "classification": classification,
            "actions": actions,
            "tool_results": results,
        }

    def _classify(self, ticket: Ticket) -> Classification:
        text = f"{ticket.title} {ticket.description} {ticket.affected_service or ''}".lower()
        if any(term in text for term in ["mfa", "authenticator", "login", "sign in", "password"]):
            return Classification(TicketCategory.IDENTITY, Severity.MEDIUM, 55, "Identity or authentication issue.")
        if any(term in text for term in ["vpn", "network", "latency"]):
            return Classification(TicketCategory.NETWORK, Severity.MEDIUM, 45, "Network or VPN issue.")
        if any(term in text for term in ["phish", "malware", "suspicious", "compromised"]):
            return Classification(TicketCategory.SECURITY, Severity.HIGH, 85, "Potential security issue.")
        return Classification(TicketCategory.UNKNOWN, Severity.LOW, 20, "No strong category signal found.")

    def _plan(self, ticket: Ticket, classification: Classification) -> list[PlannedAction]:
        note = PlannedAction(
            "create_ticket_note",
            ActionSafety.SAFE,
            "Document triage result.",
            {"ticket_id": ticket.id, "note": f"Classified as {classification.category.value}."},
        )

        if classification.category == TicketCategory.IDENTITY:
            return [
                PlannedAction("check_user_status", ActionSafety.SAFE, "Verify user state.", {"email": ticket.requester_email}),
                PlannedAction("check_service_health", ActionSafety.SAFE, "Check identity service.", {"service": "identity"}),
                PlannedAction("reset_mfa", ActionSafety.APPROVAL_REQUIRED, "MFA reset changes authentication state.", {"email": ticket.requester_email}),
                note,
            ]

        if classification.category == TicketCategory.NETWORK:
            return [
                PlannedAction("check_service_health", ActionSafety.SAFE, "Check VPN service.", {"service": "vpn"}),
                note,
            ]

        return [note]
```

### Add a command-line entry point

Create the file. Run this in **PowerShell** from the project root:

```powershell
New-Item src\it_agent\__main__.py
notepad src\it_agent\__main__.py
```

Paste the following Python code into `src\it_agent\__main__.py`, then save and close Notepad:

```python
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .agent import ItHelpdeskAgent
from .models import Ticket


parser = argparse.ArgumentParser()
parser.add_argument("--ticket", required=True)
parser.add_argument("--approve", action="store_true")
args = parser.parse_args()

ticket = Ticket.from_dict(json.loads(Path(args.ticket).read_text()))
result = ItHelpdeskAgent().handle_ticket(ticket, approved=args.approve)
print(json.dumps(asdict(result) if hasattr(result, "__dataclass_fields__") else result, indent=2, default=str))
```

Also create the package initializer. Run this in **PowerShell** from the project root:

```powershell
New-Item src\it_agent\__init__.py
notepad src\it_agent\__init__.py
```

Paste the following Python code into `src\it_agent\__init__.py`, then save and close Notepad:

```python
from .agent import ItHelpdeskAgent
```

### Add a sample ticket

Create the sample ticket file. Run this in **PowerShell** from the project root:

```powershell
New-Item examples\mfa-lockout.json
notepad examples\mfa-lockout.json
```

Paste the following JSON into `examples\mfa-lockout.json`, then save and close Notepad:

```json
{
  "id": "INC-1042",
  "requester": "Alex Kim",
  "requester_email": "alex@contoso.example",
  "title": "Cannot sign in after MFA prompt",
  "description": "I changed phones and Authenticator no longer works.",
  "affected_service": "identity"
}
```

Add a second ticket for a VPN/network issue. Run this in **PowerShell** from the project root:

```powershell
New-Item examples\vpn-degraded.json
notepad examples\vpn-degraded.json
```

Paste the following JSON into `examples\vpn-degraded.json`, then save and close Notepad:

```json
{
  "id": "INC-1043",
  "requester": "Sam Patel",
  "requester_email": "sam@contoso.example",
  "title": "VPN is very slow",
  "description": "VPN latency is high and internal apps keep timing out.",
  "affected_service": "vpn"
}
```

Add a third ticket for a security/phishing issue. Run this in **PowerShell** from the project root:

```powershell
New-Item examples\phishing-report.json
notepad examples\phishing-report.json
```

Paste the following JSON into `examples\phishing-report.json`, then save and close Notepad:

```json
{
  "id": "SEC-2041",
  "requester": "Alex Kim",
  "requester_email": "alex@contoso.example",
  "title": "Suspicious phishing email",
  "description": "I received a suspicious email asking me to open an invoice link and sign in again.",
  "affected_service": "email"
}
```

### Run the local agent

Run these commands from the **project root**:

```text
C:\Agent365Labs\external-it-agent
```

```powershell
$env:PYTHONPATH = ".\src"
python -m it_agent --ticket .\examples\mfa-lockout.json
```

Expected behavior:

- The ticket is classified as an identity issue.
- Safe checks run.
- MFA reset is skipped because approval was not provided.

Now test with approval:

```powershell
python -m it_agent --ticket .\examples\mfa-lockout.json --approve
```

Expected behavior:

- The simulated MFA reset runs.

Test the VPN scenario:

```powershell
python -m it_agent --ticket .\examples\vpn-degraded.json
```

Expected behavior:

- The ticket is classified as a network issue.
- The agent checks mock VPN service health.

Test the phishing scenario:

```powershell
python -m it_agent --ticket .\examples\phishing-report.json
```

Expected behavior:

- The ticket is classified as a security issue.
- Safe checks run.
- Any risky remediation should require approval before execution.

At this point, you have a working local third-party agent. The next part is bringing it into Agent 365.

### Optional: Add a local browser interface

This step is optional. The command-line agent is enough to complete the Agent 365 onboarding lab.

Add the browser interface only if you want a more visual local demo where users can select a ticket, edit JSON, toggle approval, and view the structured result.

The browser interface uses a lightweight local web server based on Python's standard library. It does not require OpenAI, Agent 365, or Microsoft 365 services.

Create the file. Run this in **PowerShell** from the project root:

```powershell
New-Item src\it_agent\web.py
notepad src\it_agent\web.py
```

Paste the following Python code into `src\it_agent\web.py`, then save and close Notepad:

```python
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .agent import ItHelpdeskAgent
from .models import Ticket


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "examples"


class AgentWebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self._send_html(INDEX_HTML)
            return

        if parsed.path == "/api/tickets":
            tickets = sorted(path.name for path in EXAMPLES_DIR.glob("*.json"))
            self._send_json({"tickets": tickets})
            return

        if parsed.path == "/api/ticket":
            name = parse_qs(parsed.query).get("name", [""])[0]
            ticket_path = _safe_ticket_path(name)
            if ticket_path is None:
                self._send_json({"error": "Ticket not found."}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(json.loads(ticket_path.read_text(encoding="utf-8")))
            return

        self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if urlparse(self.path).path != "/api/run":
            self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            ticket = Ticket.from_dict(payload["ticket"])
            approved = bool(payload.get("approved", False))
            result = ItHelpdeskAgent().handle_ticket(ticket, approved=approved)
            self._send_json(result)
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format, *args):
        return

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _safe_ticket_path(name):
    if not name or Path(name).name != name:
        return None
    path = EXAMPLES_DIR / name
    if path.suffix != ".json" or not path.exists():
        return None
    return path


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), AgentWebHandler)
    print("External IT agent web UI running at http://127.0.0.1:8765")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>External IT Helpdesk Agent</title>
  <style>
    body { font-family: Segoe UI, Arial, sans-serif; margin: 32px; max-width: 1100px; }
    textarea, select { width: 100%; margin: 8px 0 16px; }
    textarea { height: 260px; font-family: Consolas, monospace; }
    button { padding: 10px 14px; margin-right: 8px; }
    pre { background: #f5f5f5; padding: 16px; overflow: auto; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  </style>
</head>
<body>
  <h1>External IT Helpdesk Agent</h1>
  <p>Select a sample ticket, edit the JSON if needed, and run the local agent.</p>

  <div class="grid">
    <section>
      <label>Sample ticket</label>
      <select id="ticketList"></select>
      <button id="loadTicket">Load ticket</button>
      <label>
        <input type="checkbox" id="approved">
        Approve risky actions
      </label>
      <textarea id="ticketJson"></textarea>
      <button id="runAgent">Run agent</button>
    </section>
    <section>
      <h2>Agent result</h2>
      <pre id="result">Run a ticket to see the result.</pre>
    </section>
  </div>

  <script>
    const ticketList = document.getElementById("ticketList");
    const ticketJson = document.getElementById("ticketJson");
    const result = document.getElementById("result");
    const approved = document.getElementById("approved");

    async function loadTickets() {
      const response = await fetch("/api/tickets");
      const data = await response.json();
      ticketList.innerHTML = data.tickets.map((name) => `<option value="${name}">${name}</option>`).join("");
      await loadTicket();
    }

    async function loadTicket() {
      const response = await fetch(`/api/ticket?name=${encodeURIComponent(ticketList.value)}`);
      const data = await response.json();
      ticketJson.value = JSON.stringify(data, null, 2);
    }

    async function runAgent() {
      const ticket = JSON.parse(ticketJson.value);
      const response = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket, approved: approved.checked })
      });
      const data = await response.json();
      result.textContent = JSON.stringify(data, null, 2);
    }

    document.getElementById("loadTicket").addEventListener("click", loadTicket);
    document.getElementById("runAgent").addEventListener("click", runAgent);
    ticketList.addEventListener("change", loadTicket);
    loadTickets();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
```

Start the browser UI:

Run this from the **project root** in PowerShell:

```powershell
$env:PYTHONPATH = ".\src"
python -m it_agent.web
```

Then open:

```text
http://127.0.0.1:8765
```

From the browser, you can:

- Select a sample ticket
- Edit the JSON payload
- Choose whether to approve risky actions
- Run the agent
- View the structured result

This is still a local demo. OpenAI, Agent 365, and Microsoft 365 services are not required for this browser UI to work.

## What Agent 365 does and does not do

Before starting, it is important to clarify the role of Agent 365.

Agent 365 does not build, host, or orchestrate your agent. You still own:

- The model or reasoning engine
- The agent runtime or framework
- The hosting environment
- The business logic and tools

Agent 365 adds the enterprise layer around that agent:

- Microsoft Entra-backed agent identity
- Agent registration and inventory
- Governance and lifecycle controls
- Permission and consent management
- Microsoft 365 governed tooling, where needed
- Observability through Microsoft OpenTelemetry
- Optional notification and AI teammate capabilities

For third-party agents where you control the code, the usual path is:

```text
Existing agent code
  -> Agent 365 CLI registration
  -> Entra agent identity
  -> Microsoft OpenTelemetry instrumentation
  -> Optional Work IQ tools / Purview controls
  -> Validate and operate in Agent 365
```

## Step 1: Choose the right integration path

Not every agent needs the Agent 365 SDK path. Start by identifying where the agent comes from.

| Agent source | Recommended integration |
|---|---|
| Copilot Studio, Agent Builder, supported Microsoft platform agents | Built-in Agent 365 integration |
| Connected platforms such as Vertex AI or AWS Bedrock, where supported | Registry sync |
| Custom or third-party code-based agents | Agent 365 SDK and CLI |

For agents built with OpenAI Agents SDK, LangChain, CrewAI, LlamaIndex, Semantic Kernel, custom Python, Node.js, or .NET code, use the Agent 365 SDK path.

## Step 2: Prepare prerequisites

You need:

- Existing agent source code
- Microsoft tenant with Agent 365 enabled
- Azure subscription access
- .NET 8 or later
- Azure CLI
- Agent 365 CLI
- GitHub CLI, if using Agent 365 Skills
- Microsoft Entra role: Agent ID Developer minimum
- Global Administrator available for tenant-wide consent
- Azure Contributor access if the setup creates Azure resources

### 2.1 Open PowerShell

Open **Windows PowerShell** as your normal user. You do not usually need Administrator mode for this lab, but your Microsoft tenant and Azure account must have the required permissions.

### 2.2 Confirm Python is available

Run this anywhere in PowerShell:

```powershell
python --version
```

Expected result: Python 3.10 or later.

If Python is missing, install it from:

```text
https://www.python.org/downloads/
```

or use your organization's approved Python distribution.

### 2.3 Install .NET 8 or later

The Agent 365 CLI is installed as a .NET global tool, so .NET must be available first.

Run this anywhere in PowerShell:

```powershell
dotnet --version
```

Expected result: version 8.0 or later.

If `dotnet` is missing, install .NET from:

```text
https://dotnet.microsoft.com/download
```

### 2.4 Install the Agent 365 CLI

Run this anywhere in PowerShell. This installs the CLI for your Windows user profile, not inside the Python project:

```powershell
dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli
```

Verify:

```powershell
a365 -h
```

Expected result: help text for the `a365` command.

If PowerShell says `a365` is not recognized, close and reopen PowerShell. The .NET global tools folder might not be loaded into the current PATH yet.

### 2.5 Install Azure CLI

The Agent 365 setup uses Azure context for tenant/subscription detection and resource setup.

Run this anywhere in PowerShell:

```powershell
az --version
```

If `az` is missing, install Azure CLI from:

```text
https://learn.microsoft.com/cli/azure/install-azure-cli-windows
```

Then sign in:

```powershell
az login
az account show
```

Confirm the displayed tenant and subscription are the ones you want to use for the lab.

### 2.6 Install GitHub CLI if using Agent 365 Skills

GitHub CLI is needed only for installing Agent 365 Skills into your coding assistant environment.

Run this anywhere in PowerShell:

```powershell
winget install --id GitHub.cli --exact --source winget
```

Close and reopen PowerShell, then verify:

```powershell
gh --version
```

If `gh` is still not recognized, add GitHub CLI to the current PowerShell session's PATH:

```powershell
$env:PATH = "C:\Program Files\GitHub CLI;" + $env:PATH
gh --version
```

### 2.7 Move into the agent project folder

For all `a365` commands, go to the agent project root first:

```powershell
cd C:\Agent365Labs\external-it-agent
```

## Step 3: Install Agent 365 Skills

This step is needed only if you choose **Option 1: guided setup with Agent 365 Skills** later in the lab.

GitHub Copilot Skills are not the Agent 365 SDK. They are an optional automation helper that can guide setup, edit the project, and validate the result. The actual Agent 365 integration still uses the Agent 365 CLI, Microsoft OpenTelemetry, and Agent 365 SDK packages.

If you prefer to integrate manually, skip this step and use **Option 2: manual SDK path**.

Run this from PowerShell. It can be run from any folder:

```powershell
gh skill add microsoft/agent365-skills
```

If `gh` is not on PATH, add GitHub CLI to the current PowerShell session first:

```powershell
$env:PATH = "C:\Program Files\GitHub CLI;" + $env:PATH
gh skill add microsoft/agent365-skills
```

Alternative: you can also run GitHub CLI by full path:

```powershell
& "C:\Program Files\GitHub CLI\gh.exe" skill add microsoft/agent365-skills
```

When prompted, select the Agent 365 skills you need. For a full onboarding flow, select all. In the interactive picker, the right arrow typically selects all skills, then Enter confirms.

Common skills include:

| Skill | Purpose |
|---|---|
| `a365-setup` | Entry point for Agent 365 setup |
| `make-a365-agent` | Registers a standard agent |
| `instrument-observability` | Adds Microsoft OpenTelemetry observability |
| `add-workiq-tools` | Adds governed Microsoft 365 Work IQ MCP tools |
| `purview-dlp-integration` | Adds Purview DLP checks |
| `a365-code-validator` | Validates an Agent 365 integration |

Verify the skills are installed:

```powershell
gh skill list
```

Restart the coding assistant after installing the skills. This is important; the assistant may not detect newly installed skills until it restarts.

## Step 4: Confirm the agent runs before onboarding

Do not start Agent 365 integration until the agent runs locally.

For a Python agent, this might look like:

```powershell
cd "C:\path\to\agent"
$env:PYTHONPATH = ".\src"
python -m unittest discover -s tests
python -m it_agent --ticket .\examples\mfa-lockout.json
```

The purpose is to establish a baseline. Agent 365 integration should be additive; it should not change core agent behavior.

## Step 5: Choose your Agent 365 integration option

There are two valid ways to continue.

| Option | Best for | Uses GitHub Copilot Skills? | Uses Agent 365 SDK/OpenTelemetry? |
|---|---|---:|---:|
| Option 1: Guided setup with Agent 365 Skills | Labs, demos, first-time onboarding, faster setup | Yes | Yes |
| Option 2: Manual SDK path | Developers who want full control or cannot use coding assistant skills | No | Yes |

Both options use the same underlying Agent 365 concepts:

- Agent 365 CLI for registration
- Microsoft Entra Agent ID for identity
- Microsoft OpenTelemetry for observability
- Agent 365 SDK packages for tooling or notifications, if needed

GitHub Copilot is not required. It only automates and guides the steps.

## Option 1: Guided setup with Agent 365 Skills

Use this option if you installed the Agent 365 Skills in Step 3.

### Option 1.1: Run Agent 365 setup

Open the project folder in your coding assistant. The current working directory should be the agent root:

```text
C:\Agent365Labs\external-it-agent
```

In the coding assistant, ask:

```text
set up this project for Agent 365
```

This invokes the `a365-setup` skill. It detects the stack, checks prerequisites, and chooses the right path.

For most third-party agents, choose:

```text
Standard agent
```

Use the AI teammate path only when the agent needs its own Microsoft 365 user account, mailbox, Teams presence, or Outlook/Word notification participation. That path requires Frontier preview.

### Option 1.2: Register the agent

Stay in the same project folder. Ask the coding assistant:

```text
register this agent with Agent 365
```

This invokes `make-a365-agent`.

Manual CLI equivalent:

Run this from the **project root**:

```powershell
a365 setup requirements
a365 setup all --agent-name "external-it-helpdesk-agent"
```

This creates:

- Agent identity blueprint
- Agent identity in Microsoft Entra
- Agent registration in Agent 365
- Required permission configuration
- Generated configuration files

The key generated file is:

```text
a365.generated.config.json
```

Important values include:

```text
agentBlueprintId
agenticAppId
agentRegistrationId
resourceConsents
```

If the developer is not a Global Administrator, the CLI may print a consent URL. Send that URL to a Global Administrator to complete tenant-wide consent.

### Option 1.3: Verify registration

Use the CLI to verify permissions. Run these commands from the **project root**:

```powershell
a365 query-entra blueprint-scopes --agent-name "external-it-helpdesk-agent"
a365 query-entra instance-scopes --agent-name "external-it-helpdesk-agent"
```

You should see the blueprint and agent identity permissions.

Also verify in Microsoft Entra:

```text
https://entra.microsoft.com
```

Search for:

```text
external-it-helpdesk-agent Blueprint
external-it-helpdesk-agent Identity
```

Then check the Microsoft 365 admin center:

```text
https://admin.cloud.microsoft/#/agents/all
```

At this stage, the agent is registered. That means Agent 365 knows about it. Runtime telemetry is a separate step.

### Option 1.4: Add Microsoft OpenTelemetry observability

Registration gives identity and governance metadata. Observability makes the agent operationally visible.

Use the coding assistant from the **project root** and ask:

```text
add observability to this agent
```

This invokes `instrument-observability`.

For a backend-style third-party agent, choose:

```text
S2S
```

The integration should use the Microsoft OpenTelemetry Distro, not the deprecated Agent 365 Observability SDK.

For Python, the package is:

Run package installs from the **project root**, ideally after activating your Python virtual environment if you use one:

```powershell
pip install microsoft-opentelemetry
```

The observability integration should emit:

- A root `invoke_agent` span for each agent invocation
- Tool execution spans
- Model inference spans, where applicable
- Error spans
- Required Agent 365 baggage attributes, such as tenant ID and agent ID

The root `invoke_agent` span is important. Without it, spans might be queryable in Defender advanced hunting but not show in the main Agent 365 product surfaces.

### Option 1.5: Add governed Microsoft 365 tools, if needed

If the agent needs to read or act on Microsoft 365 data, add Work IQ tools.

Use the coding assistant from the **project root** and ask:

```text
add Work IQ tools to this agent
```

or more specifically:

```text
wire up Work IQ Mail and Calendar
```

This invokes `add-workiq-tools`.

Use this when the agent needs governed access to:

- Mail
- Calendar
- Teams
- Word
- SharePoint
- Other Microsoft 365 workloads

This step requires the right Microsoft 365 licensing and admin consent. It is skipped when the selected authentication model does not support the required delegated access.

### Option 1.6: Add Purview DLP, if needed

If the agent processes sensitive data, add Microsoft Purview checks.

Use the coding assistant from the **project root** and ask:

```text
add Purview DLP to this agent
```

This invokes `purview-dlp-integration`.

Use this for:

- Prompt-based DLP
- Sensitive information checks
- Compliance audit
- Blocking risky prompts before LLM calls

### Option 1.7: Validate the integration

Use the coding assistant from the **project root** and ask:

```text
validate this Agent 365 integration
```

This invokes `a365-code-validator`, where available.

Also run your original test suite:

Run this from the **project root**:

```powershell
python -m unittest discover -s tests
```

Validate:

- The agent still works as before
- The blueprint exists
- The agent identity exists
- Permission grants are complete
- Runtime spans are emitted
- Tool calls are visible, if configured
- No secrets are committed to source control

## Option 2: Manual SDK path

Use this option if you do not want to use GitHub Copilot Skills. This path uses the same Agent 365 CLI and SDK components, but you make the code/configuration changes yourself.

### Option 2.1: Register the agent with the Agent 365 CLI

Run these commands from the **project root**:

```powershell
cd C:\Agent365Labs\external-it-agent
a365 setup requirements
a365 setup all --agent-name "external-it-helpdesk-agent"
```

This creates or updates:

- Agent identity blueprint
- Agent identity in Microsoft Entra
- Agent registration in Agent 365
- Permission configuration
- `.env`
- `a365.generated.config.json`

If the CLI prints a consent URL, a Global Administrator must open it and approve the requested permissions.

### Option 2.2: Verify registration

Run:

```powershell
a365 query-entra blueprint-scopes --agent-name "external-it-helpdesk-agent"
a365 query-entra instance-scopes --agent-name "external-it-helpdesk-agent"
```

Confirm that:

- The blueprint exists
- The agent identity exists
- Required permissions are granted
- `a365.generated.config.json` contains `agentBlueprintId`, `agenticAppId`, and `agentRegistrationId`

### Option 2.3: Install Microsoft OpenTelemetry

Run this from the **project root**, ideally inside your Python virtual environment:

```powershell
pip install microsoft-opentelemetry
```

This is the supported observability path. Do not use the deprecated Agent 365 Observability SDK for new integrations.

### Option 2.4: Initialize Microsoft OpenTelemetry early in the app

Add initialization code near the start of the application, before the agent handles requests.

Conceptually:

```python
from microsoft.opentelemetry import use_microsoft_opentelemetry


use_microsoft_opentelemetry(
    enable_a365=True,
    a365_token_resolver=token_resolver,
    a365_use_s2s_endpoint=True,
    a365_enable_observability_exporter=True,
)
```

The `token_resolver` must return a valid Agent 365 observability token for the agent and tenant. For standard blueprint agents, Microsoft recommends the S2S route.

### Option 2.5: Add Agent 365 baggage

Agent 365 needs tenant and agent identity context on telemetry spans.

Conceptually:

```python
from microsoft.opentelemetry.a365.core import BaggageBuilder


with (
    BaggageBuilder()
    .tenant_id(tenant_id)
    .agent_id(agent_id)
    .build()
):
    # Create invoke_agent and tool spans here.
    pass
```

Without baggage, spans may not correlate to the registered agent.

### Option 2.6: Add an `invoke_agent` span

Wrap the main agent run in a root `invoke_agent` span:

```text
ticket received
  -> invoke_agent span starts
  -> classify ticket
  -> plan actions
  -> call tools
  -> produce response
  -> invoke_agent span ends
```

This root span is important for Agent 365 product views.

### Option 2.7: Add tool execution spans

Wrap each tool call in a tool span:

```text
check_user_status
check_service_health
reset_mfa
create_ticket_note
```

Each span should include:

- Tool name
- Safe arguments
- Success or failure
- Error details, if any
- Response summary

### Option 2.8: Add SDK tooling only if the agent needs Microsoft 365 tools

If the agent needs governed Microsoft 365 tools, install the Agent 365 tooling packages:

```powershell
pip install microsoft-agents-a365-runtime
pip install microsoft-agents-a365-tooling
pip install microsoft-agents-a365-tooling-extensions-openai
```

Use these only when the agent needs governed Work IQ MCP access to Microsoft 365 workloads such as Mail, Calendar, Word, SharePoint, or Teams.

If the agent only needs registration and observability, you do not need the tooling packages.

### Option 2.9: Run and validate

Run the local agent:

```powershell
$env:PYTHONPATH = ".\src"
python -m it_agent --ticket .\examples\mfa-lockout.json
```

Then validate:

```powershell
a365 query-entra blueprint-scopes --agent-name "external-it-helpdesk-agent"
a365 query-entra instance-scopes --agent-name "external-it-helpdesk-agent"
```

Check the Agent 365 admin surface:

```text
https://admin.cloud.microsoft/#/agents/all
```

Also confirm your tenant has the required licensing for telemetry visibility. Without the required Microsoft 365 E7 or Microsoft Agent 365 licensing, telemetry ingestion can succeed but product surfaces may remain empty.

## Which option should you choose?

Use **Option 1** if you want a guided lab experience and are comfortable using GitHub Copilot Skills.

Use **Option 2** if you want to understand exactly what the SDK and OpenTelemetry integration does, or if your organization does not allow coding-assistant skill installation.

The important point: **the SDK/OpenTelemetry path is the real integration. Copilot Skills only help automate that path.**

## Step 12: Deploy the agent

Agent 365 does not host the agent. Deploy it to your preferred runtime:

- Azure App Service
- Azure Container Apps
- Azure Functions
- Kubernetes
- AWS
- Google Cloud
- On-premises
- Existing third-party platform

After deployment, make sure the same Agent 365 environment variables and identity configuration are present in the deployed runtime.

## Step 13: Operate in Agent 365

Once registered and instrumented, admins can use Agent 365 and Microsoft 365 admin surfaces to:

- Discover the agent
- Review ownership
- Audit activity
- Govern permissions
- Review tools
- Monitor sessions
- Investigate risk
- Apply lifecycle policy

Security teams can also use Microsoft Defender and Microsoft Purview integrations, depending on the telemetry and compliance capabilities enabled.

## Common issue: CLI says completed false

In some standard-agent scenarios, `a365.generated.config.json` might show:

```json
"completed": false
```

even though the CLI output says setup completed successfully.

Do not rely only on that flag. Check the actual setup summary and verify that these exist:

```text
agentBlueprintId
agenticAppId
agentRegistrationId
resourceConsents with consentGranted = true
```

Also confirm with:

```powershell
a365 query-entra blueprint-scopes --agent-name "<agent-name>"
a365 query-entra instance-scopes --agent-name "<agent-name>"
```

If blueprint, identity, registration, and permissions are present, registration is complete. Observability may still need to be added separately.

## Summary

The shortest path for most third-party agents is:

```text
1. Confirm the agent runs locally
2. Install Agent 365 CLI
3. Choose one onboarding path:
   - Option 1: guided setup with Agent 365 Skills
   - Option 2: manual SDK path
4. Register the agent with Agent 365
5. Complete Global Admin consent, if required
6. Add Microsoft OpenTelemetry observability
7. Add Work IQ tools or Purview DLP if needed
8. Validate
9. Deploy
10. Operate in Agent 365
```

The Agent 365 CLI gets the agent registered. Microsoft OpenTelemetry makes runtime activity visible. The Agent 365 SDK tooling and notification packages add deeper Microsoft 365 integration when the agent needs it. GitHub Copilot Skills are optional; they help automate the setup, but they are not the integration itself.
