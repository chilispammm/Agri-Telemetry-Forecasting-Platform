"""
ESP32 / Wokwi Agricultural Telemetry Firmware Simulator.
Simulates ESP32 edge microcontroller transmitting multi-channel soil moisture and weather telemetry over MQTT.
Explicitly labels all generated telemetry as SIMULATED (never physical observations).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Generator
import json
import random
import uuid


@dataclass
class ESP32SensorReading:
    """Raw sensor readings captured on the ESP32 edge board."""
    timestamp_utc: str
    device_id: str
    site_id: str
    battery_mv: int
    wifi_rssi_dbm: int
    firmware_version: str
    soil_moisture_5cm_vwc: Optional[float]
    soil_moisture_10cm_vwc: Optional[float]
    soil_moisture_20cm_vwc: Optional[float]
    soil_moisture_50cm_vwc: Optional[float]
    soil_moisture_100cm_vwc: Optional[float]
    soil_temp_10cm_c: Optional[float]
    air_temp_c: Optional[float]
    relative_humidity_pct: Optional[float]
    solar_radiation_wm2: Optional[float]
    precipitation_pulse_mm: Optional[float]
    is_simulated: bool = True  # Strict simulation label


class ESP32TelemetrySimulator:
    """
    Simulates field-deployed ESP32 node transmitting telemetry packets via MQTT.
    """

    def __init__(
        self,
        device_id: str = "ESP32-AGRI-NODE-001",
        site_id: str = "FIELD_SIM_01",
        base_theta: float = 0.26,
        random_seed: int = 42,
    ):
        self.device_id = device_id
        self.site_id = site_id
        self.base_theta = base_theta
        self.current_theta = base_theta
        self.rng = random.Random(random_seed)
        self.seq_number = 0

    def generate_packet(
        self,
        event_time: Optional[datetime] = None,
        inject_spike: bool = False,
        inject_stuck: bool = False,
        inject_nan: bool = False,
    ) -> Dict[str, Any]:
        """
        Generates a single MQTT JSON telemetry payload formatted as emitted by ESP32 C++/MicroPython firmware.
        """
        self.seq_number += 1
        t_dt = event_time or datetime.now(timezone.utc)
        t_iso = t_dt.isoformat().replace("+00:00", "Z")

        hour = t_dt.hour
        # Diurnal solar cycle
        solar = max(0.0, 750.0 * max(0.0, (1.0 - ((hour - 13) / 6.0) ** 2))) if 6 <= hour <= 19 else 0.0
        # Diurnal temp cycle
        air_t = 18.0 + 8.0 * (1.0 - ((hour - 14) / 7.0) ** 2) + self.rng.gauss(0, 0.5)
        rh = max(20.0, min(95.0, 85.0 - (air_t - 15.0) * 2.5 + self.rng.gauss(0, 1.0)))

        # Evapotranspiration drying during daylight, occasional rain pulse
        is_rain = self.rng.random() < 0.05
        rain_mm = round(self.rng.uniform(1.0, 8.0), 1) if is_rain else 0.0

        if is_rain:
            self.current_theta = min(0.42, self.current_theta + rain_mm * 0.015)
        else:
            et_drying = 0.0003 * (solar / 500.0) if solar > 0 else 0.00005
            self.current_theta = max(0.08, self.current_theta - et_drying)

        sm_10 = round(self.current_theta + self.rng.gauss(0, 0.002), 4)
        sm_5 = round(self.current_theta * 0.95 + self.rng.gauss(0, 0.003), 4)
        sm_20 = round(self.current_theta * 1.02 + self.rng.gauss(0, 0.001), 4)
        sm_50 = round(self.current_theta * 1.05, 4)
        sm_100 = round(self.current_theta * 1.08, 4)

        if inject_spike:
            sm_10 = 0.88  # Unphysical spike
        if inject_stuck:
            sm_10 = 0.2222
        if inject_nan:
            sm_10 = None

        payload = {
            "device_id": self.device_id,
            "site_id": self.site_id,
            "seq": self.seq_number,
            "timestamp_utc": t_iso,
            "battery_mv": 3950 - (self.seq_number % 100),
            "wifi_rssi_dbm": -68 + self.rng.randint(-3, 3),
            "firmware_version": "2.4.1-wokwi",
            "is_simulated": True,  # Mandatory simulation flag
            "sensors": {
                "soil_moisture_5cm": sm_5,
                "soil_moisture_10cm": sm_10,
                "soil_moisture_20cm": sm_20,
                "soil_moisture_50cm": sm_50,
                "soil_moisture_100cm": sm_100,
                "soil_temp_10cm_c": round(air_t * 0.8 + 2.0, 1),
                "air_temp_c": round(air_t, 1),
                "rh_pct": round(rh, 1),
                "solar_radiation_wm2": round(solar, 1),
                "precipitation_mm": rain_mm,
            }
        }
        return payload

    def generate_stream(
        self,
        start_time: datetime,
        hours: int = 48,
    ) -> Generator[Dict[str, Any], None, None]:
        """Generates a continuous hourly stream of simulated ESP32 MQTT payloads."""
        cur = start_time
        for _ in range(hours):
            yield self.generate_packet(event_time=cur)
            cur += timedelta(hours=1)
