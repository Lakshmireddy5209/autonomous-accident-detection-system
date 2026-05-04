# Autonomous Accident Detection System

An IoT-based system that uses an **MPU-6050 accelerometer/gyroscope** and a
**GPS module** (NEO-6M or any NMEA-0183 source) to detect vehicle accidents in
real time and immediately dispatch emergency alerts — with exact location
details — to configured contacts via **e-mail** and/or **SMS (Twilio)**.

---

## Features

| Feature | Details |
|---|---|
| **Accident detection** | Monitors G-force magnitude; confirms an event only after *N* consecutive above-threshold readings (configurable) |
| **GPS location** | Parses NMEA sentences from a serial GPS module; generates a Google Maps link |
| **E-mail alerts** | Sends plain-text alert via any SMTP server (Gmail supported out of the box) |
| **SMS alerts** | Sends SMS via the [Twilio REST API](https://www.twilio.com/) (optional) |
| **Simulation mode** | Runs without hardware (default); useful for development and CI |
| **Configurable** | All thresholds, credentials, and contacts are set via environment variables |

---

## Hardware Requirements

| Component | Purpose |
|---|---|
| Raspberry Pi (any model with I2C & UART) | Host computer |
| MPU-6050 breakout board | 3-axis accelerometer + 3-axis gyroscope |
| NEO-6M GPS module (or compatible) | Real-time GNSS location |
| GSM module / internet connection | Alert delivery (e-mail / SMS) |

### MPU-6050 Wiring (Raspberry Pi)

```
MPU-6050   →   Raspberry Pi
VCC        →   3.3 V  (pin 1)
GND        →   GND    (pin 6)
SDA        →   GPIO 2 (pin 3)
SCL        →   GPIO 3 (pin 5)
AD0        →   GND    (I2C address 0x68)
```

### GPS Module Wiring

```
NEO-6M     →   Raspberry Pi
VCC        →   3.3 V / 5 V
GND        →   GND
TX         →   GPIO 15 / RXD (pin 10)
RX         →   GPIO 14 / TXD (pin 8)
```

Enable UART on the Pi: `sudo raspi-config` → Interface Options → Serial Port.

---

## Project Structure

```
autonomous-accident-detection-system/
├── main.py                   # Entry point – monitoring loop
├── config.py                 # All settings loaded from environment
├── sensors/
│   ├── accelerometer.py      # MPU-6050 interface (I2C + simulation fallback)
│   └── gps.py                # GPS NMEA parser (serial + simulation fallback)
├── detection/
│   └── accident_detector.py  # G-force spike detection algorithm
├── alerts/
│   └── alert_manager.py      # E-mail (SMTP) and SMS (Twilio) dispatcher
├── tests/                    # pytest unit tests
│   ├── test_accelerometer.py
│   ├── test_gps.py
│   ├── test_accident_detector.py
│   └── test_alert_manager.py
├── requirements.txt
├── .env.example              # Template – copy to .env and fill in values
└── pytest.ini
```

---

## Quick Start

### 1 – Clone and install dependencies

```bash
git clone https://github.com/Lakshmireddy5209/autonomous-accident-detection-system.git
cd autonomous-accident-detection-system
pip install -r requirements.txt
```

### 2 – Configure

```bash
cp .env.example .env
# Edit .env with your SMTP credentials, Twilio keys, and emergency contacts.
```

### 3 – Run (simulation mode – no hardware needed)

```bash
python main.py
```

### 4 – Run on real hardware

Set `SIMULATION_MODE=false` in `.env`, connect the MPU-6050 and GPS module,
then run:

```bash
python main.py
```

---

## Configuration Reference

All variables are read from the environment (or from a `.env` file via
`python-dotenv`).

| Variable | Default | Description |
|---|---|---|
| `SIMULATION_MODE` | `true` | Set `false` to use physical sensors |
| `ACCELEROMETER_THRESHOLD` | `2.5` | G-force magnitude that triggers detection |
| `ACCIDENT_CONFIRMATION_COUNT` | `3` | Consecutive readings needed to confirm accident |
| `SAMPLE_INTERVAL` | `0.1` | Seconds between sensor reads |
| `GPS_PORT` | `/dev/ttyAMA0` | Serial port for the GPS module |
| `GPS_BAUDRATE` | `9600` | GPS serial baudrate |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port (TLS) |
| `SENDER_EMAIL` | _(empty)_ | Sender address |
| `SENDER_PASSWORD` | _(empty)_ | SMTP password / App Password |
| `EMERGENCY_EMAIL_CONTACTS` | _(empty)_ | Comma-separated recipient e-mails |
| `TWILIO_ACCOUNT_SID` | _(empty)_ | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | _(empty)_ | Twilio auth token |
| `TWILIO_PHONE_NUMBER` | _(empty)_ | Twilio originating number (E.164) |
| `EMERGENCY_PHONE_NUMBERS` | _(empty)_ | Comma-separated recipient numbers |

---

## Running Tests

```bash
pytest
```

All tests run without hardware – they use the built-in simulation mode and
mock objects for SMTP and Twilio.

---

## How It Works

```
┌──────────────┐   G-force reading   ┌──────────────────┐
│  MPU-6050    │ ──────────────────► │ AccidentDetector │
│ (via I2C)    │                     │                  │
└──────────────┘                     │  magnitude ≥ 2.5g│
                                     │  for N samples?  │
┌──────────────┐   location          │       │ YES      │
│  GPS Module  │ ◄───────────────────│       ▼          │
│ (via UART)   │                     │  Accident event  │
└──────────────┘                     └──────────────────┘
        │                                     │
        │ lat/lon + Maps URL                  │
        └────────────────────►  AlertManager  │
                                     │        │
                              E-mail │        │ SMS (Twilio)
                                     ▼        ▼
                              Emergency contacts notified
```

1. The main loop polls the MPU-6050 every `SAMPLE_INTERVAL` seconds.
2. `AccidentDetector.check()` calculates the vector magnitude and increments a
   streak counter when it exceeds the threshold.
3. After `ACCIDENT_CONFIRMATION_COUNT` consecutive high-G readings the event is
   confirmed and the streak resets (ready for the next event).
4. `GPSModule.get_location()` reads NMEA sentences from the GPS serial port and
   returns the current position plus a Google Maps URL.
5. `AlertManager.send_alert()` sends the formatted message (including location)
   to all configured e-mail addresses and phone numbers.

