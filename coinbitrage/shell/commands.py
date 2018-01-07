from functools import wraps
from pprint import PrettyPrinter

import click

from coinbitrage.settings import CURRENCIES


@click.command()
@click.option('--update/--no-update', default=False)
@click.option('--full/--not-full', default=False)
@click.pass_obj
def balances(obj, update: bool, full: bool):
    if update:
        obj['exchanges'].update_trading_balances()
    active_exchange = obj.get('active_exchange')
    balances = obj['exchanges'].balances(full=full)
    if active_exchange:
        balances = balances[active_exchange.name]
    PrettyPrinter().pprint(balances)


@click.command()
@click.pass_obj
def manage(obj):
    obj['exchanges'].manage_exchanges()


@click.command()
@click.option('--update/--no-update', default=False)
@click.option('--full/--not-full', default=False)
@click.pass_obj
def totals(obj, update: bool, full: bool):
    if update:
        obj['exchanges'].update_trading_balances()
    PrettyPrinter().pprint(obj['exchanges'].totals(full=full))


@click.command()
@click.argument('amount', type=float)
@click.argument('currency', type=str)
@click.option('from_exchange', '--from', type=str)
@click.option('to_exchange', '--to', type=str)
@click.pass_obj
def transfer(obj, amount, currency, from_exchange, to_exchange):
    to_exchg = obj['exchanges'].get(to_exchange)
    from_exchg = obj['exchanges'].get(from_exchange)
    to_exchg.get_funds_from(from_exchg, currency, amount)


# ---------------------- Exchange-specific commands ------------------------ #

def exchange_command(f):
    @click.pass_obj
    @wraps(f)
    def decorator(obj, *args, **kwargs):
        exchg = obj.get('active_exchange')
        if exchg:
            return f(exchg, *args, **kwargs)
    return decorator


@click.command()
@click.argument('currency', str)
@exchange_command
def address(exchg, currency: str):
    print(exchg.deposit_address(currency.upper()))


@click.command()
@click.option('base', '--base', type=str)
@click.option('quote', '--quote', type=str)
@exchange_command
def fee(exchg, base, quote):
    print(exchg.fee(base, quote))


@click.command()
@click.argument('base', type=str)
@click.argument('quote', type=str)
@exchange_command
def supports(exchg, base, quote):
    print(exchg.supports_pair(base, quote))


@click.command()
@click.argument('currency', type=str)
@exchange_command
def txfee(exchg, currency):
    print(exchg.tx_fee(currency))


@click.command()
@click.argument('amount', type=float)
@click.argument('currency', type=str)
@click.option('--address', type=str, prompt=True)
@exchange_command
def withdraw(exchg, amount, currency, address):
    exchg.withdraw(currency, address, amount)
