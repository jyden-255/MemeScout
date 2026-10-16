"""Local web UI for running MemeScout from a browser."""
import argparse
import json
import os
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .models import Coin
from .runner import RunOptions, run_pipeline


REPORT_DIR = "reports"
STATE_LOCK = threading.Lock()
STATE = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "error": "",
    "logs": [],
    "result": None,
}


def _coin_row(c: Coin) -> dict:
    row = c.__dict__.copy()
    row["sources"] = sorted(c.sources)
    return row


def _format_usd(x):
    if x is None:
        return "-"
    if x >= 1_000_000_000:
        return f"${x / 1e9:.2f}B"
    if x >= 1_000_000:
        return f"${x / 1e6:.2f}M"
    if x >= 1_000:
        return f"${x / 1e3:.1f}K"
    return f"${x:,.2f}"


def _format_price(x):
    if x is None:
        return "-"
    if x >= 1:
        return f"${x:,.4f}"
    return f"${x:.10f}".rstrip("0")


def _format_pct(x):
    if x is None:
        return "-"
    return f"{x:+.1f}%"


def _serialize_result(result) -> dict:
    return {
        "report_path": result.report_path,
        "ai_ran": result.ai_ran,
        "coins": [_coin_row(c) for c in result.coins],
    }


def _append_log(message: str) -> None:
    with STATE_LOCK:
        STATE["logs"].append({"time": time.strftime("%H:%M:%S"), "message": str(message)})


def _start_run(options: RunOptions) -> tuple[bool, str]:
    with STATE_LOCK:
        if STATE["running"]:
            return False, "A scan is already running."
        STATE.update({
            "running": True,
            "started_at": time.time(),
            "finished_at": None,
            "error": "",
            "logs": [],
            "active_options": options.__dict__.copy(),
        })

    def worker():
        try:
            result = run_pipeline(options, log=_append_log)
            with STATE_LOCK:
                STATE["result"] = _serialize_result(result)
        except Exception as exc:
            _append_log(f"failed: {exc}")
            with STATE_LOCK:
                STATE["error"] = traceback.format_exc()
        finally:
            with STATE_LOCK:
                STATE["running"] = False
                STATE["finished_at"] = time.time()

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return True, "Scan started."


