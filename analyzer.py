"""
analyzer.py — Scoring, metrics, rules, and diagnostic explanations.
All analysis is deterministic and explainable.
"""

import numpy as np
import pandas as pd

from config import (
    F_POSITION, F_SETPOINT, F_TORQUE, F_TEMPERATURE, F_POWER, F_DIRECTION,
    N_BINS,
    COMM_RANGE_THRESHOLD, COMM_RANGE_PENALTY,
    COMM_TORQUE_CV_THRESHOLD, COMM_TORQUE_CV_PENALTY,
    COMM_TRACKING_THRESHOLD, COMM_TRACKING_PENALTY,
    COMM_TEMP_THRESHOLD, COMM_TEMP_PENALTY,
    COMM_PASS_THRESHOLD, COMM_MARGINAL_THRESHOLD,
)


# ── Torque profile ───────────────────────────────────────────────────────────

def torque_profile(df: pd.DataFrame, n_bins: int = N_BINS) -> pd.Series:
    """Bin |torque| by position → mean per bin. Returns pd.Series indexed by bin centre."""
    d = df.copy()
    if F_DIRECTION in d.columns:
        d = d[d[F_DIRECTION] != 0]
    d["torque_abs"] = d[F_TORQUE].abs()
    bins = np.linspace(0, 100, n_bins + 1)
    labels = np.round((bins[:-1] + bins[1:]) / 2, 1)
    d["bin"] = pd.cut(d[F_POSITION], bins=bins, labels=labels)
    return d.groupby("bin", observed=True)["torque_abs"].mean()


# ── Health score ─────────────────────────────────────────────────────────────

def health_score(baseline: pd.Series, current: pd.Series) -> float:
    """RMS deviation between two torque profiles → score 0–100.

    When baseline and current have very different magnitude (e.g. synthetic
    baseline vs real actuator data), the profiles are auto-scaled so the
    comparison reflects shape similarity rather than absolute torque match.
    """
    common = baseline.dropna().index.intersection(current.dropna().index)
    if len(common) == 0:
        return 0.0
    b = baseline[common].values.astype(float)
    c = current[common].values.astype(float)

    b_mean = float(b.mean())
    c_mean = float(c.mean())

    # Auto-scale when magnitude mismatch exceeds 2x — this handles the
    # situation where the baseline file uses different units or scale
    # than the real actuator data.
    if b_mean > 0 and c_mean > 0:
        ratio = b_mean / c_mean
        if ratio > 2.0 or ratio < 0.5:
            c = c * (b_mean / c_mean)

    rms_dev = float(np.sqrt(np.mean((b - c) ** 2)))
    if b.max() == 0:
        return 100.0
    return float(max(0.0, 100.0 * (1.0 - rms_dev / b.max())))


# ── Health diagnosis ─────────────────────────────────────────────────────────

def health_diagnosis(baseline: pd.Series, current: pd.Series, score: float,
                     df: pd.DataFrame = None) -> list[str]:
    """Generate deterministic diagnostic text from profile comparison.
    Optionally pass raw trace df for tracking error and power diagnostics."""
    diagnostics = []
    common = baseline.dropna().index.intersection(current.dropna().index)
    if len(common) == 0:
        return ["Insufficient data for diagnosis."]

    b = baseline[common].values.astype(float)
    c = current[common].values.astype(float)

    # Auto-scale for diagnosis (same as health_score)
    b_mean = float(b.mean())
    c_mean = float(c.mean())
    if b_mean > 0 and c_mean > 0:
        ratio = b_mean / c_mean
        if ratio > 2.0 or ratio < 0.5:
            c = c * (b_mean / c_mean)

    diff = c - b

    # Uniform torque increase → friction / buildup
    if np.mean(diff) > 0 and np.all(diff > -b.max() * 0.1):
        diagnostics.append(
            "Torque is elevated across the full stroke range. "
            "This pattern is consistent with valve stem buildup, limescale, or increased friction."
        )

    # Localised spike
    max_idx = np.argmax(np.abs(diff))
    if len(common) > 0:
        spike_ratio = abs(diff[max_idx]) / (b.max() if b.max() > 0 else 1)
        if spike_ratio > 0.3:
            bin_label = common[max_idx]
            diagnostics.append(
                f"Localised torque deviation detected around position {bin_label}%. "
                f"This suggests a mechanical obstruction or resistance at that angle."
            )

    # Tracking error diagnosis (requires raw trace)
    if df is not None and F_SETPOINT in df.columns and F_POSITION in df.columns:
        tracking_err = (df[F_SETPOINT] - df[F_POSITION]).abs().mean()
        if tracking_err > 10:
            diagnostics.append(
                f"Mean position tracking error is {tracking_err:.1f}%. "
                "The actuator is not reaching commanded positions — "
                "check coupling, linkage, or mechanical binding."
            )

    # Power anomaly diagnosis (requires raw trace)
    if df is not None and F_POWER in df.columns:
        power_mean = df[F_POWER].mean()
        if power_mean > 2.5:
            diagnostics.append(
                f"Average power consumption is {power_mean:.1f}W, which is elevated. "
                "This may indicate increased mechanical load or internal friction."
            )

    # General low score
    if score < 50 and not diagnostics:
        diagnostics.append(
            "Significant overall deviation from healthy baseline. "
            "Recommend physical inspection of actuator and valve linkage."
        )

    if not diagnostics:
        diagnostics.append("Torque profile is within normal range. No anomalies detected.")

    return diagnostics


