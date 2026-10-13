---
title: "Bringing a Third-Party Agent to Microsoft Agent 365: A Step-by-Step Guide"
description: "A practical walkthrough for registering, instrumenting, and validating a custom or third-party agent with Microsoft Agent 365."
date: 2026-10-13
tags:
  - Microsoft Agent 365
  - Entra Agent ID
  - OpenTelemetry
  - AI Agents
  - Governance
---

# Bringing a Third-Party Agent to Microsoft Agent 365: A Step-by-Step Guide

AI agents are moving quickly from experiments to business-critical systems. That creates a new operational question for IT and security teams: how do we discover, govern, observe, and secure agents that were not originally built on Microsoft platforms?

Microsoft Agent 365 helps answer that question by bringing agents into a unified enterprise control plane. In this post, I walk through a practical step-by-step process for bringing a third-party or custom agent into Agent 365.

The example scenario is an external IT helpdesk triage agent. The agent classifies support tickets, checks mock IT systems, separates safe actions from approval-required actions, and can use OpenAI for conversation. The same pattern applies to agents built with OpenAI Agents SDK, LangChain, CrewAI, LlamaIndex, custom Python or Node.js runtimes, and other third-party frameworks.

## Exercise overview

This walkthrough has two parts:

1. Build a simple local third-party agent.
2. Register and instrument that agent with Microsoft Agent 365.

The local agent is intentionally simple. It does not depend on Microsoft 365 data, real ticketing systems, or production identity. That makes it a safe starting point for learning the onboarding flow.

The agent will:

- Accept a helpdesk ticket as JSON
- Classify the ticket
- Assign severity and risk
- Plan safe and approval-required actions
- Run mock IT tools
- Write local telemetry
- Later connect to Agent 365 registration and observability

## Part 1: Build a local third-party agent

Start by creating a small Python project.

```powershell
mkdir external-it-agent
cd external-it-agent
mkdir src\it_agent
mkdir examples
mkdir tests
```

Create a basic project file:

```powershell
New-Item pyproject.toml
```

Add:

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

Create:

```text
src\it_agent\models.py
```

The agent needs a ticket input, a classification result, planned actions, and tool results.

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

Create:

```text
src\it_agent\tools.py
```

Use mock tools so the exercise is safe to run locally.

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

Create:

```text
src\it_agent\agent.py
```

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

Create:

```text
src\it_agent\__main__.py
```

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

Also create:

```text
src\it_agent\__init__.py
```

```python
from .agent import ItHelpdeskAgent
```

### Add a sample ticket

Create:

```text
examples\mfa-lockout.json
```

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

### Run the local agent

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

At this point, you have a working local third-party agent. The next part is bringing it into Agent 365.

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

Install the Agent 365 CLI:

```powershell
dotnet tool install --global Microsoft.Agents.A365.DevTools.Cli
a365 -h
```

Install GitHub CLI if you plan to use Agent 365 Skills:

```powershell
winget install --id GitHub.cli --exact --source winget
gh --version
```

Sign in to Azure:

```powershell
az login
az account show
```

## Step 3: Install Agent 365 Skills

Microsoft recommends using Agent 365 Skills from a supported coding assistant because they guide the setup, make code changes, and validate the result.

Install the skills:

```powershell
gh skill add microsoft/agent365-skills
```

When prompted, select the Agent 365 skills you need. For a full onboarding flow, select all.

Common skills include:

| Skill | Purpose |
|---|---|
| `a365-setup` | Entry point for Agent 365 setup |
| `make-a365-agent` | Registers a standard agent |
| `instrument-observability` | Adds Microsoft OpenTelemetry observability |
| `add-workiq-tools` | Adds governed Microsoft 365 Work IQ MCP tools |
| `purview-dlp-integration` | Adds Purview DLP checks |
| `a365-code-validator` | Validates an Agent 365 integration |

Restart the coding assistant after installing the skills.

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

## Step 5: Run Agent 365 setup

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

## Step 6: Register the agent

Ask:

```text
register this agent with Agent 365
```

This invokes `make-a365-agent`.

Manual CLI equivalent:

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

## Step 7: Verify registration

Use the CLI to verify permissions:

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

## Step 8: Add Microsoft OpenTelemetry observability

Registration gives identity and governance metadata. Observability makes the agent operationally visible.

Ask the coding assistant:

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

## Step 9: Add governed Microsoft 365 tools, if needed

If the agent needs to read or act on Microsoft 365 data, add Work IQ tools.

Ask:

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

## Step 10: Add Purview DLP, if needed

If the agent processes sensitive data, add Microsoft Purview checks.

Ask:

```text
add Purview DLP to this agent
```

This invokes `purview-dlp-integration`.

Use this for:

- Prompt-based DLP
- Sensitive information checks
- Compliance audit
- Blocking risky prompts before LLM calls

## Step 11: Validate the integration

Ask:

```text
validate this Agent 365 integration
```

This invokes `a365-code-validator`, where available.

Also run your original test suite:

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
3. Install Agent 365 Skills
4. Run Agent 365 setup
5. Register the agent
6. Complete Global Admin consent
7. Add Microsoft OpenTelemetry observability
8. Add Work IQ tools or Purview DLP if needed
9. Validate
10. Deploy
11. Operate in Agent 365
```

The Agent 365 CLI gets the agent registered. Microsoft OpenTelemetry makes runtime activity visible. The Agent 365 SDK tooling and notification packages add deeper Microsoft 365 integration when the agent needs it.
