"""Email delivery abstraction (reconciliation R7).

The console provider logs messages for development only. Activating a real
SMTP/API provider is a material decision reserved to the user (Directive §6)
and must happen before production launch; no credentials are configured here.
"""

import logging
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class ConsoleEmailProvider:
    """Development-only: writes the message to the application log."""

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "[console-email] to=%s subject=%s\n%s", message.to, message.subject, message.body
        )


def get_email_provider() -> ConsoleEmailProvider:
    settings = get_settings()
    if settings.email_provider != "console":
        raise RuntimeError(
            f"Email provider '{settings.email_provider}' is not implemented; "
            "real providers require explicit activation approval."
        )
    return ConsoleEmailProvider()


def send_email(message: EmailMessage) -> None:
    get_email_provider().send(message)
