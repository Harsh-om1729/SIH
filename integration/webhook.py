import logging

import requests

log = logging.getLogger("ibvap.integration")


class WebhookNotifier:
    """Posts incident events as JSON to an external URL — the roadmap's
    "outbound webhook" mechanism for plugging into whatever C2/SIEM system a
    deploying force already runs, without this platform needing to know that
    system's internals. Failures (URL down, timeout, misconfigured) are
    logged and swallowed — a webhook outage must never crash detection.
    """

    def __init__(self, url: str, timeout: float = 3.0):
        self.url = url
        self.timeout = timeout

    def notify(self, payload: dict) -> None:
        if not self.url:
            return
        try:
            requests.post(self.url, json=payload, timeout=self.timeout)
        except Exception as e:
            log.warning("Webhook POST to %s failed: %s", self.url, e)
