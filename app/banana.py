"""Interoperability: adapter for Marc Conrad's Banana API (University of Bedfordshire).

The API answers a plain HTTPS GET with JSON:
    { "question": "https://.../picture.png", "solution": 7 }
`question` is the link to a puzzle image, `solution` is the digit (0-9) that solves it.
We call it from the SERVER so the solution is never sent to the browser before the player answers.
"""
import json
import urllib.request

from .core import CONFIG, HttpError

TIMEOUT = 8          # seconds


def validate(data):
    """Check the JSON contract. Returns (image_url, solution) or raises ValueError."""
    if not isinstance(data, dict):
        raise ValueError('response is not a JSON object')
    image, solution = data.get('question'), data.get('solution')
    if not isinstance(image, str) or not image.startswith(('http://', 'https://')):
        raise ValueError('question is not an image URL')
    try:
        solution = int(solution)
    except (TypeError, ValueError):
        raise ValueError('solution is not a number')
    if not 0 <= solution <= 9:
        raise ValueError('solution is not a single digit')
    return image, solution


def fetch_puzzle():
    """Get one puzzle. Tries twice; if the API is down we answer 502 instead of crashing."""
    last_error = None
    for _ in range(2):
        try:
            request = urllib.request.Request(CONFIG['banana_api'],
                                             headers={'User-Agent': 'DigitGrove/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:      # follows redirects
                return validate(json.loads(response.read().decode('utf-8')))
        except Exception as err:
            last_error = err
    print('Banana API error:', last_error)
    raise HttpError(502, 'The Banana API is not available right now. Please try again.')
