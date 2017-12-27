import click

from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine
from coinbitrage.exchanges import get_exchange
from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.settings import (CURRENCIES, EXCHANGES, DEFAULT_BASE_CURRENCIES,
                                  DEFAULT_QUOTE_CURRENCY)
from coinbitrage.shell import CoinbitrageShell


bitlogging.configure()


@click.group()
def coin():
    pass


@coin.command()
@click.option('--base-currency', type=list, default=DEFAULT_BASE_CURRENCIES)
@click.option('--quote-currency', type=click.Choice(CURRENCIES.keys()), default=DEFAULT_QUOTE_CURRENCY)
@click.option('--min-profit', type=float, default=0.001)
@click.option('--initial-tx-credit', type=float, default=0.)
def run(**kwargs):
    engine = ArbitrageEngine(exchanges=EXCHANGES, **kwargs)
    engine.run()


@coin.command()
@click.option('--base-currency', type=list, default=DEFAULT_BASE_CURRENCIES)
@click.option('--quote-currency', type=click.Choice(CURRENCIES.keys()), default=DEFAULT_QUOTE_CURRENCY)
def shell(base_currency, quote_currency):
    coin_shell = CoinbitrageShell(EXCHANGES, base_currency, quote_currency)
    coin_shell.cmdloop()


@coin.command()
def pdb():
    kraken = get_exchange('kraken')
    hitbtc = get_exchange('hitbtc')
    coinbase = get_exchange('coinbase')
    import ipdb; ipdb.set_trace()
