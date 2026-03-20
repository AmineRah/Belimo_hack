"""
collector.py — InfluxDB trace retrieval.
Queries telemetry, returns clean DataFrames.
"""

import pandas as pd
from influxdb_client import InfluxDBClient

from config import (
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET,
    INFLUX_MEASUREMENT, REQUIRED_FIELDS, INFLUX_TIMEOUT_MS,
)


_client = None


def _get_client() -> InfluxDBClient:
    global _client
    if _client is None:
        _client = InfluxDBClient(
            url=INFLUX_URL,
            token=INFLUX_TOKEN,
            org=INFLUX_ORG,
            verify_ssl=False,
            timeout=INFLUX_TIMEOUT_MS,
        )
    return _client


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Drop InfluxDB metadata columns, parse timestamps."""
    if isinstance(df, list):
        df = pd.concat(df, ignore_index=True) if df else pd.DataFrame()
    if df.empty:
        return df
    for col in ["result", "table", "_start", "_stop", "_measurement"]:
        if col in df.columns:
            df.drop(columns=col, inplace=True)
    if "_time" in df.columns:
        df["_time"] = pd.to_datetime(df["_time"])
    return df


def validate_trace(df: pd.DataFrame) -> pd.DataFrame:
    """Verify key fields exist in trace data. Raises ValueError if critical fields missing."""
    if df.empty:
        return df
    missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
    if missing:
        raise ValueError(f"Trace missing required fields: {missing}")
    return df


def query_recent(range_str: str = "-5m") -> pd.DataFrame:
    """Get all recent telemetry (for live monitor). Returns empty DataFrame on connection error."""
    try:
        client = _get_client()
        flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {range_str})
  |> filter(fn: (r) => r["_measurement"] == "{INFLUX_MEASUREMENT}")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''
        df = client.query_api().query_data_frame(flux, org=INFLUX_ORG)
        return _clean_df(df)
    except Exception as e:
        print(f"[collector] query_recent failed: {e}")
        return pd.DataFrame()


def query_by_test_number(test_number: int, range_str: str = "-24h") -> pd.DataFrame:
    """Get telemetry for a specific test number.

    Returns an empty DataFrame when no rows match.
    Raises ConnectionError when InfluxDB query fails.
    """
    try:
        client = _get_client()
        flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {range_str})
  |> filter(fn: (r) => r["_measurement"] == "{INFLUX_MEASUREMENT}")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => r["test_number"] == {test_number})
  |> sort(columns: ["_time"])
'''
        df = client.query_api().query_data_frame(flux, org=INFLUX_ORG)
        return validate_trace(_clean_df(df))
    except Exception as e:
        raise ConnectionError(
            f"Failed to query InfluxDB for test_number={test_number}: {e}"
        ) from e


def count_by_test_number(test_number: int, range_str: str = "-1h") -> int:
    """Count rows for a test_number without downloading the full DataFrame.

    Returns 0 when InfluxDB is unreachable or no data exists.
    """
    try:
        client = _get_client()
        flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {range_str})
  |> filter(fn: (r) => r["_measurement"] == "{INFLUX_MEASUREMENT}")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => r["test_number"] == {test_number})
  |> count(column: "_time")
'''
        tables = client.query_api().query(flux, org=INFLUX_ORG)
        for table in tables:
            for record in table.records:
                return int(record.get_value())
        return 0
    except Exception as e:
        print(f"[collector] count_by_test_number({test_number}) failed: {e}")
        return 0


def query_all_test_numbers(range_str: str = "-24h") -> pd.DataFrame:
    """Get all telemetry in range (for fleet analysis). Returns empty DataFrame on connection error."""
    try:
        client = _get_client()
        flux = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: {range_str})
  |> filter(fn: (r) => r["_measurement"] == "{INFLUX_MEASUREMENT}")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''
        df = client.query_api().query_data_frame(flux, org=INFLUX_ORG)
        return validate_trace(_clean_df(df))
    except Exception as e:
        print(f"[collector] query_all_test_numbers failed: {e}")
        return pd.DataFrame()
