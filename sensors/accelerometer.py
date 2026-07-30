"""MPU-6050 accelerometer/gyroscope sensor interface.

Provides a unified API that works with the physical MPU-6050 chip via I2C
(using *smbus2*) **and** in simulation mode when the library or hardware is
not present.  Simulation mode is selected automatically when *smbus2* cannot
be imported; it can also be forced via the ``simulation_mode`` constructor
parameter.

Typical hardware setup (Raspberry Pi):
    VCC → 3.3 V pin
    GND → GND pin
    SDA → GPIO 2 (pin 3)
    SCL → GPIO 3 (pin 5)
    AD0 → GND  → I2C address 0x68
"""
from __future__ import annotations

import logging
import math
import random

logger = logging.getLogger(__name__)

# Try to import the I2C library; gracefully fall back to simulation mode.
try:
    import smbus2  # noqa: F401 – presence check only at import time
    _SMBUS_AVAILABLE = True
except ImportError:
    _SMBUS_AVAILABLE = False

# ── MPU-6050 register addresses ───────────────────────────────────────────────
_PWR_MGMT_1 = 0x6B
_ACCEL_XOUT_H = 0x3B
_GYRO_XOUT_H = 0x43

# Sensitivity scale factors for default full-scale ranges
_ACCEL_SCALE = 16384.0  # LSB / g   for ±2 g
_GYRO_SCALE = 131.0     # LSB / °/s for ±250 °/s

_DEFAULT_ADDRESS = 0x68
_DEFAULT_BUS = 1


class Accelerometer:
    """High-level interface for the MPU-6050 6-axis IMU sensor.

    Parameters
    ----------
    bus_number:
        I2C bus number (default 1 on Raspberry Pi models B+/2/3/4).
    address:
        I2C address of the sensor (``0x68`` when AD0 is pulled low, ``0x69``
        when AD0 is pulled high).
    simulation_mode:
        * ``True``  – always return simulated values (no hardware needed).
        * ``False`` – always attempt to use real hardware; raises on failure.
        * ``None``  – auto-detect: use hardware when *smbus2* is available and
          the device can be opened, otherwise fall back to simulation.
    """

    def __init__(
        self,
        bus_number: int = _DEFAULT_BUS,
        address: int = _DEFAULT_ADDRESS,
        simulation_mode: bool | None = None,
    ) -> None:
        self.address = address

        if simulation_mode is True:
            self.simulation_mode = True
        elif simulation_mode is False:
            self.simulation_mode = False
            self._init_hardware(bus_number)
        else:
            # Auto-detect
            if not _SMBUS_AVAILABLE:
                logger.info(
                    "smbus2 not available; Accelerometer running in simulation mode."
                )
                self.simulation_mode = True
            else:
                try:
                    self._init_hardware(bus_number)
                    self.simulation_mode = False
                except Exception as exc:
                    logger.warning(
                        "MPU-6050 hardware init failed (%s); "
                        "falling back to simulation mode.",
                        exc,
                    )
                    self.simulation_mode = True

    # ── Hardware initialisation ───────────────────────────────────────────────

    def _init_hardware(self, bus_number: int) -> None:
        import smbus2

        self._bus = smbus2.SMBus(bus_number)
        # Clear the sleep bit in PWR_MGMT_1 to wake the sensor.
        self._bus.write_byte_data(self.address, _PWR_MGMT_1, 0x00)
        logger.info(
            "MPU-6050 initialised on I2C bus %d, address 0x%02X.",
            bus_number,
            self.address,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _read_word_signed(self, register: int) -> int:
        """Read two consecutive registers and return a signed 16-bit integer."""
        high = self._bus.read_byte_data(self.address, register)
        low = self._bus.read_byte_data(self.address, register + 1)
        value = (high << 8) | low
        return value - 65536 if value > 32767 else value

    # ── Public API ────────────────────────────────────────────────────────────

    def get_acceleration(self) -> tuple[float, float, float]:
        """Return ``(ax, ay, az)`` acceleration in *g* units.

        In simulation mode the z-axis reads ≈ 1 g (gravity) with small
        Gaussian noise on all three axes, representing steady driving.
        """
        if self.simulation_mode:
            noise = lambda: random.gauss(0.0, 0.02)
            return noise(), noise(), 1.0 + noise()

        ax = self._read_word_signed(_ACCEL_XOUT_H) / _ACCEL_SCALE
        ay = self._read_word_signed(_ACCEL_XOUT_H + 2) / _ACCEL_SCALE
        az = self._read_word_signed(_ACCEL_XOUT_H + 4) / _ACCEL_SCALE
        return ax, ay, az

    def get_gyroscope(self) -> tuple[float, float, float]:
        """Return ``(gx, gy, gz)`` angular velocity in degrees per second.

        In simulation mode all axes return near-zero values with small noise.
        """
        if self.simulation_mode:
            noise = lambda: random.gauss(0.0, 0.5)
            return noise(), noise(), noise()

        gx = self._read_word_signed(_GYRO_XOUT_H) / _GYRO_SCALE
        gy = self._read_word_signed(_GYRO_XOUT_H + 2) / _GYRO_SCALE
        gz = self._read_word_signed(_GYRO_XOUT_H + 4) / _GYRO_SCALE
        return gx, gy, gz

    @staticmethod
    def magnitude(ax: float, ay: float, az: float) -> float:
        """Return the Euclidean magnitude of the acceleration vector in g."""
        return math.sqrt(ax * ax + ay * ay + az * az)
