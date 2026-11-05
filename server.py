#!/usr/bin/env python3
"""Digit Grove - server entry point.

Serves the web client from ./public and the JSON API under /api/.
Only the Python standard library is used, so there is nothing to install.

    py server.py            (then open http://localhost:8000)
"""
import json
import mimetypes
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from app import core
from app.core import ROUTES, HttpError, Request

# Feature modules register their routes when they are imported.
from app import auth, db, game, health, stats  # noqa: F401,E402

PUBLIC = os.path.join(core.ROOT, 'public')
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'same-origin',
    'Content-Security-Policy': "default-src 'self'; img-src 'self' data: http: https:; style-src 'self'; script-src 'self'",
}


class Handler(BaseHTTPRequestHandler):
    server_version = 'DigitGrove/1.0'

    def log_message(self, fmt, *args):
        if not os.environ.get('TQ_QUIET'):
            super().log_message(fmt, *args)

    # ---- responses ----
    def send_bytes(self, status, body, ctype, extra=()):
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for key, value in {**SECURITY_HEADERS}.items():
            self.send_header(key, value)
        for key, value in extra:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, obj, extra=()):
        body = b'' if obj is None else json.dumps(obj).encode('utf-8')
        self.send_bytes(status, body, 'application/json', extra)

    # ---- routing ----
    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def dispatch(self, method):
        parts = urlsplit(self.path)
        try:
            if parts.path.startswith('/api/'):
                self.handle_api(method, parts.path, parse_qs(parts.query))
            elif method == 'GET':
                self.handle_static(parts.path)
            else:
                raise HttpError(405, 'method not allowed')
        except HttpError as err:
            self.send_json(err.status, {'error': err.message})
        except Exception:                      # a bug on our side: log it, tell the client nothing secret
            traceback.print_exc()
            self.send_json(500, {'error': 'internal server error'})

    def handle_api(self, method, path, query):
        entry = ROUTES.get((method, path))
        if not entry:
            raise HttpError(404, 'not found')
        fn, needs_login = entry
        if method == 'POST' and self.headers.get('X-Requested-With') != 'fetch':
            raise HttpError(403, 'missing X-Requested-With header')      # simple CSRF defence
        req = Request(self, method, path, query)
        if needs_login:
            req.user = core.authenticate(req.cookie('tq_session'))
            if not req.user:
                raise HttpError(401, 'please log in')
        result = fn(req)
        extra = result[2] if len(result) > 2 else ()
        self.send_json(result[0], result[1], extra)

    def handle_static(self, path):
        if path == '/':
            path = '/index.html'
        full = os.path.normpath(os.path.join(PUBLIC, path.lstrip('/')))
        if not full.startswith(PUBLIC + os.sep) or not os.path.isfile(full):   # blocks ../ tricks
            raise HttpError(404, 'not found')
        ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        with open(full, 'rb') as fh:
            self.send_bytes(200, fh.read(), ctype)


def create_server(port=8000, host='127.0.0.1'):
    db.init()
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f'Digit Grove running at http://localhost:{port}  (Ctrl+C to stop)')
    create_server(port).serve_forever()
