from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'
DEFAULT_ORDER_FEE = 0.0025
DEFAULT_QUOTE_CURRENCY = 'USDT'
MAX_TRANSFER_FEE = 0.01
ORDER_PRECISION = 0.001
REQUESTS_TIMEOUT = 10


# TODO: refactor this info and fetch up-to-date tx fees on startup
CURRENCIES = {
    'BTC': {
        'est_tx_fee': 0.001,
        'order_size': 0.0017,
    },
    'ETH': {
        'est_tx_fee': 0.0012,
        'order_size': 0.06,
    },
    'LTC': {
        'est_tx_fee': 0.0075,
        'order_size': 0.16,
    },
    'BCH': {
        'est_tx_fee': 0.0003,
        'order_size': 0.019,
    },
    'USDT': {
        'est_tx_fee': 5.,
        'order_size': 25,
    }
}


for data in CURRENCIES.values():
    data['min_transfer_size'] = data['est_tx_fee'] * (1. / MAX_TRANSFER_FEE)
