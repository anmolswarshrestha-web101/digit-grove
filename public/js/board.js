// Digit Grove - leaderboard and profile pages (event driven: they load when their page is shown).
const $b = sel => document.querySelector(sel);

function cell(text) {
  const td = document.createElement('td');
  td.textContent = text;                                     // textContent: never interpreted as HTML
  return td;
}

function fill(tbody, rows, mark) {
  tbody.replaceChildren();
  for (const values of rows) {
    const tr = document.createElement('tr');
    if (mark && mark(values)) tr.className = 'you';
    values.forEach(v => tr.appendChild(cell(v)));
    tbody.appendChild(tr);
  }
}

async function loadBoard() {
  const data = await api('GET', '/api/leaderboard');
  fill($b('#boardTable tbody'),
       data.leaders.map((r, i) => [i + 1, r.username, r.best, r.average, r.games]),
       row => row[1] === data.you);
  $b('#boardEmpty').hidden = data.leaders.length > 0;
}

const eventNames = {
  'user.registered': 'Account created', 'user.login': 'Logged in', 'user.logout': 'Logged out',
  'game.started': 'Game started', 'challenge.issued': 'Puzzle received from the Tomato API',
  'answer.submitted': 'Answer submitted', 'game.finished': 'Game finished',
};

async function loadProfile() {
  const p = await api('GET', '/api/profile');
  $b('#profName').textContent = p.username;
  $b('#pBest').textContent = p.best;
  $b('#pRank').textContent = p.rank ? '#' + p.rank : '-';
  $b('#pGames').textContent = p.games;
  $b('#pAcc').textContent = p.accuracy + '%';
  $b('#pTime').textContent = p.avg_seconds === null ? '-' : p.avg_seconds + ' s';
  fill($b('#recentTable tbody'), p.recent.map(g => [new Date(g.finished_at * 1000).toLocaleString(), g.score, g.correct + ' / 5', g.best_streak]));
  const list = $b('#activity');
  list.replaceChildren();
  for (const a of p.activity) {
    const li = document.createElement('li');
    const name = document.createElement('span');
    name.textContent = eventNames[a.event] || a.event;
    const when = document.createElement('span');
    when.className = 'when';
    when.textContent = new Date(a.ts * 1000).toLocaleTimeString();
    li.append(name, when);
    list.appendChild(li);
  }
}

bus.on('page:show', name => {
  if (name === 'board') loadBoard().catch(err => bus.emit('ui:toast', err.message));
  if (name === 'profile') loadProfile().catch(err => bus.emit('ui:toast', err.message));
});
