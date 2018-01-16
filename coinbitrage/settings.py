from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'


EXCHANGES = ['bitfinex', 'bittrex', 'hitbtc', 'poloniex']
# INACTIVE_EXCHANGES = ['kraken']
INACTIVE_EXCHANGES = []

CURRENCIES = {
    'BCH': {
        'hitbtc_withdraw_fee': 0.002,
        'kraken_method': 'Bitcoin Cash',
        'min_order_size': 0.019,
    },
    'BTC': {
        'bitfinex_method': 'bitcoin',
        'hitbtc_withdraw_fee': 0.001,
        'kraken_method': 'Bitcoin',
        'min_order_size': 0.0017,
    },
    'ETC': {
        'bitfinex_method': 'ethereumc',
        'hitbtc_withdraw_fee': 0.005,
        'min_order_size': 0.5,
    },
    'ETH': {
        'bitfinex_method': 'ethereum',
        'hitbtc_withdraw_fee': 0.01,
        'kraken_method': 'Ether (Hex)',
        'min_order_size': 0.05,
    },
    'LTC': {
        'bitfinex_method': 'litecoin',
        'hitbtc_withdraw_fee': 0.003,
        'kraken_method': 'Litecoin',
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
        'bitfinex_method': 'tetheruso',
        'hitbtc_withdraw_fee': 100.,
        'kraken_method': 'Tether USD',
        'min_order_size': 20,
    },
    'USD': {
        'bitfinex_method': 'tetheruso',
        'hitbtc_withdraw_fee': 100.,
        'min_order_size': 20,
    },
    'XRP': {
        'bitfinex_method': 'ripple',
        'hitbtc_withdraw_fee': 0.6,
        'kraken_method': 'Ripple XRP',
        'min_order_size': 10,
    },
    'ZEC': {
        'bitfinex_method': 'zcash',
        'hitbtc_withdraw_fee': 0.0001,
        'min_order_size': 0.01,
    }
}


class Defaults(object):
    BASE_CURRENCIES = ['XRP', 'ETC']
    FILL_ORDER_TIMEOUT = 120
    HI_BALANCE_PERCENT = 0.9
    HTTP_TIMEOUT = 20
    MAX_REFRESH_DELAY = 5
    MIN_PROFIT = 0.
    ORDER_FEE = 0.0025
    LOW_PRECISION = 0.004
    HI_PRECISION = 0.002
    PLACE_ORDER_TIMEOUT = 60
    QUOTE_CURRENCY = 'BTC'
    RECEIVE_TIME_OFFSET = 1
    USDT_ASK = 1.01
    USDT_BID = 0.99
