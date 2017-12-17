import datetime
import json
import logging
import pytz
from json import JSONEncoder

from tzlocal import get_localzone


class BaseFormatter(logging.Formatter):
    converter = datetime.datetime.fromtimestamp

    def __init__(self, fmt: str = None, datefmt: str = None, style: str = '%', as_utc: bool = True):
        super(BaseFormatter, self).__init__(fmt=fmt, style=style)
        self.datefmt = datefmt
        self.as_utc = as_utc

    def formatTime(self, record: logging.LogRecord, datefmt: str = None) -> str:
        datefmt = datefmt or self.datefmt
        tz = pytz.utc if self.as_utc else get_localzone()
        ct = self.converter(record.created).astimezone(tz)

        if datefmt:
            s = ct.strftime(datefmt)
        else:
            t = ct.strftime(self.default_time_format)
            s = self.default_msec_format % (t, record.msecs)
        return s


class JSONFormatter(BaseFormatter):

    class BitLogJSONEncoder(JSONEncoder):
        def default(self, o):
            if isinstance(o, set):
                return list(o)
            if isinstance(o, object):
                return repr(o)
            return JSONEncoder.default(self, o)

    def format(self, record: logging.LogRecord) -> str:
        record.asctime = self.formatTime(record)
        return json.dumps(record.__dict__, cls=self.BitLogJSONEncoder)
