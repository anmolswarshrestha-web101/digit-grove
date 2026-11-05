"""Tiny framework: configuration, routing, request helpers and errors."""
import json
import os
from http.cookies import SimpleCookie

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Settings can be overridden with environment variables (tests do this).
CONFIG = {
    'db_path': os.environ.get('TQ_DB', os.path.join(ROOT, 'data', 'digit_grove.db')),
    'banana_api': os.environ.get('BANANA_API', 'https://marcconrad.com/uob/banana/api.php?out=json'),
}

ROUTES = {}          # (method, path) -> (function, needs_login)


def route(method, path, auth=False):
    """Decorator: register a function as the handler of METHOD PATH."""
    def register(fn):
        ROUTES[(method, path)] = (fn, auth)
        return fn
    return register


class HttpError(Exception):
    """Raise this anywhere to answer with an error status and a JSON message."""
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def authenticate(token):
    """Replaced by the auth module: returns the user row for a session token, or None."""
    return None


class Request:
    def __init__(self, handler, method, path, query):
        self.handler, self.method, self.path, self.query = handler, method, path, query
        self.user = None

    @property
    def ip(self):
        return self.handler.client_address[0]

    def cookie(self, name):
        morsel = SimpleCookie(self.handler.headers.get('Cookie', '')).get(name)
        return morsel.value if morsel else None

    def json(self):
        if 'application/json' not in self.handler.headers.get('Content-Type', ''):
            raise HttpError(415, 'JSON body required')
        length = int(self.handler.headers.get('Content-Length') or 0)
        if length > 10_000:
            raise HttpError(413, 'request body too large')
        try:
            data = json.loads(self.handler.rfile.read(length) or b'{}')
        except ValueError:
            raise HttpError(400, 'invalid JSON')
        if not isinstance(data, dict):
            raise HttpError(400, 'JSON object expected')
        return data
