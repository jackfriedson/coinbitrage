from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'


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
        'order_size': 10,
    },
    'USD': {
        'order_size': 10,
    },
}


class Defaults(object):
    BASE_CURRENCIES = ['BCH', 'ETH', 'LTC']
    HTTP_TIMEOUT = 10
    ORDER_FEE = 0.0025
    ORDER_PRECISION = 0.0005
    ORDER_TIMEOUT = 90
    QUOTE_CURRENCY = 'USD'
    USDT_ASK = 1.01
    USDT_BID = 0.99
