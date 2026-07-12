"""
Lightweight local backend for Aether (stdlib only).

Serves research/status JSON from LaCie so the cockpit (or curl) can hit a
stable API while `vite dev` runs the SvelteKit frontend.

  python -m aether.dev_server
  python -m aether.dev_server --port 8787
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from aether.paths import FMP_RAW, PROCESSED, LACIE_ROOT


def _read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        return {"error": str(e), "path": str(path)}


def _count_files(d: Path) -> int:
    if not d.exists():
        return 0
    return sum(1 for p in d.iterdir() if p.is_file() and not p.name.startswith("._"))


def build_status() -> dict:
    research = PROCESSED / "research"
    specialists = {}
    for p in sorted(research.glob("earnings_specialist_*.json")):
        if p.name.startswith("._"):
            continue
        specialists[p.stem] = _read_json(p)

    mtf = {}
    for univ, root in (
        ("sp500", FMP_RAW / "sp500_full"),
        ("iwm", FMP_RAW / "iwm_russell2000"),
        ("nasdaq", FMP_RAW / "nasdaq_full"),
    ):
        mtf[univ] = {
            iv: _count_files(root / f"ohlcv_{iv}")
            for iv in ("eod", "1hour", "15min", "5min", "1min")
        }

    return {
        "ok": True,
        "lacie_mounted": LACIE_ROOT.exists(),
        "lacie_root": str(LACIE_ROOT),
        "mission": _read_json(PROCESSED / "telemetry" / "latest_flight.json"),
        "earnings_specialists": specialists,
        "mtf_counts": mtf,
        "research_index": _read_json(research / "index.json"),
    }


ROUTES = {
    "/health": lambda: {"ok": True, "service": "aether-backend"},
    "/api/status": build_status,
    "/api/research/earnings": lambda: {
        k: v
        for k, v in (build_status().get("earnings_specialists") or {}).items()
    },
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[aether-api] {self.address_string()} {fmt % args}", flush=True)

    def _send(self, code: int, body: dict | list) -> None:
        raw = json.dumps(body, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        # normalize /api/foo/
        if path != "/" and not path.startswith("/"):
            path = "/" + path
        fn = ROUTES.get(path) or ROUTES.get(path + "/")
        if fn is None and path == "":
            fn = ROUTES.get("/health")
        if fn is None:
            # specialist by name: /api/research/earnings/sp500_pre8
            m = re.match(r"^/api/research/earnings/([a-z0-9_]+)$", path)
            if m:
                p = PROCESSED / "research" / f"earnings_specialist_{m.group(1)}.json"
                data = _read_json(p)
                if data is None:
                    self._send(404, {"error": "not found", "name": m.group(1)})
                    return
                self._send(200, data)
                return
            self._send(404, {"error": "not found", "path": path, "routes": list(ROUTES)})
            return
        try:
            self._send(200, fn())
        except Exception as e:
            self._send(500, {"error": str(e)})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Aether local backend API")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"Aether backend http://{args.host}:{args.port}  "
        f"(health /api/status /api/research/earnings)",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutdown", flush=True)


if __name__ == "__main__":
    main()
