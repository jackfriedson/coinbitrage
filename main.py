import click
import ipdb

from coinbitrage import bitlogging, settings
from coinbitrage.engine import ArbitrageEngine
from coinbitrage.exchanges import get_exchange
from coinbitrage.exchanges.manager import ExchangeManager


bitlogging.configure()


EXCHANGES = ['bittrex', 'kraken', 'poloniex']


@click.group()
def coin():
    pass


@coin.command()
@click.option('--base-currency', type=click.Choice(settings.CURRENCIES.keys()), default='ETH')
@click.option('--quote-currency', type=click.Choice(settings.CURRENCIES.keys()), default='USDT')
@click.option('--min-profit', type=float, default=0.005)
def run(**kwargs):
    engine = ArbitrageEngine(exchanges=EXCHANGES, **kwargs)
    engine.run()


@coin.command()
def shell():
    bitstamp = get_exchange('bitstamp')
    bittrex = get_exchange('bittrex')
    coinbase = get_exchange('coinbase')
    hitbtc = get_exchange('hitbtc')
    kraken = get_exchange('kraken')
    poloniex = get_exchange('poloniex')
    # TODO: find a better way to do this than ipdb
    exchanges = ExchangeManager(EXCHANGES, 'ETH', 'USDT')
    ipdb.set_trace()
