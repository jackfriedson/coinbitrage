from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'

ACCEPTABLE_USDT_ASK = 1.01
ACCEPTABLE_USDT_BID = 0.99

DEFAULT_ORDER_FEE = 0.0025
DEFAULT_BASE_CURRENCIES = ['BCH', 'ETH', 'LTC']
DEFAULT_QUOTE_CURRENCY = 'USD'
ORDER_PRECISION = 0.0005

REQUESTS_TIMEOUT = 10
WAIT_FOR_FILL_TIMEOUT = 90


EXCHANGES = ['bittrex', 'hitbtc', 'kraken', 'poloniex']

CURRENCIES = {
    'BTC': {
        'order_size': 0.0017,
    },
    'ETH': {
        'order_size': 0.05,
    },
    'LTC': {
        'order_size': 0.16,
    },
    'BCH': {
        'order_size': 0.019,
    },
    'USDT': {
        'order_size': 25,
    },
    'USD': {
        'order_size': 25,
    },
}
