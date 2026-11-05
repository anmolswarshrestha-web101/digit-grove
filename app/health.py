"""Health check route (used to see that the server is running)."""
import time

from .core import route


@route('GET', '/api/health')
def health(req):
    return 200, {'status': 'ok', 'time': round(time.time())}
