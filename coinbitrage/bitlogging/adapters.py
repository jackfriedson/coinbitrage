import logging


class BitLoggerAdapter(logging.LoggerAdapter):

    def __init__(self, logger):
        super(BitLoggerAdapter, self).__init__(logger, {'event_name': '', 'event_data': {}})

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            self.extra = {'event_name': '', 'event_data': {}}
            if 'event_name' in kwargs:
                self.extra['event_name'] = kwargs.pop('event_name')
            if 'event_data' in kwargs:
                self.extra['event_data'] = kwargs.pop('event_data')

            msg, kwargs = self.process(msg, kwargs)
            self.logger._log(level, msg, args, **kwargs)

    def process(self, msg, kwargs):
        msg, kwargs = super(BitLoggerAdapter, self).process(msg, kwargs)
        try:
            # TODO: Move this to a custom formatter
            formatted_msg = str(msg).format(**self.extra.get('event_data', {}))
        except (IndexError, KeyError):
            formatted_msg = msg
        return formatted_msg, kwargs
