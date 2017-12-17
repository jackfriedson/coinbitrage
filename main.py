import click

from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine
from coinbitrage.exchanges import get_exchange
from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.settings import (CURRENCIES, EXCHANGES, DEFAULT_BASE_CURRENCY,
                                  DEFAULT_QUOTE_CURRENCY)
from coinbitrage.shell import CoinbitrageShell


bitlogging.configure()


@click.group()
def coin():
    pass


@coin.command()
@click.option('--base-currency', type=click.Choice(CURRENCIES.keys()), default=DEFAULT_BASE_CURRENCY)
@click.option('--quote-currency', type=click.Choice(CURRENCIES.keys()), default=DEFAULT_QUOTE_CURRENCY)
@click.option('--min-profit', type=float, default=0.005)
@click.option('--transfers/--no-transfers', default=True)
def run(transfers: bool, **kwargs):
    engine = ArbitrageEngine(exchanges=EXCHANGES, **kwargs)
    engine.run(make_transfers=transfers)


@coin.command()
def shell():
    coin_shell = CoinbitrageShell(EXCHANGES, DEFAULT_BASE_CURRENCY, DEFAULT_QUOTE_CURRENCY)
    coin_shell.cmdloop()
