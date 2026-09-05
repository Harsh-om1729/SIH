import logging
import logging.handlers

_syslog_logger = logging.getLogger("ibvap.syslog")
_syslog_logger.setLevel(logging.INFO)
_syslog_logger.propagate = False


def _build_handler(host: str, port: int):
    try:
        handler = logging.handlers.SysLogHandler(address=(host, port))
        handler.setFormatter(logging.Formatter("ibvap: %(message)s"))
        return handler
    except Exception as e:
        logging.getLogger("ibvap.integration").warning(
            "Syslog handler unavailable (%s) — syslog events will be dropped", e
        )
        return None


class SyslogNotifier:
    """Emits syslog-formatted events (via Python's SysLogHandler, UDP) so
    this platform can feed any SIEM that ingests syslog, per the roadmap.
    UDP is fire-and-forget — this never blocks or crashes even if nothing is
    listening on the target host/port, which matters since a real deployment
    may not always have its SIEM reachable.
    """

    def __init__(self, host: str = "localhost", port: int = 514):
        handler = _build_handler(host, port)
        self._handler = handler
        if handler is not None:
            _syslog_logger.addHandler(handler)

    def emit(self, message: str) -> None:
        if self._handler is not None:
            _syslog_logger.info(message)
