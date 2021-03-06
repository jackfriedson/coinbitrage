import cmd
from typing import List, Union

import click

from coinbitrage.exchanges.manager import ExchangeManager
from coinbitrage.shell import commands as shell_commands


class CoinbitrageShell(cmd.Cmd):
    intro = 'Welcome to the Coinbitrage shell\n'
    prompt = '(coin) '
    file = None
    exit_commands = ['exit', 'quit', 'q']

    def __init__(self,
                 exchanges: List[str],
                 base_currency: Union[str, List[str]],
                 quote_currency: str,
                 *args, **kwargs):
        self._exchanges = ExchangeManager(exchanges, base_currency, quote_currency)
        super(CoinbitrageShell, self).__init__(*args, **kwargs)

    def parseline(self, line: str):
        args = line.split()
        if args[0] in self._exchanges.names:
            return args[0], args[1], args[2:]
        else:
            return None, args[0], args[1:]

    def onecmd(self, line: str):
        if not line:
            return self.emptyline()

        exchg, cmd, args = self.parseline(line)
        if cmd in self.exit_commands:
            return True
        self.lastcmd = line

        try:
            command = getattr(shell_commands, cmd)
        except AttributeError:
            return self.default(line)

        obj = {'exchanges': self._exchanges}
        if exchg:
            obj['active_exchange'] = self._exchanges.get(exchg)

        try:
            command(args, obj=obj)
        except SystemExit:
            pass
        except KeyboardInterrupt:
            return True
        except Exception as e:
            print(e)
