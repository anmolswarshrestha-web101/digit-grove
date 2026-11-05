// Digit Grove - game screen (event driven: clicks, key presses, timer ticks, server replies).
const TIME_LIMIT = 30;
const game = { challenge: null, locked: true, timer: null, deadline: 0, seconds: TIME_LIMIT, retry: null };
const $g = sel => document.querySelector(sel);

function showPanel(name) {                                   // 'start' | 'game' | 'end'
  for (const p of ['start', 'game', 'end']) $g('#play-' + p).hidden = p !== name;
}

function setHud(g) {
  $g('#hudRound').textContent = `${Math.min(g.answered + 1, g.rounds)} / ${g.rounds}`;
  $g('#hudScore').textContent = g.score;
  $g('#hudStreak').textContent = g.streak;
}

function say(text, cls = '') {
  const el = $g('#feedback');
  el.textContent = text || '\u00a0';
  el.className = 'feedback ' + cls;
}

function startTimer(seconds) {
  clearInterval(game.timer);
  game.seconds = seconds;
  game.deadline = Date.now() + seconds * 1000;
  tick();
  game.timer = setInterval(tick, 100);                       // timer event
}

function tick() {
  const left = Math.max(0, (game.deadline - Date.now()) / 1000);
  $g('#hudTime').textContent = Math.ceil(left);
  $g('#timeFill').style.width = (left / TIME_LIMIT * 100) + '%';
  if (left <= 0) { clearInterval(game.timer); submit(null); }   // time is up: answer is null
}

function showChallenge(ch, g) {
  game.challenge = ch;
  $g('#puzzleImg').src = ch.image;
  setHud(g);
  say('');
  $g('#pad').classList.remove('off');
  game.locked = false;
  startTimer(ch.seconds);
}

async function startGame() {
  $g('#playMsg').textContent = '';
  $g('#startGame').disabled = true;
  try {
    const data = await api('POST', '/api/game/start');
    showPanel('game');
    showChallenge(data.challenge, data.game);
  } catch (err) {
    showPanel('start');
    $g('#playMsg').textContent = err.message;
  } finally {
    $g('#startGame').disabled = false;
  }
}

async function retryNext() {                                 // the Banana API failed while fetching the next puzzle
  const g = game.retry;
  game.retry = null;
  say('Loading the next puzzle...');
  try {
    const next = (await api('POST', '/api/game/next', { game_id: g.id })).challenge;
    showChallenge(next, g);
  } catch (err) {
    say(err.message + ' Press any digit to try again.', 'bad');
    game.retry = g;
    $g('#pad').classList.remove('off');
  }
}

async function submit(digit) {
  if (game.retry) return retryNext();
  if (game.locked || !game.challenge) return;
  game.locked = true;
  clearInterval(game.timer);
  $g('#pad').classList.add('off');
  try {
    const data = await api('POST', '/api/game/answer', { challenge_id: game.challenge.id, answer: digit });
    bus.emit('game:result', data);
  } catch (err) {
    say(err.message, 'bad');
  }
}

function describe(r) {
  const p = r.points;
  if (r.correct) return `Correct! +${p.total}  (base ${p.base}, speed +${p.speed}, streak +${p.streak})`;
  return (r.timed_out ? 'Time is up. ' : 'Not quite. ') + `The answer was ${r.solution}.`;
}

bus.on('game:result', data => {
  say(describe(data.result), data.result.correct ? 'ok' : 'bad');
  setHud(data.game);
  setTimeout(async () => {                                    // short pause so the player can read the result
    if (data.game.finished) return bus.emit('game:finished', data.game);
    try {
      const next = data.next || (await api('POST', '/api/game/next', { game_id: data.game.id })).challenge;
      showChallenge(next, data.game);
    } catch (err) {
      say(err.message + ' Press any digit to try again.', 'bad');
      game.retry = data.game;
      $g('#pad').classList.remove('off');
    }
  }, 1600);
});

bus.on('game:finished', g => {
  $g('#endScore').textContent = g.score;
  $g('#endCorrect').textContent = `${g.correct} / ${g.rounds}`;
  $g('#endStreak').textContent = g.best_streak;
  showPanel('end');
});

// ----- events -----
$g('#pad').innerHTML = [...Array(10).keys()].map(n => `<button data-n="${n}">${n}</button>`).join('');
$g('#pad').addEventListener('click', e => { if (e.target.dataset.n !== undefined) submit(+e.target.dataset.n); });
$g('#startGame').addEventListener('click', startGame);
$g('#playAgain').addEventListener('click', startGame);
document.addEventListener('keydown', e => {
  if (/^[0-9]$/.test(e.key) && !$g('#play-game').hidden) submit(+e.key);
  if (e.key === 'Enter' && !$g('#play-start').hidden && !$g('#app').hidden) startGame();
});
bus.on('auth:logout', () => { clearInterval(game.timer); game.locked = true; showPanel('start'); });
