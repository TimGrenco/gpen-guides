#!/usr/bin/env python3
"""Local preview server for the G Pen product guides."""

import functools
import http.server
import pathlib
import socketserver

PORT = 8811
ROOT = pathlib.Path(__file__).parent


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".yml": "text/yaml; charset=utf-8",
    }

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    handler = functools.partial(Handler, directory=str(ROOT))
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"G Pen guides → http://localhost:{PORT}/")
        print(f"Hydout guide → http://localhost:{PORT}/hydout/")
        httpd.serve_forever()