def _reports() -> list[dict]:
    if not os.path.isdir(REPORT_DIR):
        return []
    rows = []
    for name in os.listdir(REPORT_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(REPORT_DIR, name)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        rows.append({
            "name": name,
            "path": path,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
        })
    return sorted(rows, key=lambda r: r["mtime"], reverse=True)


INDEX = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MemeScout</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101215;
      --panel: #181b20;
      --panel-2: #20242b;
      --text: #eef1f4;
      --muted: #9ca7b4;
      --line: #313741;
      --green: #65d88d;
      --red: #ff7f7f;
      --gold: #f4c95d;
      --blue: #73b7ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px 24px;
      border-bottom: 1px solid var(--line);
      background: #14171b;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 { margin: 0; font-size: 20px; letter-spacing: 0; }
    main {
      display: grid;
      grid-template-columns: 340px minmax(0, 1fr);
      min-height: calc(100vh - 65px);
    }
    aside {
      border-right: 1px solid var(--line);
      padding: 20px;
      background: var(--panel);
    }
    section { padding: 20px 24px; min-width: 0; }
    label { display: block; color: var(--muted); font-size: 12px; margin: 16px 0 6px; }
    input[type="text"], input[type="number"] {
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #101215;
      color: var(--text);
      padding: 0 10px;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 9px;
      color: var(--text);
      margin-top: 14px;
    }
    .check input { width: 17px; height: 17px; }
    button {
      border: 1px solid #5ea8ff;
      border-radius: 6px;
      background: #1d6fd1;
      color: white;
      height: 40px;
      padding: 0 14px;
      font-weight: 700;
      cursor: pointer;
    }
    button:disabled { opacity: .55; cursor: wait; }
    .actions { display: flex; gap: 10px; margin-top: 20px; }
    .secondary {
      background: var(--panel-2);
      border-color: var(--line);
      color: var(--text);
      font-weight: 600;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
    }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--green); }
    .dot.running { background: var(--gold); }
    .grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .metric {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 72px;
    }
    .metric b { display: block; font-size: 20px; margin-top: 4px; }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }
    table { width: 100%; border-collapse: collapse; min-width: 1020px; }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
    th { color: var(--muted); font-size: 12px; background: #15181d; position: sticky; top: 0; }
    tr:last-child td { border-bottom: 0; }
    .pos { color: var(--green); }
    .neg { color: var(--red); }
    .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .logs {
      height: 170px;
      overflow: auto;
      background: #0c0e11;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      margin-top: 18px;
    }
    .log-line { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
    .reports { margin-top: 18px; display: grid; gap: 8px; }
    .report-link {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      color: var(--blue);
      text-decoration: none;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      background: #12151a;
    }
    @media (max-width: 860px) {
      main { grid-template-columns: 1fr; }
      aside { border-right: 0; border-bottom: 1px solid var(--line); }
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <h1>MemeScout</h1>
    <div class="status"><span id="dot" class="dot"></span><span id="status">Ready</span></div>
  </header>
  <main>
    <aside>
      <form id="scan-form">
        <label for="networks">Networks</label>
        <input id="networks" name="networks" type="text" value="solana">

        <label for="top">Coins to show</label>
        <input id="top" name="top" type="number" value="50" min="1" max="100">

        <label for="ai_top">DeepSeek coins</label>
        <input id="ai_top" name="ai_top" type="number" value="12" min="0" max="50">

        <label for="min_liquidity">Minimum liquidity USD</label>
        <input id="min_liquidity" name="min_liquidity" type="number" value="10000" min="0" step="1000">

        <label for="coingecko_limit">CoinGecko lookups</label>
        <input id="coingecko_limit" name="coingecko_limit" type="number" value="3" min="0" max="15">

        <label class="check"><input id="skip_holders" name="skip_holders" type="checkbox" checked> Skip holder RPC</label>
        <label class="check"><input id="all_trending" name="all_trending" type="checkbox"> Include all CoinGecko trending</label>
        <label class="check"><input id="no_llm" name="no_llm" type="checkbox"> Skip DeepSeek</label>
        <label class="check"><input id="demo" name="demo" type="checkbox"> Demo data</label>

        <div class="actions">
          <button id="run" type="submit">Run scan</button>
          <button class="secondary" id="refresh" type="button">Refresh</button>
        </div>
      </form>

      <div class="logs" id="logs"></div>
      <div class="reports" id="reports"></div>
    </aside>
    <section>
      <div class="grid">
        <div class="metric"><span>Coins</span><b id="metric-coins">0</b></div>
        <div class="metric"><span>Report</span><b id="metric-report">-</b></div>
        <div class="metric"><span>AI pass</span><b id="metric-ai">-</b></div>
        <div class="metric"><span>Updated</span><b id="metric-updated">-</b></div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Symbol</th><th>Chain</th><th>Price</th><th>1h</th><th>24h</th>
              <th>Vol 24h</th><th>Liq</th><th>MCap</th><th>Top10%</th><th>Src</th>
              <th>Hype</th><th>AI</th><th>Risk</th><th>Thesis</th><th>Flags</th>
            </tr>
          </thead>
          <tbody id="rows">
            <tr><td colspan="16">No scan loaded yet.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const money = (x) => x === null || x === undefined ? "-" :
      x >= 1e9 ? `$${(x / 1e9).toFixed(2)}B` :
      x >= 1e6 ? `$${(x / 1e6).toFixed(2)}M` :
      x >= 1e3 ? `$${(x / 1e3).toFixed(1)}K` : `$${Number(x).toFixed(2)}`;
    const price = (x) => x === null || x === undefined ? "-" :
      x >= 1 ? `$${Number(x).toFixed(4)}` : `$${Number(x).toFixed(10)}`.replace(/0+$/, "");
    const pct = (x) => x === null || x === undefined ? "-" : `${x >= 0 ? "+" : ""}${Number(x).toFixed(1)}%`;
    const esc = (x) => String(x ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

    async function postRun(ev) {
      ev.preventDefault();
      const form = new FormData($("scan-form"));
      $("run").disabled = true;
      await fetch("/api/run", { method: "POST", body: new URLSearchParams(form) });
      poll();
    }

    function renderRows(coins) {
      if (!coins || coins.length === 0) {
        $("rows").innerHTML = `<tr><td colspan="16">No completed scan loaded yet.</td></tr>`;
        return;
      }
      $("rows").innerHTML = coins.map((c, i) => {
        const h1Class = Number(c.change_h1) >= 0 ? "pos" : "neg";
        const h24Class = Number(c.change_h24) >= 0 ? "pos" : "neg";
        return `<tr>
          <td>${i + 1}</td><td><b>${esc(c.symbol)}</b></td><td>${esc(c.chain)}</td>
          <td>${price(c.price_usd)}</td><td class="${h1Class}">${pct(c.change_h1)}</td>
          <td class="${h24Class}">${pct(c.change_h24)}</td><td>${money(c.volume_h24)}</td>
          <td>${money(c.liquidity_usd)}</td><td>${money(c.market_cap || c.fdv)}</td>
          <td>${c.top10_pct == null ? "-" : Number(c.top10_pct).toFixed(0) + "%"}</td>
          <td>${(c.sources || []).length}</td><td>${Number(c.hype_score || 0).toFixed(0)}</td>
          <td>${c.ai_hype == null ? "-" : c.ai_hype}</td><td>${c.ai_risk == null ? "-" : c.ai_risk}</td>
          <td>${esc(c.ai_thesis || "")}</td>
          <td>${esc((c.ai_flags || []).join(", "))}</td>
        </tr>`;
      }).join("");
    }

    function renderReports(reports) {
      $("reports").innerHTML = reports.slice(0, 8).map(r =>
        `<a class="report-link" href="/reports/${encodeURIComponent(r.name)}" target="_blank">
          <span>${esc(r.name)}</span><span>${new Date(r.mtime * 1000).toLocaleTimeString()}</span>
        </a>`
      ).join("");
    }

    async function poll() {
      const res = await fetch("/api/state");
      const data = await res.json();
      $("dot").className = data.running ? "dot running" : "dot";
      $("status").textContent = data.running ? "Running scan" : (data.error ? "Failed" : "Ready");
      $("run").disabled = data.running;
      $("logs").innerHTML = (data.logs || []).map(l => `<div class="log-line">${esc(l.time)} ${esc(l.message)}</div>`).join("");
      $("logs").scrollTop = $("logs").scrollHeight;

      const result = data.result || {};
      const coins = result.coins || [];
      $("metric-coins").textContent = coins.length;
      $("metric-report").textContent = result.report_path ? result.report_path.split("/").pop() : "-";
      $("metric-ai").textContent = result.ai_ran ? "Yes" : "No";
      $("metric-updated").textContent = data.finished_at ? new Date(data.finished_at * 1000).toLocaleTimeString() : "-";
      renderRows(coins);
      if (data.running && coins.length === 0) {
        $("rows").innerHTML = `<tr><td colspan="16">Scan is running. Progress appears in the log panel.</td></tr>`;
      }
      renderReports(data.reports || []);
    }

    $("scan-form").addEventListener("submit", postRun);
    $("refresh").addEventListener("click", poll);
    poll();
    setInterval(poll, 1500);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[web] {self.address_string()} - {fmt % args}")

    def _send(self, status=HTTPStatus.OK, content_type="application/json", body=b""):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data, status=HTTPStatus.OK):
        self._send(status, "application/json", json.dumps(data, default=str).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(content_type="text/html; charset=utf-8", body=INDEX.encode())
            return
        if parsed.path == "/api/state":
            with STATE_LOCK:
                data = dict(STATE)
                data["logs"] = list(STATE["logs"])
            data["reports"] = _reports()
            self._json(data)
            return
        if parsed.path.startswith("/reports/"):
            name = os.path.basename(parsed.path.removeprefix("/reports/"))
            path = os.path.join(REPORT_DIR, name)
            if not os.path.isfile(path):
                self._json({"error": "Report not found."}, HTTPStatus.NOT_FOUND)
                return
            with open(path, "rb") as f:
                self._send(content_type="application/json", body=f.read())
            return
        self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length") or "0")
        params = parse_qs(self.rfile.read(length).decode())
        try:
            options = RunOptions(
                networks=params.get("networks", ["solana"])[0] or "solana",
                top=max(1, min(100, int(params.get("top", ["50"])[0] or "50"))),
                min_liquidity=max(0.0, float(params.get("min_liquidity", ["10000"])[0] or "10000")),
                all_trending="all_trending" in params,
                no_llm="no_llm" in params,
                demo="demo" in params,
                coingecko_limit=max(0, min(15, int(params.get("coingecko_limit", ["3"])[0] or "3"))),
                skip_holders="skip_holders" in params,
                llm_timeout=45,
                ai_top=max(0, min(50, int(params.get("ai_top", ["12"])[0] or "12"))),
            )
        except ValueError:
            self._json({"error": "Invalid scan settings."}, HTTPStatus.BAD_REQUEST)
            return
        ok, message = _start_run(options)
        self._json({"ok": ok, "message": message}, HTTPStatus.ACCEPTED if ok else HTTPStatus.CONFLICT)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MemeScout web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"MemeScout web UI: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
