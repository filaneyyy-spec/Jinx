"""Redact the bot credential even in third-party logs and formatted tracebacks."""

import logging
from urllib.parse import quote


class SecretFormatter(logging.Formatter):
    def __init__(self, token: str | None):
        super().__init__("%(levelname)s %(name)s: %(message)s")
        self._secrets = (
            {token, quote(token, safe=""), quote(token, safe="").replace("%3A", "%3a")}
            if token
            else set()
        )

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        for secret in self._secrets:
            rendered = rendered.replace(secret, "[REDACTED]")
        return rendered


def configure_logging(token: str | None) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(SecretFormatter(token))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
