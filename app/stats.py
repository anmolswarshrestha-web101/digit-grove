"""Leaderboard and player profile (read-only queries over the games, challenges and audit tables)."""
from .core import route
from .db import db


@route('GET', '/api/leaderboard', auth=True)
def leaderboard(req):
    with db() as conn:
        rows = conn.execute(
            "SELECT u.username, MAX(g.score) AS best, COUNT(g.id) AS games, CAST(ROUND(AVG(g.score)) AS INTEGER) AS average "
            "FROM games g JOIN users u ON u.id = g.user_id WHERE g.status = 'finished' "
            "GROUP BY u.id ORDER BY best DESC, games ASC LIMIT 10").fetchall()
    return 200, {'leaders': [dict(r) for r in rows], 'you': req.user['username']}


@route('GET', '/api/profile', auth=True)
def profile(req):
    uid = req.user['id']
    with db() as conn:
        totals = conn.execute(
            "SELECT COUNT(*) AS games, COALESCE(MAX(score), 0) AS best, COALESCE(CAST(ROUND(AVG(score)) AS INTEGER), 0) AS average "
            "FROM games WHERE user_id = ? AND status = 'finished'", (uid,)).fetchone()
        answers = conn.execute(
            "SELECT COUNT(*) AS answered, COALESCE(SUM(correct), 0) AS correct, "
            "AVG(CASE WHEN correct = 1 THEN seconds END) AS avg_seconds "
            "FROM challenges WHERE user_id = ? AND answered_at IS NOT NULL", (uid,)).fetchone()
        rank = None
        if totals['games']:
            rank = conn.execute(
                "SELECT COUNT(*) + 1 FROM (SELECT MAX(score) AS best FROM games WHERE status = 'finished' "
                "GROUP BY user_id) WHERE best > ?", (totals['best'],)).fetchone()[0]
        recent = conn.execute(
            "SELECT id, score, correct, best_streak, finished_at FROM games "
            "WHERE user_id = ? AND status = 'finished' ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        activity = conn.execute(
            "SELECT ts, event FROM audit WHERE user_id = ? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
    accuracy = round(100 * answers['correct'] / answers['answered']) if answers['answered'] else 0
    return 200, {
        'username': req.user['username'], 'games': totals['games'], 'best': totals['best'],
        'average': totals['average'], 'rank': rank, 'accuracy': accuracy,
        'avg_seconds': round(answers['avg_seconds'], 1) if answers['avg_seconds'] is not None else None,
        'recent': [dict(r) for r in recent], 'activity': [dict(r) for r in activity],
    }
