from collections import defaultdict
from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'


DEFAULT_FEE = 0.0025
DEFAULT_QUOTE_CURRENCY = 'USD'
REQUESTS_TIMEOUT = 10
TRANSFER_FEE = 0.01


CURRENCIES = {
    'BTC': {
        'ticker': 'BTC',
        'avg_tx_fee': 0.001,
        'order_size': 0.0017,
    },
    'ETH': {
        'ticker': 'ETH',
        'avg_tx_fee': 0.0012,
        'order_size': 0.06,
    }
}


for data in CURRENCIES.values():
    tx_fee = data.get('avg_tx_fee')
    data['min_transfer_size'] = tx_fee * (1. / TRANSFER_FEE)
