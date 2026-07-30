"""Accident detection algorithm.

Monitors a rolling window of accelerometer readings and declares an *accident
event* when the instantaneous G-force magnitude exceeds the configured
threshold for a configurable number of **consecutive** samples.

The confirmation window prevents false positives caused by individual road
bumps or sensor noise: a single spike resets the streak counter and does not
trigger an alert.
"""
from __future__ import annotations

import logging

from config import ACCELEROMETER_THRESHOLD, ACCIDENT_CONFIRMATION_COUNT
from sensors.accelerometer import Accelerometer

logger = logging.getLogger(__name__)


class AccidentDetector:
    """Detects vehicle accidents from accelerometer data.

    Parameters
    ----------
    accelerometer:
        An :class:`~sensors.accelerometer.Accelerometer` instance to read from.
    threshold:
        Minimum G-force magnitude (in g) that counts as a potential impact.
        Defaults to :data:`config.ACCELEROMETER_THRESHOLD`.
    confirmation_count:
        Number of *consecutive* above-threshold readings required to confirm
        an accident.  Defaults to :data:`config.ACCIDENT_CONFIRMATION_COUNT`.
    """

    def __init__(
        self,
        accelerometer: Accelerometer,
        threshold: float = ACCELEROMETER_THRESHOLD,
        confirmation_count: int = ACCIDENT_CONFIRMATION_COUNT,
    ) -> None:
        self._sensor = accelerometer
        self.threshold = threshold
        self.confirmation_count = confirmation_count
        self._streak: int = 0
        self._last_magnitude: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self) -> bool:
        """Sample the sensor once and return ``True`` if an accident is confirmed.

        The accident flag is **auto-reset** after each confirmed event so that
        subsequent collisions can be detected independently.
        """
        ax, ay, az = self._sensor.get_acceleration()
        magnitude = Accelerometer.magnitude(ax, ay, az)
        self._last_magnitude = magnitude

        if magnitude >= self.threshold:
            self._streak += 1
            logger.debug(
                "High G-force %.3f g (streak %d / %d).",
                magnitude,
                self._streak,
                self.confirmation_count,
            )
        else:
            self._streak = 0

        if self._streak >= self.confirmation_count:
            self._streak = 0  # reset for next potential event
            logger.warning("Accident confirmed – G-force magnitude: %.3f g.", magnitude)
            return True

        return False

    @property
    def last_magnitude(self) -> float:
        """G-force magnitude from the most recent :meth:`check` call."""
        return self._last_magnitude

    def reset(self) -> None:
        """Reset internal detection state (useful between test scenarios)."""
        self._streak = 0
        self._last_magnitude = 0.0
