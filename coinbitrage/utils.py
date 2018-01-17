import logging
import time
from contextlib import ContextDecorator, _GeneratorContextManager
from functools import wraps
from threading import Thread
from typing import Callable, List, Tuple, Union

from coinbitrage import bitlogging
from coinbitrage.exchanges.interfaces import PrivateExchangeAPI
from coinbitrage.exchanges.types import Timestamp
from coinbitrage.settings import Defaults


log = bitlogging.getLogger(__name__)


def format_floats(value, precision: int = Defaults.FLOAT_PRECISION):
    if isinstance(value, float):
        return f'{value:.{precision}f}'
    elif isinstance(value, list):
        return [format_floats(v) for v in value]
    elif isinstance(value, set):
        return {format_floats(v) for v in value}
    elif isinstance(value, tuple):
        return tuple(format_floats(v) for v in value)
    elif isinstance(value, dict):
        return {k: format_floats(v) for k, v in value.items()}
    else:
        return value


def format_log_args(args: tuple, kwargs: dict) -> tuple:
    return tuple(list(args) + ['{}={}'.format(kw, arg) for kw, arg in kwargs.items()])


def thread_running(thread: Thread) -> bool:
    if thread is None:
        return False

    return thread.is_alive()


def to_unixtime(ts: Timestamp) -> int:
    if isinstance(ts, pd.Timestamp):
        ts = ts.astype(int)
    return ts


def load_key_from(path: str) -> Tuple[str, str]:
    with open(path, 'rb') as f:
        key = f.readline().strip()
        secret = f.readline().strip()
    return key, secret


def retry_on_exception(*exc_classes, max_retries: int = 4, backoff_factor: float = 0.5):
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


# TODO: see if this can be made into a decorator
class RunEvery(object):
    """Ensures the given function is only run at most once every `delay` seconds. If
    called before `delay` seconds have passed since the last call, the function becomes
    a no-op. Especially useful in loops where some functions should be run every iteration
    and others only at certain intervals.
    """

    def __init__(self, func: Callable, delay: int, first_delay: bool = False):
        self._func = func
        self._delay = delay
        self._next_scheduled = time.time() if first_delay else 0

    def __call__(self, *args, **kwargs):
        if self._next_scheduled > time.time():
            return

        result = self._func(*args, **kwargs)

        self._next_scheduled = time.time() + self._delay
        return result
