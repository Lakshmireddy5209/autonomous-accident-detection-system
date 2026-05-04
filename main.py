"""Autonomous Accident Detection System – main entry point.

Runs a continuous monitoring loop that:

1. Samples the MPU-6050 accelerometer every ``SAMPLE_INTERVAL`` seconds.
2. Passes each reading through the accident detection algorithm.
3. On confirmation, fetches the current GPS location.
4. Dispatches emergency e-mail and SMS alerts to all configured contacts.

Press **Ctrl-C** (or send SIGTERM) to stop gracefully.
"""
from __future__ import annotations

import logging
import signal
import sys
import time

import config
from alerts.alert_manager import AlertManager
from detection.accident_detector import AccidentDetector
from sensors.accelerometer import Accelerometer
from sensors.gps import GPSModule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_RUNNING = True


def _on_shutdown(signum: int, frame: object) -> None:
    global _RUNNING
    logger.info("Shutdown signal received – stopping monitoring loop.")
    _RUNNING = False


def run() -> None:
    """Initialise hardware (or simulation) and start the monitoring loop."""
    logger.info(
        "Autonomous Accident Detection System starting – mode: %s",
        "SIMULATION" if config.SIMULATION_MODE else "HARDWARE",
    )
    logger.info(
        "Config – threshold: %.2f g | confirmation: %d samples "
        "| interval: %.2f s",
        config.ACCELEROMETER_THRESHOLD,
        config.ACCIDENT_CONFIRMATION_COUNT,
        config.SAMPLE_INTERVAL,
    )

    # ── Initialise components ─────────────────────────────────────────────────
    sim = config.SIMULATION_MODE if config.SIMULATION_MODE else None

    accelerometer = Accelerometer(simulation_mode=sim)
    gps = GPSModule(
        port=config.GPS_PORT,
        baudrate=config.GPS_BAUDRATE,
        simulation_mode=sim,
    )
    detector = AccidentDetector(accelerometer)
    alert_manager = AlertManager()

    # ── Graceful shutdown on Ctrl-C / SIGTERM ─────────────────────────────────
    signal.signal(signal.SIGINT, _on_shutdown)
    signal.signal(signal.SIGTERM, _on_shutdown)

    logger.info("Monitoring started. Press Ctrl-C to stop.")

    while _RUNNING:
        try:
            if detector.check():
                logger.warning(
                    "Accident event confirmed! G-force: %.3f g – "
                    "fetching GPS location…",
                    detector.last_magnitude,
                )
                location = gps.get_location()
                if location:
                    logger.debug(
                        "Location: %.6f, %.6f | %s",
                        location["latitude"],
                        location["longitude"],
                        location["maps_url"],
                    )
                else:
                    logger.warning("GPS location unavailable.")

                result = alert_manager.send_alert(location)
                logger.info("Alert dispatch result: email=%s sms=%s", *result.values())
        except Exception as exc:
            logger.error("Unexpected error in monitoring loop: %s", exc, exc_info=True)

        time.sleep(config.SAMPLE_INTERVAL)

    logger.info("Monitoring stopped.")


if __name__ == "__main__":
    run()