# ── Commissioning score ──────────────────────────────────────────────────────

def commissioning_score(df: pd.DataFrame) -> dict:
    """Score an installation stroke. Returns dict with score, verdict, checks, diagnostics.

    All values are cast to Python native types (not numpy) to ensure
    JSON serialisation works across all numpy versions.
    """
    total = 100
    checks = {}
    diagnostics = []

    # 1. Range of motion
    pos_range = float(df[F_POSITION].max() - df[F_POSITION].min())
    passed = bool(pos_range >= COMM_RANGE_THRESHOLD)
    penalty = 0 if passed else COMM_RANGE_PENALTY
    total -= penalty
    checks["range_of_motion"] = {
        "label": "Range of Motion",
        "value": round(pos_range, 1),
        "unit": "%",
        "threshold": COMM_RANGE_THRESHOLD,
        "passed": passed,
        "penalty": penalty,
    }
    if not passed:
        diagnostics.append(
            f"Range of motion is only {pos_range:.0f}% (minimum {COMM_RANGE_THRESHOLD}%). "
            "The actuator may be mechanically blocked or the linkage is too short."
        )

    # 2. Torque variability (coefficient of variation)
    torque_abs = df[F_TORQUE].abs()
    torque_mean = float(torque_abs.mean())
    torque_std = float(torque_abs.std())
    cv = torque_std / torque_mean if torque_mean > 0 else 0.0
    passed = bool(cv <= COMM_TORQUE_CV_THRESHOLD)
    penalty = 0 if passed else COMM_TORQUE_CV_PENALTY
    total -= penalty
    checks["torque_cv"] = {
        "label": "Torque Variability (CV)",
        "value": round(cv, 2),
        "unit": "",
        "threshold": COMM_TORQUE_CV_THRESHOLD,
        "passed": passed,
        "penalty": penalty,
    }
    if not passed:
        diagnostics.append(
            f"Torque variability (CV={cv:.2f}) exceeds threshold ({COMM_TORQUE_CV_THRESHOLD}). "
            "This suggests obstruction, misalignment, or an improperly coupled valve."
        )

    # 3. Position tracking error
    tracking_err = float((df[F_SETPOINT] - df[F_POSITION]).abs().mean())
    passed = bool(tracking_err <= COMM_TRACKING_THRESHOLD)
    penalty = 0 if passed else COMM_TRACKING_PENALTY
    total -= penalty
    checks["tracking_error"] = {
        "label": "Position Tracking Error",
        "value": round(tracking_err, 1),
        "unit": "%",
        "threshold": COMM_TRACKING_THRESHOLD,
        "passed": passed,
        "penalty": penalty,
    }
    if not passed:
        diagnostics.append(
            f"Mean tracking error is {tracking_err:.1f}% (limit {COMM_TRACKING_THRESHOLD}%). "
            "The actuator is not reaching commanded positions — check coupling and linkage."
        )

    # 4. Temperature rise
    temp_rise = float(df[F_TEMPERATURE].max() - df[F_TEMPERATURE].min())
    passed = bool(temp_rise <= COMM_TEMP_THRESHOLD)
    penalty = 0 if passed else COMM_TEMP_PENALTY
    total -= penalty
    checks["temp_rise"] = {
        "label": "Temperature Rise",
        "value": round(temp_rise, 1),
        "unit": "°C",
        "threshold": COMM_TEMP_THRESHOLD,
        "passed": passed,
        "penalty": penalty,
    }
    if not passed:
        diagnostics.append(
            f"Temperature rose {temp_rise:.1f}°C during commissioning (limit {COMM_TEMP_THRESHOLD}°C). "
            "Motor may be overloaded — check for mechanical binding."
        )

    total = max(total, 0)
    if total >= COMM_PASS_THRESHOLD:
        verdict = "PASS"
    elif total >= COMM_MARGINAL_THRESHOLD:
        verdict = "MARGINAL"
    else:
        verdict = "FAIL"

    if not diagnostics:
        diagnostics.append("All commissioning checks passed. Installation quality is good.")

    return {
        "score": int(total),
        "verdict": verdict,
        "checks": checks,
        "diagnostics": diagnostics,
    }
