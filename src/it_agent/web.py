from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .agent import ItHelpdeskAgent
from .models import Ticket


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = PROJECT_ROOT / "examples"


class AgentWebHandler(BaseHTTPRequestHandler):
    server_version = "ExternalItAgent/0.1"

    def do_GET(self) -> None:
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

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/run":
            self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return

        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            ticket = Ticket.from_dict(payload["ticket"])
            approved = bool(payload.get("approved", False))
            result = ItHelpdeskAgent().handle_ticket(ticket, approved=approved)
            self._send_json(_json_safe(asdict(result)))
        except (KeyError, ValueError, json.JSONDecodeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the external IT helpdesk agent browser UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), AgentWebHandler)
    print(f"External IT agent web UI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _safe_ticket_path(name: str) -> Path | None:
    if not name or Path(name).name != name:
        return None
    path = EXAMPLES_DIR / name
    if path.suffix != ".json" or not path.exists():
        return None
    return path


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


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>External IT Helpdesk Agent</title>
  <script>
    (() => {
      const param = new URLSearchParams(window.location.search).get("scoutTheme");
      const theme =
        param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      document.documentElement.setAttribute("data-theme", theme);
    })();
  </script>
  <style>
    :root {
      color-scheme: light;
      --cp-bg: #f7f4ef;
      --cp-bg-elevated: #fcfbf8;
      --cp-surface: #ffffff;
      --cp-surface-soft: #f5f5f5;
      --cp-border: #dedede;
      --cp-border-strong: #919191;
      --cp-text: #242424;
      --cp-text-muted: #5c5c5c;
      --cp-text-soft: #6f6f6f;
      --cp-accent: #b11f4b;
      --cp-accent-hover: #9a1a41;
      --cp-accent-soft: rgba(177, 31, 75, 0.08);
      --cp-accent-fg: #ffffff;
      --cp-success: #16a34a;
      --cp-danger: #dc2626;
      --cp-warning: #f59e0b;
      --cp-link: #0078d4;
      --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.12);
      --cp-overlay: rgba(255, 255, 255, 0.8);
      --cp-panel: rgba(255, 255, 255, 0.86);
      --cp-panel-strong: rgba(255, 255, 255, 0.96);
      --cp-sheen: rgba(255, 255, 255, 0.55);
      --cp-highlight: rgba(177, 31, 75, 0.12);
    }
    html[data-theme="dark"] {
      color-scheme: dark;
      --cp-bg: #3d3b3a;
      --cp-bg-elevated: #343231;
      --cp-surface: #292929;
      --cp-surface-soft: #2e2e2e;
      --cp-border: #474747;
      --cp-border-strong: #5f5f5f;
      --cp-text: #dedede;
      --cp-text-muted: #919191;
      --cp-text-soft: #b0b0b0;
      --cp-accent: #fd8ea1;
      --cp-accent-hover: #fb7b91;
      --cp-accent-soft: rgba(253, 142, 161, 0.14);
      --cp-accent-fg: #1a1a1a;
      --cp-success: #4ade80;
      --cp-danger: #f87171;
      --cp-warning: #fbbf24;
      --cp-link: #4da6ff;
      --cp-shadow: 0 18px 48px rgba(0, 0, 0, 0.32);
      --cp-overlay: rgba(41, 41, 41, 0.88);
      --cp-panel: rgba(41, 41, 41, 0.72);
      --cp-panel-strong: rgba(41, 41, 41, 0.96);
      --cp-sheen: rgba(255, 255, 255, 0.04);
      --cp-highlight: rgba(253, 142, 161, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--cp-bg);
      color: var(--cp-text);
      font-family: "Segoe UI", Aptos, Calibri, -apple-system, BlinkMacSystemFont, sans-serif;
    }
    main {
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px;
    }
    header {
      margin-bottom: 24px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 32px;
    }
    p {
      color: var(--cp-text-muted);
      line-height: 1.5;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(340px, 0.85fr) minmax(420px, 1.15fr);
      gap: 20px;
    }
    .card {
      background: var(--cp-surface);
      border: 1px solid var(--cp-border);
      border-radius: 16px;
      box-shadow: 0 0 2px var(--cp-overlay), 0 1px 2px var(--cp-overlay);
      padding: 20px;
    }
    label {
      display: block;
      color: var(--cp-text-muted);
      font-weight: 600;
      margin-bottom: 8px;
    }
    select, textarea {
      width: 100%;
      border: 1px solid var(--cp-border);
      border-radius: 0.625rem;
      background: var(--cp-bg-elevated);
      color: var(--cp-text);
      font: inherit;
      padding: 12px;
    }
    textarea {
      min-height: 330px;
      font-family: Consolas, "Courier New", Courier, monospace;
      resize: vertical;
    }
    .row {
      display: flex;
      gap: 12px;
      align-items: center;
      margin-top: 16px;
      flex-wrap: wrap;
    }
    button {
      border: 0;
      border-radius: 0.625rem;
      background: var(--cp-accent);
      color: var(--cp-accent-fg);
      cursor: pointer;
      font: inherit;
      font-weight: 700;
      padding: 12px 16px;
    }
    button:hover {
      background: var(--cp-accent-hover);
    }
    .secondary {
      background: var(--cp-surface-soft);
      color: var(--cp-text);
      border: 1px solid var(--cp-border);
    }
    .secondary:hover {
      background: var(--cp-accent-soft);
    }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--cp-text-muted);
      font-weight: 600;
    }
    .result {
      white-space: pre-wrap;
      overflow: auto;
      min-height: 520px;
      background: var(--cp-surface-soft);
      border: 1px solid var(--cp-border);
      border-radius: 0.625rem;
      padding: 16px;
      font-family: Consolas, "Courier New", Courier, monospace;
      color: var(--cp-text);
    }
    .status {
      color: var(--cp-text-muted);
      min-height: 24px;
    }
    @media (max-width: 900px) {
      main { padding: 20px; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>External IT Helpdesk Agent</h1>
      <p>Select a sample ticket, optionally approve remediation actions, and run the non-Microsoft agent from the browser.</p>
    </header>
    <section class="grid">
      <div class="card">
        <label for="ticketList">Sample ticket</label>
        <select id="ticketList"></select>
        <div class="row">
          <button class="secondary" id="loadTicket">Load ticket</button>
          <label class="check"><input type="checkbox" id="approved"> Approve risky actions</label>
        </div>
        <div class="row">
          <button id="runAgent">Run agent</button>
          <span class="status" id="status"></span>
        </div>
        <p>The ticket JSON is editable, so you can test your own issue text before running.</p>
        <textarea id="ticketJson" spellcheck="false"></textarea>
      </div>
      <div class="card">
        <label for="result">Agent result</label>
        <div class="result" id="result">Run a ticket to see classification, planned actions, tool results, approval gates, and telemetry count.</div>
      </div>
    </section>
  </main>
  <script>
    const ticketList = document.getElementById("ticketList");
    const ticketJson = document.getElementById("ticketJson");
    const result = document.getElementById("result");
    const statusEl = document.getElementById("status");
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
      statusEl.textContent = "Ticket loaded";
    }

    async function runAgent() {
      statusEl.textContent = "Running...";
      result.textContent = "";
      try {
        const ticket = JSON.parse(ticketJson.value);
        const response = await fetch("/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticket, approved: approved.checked })
        });
        const data = await response.json();
        result.textContent = JSON.stringify(data, null, 2);
        statusEl.textContent = response.ok ? "Complete" : "Failed";
      } catch (error) {
        result.textContent = String(error);
        statusEl.textContent = "Failed";
      }
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

