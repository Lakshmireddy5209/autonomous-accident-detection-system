"""Tests for detection/accident_detector.py"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from detection.accident_detector import AccidentDetector
from sensors.accelerometer import Accelerometer


def _make_sensor(ax: float = 0.0, ay: float = 0.0, az: float = 1.0) -> Accelerometer:
    """Return a mock Accelerometer that always yields the given reading."""
    sensor = MagicMock(spec=Accelerometer)
    sensor.get_acceleration.return_value = (ax, ay, az)
    return sensor


class TestNormalDriving:
    def test_no_accident_on_1g(self) -> None:
        """Normal 1-g (gravity) readings must never trigger an alert."""
        sensor = _make_sensor(0.0, 0.0, 1.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=3)
        for _ in range(20):
            assert detector.check() is False


class TestAccidentConfirmation:
    def test_accident_detected_after_confirmation_count(self) -> None:
        # magnitude(3, 0, 0) = 3.0 > threshold 2.5
        sensor = _make_sensor(3.0, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=3)
        results = [detector.check() for _ in range(3)]
        assert results[-1] is True

    def test_no_accident_before_confirmation_count(self) -> None:
        sensor = _make_sensor(3.0, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=3)
        # First two checks must not trigger the alarm.
        assert detector.check() is False
        assert detector.check() is False

    def test_exactly_at_threshold_counts_as_above(self) -> None:
        # magnitude(2.5, 0, 0) == threshold → should count.
        sensor = _make_sensor(2.5, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=1)
        assert detector.check() is True

    def test_just_below_threshold_never_triggers(self) -> None:
        sensor = _make_sensor(2.49, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=1)
        for _ in range(10):
            assert detector.check() is False

    def test_confirmation_count_one_triggers_immediately(self) -> None:
        sensor = _make_sensor(3.0, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=1)
        assert detector.check() is True


class TestStreakReset:
    def test_below_threshold_reading_resets_streak(self) -> None:
        sensor = _make_sensor()
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=3)

        sensor.get_acceleration.return_value = (3.0, 0.0, 0.0)
        detector.check()  # streak = 1
        detector.check()  # streak = 2

        # Drop below threshold → streak reset.
        sensor.get_acceleration.return_value = (0.0, 0.0, 1.0)
        assert detector.check() is False  # streak = 0

        # Need another full confirmation_count after the reset.
        sensor.get_acceleration.return_value = (3.0, 0.0, 0.0)
        assert detector.check() is False  # streak = 1
        assert detector.check() is False  # streak = 2

    def test_streak_auto_resets_after_confirmation(self) -> None:
        """After an accident is confirmed, the next event needs a fresh streak."""
        sensor = _make_sensor(3.0, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=2)
        # First event.
        detector.check()
        assert detector.check() is True   # confirmed; streak resets
        # Second event needs a full new streak.
        assert detector.check() is False  # streak = 1
        assert detector.check() is True   # streak = 2 → second event confirmed


class TestLastMagnitude:
    def test_last_magnitude_updated_on_check(self) -> None:
        sensor = _make_sensor(3.0, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=3)
        detector.check()
        assert abs(detector.last_magnitude - 3.0) < 0.001

    def test_last_magnitude_zero_before_any_check(self) -> None:
        sensor = _make_sensor()
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=3)
        assert detector.last_magnitude == 0.0


class TestReset:
    def test_reset_clears_streak_and_magnitude(self) -> None:
        sensor = _make_sensor(3.0, 0.0, 0.0)
        detector = AccidentDetector(sensor, threshold=2.5, confirmation_count=3)
        detector.check()
        detector.check()  # streak = 2
        detector.reset()
        assert detector.last_magnitude == 0.0
        # After reset, confirmation_count fresh readings are needed again.
        assert detector.check() is False  # streak = 1
