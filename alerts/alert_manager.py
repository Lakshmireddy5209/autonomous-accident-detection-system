"""Emergency alert system.

Dispatches real-time emergency notifications via two independent channels:

* **E-mail** – uses the standard library ``smtplib`` (no extra dependency).
* **SMS**    – uses the *Twilio* REST API (optional; omit if not needed).

When a channel has no contacts configured it is silently skipped and reported
as successful so that a partial configuration does not fail the whole alert.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config

logger = logging.getLogger(__name__)

try:
    from twilio.rest import Client as _TwilioClient
    _TWILIO_AVAILABLE = True
except ImportError:
    _TwilioClient = None  # type: ignore[assignment,misc]
    _TWILIO_AVAILABLE = False


# ── Message builder ───────────────────────────────────────────────────────────

def _build_message(location: dict | None) -> str:
    """Compose the plain-text alert body from optional location data."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "*** ACCIDENT DETECTED ***",
        f"Time     : {timestamp}",
    ]
    if location:
        lines += [
            f"Latitude : {location['latitude']:.6f}",
            f"Longitude: {location['longitude']:.6f}",
            f"Speed    : {location.get('speed_kmh', 0.0):.1f} km/h",
            f"Map      : {location.get('maps_url', 'N/A')}",
        ]
    else:
        lines.append("Location : unavailable")
    lines.append("\nPlease respond immediately.")
    return "\n".join(lines)


# ── AlertManager ──────────────────────────────────────────────────────────────

def _mask_phone(number: str) -> str:
    """Return a partially redacted phone number for safe logging."""
    if len(number) <= 4:
        return "****"
    return number[:3] + "****" + number[-2:]


class AlertManager:
    """Sends emergency alerts to all configured contacts.

    Parameters
    ----------
    smtp_host / smtp_port:
        SMTP server address and port (default: Gmail TLS).
    sender_email / sender_password:
        Credentials used to authenticate with the SMTP server.
    email_contacts:
        List of recipient e-mail addresses.  Falls back to
        :data:`config.EMERGENCY_EMAIL_CONTACTS` when ``None``.
    twilio_sid / twilio_token / twilio_from:
        Twilio API credentials and originating phone number.
    phone_contacts:
        List of E.164 phone numbers to receive SMS alerts.  Falls back to
        :data:`config.EMERGENCY_PHONE_NUMBERS` when ``None``.
    """

    def __init__(
        self,
        smtp_host: str = config.SMTP_HOST,
        smtp_port: int = config.SMTP_PORT,
        sender_email: str = config.SENDER_EMAIL,
        sender_password: str = config.SENDER_PASSWORD,
        email_contacts: list[str] | None = None,
        twilio_sid: str = config.TWILIO_ACCOUNT_SID,
        twilio_token: str = config.TWILIO_AUTH_TOKEN,
        twilio_from: str = config.TWILIO_PHONE_NUMBER,
        phone_contacts: list[str] | None = None,
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.email_contacts = (
            email_contacts if email_contacts is not None
            else config.EMERGENCY_EMAIL_CONTACTS
        )
        self.twilio_sid = twilio_sid
        self.twilio_token = twilio_token
        self.twilio_from = twilio_from
        self.phone_contacts = (
            phone_contacts if phone_contacts is not None
            else config.EMERGENCY_PHONE_NUMBERS
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def send_alert(self, location: dict | None = None) -> dict[str, bool]:
        """Dispatch an emergency alert via all configured channels.

        Parameters
        ----------
        location:
            Location dict produced by :meth:`~sensors.gps.GPSModule.get_location`,
            or ``None`` when GPS data is unavailable.

        Returns
        -------
        dict
            ``{"email": bool, "sms": bool}`` where ``True`` means the channel
            succeeded (or had no contacts to notify).
        """
        message = _build_message(location)
        email_ok = self._send_emails(message)
        sms_ok = self._send_sms(message)
        return {"email": email_ok, "sms": sms_ok}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _send_emails(self, message: str) -> bool:
        """Send alert e-mail to every configured contact.

        Returns ``True`` on success, or when no e-mail contacts are configured.
        """
        if not self.email_contacts:
            return True
        if not self.sender_email or not self.sender_password:
            logger.warning(
                "E-mail credentials not configured; skipping e-mail alerts."
            )
            return False

        subject = "Emergency Alert: Accident Detected"
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                for recipient in self.email_contacts:
                    msg = MIMEMultipart()
                    msg["From"] = self.sender_email
                    msg["To"] = recipient
                    msg["Subject"] = subject
                    msg.attach(MIMEText(message, "plain"))
                    server.sendmail(self.sender_email, recipient, msg.as_string())
                    logger.info("E-mail alert sent to %s.", recipient)
        except smtplib.SMTPException as exc:
            logger.error("Failed to send e-mail alert: %s", exc)
            return False
        return True

    def _send_sms(self, message: str) -> bool:
        """Send SMS alert to every configured phone number via Twilio.

        Returns ``True`` on success, or when no phone contacts are configured.
        """
        if not self.phone_contacts:
            return True
        if not _TWILIO_AVAILABLE:
            logger.warning(
                "Twilio library not installed; skipping SMS alerts."
            )
            return False
        if not self.twilio_sid or not self.twilio_token or not self.twilio_from:
            logger.warning(
                "Twilio credentials not configured; skipping SMS alerts."
            )
            return False

        client = _TwilioClient(self.twilio_sid, self.twilio_token)
        success = True
        for number in self.phone_contacts:
            try:
                client.messages.create(
                    body=message,
                    from_=self.twilio_from,
                    to=number,
                )
                logger.info("SMS alert sent to %s.", _mask_phone(number))
            except Exception as exc:
                logger.error("Failed to send SMS to %s: %s", _mask_phone(number), exc)
                success = False
        return success
