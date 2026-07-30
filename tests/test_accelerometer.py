"""Tests for sensors/accelerometer.py"""
from __future__ import annotations

import math

import pytest

from sensors.accelerometer import Accelerometer


@pytest.fixture
def sensor() -> Accelerometer:
    """Return an Accelerometer in forced simulation mode."""
    return Accelerometer(simulation_mode=True)


class TestGetAcceleration:
    def test_returns_three_floats(self, sensor: Accelerometer) -> None:
        ax, ay, az = sensor.get_acceleration()
        assert isinstance(ax, float)
        assert isinstance(ay, float)
        assert isinstance(az, float)

    def test_z_axis_near_one_g(self, sensor: Accelerometer) -> None:
        """Gravity should keep the z-axis close to 1 g in simulation."""
        for _ in range(20):
            _, _, az = sensor.get_acceleration()
            assert abs(az - 1.0) < 0.2

    def test_xy_axes_near_zero(self, sensor: Accelerometer) -> None:
        values_x, values_y = [], []
        for _ in range(20):
            ax, ay, _ = sensor.get_acceleration()
            values_x.append(ax)
            values_y.append(ay)
        # Mean should be close to 0; allow generous tolerance for random noise.
        assert abs(sum(values_x) / len(values_x)) < 0.1
        assert abs(sum(values_y) / len(values_y)) < 0.1


class TestGetGyroscope:
    def test_returns_three_floats(self, sensor: Accelerometer) -> None:
        gx, gy, gz = sensor.get_gyroscope()
        assert isinstance(gx, float)
        assert isinstance(gy, float)
        assert isinstance(gz, float)


class TestMagnitude:
    def test_zero_vector(self) -> None:
        assert Accelerometer.magnitude(0.0, 0.0, 0.0) == 0.0

    def test_unit_x_vector(self) -> None:
        assert math.isclose(Accelerometer.magnitude(1.0, 0.0, 0.0), 1.0)

    def test_pythagorean_triple(self) -> None:
        # sqrt(1² + 2² + 2²) = sqrt(9) = 3
        assert math.isclose(Accelerometer.magnitude(1.0, 2.0, 2.0), 3.0)

    def test_normal_driving_magnitude(self, sensor: Accelerometer) -> None:
        ax, ay, az = sensor.get_acceleration()
        mag = Accelerometer.magnitude(ax, ay, az)
        assert 0.8 < mag < 1.2

    def test_high_impact_magnitude(self) -> None:
        mag = Accelerometer.magnitude(3.0, 0.0, 0.0)
        assert mag == pytest.approx(3.0)
