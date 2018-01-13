import click

from coinbitrage import bitlogging
from coinbitrage.engine import ArbitrageEngine
from coinbitrage.exchanges import get_exchange
from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.settings import CURRENCIES, EXCHANGES, INACTIVE_EXCHANGES, Defaults
from coinbitrage.shell import CoinbitrageShell


@click.group()
@click.option('-d', '--debug', is_flag=True)
def coin(debug):
    bitlogging.configure(debug=debug)


@coin.command()
@click.option('--base-currency', default=Defaults.BASE_CURRENCIES)
@click.option('--quote-currency', type=click.Choice(CURRENCIES.keys()), default=Defaults.QUOTE_CURRENCY)
@click.option('--min-profit', type=float, default=Defaults.MIN_PROFIT)
@click.option('--initial-tx-credit', type=float, default=0.)
def run(**kwargs):
    engine = ArbitrageEngine(exchanges=EXCHANGES, **kwargs)
    engine.run()


@coin.command()
@click.option('--base-currency', default=Defaults.BASE_CURRENCIES)
@click.option('--quote-currency', type=click.Choice(CURRENCIES.keys()), default=Defaults.QUOTE_CURRENCY)
def shell(base_currency, quote_currency):
    exchgs = EXCHANGES + INACTIVE_EXCHANGES
    coin_shell = CoinbitrageShell(exchgs, base_currency, quote_currency)
    coin_shell.cmdloop()


@coin.command()
def test():
    import time
    exchanges = ExchangeManager(['bitfinex'], Defaults.BASE_CURRENCIES, Defaults.QUOTE_CURRENCY)
    with exchanges.live_updates():
        try:
            bitfinex = exchanges.get('bitfinex')
            while True:
                bitfinex._update()
        except Exception as e:
            print(e)
