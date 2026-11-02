#!/usr/bin/env python3
"""Basis desk. One local page, public Polymarket data, no wallet and no orders.

    python server.py
    open http://127.0.0.1:8765
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from basis.analyze import analyze
from basis.markets import MarketClient

HERE = Path(__file__).resolve().parent
PAGE = (HERE / "static" / "index.html").read_text()
CLIENT = MarketClient()
HOST, PORT = "127.0.0.1", 8765


def read_markets(markets: list[dict]) -> list[dict]:
    return [{**market, "read": analyze(market)} for market in markets]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = PAGE.encode()
            self._send(200, "text/html; charset=utf-8", body)
            return
        if parsed.path == "/api/board":
            self._json({"markets": read_markets(CLIENT.board())})
            return
        if parsed.path == "/api/market":
            query = (parse_qs(parsed.query).get("q") or [""])[0]
            self._json({"markets": read_markets(CLIENT.lookup(query))})
            return
        self._send(404, "text/plain; charset=utf-8", b"not found")

    def _json(self, payload: dict):
        self._send(200, "application/json", json.dumps(payload).encode())

    def _send(self, status: int, content_type: str, body: bytes):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Basis desk at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
