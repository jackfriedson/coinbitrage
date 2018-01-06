from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'


EXCHANGES = ['bittrex', 'hitbtc', 'poloniex']

CURRENCIES = {
    'BCH': {'order_size': 0.019,},
    'BTC': {'order_size': 0.0017,},
    'ETH': {'order_size': 0.05,},
    'LTC': {'order_size': 0.16,},
    'USDT': {'order_size': 10,},
    'USD': {'order_size': 10,},
    'XRP': {'order_size': 5,}
}


class Defaults(object):
    BASE_CURRENCIES = ['XRP', 'LTC', 'ETH']
    FILL_ORDER_TIMEOUT = 120
    HTTP_TIMEOUT = 15
    MIN_PROFIT = 0.
    ORDER_FEE = 0.0025
    ORDER_PRECISION = 0.001
    PLACE_ORDER_TIMEOUT = 60
    QUOTE_CURRENCY = 'BTC'
    REBALANCE_QUOTE_THRESHOLD = 0.9
    USDT_ASK = 1.01
    USDT_BID = 0.99
