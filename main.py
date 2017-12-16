import click

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
@click.option('--transfers/--no-transfers', default=True)
def run(transfers: bool, **kwargs):
    engine = ArbitrageEngine(exchanges=EXCHANGES, **kwargs)
    engine.run(transfers=transfers)


@coin.command()
def shell():
    # TODO: find a better way to do this than ipdb
    exchanges = ExchangeManager(EXCHANGES, 'ETH', 'USDT')
    kraken = exchanges.get('kraken')
    poloniex = exchanges.get('poloniex')
    bittrex = exchanges.get('bittrex')
    import ipdb; ipdb.set_trace()
