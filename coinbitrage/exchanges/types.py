import datetime
from typing import Any, Dict, List, Union


Timestamp = Union[int, datetime.datetime]
"""A Timestamp can be either an integer representing a POSIX timestamp, or a
datetime object.
"""

OHLC = Dict[str, Union[Timestamp, float]]
"""
    {
        'datetime': ...,
        'open': ...,
        'high': ...,
        'low': ...,
        'close': ...,
        'volume': ...,
    }
"""

Order = Dict[str, Any]
"""
    {
        'id': ...,
        'status': ...,
        'side': ...,
        'ask_price': ...,
        'volume': ...,
        'fill_price': ...,
        'trades': ...,
        'fee': ...,
    }
"""

OrderBook = Dict[str, List[Dict[str, float]]]
"""
    {
        'asks': [ { 'price': ..., 'amount': ... }, ... ],
        'bids': [ { 'price': ..., 'amount': ... }, ... ]
    }
"""

Trade = Dict[str, float]
"""
        {
            'id': ... ,
            'timestamp': ...,
            'price': ...,
            'amount': ...,
            'side': ...
        }
"""
