from coinbitrage import settings

from .bitfinex import BitfinexAPIAdapter as Bitfinex
from .bitstamp import BitstampClient as Bitstamp
from .hitbtc import HitBTCAdapter as HitBTC
from .coinbase import CoinbaseClient as Coinbase
from .kraken import KrakenAPIAdapter as Kraken
from .poloniex import PoloniexClient as Poloniex


_exchange_map = {
    'bitfinex': Bitfinex,
    'bitstamp': Bitstamp,
    'coinbase': Coinbase,
    'hitbtc': HitBTC,
    'kraken': Kraken,
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
