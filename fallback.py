"""
fallback.py — Replay trace provider and local trace persistence.
Loads prerecorded traces for demo fallback mode.
Saves useful live traces locally so they survive Pi reboots.
"""

import json
import os

import pandas as pd

from config import (
    DATA_DIR,
    REPLAY_HEALTHY_FILE,
    REPLAY_FAULT_FILE,
    REPLAY_COMMISSIONING_FILE,
)

SCENARIOS = {
    "healthy": REPLAY_HEALTHY_FILE,
    "fault": REPLAY_FAULT_FILE,
    "commissioning": REPLAY_COMMISSIONING_FILE,
}


def load_replay(scenario: str) -> pd.DataFrame:
    """Load a prerecorded trace. scenario: 'healthy', 'fault', or 'commissioning'."""
    filename = SCENARIOS.get(scenario)
    if filename is None:
        raise ValueError(f"Unknown scenario '{scenario}'. Choose from: {list(SCENARIOS.keys())}")
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    if "_time" in df.columns:
        df["_time"] = pd.to_datetime(df["_time"])
    return df


def save_trace(df: pd.DataFrame, name: str) -> str:
    """Save a DataFrame trace to data/ as JSON. Returns the file path."""
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
    filename = f"{safe_name}.json"
    path = os.path.join(DATA_DIR, filename)
    records = df.copy()
    if "_time" in records.columns:
        records["_time"] = records["_time"].astype(str)
    records.to_json(path, orient="records", indent=2)
    return path
