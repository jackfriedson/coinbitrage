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


class _GeneratorContextDecorator(_GeneratorContextManager, ContextDecorator):
    pass


def _contextmanager(func):
    @wraps(func)
    def helper(*args, **kwds):
        return _GeneratorContextDecorator(func, args, kwds)
    return helper


@_contextmanager
def retry_on_exception(*exc_classes, max_retries: int = 3, backoff_factor: float = 0.5):
    retries = 0
    backoff = backoff_factor

    while True:
        try:
            yield
        except exc_classes as e:
            if retries >= max_retries:
                log.debug('Max number of retries exceeded, raising...',
                          event_name='retry_handler.max_retries_exceeded',
                          event_data={'exc': e, 'max_retries': max_retries})
                raise
            retries += 1
            log.debug('Caught {exc} -- Retrying in {backoff} seconds...',
                      event_name='retry_handler.will_retry',
                      event_data={'exc': exc, 'backoff': backoff, 'try_num': retries})
            time.sleep(backoff)
            backoff *= 2
        else:
            break
