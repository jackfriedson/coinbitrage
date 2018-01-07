from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'


EXCHANGES = ['bittrex', 'hitbtc', 'poloniex']

CURRENCIES = {
    'BCH': {
        'hitbtc_withdraw_fee': 0.002,
        'min_order_size': 0.019,
    },
    'BTC': {
        'hitbtc_withdraw_fee': 0.001,
        'min_order_size': 0.0017,
    },
    'ETH': {
        'hitbtc_withdraw_fee': 0.01,
        'min_order_size': 0.05,
    },
    'LTC': {
        'hitbtc_withdraw_fee': 0.003,
        'min_order_size': 0.16,
    },
    'LSK': {
        'hitbtc_withdraw_fee': 0.3,
        'min_order_size': 0.4,
    },
    'SC': {
        'hitbtc_withdraw_fee': 30.,
        'min_order_size': 100.,
    },
    'USDT': {
        'hitbtc_withdraw_fee': 100.,
        'min_order_size': 10,
    },
    'USD': {
        'hitbtc_withdraw_fee': 100.,
        'min_order_size': 10,
    },
    'XRP': {
        'hitbtc_withdraw_fee': 0.05,
        'min_order_size': 5,
    }
}


class Defaults(object):
    BASE_CURRENCIES = ['XRP']
    FILL_ORDER_TIMEOUT = 120
    HTTP_TIMEOUT = 20
    MIN_PROFIT = 0.
    ORDER_FEE = 0.0025
    ORDER_PRECISION = 0.002
    PLACE_ORDER_TIMEOUT = 60
    QUOTE_CURRENCY = 'BTC'
    REBALANCE_QUOTE_THRESHOLD = 0.9
    USDT_ASK = 1.01
    USDT_BID = 0.99
