import logging
import time
from contextlib import ContextDecorator, _GeneratorContextManager
from functools import wraps
from threading import Thread
from typing import Callable, List, Tuple, Union

from coinbitrage import bitlogging
from coinbitrage.exchanges.interfaces import PrivateExchangeAPI
from coinbitrage.exchanges.types import Timestamp


log = bitlogging.getLogger(__name__)


def thread_running(thread: Thread) -> bool:
    return thread and thread.is_alive()


def to_unixtime(ts: Timestamp) -> int:
    if isinstance(ts, pd.Timestamp):
        ts = ts.astype(int)
    return ts


def load_key_from(path: str) -> Tuple[str, str]:
    with open(path, 'rb') as f:
        key = f.readline().strip()
        secret = f.readline().strip()
    return key, secret


def retry_on_exception(*exc_classes, max_retries: int = 3, backoff_factor: float = 0.5):
    def decorator(func):
        @wraps(func)
        def retry_func(*args, **kwargs):
            retries = 0
            backoff = backoff_factor

            while True:
                try:
                    return func(*args, **kwargs)
                except exc_classes as e:
                    if retries >= max_retries:
                        log.debug('Max number of retries exceeded, raising...',
                                  event_name='retry_handler.max_retries_exceeded',
                                  event_data={'exception': e, 'max_retries': max_retries})
                        raise
                    retries += 1
                    log.debug('Caught {exception} -- Retrying in {backoff} seconds...',
                              event_name='retry_handler.will_retry',
                              event_data={'exception': e, 'backoff': backoff, 'try_num': retries})
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    break

        return retry_func
    return decorator


class run_every(object):
    def __init__(self, func: Callable, delay: int):
        self._func = func
        self._delay = delay
        self._next_scheduled = 0

    def __call__(self, *args, **kwargs):
        if self._next_scheduled > time.time():
            return

        result = self._func(*args, **kwargs)

        self._next_scheduled = time.time() + self._delay
        return result
