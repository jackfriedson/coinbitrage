from pathlib import Path


API_KEY_DIR = Path.home()/'.api_keys'


EXCHANGES = ['bitfinex', 'bittrex', 'hitbtc', 'kraken', 'poloniex']
INACTIVE_EXCHANGES = []


CURRENCIES = {
    'BCH': {
        'hitbtc_withdraw_fee': 0.002,
        'kraken_method': 'Bitcoin Cash',
        'kraken_withdraw_fee': 0.001,
        'min_order_size': 0.019,
    },
    'BTC': {
        'bitfinex_method': 'bitcoin',
        'hitbtc_withdraw_fee': 0.001,
        'kraken_method': 'Bitcoin',
        'kraken_withdraw_fee': 0.001,
        'min_order_size': 0.0017,
    },
    'ETC': {
        'bitfinex_method': 'ethereumc',
        'hitbtc_withdraw_fee': 0.005,
        'kraken_withdraw_fee': 0.005,
        'min_order_size': 0.5,
    },
    'ETH': {
        'bitfinex_method': 'ethereum',
        'hitbtc_withdraw_fee': 0.01,
        'kraken_withdraw_fee': 0.005,
        'kraken_method': 'Ether (Hex)',
        'min_order_size': 0.05,
    },
    'LTC': {
        'bitfinex_method': 'litecoin',
        'hitbtc_withdraw_fee': 0.003,
        'kraken_method': 'Litecoin',
        'kraken_withdraw_fee': 0.001,
        'min_order_size': 0.16,
    },
    'USDT': {
        'bitfinex_method': 'tetheruso',
        'hitbtc_withdraw_fee': 100.,
        'kraken_method': 'Tether USD',
        'kraken_withdraw_fee': 5.,
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
        'kraken_withdraw_fee': 0.02,
        'min_order_size': 10,
    },
}


class Defaults(object):
    BASE_CURRENCIES = ['XRP']
    FILL_ORDER_TIMEOUT = 60
    FLOAT_PRECISION = 9
    HI_BALANCE_PERCENT = 0.9
    HTTP_TIMEOUT = 20
    MIN_PROFIT = 0.005
    ORDER_BOOK_BUFFER = 0.25
    ORDER_FEE = 0.0025
    PLACE_ORDER_TIMEOUT = 45
    QUOTE_CURRENCY = 'BTC'
    RECEIVE_TIME_OFFSET = 1
    STALE_DATA_TIMEOUT = 10
    USDT_ASK = 1.01
    USDT_BID = 0.99
