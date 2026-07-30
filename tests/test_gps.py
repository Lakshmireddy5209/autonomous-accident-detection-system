"""Tests for sensors/gps.py"""
from __future__ import annotations

import pytest

from sensors.gps import (
    GPSModule,
    _maps_link,
    _nmea_to_decimal,
    _parse_nmea_gprmc,
)


class TestNmeaToDecimal:
    def test_latitude_north(self) -> None:
        # 48°07.038' N  →  48 + 7.038/60 ≈ 48.1173
        result = _nmea_to_decimal("4807.038", "N")
        assert abs(result - 48.1173) < 0.001

    def test_latitude_south_is_negative(self) -> None:
        result = _nmea_to_decimal("4807.038", "S")
        assert result < 0
        assert abs(result - (-48.1173)) < 0.001

    def test_longitude_east(self) -> None:
        # 011°31.000' E  →  11 + 31/60 ≈ 11.5167
        result = _nmea_to_decimal("01131.000", "E")
        assert abs(result - 11.5167) < 0.001

    def test_longitude_west_is_negative(self) -> None:
        result = _nmea_to_decimal("01131.000", "W")
        assert result < 0

    def test_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _nmea_to_decimal("12", "N")


class TestParseNmeaGprmc:
    # Valid sentence from the NMEA spec examples.
    VALID = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"

    def test_valid_sentence_returns_dict(self) -> None:
        data = _parse_nmea_gprmc(self.VALID)
        assert data is not None
        assert abs(data["latitude"] - 48.1173) < 0.001
        assert abs(data["longitude"] - 11.5167) < 0.001
        assert data["speed_kmh"] > 0.0

    def test_void_fix_returns_none(self) -> None:
        void = self.VALID.replace(",A,", ",V,")
        assert _parse_nmea_gprmc(void) is None

    def test_non_gprmc_sentence_returns_none(self) -> None:
        gpgga = (
            "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
        )
        assert _parse_nmea_gprmc(gpgga) is None

    def test_gnrmc_variant_accepted(self) -> None:
        gnrmc = self.VALID.replace("GPRMC", "GNRMC")
        assert _parse_nmea_gprmc(gnrmc) is not None

    def test_garbage_input_returns_none(self) -> None:
        assert _parse_nmea_gprmc("not a sentence") is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_nmea_gprmc("") is None

    def test_speed_converted_from_knots(self) -> None:
        data = _parse_nmea_gprmc(self.VALID)
        assert data is not None
        # 22.4 knots * 1.852 ≈ 41.485 km/h
        assert abs(data["speed_kmh"] - 22.4 * 1.852) < 0.01


class TestMapsLink:
    def test_url_format(self) -> None:
        url = _maps_link(17.385, 78.4867)
        assert url.startswith("https://maps.google.com/?q=")
        assert "17.385000" in url
        assert "78.486700" in url

    def test_negative_coordinates(self) -> None:
        url = _maps_link(-33.865, 151.209)
        assert "-33.865000" in url
        assert "151.209000" in url


class TestGPSModuleSimulation:
    @pytest.fixture
    def gps(self) -> GPSModule:
        return GPSModule(simulation_mode=True)

    def test_get_location_returns_dict(self, gps: GPSModule) -> None:
        loc = gps.get_location()
        assert loc is not None

    def test_location_has_required_keys(self, gps: GPSModule) -> None:
        loc = gps.get_location()
        assert loc is not None
        for key in ("latitude", "longitude", "speed_kmh", "maps_url"):
            assert key in loc

    def test_maps_url_is_google_maps(self, gps: GPSModule) -> None:
        loc = gps.get_location()
        assert loc is not None
        assert loc["maps_url"].startswith("https://maps.google.com/?q=")

    def test_simulated_location_near_hyderabad(self, gps: GPSModule) -> None:
        loc = gps.get_location()
        assert loc is not None
        assert abs(loc["latitude"] - 17.385) < 0.01
        assert abs(loc["longitude"] - 78.4867) < 0.01

    def test_speed_is_non_negative(self, gps: GPSModule) -> None:
        for _ in range(5):
            loc = gps.get_location()
            assert loc is not None
            assert loc["speed_kmh"] >= 0.0
