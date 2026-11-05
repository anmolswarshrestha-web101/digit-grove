"""Event-driven server design: a small publish/subscribe bus.

Code that does something (login, answer a puzzle ...) only *emits* an event.
Subscribers react to it. Here every event is written to the audit table.
"""
import json
import time

from .db import db


class EventBus:
    def __init__(self):
        self.handlers = {}

    def on(self, name, fn):
        self.handlers.setdefault(name, []).append(fn)

    def emit(self, name, **data):
        for fn in self.handlers.get(name, []):
            try:
                fn(data)
            except Exception as err:          # one broken subscriber must not break the request
                print(f'event handler for {name} failed: {err}')


bus = EventBus()
EVENTS = ('user.registered', 'user.login', 'user.logout',
          'game.started', 'challenge.issued', 'answer.submitted', 'game.finished')


def audit_handler(name):
    def write(data):
        detail = {k: v for k, v in data.items() if k != 'user_id'}
        with db() as conn:
            conn.execute('INSERT INTO audit(ts, event, user_id, detail) VALUES (?, ?, ?, ?)',
                         (time.time(), name, data.get('user_id'), json.dumps(detail)))
    return write


for _event in EVENTS:
    bus.on(_event, audit_handler(_event))
