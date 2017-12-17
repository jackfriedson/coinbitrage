import cmd
from typing import List

from coinbitrage.exchanges.manager import ExchangeManager


class CoinbitrageShell(cmd.Cmd):
    intro = 'Welcome to the Coinbitrage shell\n'
    prompt = '(coin) '
    file = None

    def __init__(self,
                 exchanges: List[str],
                 base_currency: str,
                 quote_currency: str,
                 *args, **kwargs):
        self._exchanges = ExchangeManager(exchanges, base_currency, quote_currency)
        self._active_exchange = None
        super(CoinbitrageShell, self).__init__(*args, **kwargs)

    def precmd(self, line: str):
        args = line.split()
        if args and args[0] in self._exchanges.names:
            exchg_name = args[0]
            self._active_exchange = self._exchanges.get(exchg_name)
            return line[len(exchg_name):]
        return line

    def postcmd(self, stop: bool, line: str):
        self._active_exchange = None
        return stop

    def do_balances(self, args: str):
        if '--update' in args:
            self._exchanges.update_trading_balances()
        balances = self._exchanges.balances
        if not self._active_exchange:
            print(balances)
        else:
            print(balances[self._active_exchange.name])

    def do_totals(self, args: str):
        if '--update' in args:
            self._exchanges.update_trading_balances()
        print(self._exchanges.totals)

    def do_deposit_address(self, currency: str):
        if self._active_exchange:
            addr = self._active_exchange.deposit_address(currency.upper())
            print(addr)

    def do_update(self, args: str):
        self._exchanges.update_trading_balances()

    def do_manage(self, args: str):
        self._exchanges.manage_balances()

    def do_exit(self, args: str):
        return True
