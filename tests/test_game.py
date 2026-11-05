"""Automated tests (standard library unittest). Run from the project folder:  python -m unittest discover tests -v"""
import http.cookiejar
import http.server
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

os.environ['TQ_QUIET'] = '1'
from app import auth, core, db, game, banana  # noqa: E402
import server  # noqa: E402


class MockBanana(http.server.BaseHTTPRequestHandler):
    """Pretends to be the Banana API so the tests do not need the internet."""
    broken = False

    def log_message(self, *args):
        pass

    def do_GET(self):
        if MockBanana.broken:
            self.send_response(500)
            self.end_headers()
            return
        body = json.dumps({'question': 'https://example.com/puzzle.png', 'solution': 7}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(body)


class Client:
    def __init__(self, base):
        self.base = base
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None):
        headers = {'Content-Type': 'application/json', 'X-Requested-With': 'fetch'}
        data = None if body is None else json.dumps(body).encode()
        try:
            res = self.opener.open(urllib.request.Request(self.base + path, data=data, headers=headers, method=method))
            text = res.read()
            return res.status, json.loads(text) if text else None
        except urllib.error.HTTPError as err:
            text = err.read()
            return err.code, json.loads(text) if text else None


class UnitTests(unittest.TestCase):
    def test_scoring(self):
        self.assertEqual(game.score_answer(False, 5, 0)['total'], 0)
        self.assertEqual(game.score_answer(True, 0, 1)['total'], 150)          # 100 + 50 speed + 0 streak
        self.assertEqual(game.score_answer(True, 30, 1)['total'], 100)         # no speed bonus when slow
        self.assertEqual(game.score_answer(True, 15, 3)['total'], 100 + 25 + 20)
        self.assertEqual(game.score_answer(True, 30, 99)['streak'], game.STREAK_CAP)

    def test_banana_contract(self):
        self.assertEqual(banana.validate({'question': 'https://x/y.png', 'solution': 4}), ('https://x/y.png', 4))
        for bad in [None, {}, {'question': 'ftp://x', 'solution': 1}, {'question': 'https://x', 'solution': 12},
                    {'question': 'https://x', 'solution': 'abc'}]:
            with self.assertRaises(ValueError):
                banana.validate(bad)

    def test_password_hashing(self):
        salt, digest = auth.hash_password('correct horse')
        self.assertNotIn('correct', digest)
        self.assertTrue(auth.verify_password('correct horse', salt, digest))
        self.assertFalse(auth.verify_password('wrong horse', salt, digest))
        self.assertNotEqual(auth.hash_password('correct horse')[1], digest)       # new salt -> new hash


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        core.CONFIG['db_path'] = os.path.join(cls.tmp, 'test.db')
        cls.mock = http.server.ThreadingHTTPServer(('127.0.0.1', 0), MockBanana)
        core.CONFIG['banana_api'] = f'http://127.0.0.1:{cls.mock.server_address[1]}/api'
        cls.srv = server.create_server(0)
        for s in (cls.mock, cls.srv):
            threading.Thread(target=s.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.srv.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.mock.shutdown()
        cls.srv.shutdown()

    def setUp(self):
        MockBanana.broken = False
        self.users = getattr(ApiTests, 'counter', 0) + 1
        ApiTests.counter = self.users

    def player(self):
        c = Client(self.base)
        status, _ = c.call('POST', '/api/register', {'username': f'player{self.users}_{time.time_ns() % 10**6}', 'password': 'password123'})
        self.assertEqual(status, 201)
        return c

    def test_protected_routes_need_login(self):
        self.assertEqual(Client(self.base).call('POST', '/api/game/start')[0], 401)

    def test_solution_is_never_sent_to_the_browser(self):
        c = self.player()
        status, body = c.call('POST', '/api/game/start')
        self.assertEqual(status, 201)
        self.assertNotIn('solution', json.dumps(body))
        self.assertEqual(body['challenge']['image'], 'https://example.com/puzzle.png')

    def test_correct_and_wrong_answers(self):
        c = self.player()
        _, started = c.call('POST', '/api/game/start')
        status, res = c.call('POST', '/api/game/answer', {'challenge_id': started['challenge']['id'], 'answer': 7})
        self.assertEqual(status, 200)
        self.assertTrue(res['result']['correct'])
        self.assertGreaterEqual(res['result']['points']['total'], 100)
        _, res2 = c.call('POST', '/api/game/answer', {'challenge_id': res['next']['id'], 'answer': 3})
        self.assertFalse(res2['result']['correct'])
        self.assertEqual(res2['result']['points']['total'], 0)
        self.assertEqual(res2['game']['streak'], 0)

    def test_cannot_answer_twice(self):
        c = self.player()
        _, started = c.call('POST', '/api/game/start')
        cid = started['challenge']['id']
        self.assertEqual(c.call('POST', '/api/game/answer', {'challenge_id': cid, 'answer': 7})[0], 200)
        self.assertEqual(c.call('POST', '/api/game/answer', {'challenge_id': cid, 'answer': 7})[0], 409)

    def test_other_players_challenge_is_forbidden(self):
        a, b = self.player(), self.player()
        _, started = a.call('POST', '/api/game/start')
        self.assertEqual(b.call('POST', '/api/game/answer', {'challenge_id': started['challenge']['id'], 'answer': 7})[0], 403)

    def test_invalid_answers_are_rejected(self):
        c = self.player()
        _, started = c.call('POST', '/api/game/start')
        for bad in (10, -1, 'x', True, 3.5):
            self.assertEqual(c.call('POST', '/api/game/answer', {'challenge_id': started['challenge']['id'], 'answer': bad})[0], 400)

    def test_late_answer_scores_zero(self):
        c = self.player()
        _, started = c.call('POST', '/api/game/start')
        with db.db() as conn:
            conn.execute('UPDATE challenges SET issued_at = issued_at - 100 WHERE id = ?', (started['challenge']['id'],))
        _, res = c.call('POST', '/api/game/answer', {'challenge_id': started['challenge']['id'], 'answer': 7})
        self.assertTrue(res['result']['timed_out'])
        self.assertFalse(res['result']['correct'])

    def test_full_game_finishes_after_five_rounds(self):
        c = self.player()
        _, res = c.call('POST', '/api/game/start')
        challenge = res['challenge']
        for round_no in range(1, game.ROUNDS + 1):
            _, res = c.call('POST', '/api/game/answer', {'challenge_id': challenge['id'], 'answer': 7})
            challenge = res['next']
        self.assertTrue(res['game']['finished'])
        self.assertIsNone(res['next'])
        self.assertEqual(res['game']['correct'], game.ROUNDS)
        self.assertEqual(res['game']['best_streak'], game.ROUNDS)

    def test_leaderboard_and_profile(self):
        c = self.player()
        _, res = c.call('POST', '/api/game/start')
        challenge = res['challenge']
        for _ in range(game.ROUNDS):
            _, res = c.call('POST', '/api/game/answer', {'challenge_id': challenge['id'], 'answer': 7})
            challenge = res['next']
        status, board = c.call('GET', '/api/leaderboard')
        self.assertEqual(status, 200)
        self.assertTrue(any(row['best'] >= 500 for row in board['leaders']))
        status, prof = c.call('GET', '/api/profile')
        self.assertEqual((status, prof['games'], prof['accuracy']), (200, 1, 100))
        self.assertGreaterEqual(prof['best'], 500)
        self.assertTrue(prof['recent'] and prof['activity'])
        self.assertEqual(Client(self.base).call('GET', '/api/profile')[0], 401)

    def test_banana_api_down_gives_502(self):
        c = self.player()
        MockBanana.broken = True
        self.assertEqual(c.call('POST', '/api/game/start')[0], 502)

    def test_events_are_audited(self):
        c = self.player()
        c.call('POST', '/api/game/start')
        with db.db() as conn:
            names = {r['event'] for r in conn.execute('SELECT event FROM audit')}
        self.assertTrue({'user.registered', 'game.started', 'challenge.issued'} <= names)


if __name__ == '__main__':
    unittest.main()
