"""
baseline.py — Healthy reference manager.
Loads baseline trace, generates baseline torque profile.
"""

import json
import os

import pandas as pd

from analyzer import torque_profile
from config import DATA_DIR, BASELINE_FILE, F_POSITION, F_TORQUE


def load_baseline_from_file() -> pd.DataFrame:
    """Load the healthy baseline trace from JSON. Returns empty DataFrame if file missing."""
    path = os.path.join(DATA_DIR, BASELINE_FILE)
    if not os.path.exists(path):
        print(f"[baseline] Warning: {path} not found, returning empty DataFrame")
        return pd.DataFrame()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[baseline] Error reading {path}: {e}")
        return pd.DataFrame()


def baseline_profile_from_file() -> pd.Series:
    """Load baseline trace and return its torque profile."""
    df = load_baseline_from_file()
    return torque_profile(df)


def baseline_profile_from_df(df: pd.DataFrame) -> pd.Series:
    """Compute torque profile from a live baseline DataFrame."""
    return torque_profile(df)


def save_baseline(df: pd.DataFrame) -> str:
    """Save a baseline trace DataFrame to the canonical baseline file. Returns path."""
    path = os.path.join(DATA_DIR, BASELINE_FILE)
    records = df.copy()
    if "_time" in records.columns:
        records["_time"] = records["_time"].astype(str)
    records.to_json(path, orient="records", indent=2)
    return path