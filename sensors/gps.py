"""GPS module interface (NEO-6M or any NMEA-0183 serial source).

Reads ``$GPRMC`` / ``$GNRMC`` sentences from a serial port, parses latitude,
longitude, and speed, and constructs a Google Maps URL for the location.

Falls back to simulation mode automatically when *pyserial* is not installed
or the serial port cannot be opened.
"""
from __future__ import annotations

import logging
import re
import time
import random

logger = logging.getLogger(__name__)

try:
    import serial  # noqa: F401 – presence check only
    _SERIAL_AVAILABLE = True
except ImportError:
    _SERIAL_AVAILABLE = False

# ── Simulation defaults (Hyderabad, India) ────────────────────────────────────
_SIM_LAT = 17.3850
_SIM_LON = 78.4867


# ── NMEA helpers ──────────────────────────────────────────────────────────────

def _nmea_to_decimal(nmea: str, direction: str) -> float:
    """Convert an NMEA coordinate string to decimal degrees.

    NMEA format: ``DDDMM.MMMM`` (degrees + minutes).
    Direction ``'S'`` or ``'W'`` negates the result.

    Raises
    ------
    ValueError
        If *nmea* is too short to be valid.
    """
    if len(nmea) < 4:
        raise ValueError(f"Invalid NMEA coordinate: {nmea!r}")
    # Latitude uses 2 degree digits; longitude uses 3.
    deg_digits = 2 if direction in ("N", "S") else 3
    degrees = float(nmea[:deg_digits])
    minutes = float(nmea[deg_digits:])
    decimal = degrees + minutes / 60.0
    if direction in ("S", "W"):
        decimal = -decimal
    return decimal


def _parse_nmea_gprmc(sentence: str) -> dict | None:
    """Parse a ``$GPRMC`` or ``$GNRMC`` sentence.

    Returns a dict with ``latitude``, ``longitude``, and ``speed_kmh`` keys,
    or ``None`` if the sentence is invalid or the fix is void.
    """
    sentence = sentence.strip().lstrip("$")
    # Split on comma or the checksum delimiter '*'
    parts = re.split(r",|\*", sentence)
    try:
        if parts[0] not in ("GPRMC", "GNRMC"):
            return None
        if parts[2] != "A":  # 'A' = active fix, 'V' = void / no fix
            return None

        lat = _nmea_to_decimal(parts[3], parts[4])
        lon = _nmea_to_decimal(parts[5], parts[6])
        speed_kmh = float(parts[7]) * 1.852 if parts[7] else 0.0

        return {"latitude": lat, "longitude": lon, "speed_kmh": speed_kmh}
    except (IndexError, ValueError):
        return None


def _maps_link(lat: float, lon: float) -> str:
    """Return a Google Maps URL for the given decimal-degree coordinates."""
    return f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"


# ── GPS module class ──────────────────────────────────────────────────────────

class GPSModule:
    """High-level GPS interface.

    Parameters
    ----------
    port:
        Serial port path (e.g. ``/dev/ttyAMA0`` on Raspberry Pi).
    baudrate:
        Serial baudrate (default 9600 for most NEO-6M modules).
    simulation_mode:
        * ``True``  – always return simulated location.
        * ``False`` – always use real hardware; raises on failure.
        * ``None``  – auto-detect.
    timeout:
        Per-read serial timeout in seconds.
    fix_timeout:
        Maximum seconds to wait for a valid GPS fix before giving up.
    """

    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        baudrate: int = 9600,
        simulation_mode: bool | None = None,
        timeout: float = 1.0,
        fix_timeout: float = 5.0,
    ) -> None:
        self._fix_timeout = fix_timeout

        if simulation_mode is True:
            self.simulation_mode = True
        elif simulation_mode is False:
            self.simulation_mode = False
            self._open_serial(port, baudrate, timeout)
        else:
            if not _SERIAL_AVAILABLE:
                logger.info(
                    "pyserial not available; GPS running in simulation mode."
                )
                self.simulation_mode = True
            else:
                try:
                    self._open_serial(port, baudrate, timeout)
                    self.simulation_mode = False
                except Exception as exc:
                    logger.warning(
                        "Failed to open GPS serial port (%s); "
                        "falling back to simulation mode.",
                        exc,
                    )
                    self.simulation_mode = True

    # ── Private helpers ───────────────────────────────────────────────────────

    def _open_serial(self, port: str, baudrate: int, timeout: float) -> None:
        import serial

        self._serial = serial.Serial(port, baudrate, timeout=timeout)
        logger.info("GPS module opened on %s @ %d baud.", port, baudrate)

    def _simulated_location(self) -> dict:
        """Return a plausible simulated location with small random offsets."""
        lat = _SIM_LAT + random.uniform(-0.001, 0.001)
        lon = _SIM_LON + random.uniform(-0.001, 0.001)
        speed = random.uniform(0.0, 5.0)
        return {
            "latitude": lat,
            "longitude": lon,
            "speed_kmh": speed,
            "maps_url": _maps_link(lat, lon),
        }

    # ── Public API ────────────────────────────────────────────────────────────

    def get_location(self) -> dict | None:
        """Return location data or ``None`` when no fix is available.

        Returns a dict with keys:
        * ``latitude``  – decimal degrees (positive = north)
        * ``longitude`` – decimal degrees (positive = east)
        * ``speed_kmh`` – ground speed in km/h
        * ``maps_url``  – Google Maps URL for the position
        """
        if self.simulation_mode:
            return self._simulated_location()

        deadline = time.monotonic() + self._fix_timeout
        while time.monotonic() < deadline:
            try:
                line = self._serial.readline().decode("ascii", errors="replace")
            except Exception as exc:
                logger.warning("GPS serial read error: %s", exc)
                break

            data = _parse_nmea_gprmc(line)
            if data is not None:
                data["maps_url"] = _maps_link(data["latitude"], data["longitude"])
                return data

        logger.warning(
            "No GPS fix obtained within %.1f s.", self._fix_timeout
        )
        return None
