"""Central configuration for the Autonomous Accident Detection System.

All settings are read from environment variables so the same code can run
on real hardware (Raspberry Pi) or in simulation/CI mode without changes.
Copy ``.env.example`` to ``.env`` and fill in your values.
"""
from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; values fall back to env / defaults

# ── Sensor settings ──────────────────────────────────────────────────────────
# Minimum G-force magnitude (in g) that indicates a potential impact.
ACCELEROMETER_THRESHOLD: float = float(os.getenv("ACCELEROMETER_THRESHOLD", "2.5"))

# Number of consecutive above-threshold readings required before an accident
# is confirmed (avoids false positives from road bumps).
ACCIDENT_CONFIRMATION_COUNT: int = int(os.getenv("ACCIDENT_CONFIRMATION_COUNT", "3"))

# Delay between sensor samples (seconds).
SAMPLE_INTERVAL: float = float(os.getenv("SAMPLE_INTERVAL", "0.1"))

# ── GPS settings ──────────────────────────────────────────────────────────────
GPS_PORT: str = os.getenv("GPS_PORT", "/dev/ttyAMA0")
GPS_BAUDRATE: int = int(os.getenv("GPS_BAUDRATE", "9600"))

# ── Email alert settings ──────────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD: str = os.getenv("SENDER_PASSWORD", "")

EMERGENCY_EMAIL_CONTACTS: list[str] = [
    e.strip()
    for e in os.getenv("EMERGENCY_EMAIL_CONTACTS", "").split(",")
    if e.strip()
]

# ── SMS alert settings (Twilio) ───────────────────────────────────────────────
TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")

EMERGENCY_PHONE_NUMBERS: list[str] = [
    p.strip()
    for p in os.getenv("EMERGENCY_PHONE_NUMBERS", "").split(",")
    if p.strip()
]

# ── Operation mode ────────────────────────────────────────────────────────────
# Set SIMULATION_MODE=false in .env (or the real environment) to use physical
# hardware (MPU-6050 via I2C, GPS via serial).
SIMULATION_MODE: bool = os.getenv("SIMULATION_MODE", "true").lower() == "true"
