from coinbitrage import settings

from .bitstamp import BitstampClient as Bitstamp
from .bittrex import BittrexClient as Bittrex
from .hitbtc import HitBTCClient as HitBTC
from .coinbase import CoinbaseClient as Coinbase
from .poloniex import PoloniexClient as Poloniex


_exchange_map = {
    'bitstamp': Bitstamp,
    'bittrex': Bittrex,
    'coinbase': Coinbase,
    'hitbtc': HitBTC,
    'poloniex': Poloniex
}


def get_exchange(name: str):
    """Gets the REST API adapter for the specified exchange.

    :param name: The name of the exchange
    """
    name = name.lower()
    api_key = str(settings.API_KEY_DIR/'{}.key'.format(name))
    kwargs = {}

    if name == 'coinbase':
        kwargs['gdax_key_file'] = str(settings.API_KEY_DIR/'gdax.key')

    return _exchange_map[name](api_key, **kwargs)
