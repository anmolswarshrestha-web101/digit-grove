// Same-origin API client. Gives useful diagnostics instead of a vague "Request failed".
async function api(method, url, body) {
  const opts = { method, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(url, opts);
  } catch (cause) {
    const err = new Error('Cannot reach the Digit Grove server. Start it from the VS Code terminal with `py server.py` (Windows) or `python3 server.py` (Mac/Linux), then open http://localhost:8000.');
    err.cause = cause;
    throw err;
  }
  let data = null;
  try { data = await res.json(); } catch { /* server may return an empty response */ }
  if (!res.ok) {
    const messages = {
      400: 'Please check your username and password. Username: 3–20 letters, numbers or underscores; password: at least 8 characters.',
      409: 'That username is already taken. Please choose another.',
      415: 'The request format was not accepted. Refresh the page and try again.',
      429: 'Too many attempts. Please wait one minute and try again.',
      500: 'The server encountered an error. Restart Digit Grove from the VS Code terminal and check the terminal for details.'
    };
    const err = new Error((data && data.error) || messages[res.status] || `Request failed (HTTP ${res.status}).`);
    err.status = res.status;
    throw err;
  }
  return data;
}
