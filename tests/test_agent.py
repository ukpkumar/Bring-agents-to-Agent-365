import tempfile
import unittest
from pathlib import Path

from it_agent.agent import ItHelpdeskAgent
from it_agent.models import ActionSafety, Ticket, TicketCategory
from it_agent.telemetry import Agent365TelemetryAdapter


class ItHelpdeskAgentTests(unittest.TestCase):
    def build_agent(self) -> ItHelpdeskAgent:
        self.temp_dir = tempfile.TemporaryDirectory()
        telemetry = Agent365TelemetryAdapter(Path(self.temp_dir.name) / "telemetry.jsonl")
        return ItHelpdeskAgent(telemetry=telemetry)

    def tearDown(self) -> None:
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_mfa_ticket_requires_approval_for_reset(self) -> None:
        agent = self.build_agent()
        ticket = Ticket(
            id="INC-1",
            requester="Alex Kim",
            requester_email="alex@contoso.example",
            title="MFA locked out",
            description="Authenticator is failing after phone replacement.",
            affected_service="identity",
        )

        result = agent.handle_ticket(ticket, approved=False)

        self.assertEqual(result.classification.category, TicketCategory.IDENTITY)
        self.assertTrue(any(action.name == "reset_mfa" and action.safety == ActionSafety.APPROVAL_REQUIRED for action in result.actions))
        self.assertTrue(any(tool.name == "reset_mfa" and not tool.success for tool in result.tool_results))

    def test_approved_mfa_reset_executes(self) -> None:
        agent = self.build_agent()
        ticket = Ticket(
            id="INC-2",
            requester="Alex Kim",
            requester_email="alex@contoso.example",
            title="Cannot login due to MFA",
            description="Need MFA reset.",
            affected_service="identity",
        )

        result = agent.handle_ticket(ticket, approved=True)

        self.assertTrue(any(tool.name == "reset_mfa" and tool.success for tool in result.tool_results))

    def test_vpn_ticket_checks_service_health(self) -> None:
        agent = self.build_agent()
        ticket = Ticket(
            id="INC-3",
            requester="Sam Patel",
            requester_email="sam@contoso.example",
            title="VPN latency",
            description="Network and VPN are slow.",
            affected_service="vpn",
        )

        result = agent.handle_ticket(ticket)

        self.assertEqual(result.classification.category, TicketCategory.NETWORK)
        self.assertTrue(any(tool.name == "check_service_health" and tool.success for tool in result.tool_results))


if __name__ == "__main__":
    unittest.main()

