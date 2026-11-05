"""Game engine: a game has 5 rounds. Each round is one Tomato puzzle, answered with a digit 0-9.

Scoring (done on the server, never in the browser):
    correct answer  = 100 base points
                    + speed bonus  (up to 50, less the longer you take)
                    + streak bonus (10 for each correct answer in a row after the first, max 40)
    wrong or late   = 0 points and the streak resets
"""
import secrets
import time

from . import tomato
from .core import HttpError, route
from .db import db
from .events import bus

ROUNDS = 5
TIME_LIMIT = 30           # seconds per puzzle
GRACE = 3                 # seconds allowed for network delay
BASE, SPEED_MAX, STREAK_STEP, STREAK_CAP = 100, 50, 10, 40


def score_answer(correct, seconds, streak):
    """Points for one answer. `streak` counts this answer, so the first correct answer has streak 1."""
    if not correct:
        return {'base': 0, 'speed': 0, 'streak': 0, 'total': 0}
    speed = round(max(0, TIME_LIMIT - seconds) / TIME_LIMIT * SPEED_MAX)
    streak_bonus = min(STREAK_CAP, STREAK_STEP * (streak - 1))
    return {'base': BASE, 'speed': speed, 'streak': streak_bonus, 'total': BASE + speed + streak_bonus}


def game_view(row):
    return {'id': row['id'], 'score': row['score'], 'correct': row['correct'], 'answered': row['answered'],
            'streak': row['streak'], 'best_streak': row['best_streak'], 'rounds': ROUNDS,
            'finished': row['status'] == 'finished'}


def challenge_view(row, seconds_left=TIME_LIMIT):
    """What the browser may see. Note: no solution."""
    return {'id': row['id'], 'image': row['image'], 'round': row['round'], 'rounds': ROUNDS,
            'seconds': round(seconds_left, 1)}


def issue_challenge(game_id, user_id, round_no):
    image, solution = tomato.fetch_puzzle()                    # outbound call to the Tomato API
    cid = secrets.token_urlsafe(9)                             # unpredictable id
    with db() as conn:
        conn.execute('INSERT INTO challenges(id, game_id, user_id, round, image, solution, issued_at) '
                     'VALUES (?, ?, ?, ?, ?, ?, ?)', (cid, game_id, user_id, round_no, image, solution, time.time()))
        row = conn.execute('SELECT * FROM challenges WHERE id = ?', (cid,)).fetchone()
    bus.emit('challenge.issued', user_id=user_id, game_id=game_id, round=round_no)
    return challenge_view(row)


@route('POST', '/api/game/start', auth=True)
def start(req):
    user_id = req.user['id']
    with db() as conn:                                         # an unfinished game is abandoned
        conn.execute("UPDATE games SET status = 'abandoned', finished_at = ? WHERE user_id = ? AND status = 'active'",
                     (time.time(), user_id))
        game_id = conn.execute('INSERT INTO games(user_id, started_at) VALUES (?, ?)',
                               (user_id, time.time())).lastrowid
        game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
    bus.emit('game.started', user_id=user_id, game_id=game_id)
    try:
        challenge = issue_challenge(game_id, user_id, 1)
    except HttpError:
        with db() as conn:
            conn.execute("UPDATE games SET status = 'abandoned', finished_at = ? WHERE id = ?", (time.time(), game_id))
        raise
    return 201, {'game': game_view(game), 'challenge': challenge}


@route('POST', '/api/game/next', auth=True)
def next_challenge(req):
    """Resume a game: returns the unanswered puzzle, or fetches a new one if needed."""
    game_id = req.json().get('game_id')
    with db() as conn:
        game = conn.execute('SELECT * FROM games WHERE id = ?', (game_id,)).fetchone()
        if not game:
            raise HttpError(404, 'unknown game')
        if game['user_id'] != req.user['id']:
            raise HttpError(403, 'not your game')
        if game['status'] != 'active':
            raise HttpError(409, 'this game is over')
        open_row = conn.execute('SELECT * FROM challenges WHERE game_id = ? AND answered_at IS NULL', (game_id,)).fetchone()
    if open_row:
        left = max(0, TIME_LIMIT - (time.time() - open_row['issued_at']))
        return 200, {'game': game_view(game), 'challenge': challenge_view(open_row, left)}
    return 200, {'game': game_view(game), 'challenge': issue_challenge(game_id, req.user['id'], game['answered'] + 1)}


@route('POST', '/api/game/answer', auth=True)
def answer(req):
    data = req.json()
    cid, given = str(data.get('challenge_id', '')), data.get('answer')
    if given is not None and (isinstance(given, bool) or not isinstance(given, int) or not 0 <= given <= 9):
        raise HttpError(400, 'answer must be a digit from 0 to 9 (or null when time is up)')
    now = time.time()
    with db() as conn:
        ch = conn.execute('SELECT * FROM challenges WHERE id = ?', (cid,)).fetchone()
        if not ch:
            raise HttpError(404, 'unknown challenge')
        if ch['user_id'] != req.user['id']:
            raise HttpError(403, 'not your challenge')            # protects other players' puzzles
        if ch['answered_at'] is not None:
            raise HttpError(409, 'already answered')              # one answer per puzzle
        game = conn.execute('SELECT * FROM games WHERE id = ?', (ch['game_id'],)).fetchone()
        seconds = now - ch['issued_at']
        timed_out = given is None or seconds > TIME_LIMIT + GRACE      # a null answer means the browser's timer ran out
        correct = given is not None and not timed_out and given == ch['solution']
        streak = game['streak'] + 1 if correct else 0
        points = score_answer(correct, min(seconds, TIME_LIMIT), streak)
        answered = game['answered'] + 1
        finished = answered >= ROUNDS
        conn.execute('UPDATE challenges SET answered_at = ?, answer = ?, correct = ?, points = ?, seconds = ? WHERE id = ?',
                     (now, given, int(correct), points['total'], seconds, cid))
        conn.execute('UPDATE games SET score = score + ?, correct = correct + ?, answered = ?, streak = ?, '
                     'best_streak = MAX(best_streak, ?), status = ?, finished_at = ? WHERE id = ?',
                     (points['total'], int(correct), answered, streak, streak,
                      'finished' if finished else 'active', now if finished else None, game['id']))
        game = conn.execute('SELECT * FROM games WHERE id = ?', (game['id'],)).fetchone()
    result = {'correct': correct, 'solution': ch['solution'], 'timed_out': timed_out, 'points': points}
    bus.emit('answer.submitted', user_id=req.user['id'], challenge_id=cid, correct=correct,
             seconds=round(seconds, 1), points=points['total'])
    body = {'result': result, 'game': game_view(game), 'next': None}
    if finished:
        bus.emit('game.finished', user_id=req.user['id'], game_id=game['id'], score=game['score'])
    else:
        try:
            body['next'] = issue_challenge(game['id'], req.user['id'], answered + 1)
        except HttpError:
            pass                                                   # browser can call /api/game/next to retry
    return 200, body
