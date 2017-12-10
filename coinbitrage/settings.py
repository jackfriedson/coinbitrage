from collections import defaultdict
from pathlib import Path

DEFAULT_FEE = 0.25
DEFAULT_QUOTE_CURRENCY = 'USD'
REQUESTS_TIMEOUT = (5, 10)

API_KEY_DIR = Path.home()/'.api_keys'
