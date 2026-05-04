"""Tests for alerts/alert_manager.py"""
from __future__ import annotations

import re
import smtplib
from unittest.mock import MagicMock, patch

import pytest

from alerts.alert_manager import AlertManager, _build_message


# ── _build_message ────────────────────────────────────────────────────────────

class TestBuildMessage:
    def test_contains_accident_marker(self) -> None:
        msg = _build_message(None)
        assert "ACCIDENT" in msg.upper()

    def test_contains_timestamp(self) -> None:
        msg = _build_message(None)
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", msg)

    def test_location_unavailable_when_none(self) -> None:
        msg = _build_message(None)
        assert "unavailable" in msg.lower()

    def test_includes_coordinates_when_location_provided(self) -> None:
        location = {
            "latitude": 17.3850,
            "longitude": 78.4867,
            "speed_kmh": 60.5,
            "maps_url": "https://maps.google.com/?q=17.385000,78.486700",
        }
        msg = _build_message(location)
        assert "17.385000" in msg
        assert "78.486700" in msg
        assert msg.find("https://maps.google.com/") >= 0

    def test_includes_speed(self) -> None:
        location = {
            "latitude": 17.385,
            "longitude": 78.487,
            "speed_kmh": 72.3,
            "maps_url": "https://maps.google.com/?q=17.385000,78.487000",
        }
        msg = _build_message(location)
        assert "72.3" in msg

    def test_ends_with_respond_immediately(self) -> None:
        msg = _build_message(None)
        assert "respond immediately" in msg.lower()


# ── AlertManager – e-mail ─────────────────────────────────────────────────────

def _email_manager(contacts: list[str] | None = None) -> AlertManager:
    return AlertManager(
        smtp_host="smtp.example.com",
        smtp_port=587,
        sender_email="sender@example.com",
        sender_password="secret",
        email_contacts=contacts if contacts is not None else ["contact@example.com"],
        phone_contacts=[],
    )


class TestAlertManagerEmail:
    def test_send_alert_returns_channel_dict(self) -> None:
        manager = _email_manager()
        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = manager.send_alert(None)
        assert "email" in result
        assert "sms" in result

    def test_email_sent_to_each_contact(self) -> None:
        contacts = ["a@example.com", "b@example.com", "c@example.com"]
        manager = _email_manager(contacts)
        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            manager.send_alert(None)
        assert instance.sendmail.call_count == len(contacts)

    def test_returns_true_when_no_email_contacts(self) -> None:
        manager = _email_manager([])
        result = manager.send_alert(None)
        assert result["email"] is True

    def test_returns_false_on_smtp_exception(self) -> None:
        manager = _email_manager()
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.side_effect = smtplib.SMTPException(
                "connection refused"
            )
            result = manager.send_alert(None)
        assert result["email"] is False

    def test_returns_false_when_credentials_missing(self) -> None:
        manager = AlertManager(
            sender_email="",
            sender_password="",
            email_contacts=["someone@example.com"],
            phone_contacts=[],
        )
        result = manager.send_alert(None)
        assert result["email"] is False

    def test_starttls_called(self) -> None:
        manager = _email_manager()
        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            manager.send_alert(None)
        instance.starttls.assert_called_once()

    def test_login_called_with_credentials(self) -> None:
        manager = _email_manager()
        with patch("smtplib.SMTP") as mock_smtp:
            instance = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=instance)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            manager.send_alert(None)
        instance.login.assert_called_once_with("sender@example.com", "secret")


# ── AlertManager – SMS ────────────────────────────────────────────────────────

class TestAlertManagerSMS:
    def test_returns_true_when_no_phone_contacts(self) -> None:
        manager = AlertManager(email_contacts=[], phone_contacts=[])
        result = manager.send_alert(None)
        assert result["sms"] is True

    def test_returns_false_when_twilio_not_installed(self) -> None:
        manager = AlertManager(
            email_contacts=[],
            phone_contacts=["+1234567890"],
        )
        with patch("alerts.alert_manager._TWILIO_AVAILABLE", False):
            result = manager.send_alert(None)
        assert result["sms"] is False

    def test_returns_false_when_twilio_credentials_missing(self) -> None:
        manager = AlertManager(
            email_contacts=[],
            phone_contacts=["+1234567890"],
            twilio_sid="",
            twilio_token="",
            twilio_from="",
        )
        with patch("alerts.alert_manager._TWILIO_AVAILABLE", True):
            result = manager.send_alert(None)
        assert result["sms"] is False

    def test_sms_sent_via_twilio_client(self) -> None:
        manager = AlertManager(
            email_contacts=[],
            phone_contacts=["+1234567890"],
            twilio_sid="ACtest",
            twilio_token="token",
            twilio_from="+0987654321",
        )
        mock_client = MagicMock()
        with (
            patch("alerts.alert_manager._TWILIO_AVAILABLE", True),
            patch("alerts.alert_manager._TwilioClient", return_value=mock_client),
        ):
            result = manager.send_alert(None)
        mock_client.messages.create.assert_called_once()
        assert result["sms"] is True

    def test_sms_sent_to_multiple_numbers(self) -> None:
        numbers = ["+111", "+222", "+333"]
        manager = AlertManager(
            email_contacts=[],
            phone_contacts=numbers,
            twilio_sid="ACtest",
            twilio_token="token",
            twilio_from="+000",
        )
        mock_client = MagicMock()
        with (
            patch("alerts.alert_manager._TWILIO_AVAILABLE", True),
            patch("alerts.alert_manager._TwilioClient", return_value=mock_client),
        ):
            manager.send_alert(None)
        assert mock_client.messages.create.call_count == len(numbers)

    def test_partial_sms_failure_returns_false(self) -> None:
        manager = AlertManager(
            email_contacts=[],
            phone_contacts=["+111", "+222"],
            twilio_sid="ACtest",
            twilio_token="token",
            twilio_from="+000",
        )
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [Exception("fail"), None]
        with (
            patch("alerts.alert_manager._TWILIO_AVAILABLE", True),
            patch("alerts.alert_manager._TwilioClient", return_value=mock_client),
        ):
            result = manager.send_alert(None)
        assert result["sms"] is False
