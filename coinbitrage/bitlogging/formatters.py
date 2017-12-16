import datetime
import json
import logging
import pytz

from tzlocal import get_localzone


class BitLogFormatter(logging.Formatter):
    converter = datetime.datetime.fromtimestamp

    def __init__(self, fmt: str = None, datefmt: str = None, style: str = '%', as_utc: bool = True):
        super(BitLogFormatter, self).__init__(fmt=fmt, style=style)
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


class OrderFormatter(BitLogFormatter):
    # TODO: Fix this formatter

    def __init__(self, *args, **kwargs):
        super(OrderFormatter, self).__init__(datefmt='%Y-%m-%d %H:%M:%S')

    def format(self, record: logging.LogRecord) -> str:
        fmt = '{asctime} {event_name:20} -- {exchange} {side} ' + \
              '{volume} {base} @ {price} {quote}{order_id}'
        order_id = record.event_data.pop('order_id', None)
        msg_args = {
            'asctime': self.formatTime(record),
            'event_name': record.event_name,
            'order_id_str': ' ({})'.format(order_id) if order_id else '',
        }
        msg_args.update(record.event_data)
        return self._fmt.format(**msg_args)


class JSONFormatter(BitLogFormatter):

    def format(self, record: logging.LogRecord) -> str:
        result = {k: str(v) for k, v in record.__dict__.items()}
        result.update({'asctime': self.formatTime(record)})
        return json.dumps(result)


