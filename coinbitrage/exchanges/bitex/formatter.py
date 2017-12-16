from typing import Dict, List

from coinbitrage.exchanges.base import BaseFormatter
from coinbitrage.exchanges.types import OrderBook, Trade


class BitExFormatter(BaseFormatter):

    def ticker(self, data):
        result = {
            'bid': data[0],
            'ask': data[1],
            'high': data[2],
            'low': data[3],
            'open': data[4],
            'close': data[5],
            'last': data[6],
            'volume': data[7],
            'time': data[8]
        }
        result = {k: float(v) for k, v in result.items() if v}
        return result

    def trades(self, data) -> List[Trade]:
        return [{
            'id': None,
            'time': trade[0],
            'price': trade[1],
            'amount': trade[2],
            'side': trade[3]
        } for trade in data]

    def order_book(self, data) -> OrderBook:
        return {
            'asks': [{'price': ask[1], 'amount': ask[2]} for ask in data['asks']],
            'bids': [{'price': bid[1], 'amount': bid[2]} for bid in data['bids']]
        }

    def balance(self, data) -> Dict[str, float]:
        return {
            self.format(cur, inverse=True): float(bal)
            for cur, bal in data.items() if float(bal) != 0.
        }
