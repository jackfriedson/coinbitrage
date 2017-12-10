import logging
import time
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


class retry_on_status_code(object):
    def __init__(self,
                 status_codes: Union[int, List[int]],
                 max_retries: int= 5,
                 backoff_factor: float = 0.5):
        if type(status_codes) is int:
            status_codes = [status_codes]

        self.status_codes = status_codes
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def should_retry(self, resp):
        return resp.status_code in self.status_codes

    def __call__(self, func: Callable):
        def with_retries(*args, **kwargs):
            retries = 0
            backoff = self.backoff_factor

            while True:
                resp = func(*args, **kwargs)
                if not self.should_retry(resp) or retries >= self.max_retries:
                    break

                retries += 1
                log.debug('Received status code %d -- Retrying in %f seconds...',
                          resp.status_code, backoff)
                time.sleep(backoff)
                backoff *= 2

            return resp
        return with_retries


class retry_on_exception(object):
    def __init__(self, exc_classes, max_retries: int = 3, backoff_factor: float = 0.5):
        if type(exc_classes) is type:
            exc_classes = [exc_classes]

        self.exc_classes = tuple(exc_classes)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def __call__(self, func: Callable):
        def with_retries(*args, **kwargs):
            retries = 0
            backoff = self.backoff_factor

            while True:
                try:
                    resp = func(*args, **kwargs)
                except self.exc_classes as e:
                    if retries >= self.max_retries:
                        raise
                    retries += 1
                    log.debug('Caught %s -- Retrying in %f seconds...',
                              e.__class__.__name__, backoff)
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    break
            return resp
        return with_retries
