"""
commander.py — Actuator command writer.
Sends setpoint commands to InfluxDB _process measurement.
"""

import time
from datetime import datetime, timezone

import pandas as pd
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS, WritePrecision

from config import (
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET,
    INFLUX_PROCESS, SEQ_STEP_DELAY, INFLUX_TIMEOUT_MS,
)


_client = None
_write_api = None
_EPOCH = datetime.fromtimestamp(0, tz=timezone.utc)


def _get_write_api():
    global _client, _write_api
    if _write_api is None:
        _client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG,
            verify_ssl=False,
            timeout=INFLUX_TIMEOUT_MS,
        )
        _write_api = _client.write_api(write_options=SYNCHRONOUS)
    return _write_api


def send_setpoint(setpoint: float, test_number: int = -1):
    """Send a single setpoint command to the actuator. Raises ConnectionError if InfluxDB unreachable."""
    if not (0 <= setpoint <= 100):
        raise ValueError(f"Setpoint {setpoint} out of range. Must be 0-100.")
    try:
        api = _get_write_api()
        df = pd.DataFrame([{
            "timestamp": _EPOCH,
            "setpoint_position_%": float(setpoint),
            "test_number": int(test_number),
        }]).set_index("timestamp")
        api.write(
            bucket=INFLUX_BUCKET,
            record=df,
            write_precision=WritePrecision.MS,
            data_frame_measurement_name=INFLUX_PROCESS,
            data_frame_tag_columns=[],
        )
    except Exception as e:
        raise ConnectionError(f"Failed to send command to InfluxDB: {e}") from e


def run_sequence(sequence: list[float], test_number: int, delay: float = SEQ_STEP_DELAY,
                 progress_callback=None):
    """Send a sequence of setpoints with delays. Optional progress callback(i, total)."""
    for sp in sequence:
        if not (0 <= sp <= 100):
            raise ValueError(f"Setpoint {sp} in sequence out of range. Must be 0-100.")
    total = len(sequence)
    for i, sp in enumerate(sequence):
        send_setpoint(sp, test_number)
        if progress_callback:
            progress_callback(i + 1, total)
        if i < total - 1:
            time.sleep(delay)
