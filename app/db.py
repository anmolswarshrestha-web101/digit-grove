"""SQLite database (Python standard library: sqlite3). Every query uses ? placeholders."""
import os
import sqlite3
from contextlib import contextmanager

from .core import CONFIG

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  username   TEXT NOT NULL UNIQUE COLLATE NOCASE,
  salt       TEXT NOT NULL,
  pw_hash    TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS games (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  started_at  REAL NOT NULL,
  finished_at REAL,
  status      TEXT NOT NULL DEFAULT 'active',      -- active | finished | abandoned
  score       INTEGER NOT NULL DEFAULT 0,
  correct     INTEGER NOT NULL DEFAULT 0,
  answered    INTEGER NOT NULL DEFAULT 0,
  streak      INTEGER NOT NULL DEFAULT 0,
  best_streak INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS challenges (
  id          TEXT PRIMARY KEY,
  game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  user_id     INTEGER NOT NULL,
  round       INTEGER NOT NULL,
  image       TEXT NOT NULL,
  solution    INTEGER NOT NULL,                    -- secret: never sent to the browser
  issued_at   REAL NOT NULL,
  answered_at REAL,
  answer      INTEGER,
  correct     INTEGER,
  points      INTEGER,
  seconds     REAL
);
CREATE TABLE IF NOT EXISTS audit (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  ts      REAL NOT NULL,
  event   TEXT NOT NULL,
  user_id INTEGER,
  detail  TEXT
);
"""


@contextmanager
def db():
    """Open a connection, commit on success, roll back on error, always close."""
    path = CONFIG['db_path']
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    with db() as conn:
        conn.executescript(SCHEMA)
