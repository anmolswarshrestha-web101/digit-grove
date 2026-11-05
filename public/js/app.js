// Digit Grove - account access, navigation and application shell.
const $ = sel => document.querySelector(sel);
let currentUser = null;
let authMode = 'login';

function setAuthMode(mode) {
  authMode = mode;
  const registering = mode === 'register';
  $('.auth-shell').classList.toggle('register-mode', registering);
  $('#password').minLength = registering ? 8 : 1;
  $('#authEyebrow').textContent = registering ? 'JOIN THE PUZZLE SPACE' : 'YOUR PUZZLE SPACE';
  $('#authTitle').textContent = registering ? 'Create your account' : 'Welcome back';
  $('#authIntro').textContent = registering ? 'Set up your player profile and start solving.' : 'Sign in to pick up where you left off.';
  $('#passwordHint').textContent = registering ? 'At least 8 characters' : 'Your password';
  $('#password').placeholder = registering ? 'Create a secure password' : 'Enter your password';
  $('#password').autocomplete = registering ? 'new-password' : 'current-password';
  $('#authSubmit').innerHTML = (registering ? 'Create account' : 'Sign in') + ' <span aria-hidden="true">→</span>';
  $('#modeLogin').classList.toggle('active', !registering);
  $('#modeRegister').classList.toggle('active', registering);
  $('#modeLogin').setAttribute('aria-pressed', String(!registering));
  $('#modeRegister').setAttribute('aria-pressed', String(registering));
  $('#authMsg').textContent = '';
}

function showApp(user) {
  currentUser = user;
  $('#who').textContent = user.username;
  $('#auth').hidden = true;
  $('#app').hidden = false;
  showPage('play');
}

function showAuth() {
  currentUser = null;
  setAuthMode('login');
  $('#app').hidden = true;
  $('#auth').hidden = false;
}

function showPage(name) {                                    // navigation between pages
  for (const sec of document.querySelectorAll('main > section')) sec.hidden = sec.id !== 'page-' + name;
  for (const tab of document.querySelectorAll('#nav .tab')) tab.classList.toggle('on', tab.dataset.page === name);
  bus.emit('page:show', name);
}

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3000);      // timeout event
}

async function submitAuth(kind) {                            // kind = 'login' or 'register'
  $('#authMsg').textContent = '';
  try {
    const data = await api('POST', '/api/' + kind, {
      username: $('#username').value.trim(),
      password: $('#password').value,
    });
    $('#password').value = '';
    bus.emit('auth:login', data.user);
  } catch (err) {
    $('#authMsg').textContent = err.message;
  }
}

// ----- events -----
$('#modeLogin').addEventListener('click', () => setAuthMode('login'));
$('#modeRegister').addEventListener('click', () => setAuthMode('register'));
$('#authForm').addEventListener('submit', e => { e.preventDefault(); submitAuth(authMode); });
$('#showpw').addEventListener('change', e => { $('#password').type = e.target.checked ? 'text' : 'password'; });
$('#nav').addEventListener('click', e => { if (e.target.dataset.page) showPage(e.target.dataset.page); });
$('#logout').addEventListener('click', async () => {
  await api('POST', '/api/logout');
  bus.emit('auth:logout');
});

bus.on('auth:login', showApp);
bus.on('auth:logout', showAuth);
bus.on('ui:toast', toast);

// ----- start: are we already logged in? -----
setAuthMode('login');
api('GET', '/api/me').then(d => bus.emit('auth:login', d.user)).catch(() => bus.emit('auth:logout'));
