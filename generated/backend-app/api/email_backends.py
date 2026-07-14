from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Django email backend that delivers messages through the Resend HTTP API.

    Any code path that uses Django's ``send_mail`` / ``EmailMessage`` machinery
    (including ``EmailMultiAlternatives`` for HTML) is routed through Resend when
    ``RESEND_API_KEY`` is configured. Transport errors are logged and, unless
    ``fail_silently`` is False, swallowed so that a mail outage never blocks the
    surrounding request.
    """

    def __init__(self, fail_silently: bool = False, **kwargs) -> None:
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._client = None
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            if not self.fail_silently:
                raise ValueError("RESEND_API_KEY is not configured.")
            return
        try:
            import resend  # imported lazily so the dependency is optional

            resend.api_key = api_key
            self._client = resend
        except ImportError as exc:  # pragma: no cover - depends on environment
            if not self.fail_silently:
                raise
            logger.error("resend package is not installed: %s", exc)

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0
        if self._client is None:
            return 0

        sent = 0
        for message in email_messages:
            try:
                self._send_one(message)
                sent += 1
            except Exception:  # pragma: no cover - network/transport failures
                logger.exception("Resend failed to send an email message.")
                if not self.fail_silently:
                    raise
        return sent

    def _send_one(self, message) -> None:
        recipients = list(message.to or [])
        if not recipients:
            return

        payload = {
            "from": message.from_email,
            "to": recipients,
            "subject": message.subject or "",
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = list(message.reply_to)

        # Plain-text body plus any HTML alternative (from EmailMultiAlternatives).
        text_body = message.body if getattr(message, "content_subtype", "plain") == "plain" else ""
        html_body = message.body if getattr(message, "content_subtype", "plain") == "html" else ""
        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                html_body = content

        if text_body:
            payload["text"] = text_body
        if html_body:
            payload["html"] = html_body
        if "text" not in payload and "html" not in payload:
            payload["text"] = ""

        self._client.Emails.send(payload)
