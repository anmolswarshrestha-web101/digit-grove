# Digit Grove — Visual Number Puzzle Game

Digit Grove is a browser-based visual number puzzle game. Players can create an account, sign in, play five timed rounds, earn points, view the leaderboard and review personal game statistics.

## Open and run the project in Visual Studio Code

1. Install **Python 3.9 or newer** and **Visual Studio Code**.
2. In VS Code, choose **File → Open Folder...** and select this `Digit_Grove` project folder.
3. If prompted, install the recommended **Python** extension.
4. Open **Terminal → New Terminal**. Make sure the terminal is in the folder that contains `server.py`.
5. Start the local server:
   - Windows: `py server.py`
   - macOS/Linux: `python3 server.py`
6. Open `http://localhost:8000` in Chrome or another browser.
7. Keep the VS Code terminal running while you use the game. Press `Ctrl+C` in that terminal to stop it.

You can also press **Ctrl+Shift+B** in VS Code to run the included **Run Digit Grove server** task. The task runs the Python file in VS Code's integrated terminal; there is no batch file or separate launcher required.

> Do not open `public/index.html` directly as a `file://` page. The browser needs the Python server for account registration, login, game requests and statistics.

## Project structure

- `server.py` — local HTTP server and API entry point.
- `app/` — Python API routes, account security, database, game logic and Banana API integration.
- `public/index.html` — page structure.
- `public/style.css` — visual design and responsive layouts.
- `public/js/` — browser-side API client, event bus, game, leaderboard and account interface.
- `tests/` — automated backend tests.
- `.vscode/tasks.json` — VS Code task for running the server from the integrated terminal.

## Features

- Account registration and login.
- PBKDF2-HMAC-SHA256 password hashing with per-user random salts.
- Random server-side sessions and HttpOnly cookies.
- Visual number puzzles supplied by the Banana API.
- Five rounds, 30 seconds per round, base/speed/streak scoring.
- Server-side answer checking; puzzle solutions are not sent to the browser before submission.
- Leaderboard, player statistics and activity log.
- Responsive sign-in and registration layouts.

## Run the tests

Open the VS Code terminal in this folder and run:

```bash
python -m unittest discover tests -v
```

The automated tests use a local mock puzzle service and do not require the live Banana API.

## Troubleshooting

- If the browser cannot connect, confirm the VS Code terminal still shows `Digit Grove running at http://localhost:8000`.
- If port 8000 is already in use, run `py server.py 8001` on Windows or `python3 server.py 8001` on macOS/Linux, then open `http://localhost:8001`.
- If a page looks out of date, refresh the browser with `Ctrl+Shift+R`.
- If the puzzle provider is temporarily unavailable, account access may still work while starting a new puzzle reports an upstream service error.

## Understanding the code

For an account-registration walkthrough, follow the request through `public/js/app.js`, `public/js/api.js`, `server.py`, `app/auth.py` and `app/db.py`. Make sure you understand each part and can explain it in your own words before presenting the project.
