import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from it_agent.agent365 import Agent365Config
from it_agent.telemetry import Agent365TelemetryAdapter


class Agent365IntegrationTests(unittest.TestCase):
    def test_local_telemetry_mode_does_not_require_sdk(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Agent365Config(
                agent_name="external-it-helpdesk-agent",
                agent_id=None,
                tenant_id=None,
                enabled=False,
                sdk_module="missing_agent365_sdk",
                log_path=Path(temp_dir) / "telemetry.jsonl",
            )
            telemetry = Agent365TelemetryAdapter(config=config)

            telemetry.emit("ticket.received", {"ticket_id": "INC-1"})

            self.assertEqual(telemetry.event_count, 1)
            self.assertTrue(config.log_path.exists())

    def test_sdk_mode_requires_registration_values(self) -> None:
        config = Agent365Config(
            agent_name="external-it-helpdesk-agent",
            agent_id=None,
            tenant_id=None,
            enabled=True,
            sdk_module="agent365",
            log_path=Path("logs/test.jsonl"),
        )

        with self.assertRaisesRegex(RuntimeError, "AGENT365_AGENT_ID, AGENT365_TENANT_ID"):
            Agent365TelemetryAdapter(config=config)

    def test_config_reads_environment(self) -> None:
        env = {
            "AGENT365_ENABLED": "true",
            "AGENT365_AGENT_ID": "agent-123",
            "AGENT365_TENANT_ID": "tenant-456",
            "AGENT365_SDK_MODULE": "contoso_agent365_adapter",
            "AGENT365_LOG_PATH": "logs/custom.jsonl",
        }

        with patch.dict(os.environ, env, clear=False):
            config = Agent365Config.from_env()

        self.assertTrue(config.enabled)
        self.assertEqual(config.agent_id, "agent-123")
        self.assertEqual(config.tenant_id, "tenant-456")
        self.assertEqual(config.sdk_module, "contoso_agent365_adapter")
        self.assertEqual(config.log_path, Path("logs/custom.jsonl"))


if __name__ == "__main__":
    unittest.main()

