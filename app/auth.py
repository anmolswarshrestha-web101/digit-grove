"""Virtual identity: registration, login, sessions.

* Passwords are never stored. We store a random salt and a PBKDF2-HMAC-SHA256 hash.
* A login creates a random session token. The browser keeps it in an HttpOnly cookie,
  the database keeps only its SHA-256 hash.
* Repeated wrong passwords are rate limited.
"""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time

from . import core
from .core import HttpError, route
from .db import db
from .events import bus

ITERATIONS = 200_000
SESSION_TTL = 24 * 3600
USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,20}$')
MAX_FAILS, WINDOW = 5, 60                 # 5 wrong passwords per minute
FAILS = {}                                # (ip, username) -> [timestamps]


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, hash_hex):
    _, digest = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest, hash_hex)          # constant-time comparison


DUMMY_SALT, DUMMY_HASH = hash_password('not-a-real-password')


def token_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_session(conn, user_id):
    conn.execute('DELETE FROM sessions WHERE expires_at < ?', (time.time(),))
    token = secrets.token_urlsafe(32)
    conn.execute('INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)',
                 (token_hash(token), user_id, time.time() + SESSION_TTL))
    return token


def cookie(token, max_age=SESSION_TTL):
    return ('Set-Cookie', f'tq_session={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={max_age}')


def user_from_token(token):
    if not token:
        return None
    with db() as conn:
        row = conn.execute(
            'SELECT u.id, u.username FROM sessions s JOIN users u ON u.id = s.user_id '
            'WHERE s.token_hash = ? AND s.expires_at > ?', (token_hash(token), time.time())).fetchone()
    return dict(row) if row else None


core.authenticate = user_from_token


def check_rate_limit(key):
    now = time.time()
    FAILS[key] = [t for t in FAILS.get(key, []) if now - t < WINDOW]
    if len(FAILS[key]) >= MAX_FAILS:
        raise HttpError(429, 'Too many wrong attempts. Please wait a minute.')


@route('POST', '/api/register')
def register(req):
    data = req.json()
    username, password = str(data.get('username', '')).strip(), str(data.get('password', ''))
    if not USERNAME_RE.match(username):
        raise HttpError(400, 'Username must be 3-20 letters, numbers or underscores.')
    if len(password) < 8:
        raise HttpError(400, 'Password must be at least 8 characters.')
    salt, pw_hash = hash_password(password)
    with db() as conn:
        try:
            cur = conn.execute('INSERT INTO users(username, salt, pw_hash, created_at) VALUES (?, ?, ?, ?)',
                               (username, salt, pw_hash, time.time()))
        except sqlite3.IntegrityError:
            raise HttpError(409, 'That username is already taken.')
        user_id = cur.lastrowid
        token = create_session(conn, user_id)
    bus.emit('user.registered', user_id=user_id)
    return 201, {'user': {'id': user_id, 'username': username}}, [cookie(token)]


@route('POST', '/api/login')
def login(req):
    data = req.json()
    username, password = str(data.get('username', '')).strip(), str(data.get('password', ''))
    key = (req.ip, username.lower())
    check_rate_limit(key)
    with db() as conn:
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        if row:
            ok = verify_password(password, row['salt'], row['pw_hash'])
        else:
            verify_password(password, DUMMY_SALT, DUMMY_HASH)     # same work for unknown users
            ok = False
        if not ok:
            FAILS.setdefault(key, []).append(time.time())
            raise HttpError(401, 'Wrong username or password.')
        FAILS.pop(key, None)
        token = create_session(conn, row['id'])                   # a fresh token on every login
    bus.emit('user.login', user_id=row['id'])
    return 200, {'user': {'id': row['id'], 'username': row['username']}}, [cookie(token)]


@route('POST', '/api/logout', auth=True)
def logout(req):
    with db() as conn:
        conn.execute('DELETE FROM sessions WHERE token_hash = ?', (token_hash(req.cookie('tq_session')),))
    bus.emit('user.logout', user_id=req.user['id'])
    return 204, None, [cookie('', 0)]


@route('GET', '/api/me', auth=True)
def me(req):
    return 200, {'user': req.user}
