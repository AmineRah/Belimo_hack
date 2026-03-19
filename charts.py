"""
charts.py — Visualization helpers using Altair.
"""

import altair as alt
import pandas as pd

from config import (
    COLOR_GREEN, COLOR_AMBER, COLOR_RED, COLOR_ORANGE, COLOR_PURPLE,
    HEALTH_GREEN, HEALTH_AMBER,
    F_POSITION, F_SETPOINT, F_TORQUE, F_TEMPERATURE, F_TIME,
)


def score_color(score: float) -> str:
    if score >= HEALTH_GREEN:
        return COLOR_GREEN
    elif score >= HEALTH_AMBER:
        return COLOR_AMBER
    return COLOR_RED


# ── Live monitor charts ──────────────────────────────────────────────────────

def position_chart(df: pd.DataFrame) -> alt.LayerChart:
    """Position + setpoint vs time."""
    base = alt.Chart(df).encode(x=alt.X(f"{F_TIME}:T", title="Time"))
    pos = base.mark_line(color=COLOR_PURPLE).encode(
        y=alt.Y(f"{F_POSITION}:Q", title="Position (%)", scale=alt.Scale(domain=[0, 100])),
    )
    layers = [pos]
    if F_SETPOINT in df.columns:
        sp = base.mark_line(color=COLOR_ORANGE, strokeDash=[4, 2]).encode(
            y=f"{F_SETPOINT}:Q",
        )
        layers.append(sp)
    return alt.layer(*layers).properties(title="Position", height=250)


def torque_time_chart(df: pd.DataFrame) -> alt.Chart:
    """Torque vs time."""
    return alt.Chart(df).mark_line(color=COLOR_GREEN).encode(
        x=alt.X(f"{F_TIME}:T", title="Time"),
        y=alt.Y(f"{F_TORQUE}:Q", title="Torque (N·mm)"),
    ).properties(title="Torque", height=250)


def phase_portrait(df: pd.DataFrame, title: str = "Phase Portrait") -> alt.Chart:
    """Torque vs position scatter — the mechanical fingerprint."""
    return alt.Chart(df).mark_circle(size=12, opacity=0.6, color=COLOR_PURPLE).encode(
        x=alt.X(f"{F_POSITION}:Q", title="Position (%)"),
        y=alt.Y(f"{F_TORQUE}:Q", title="Torque (N·mm)"),
    ).properties(title=title, height=300)


# ── Torque profile charts ───────────────────────────────────────────────────

def _profile_to_df(profile: pd.Series, series_name: str) -> pd.DataFrame:
    d = profile.reset_index()
    d.columns = ["position_bin", "torque"]
    d["position_bin"] = d["position_bin"].astype(float)
    d["series"] = series_name
    return d


def baseline_profile_chart(profile: pd.Series) -> alt.Chart:
    """Single baseline torque profile."""
    df = _profile_to_df(profile, "Baseline")
    return alt.Chart(df).mark_line(point=True, color=COLOR_ORANGE).encode(
        x=alt.X("position_bin:Q", title="Position Bin (%)"),
        y=alt.Y("torque:Q", title="Mean |Torque| (N·mm)"),
    ).properties(title="Baseline Torque Profile", height=350)


def profile_overlay_chart(baseline: pd.Series, current: pd.Series) -> alt.Chart:
    """Baseline vs current torque profiles overlaid."""
    b_df = _profile_to_df(baseline, "Baseline")
    c_df = _profile_to_df(current, "Current")
    overlay = pd.concat([b_df, c_df], ignore_index=True)
    return alt.Chart(overlay).mark_line(point=True).encode(
        x=alt.X("position_bin:Q", title="Position Bin (%)"),
        y=alt.Y("torque:Q", title="Mean |Torque| (N·mm)"),
        color=alt.Color("series:N", scale=alt.Scale(
            domain=["Baseline", "Current"],
            range=[COLOR_ORANGE, COLOR_PURPLE],
        )),
    ).properties(title="Torque Profile: Baseline vs Current", height=350)


# ── Fleet chart ──────────────────────────────────────────────────────────────

def fleet_bar_chart(fleet_df: pd.DataFrame) -> alt.Chart:
    """Bar chart of health scores across test numbers."""
    fleet_df = fleet_df.copy()
    fleet_df["color"] = fleet_df["score"].apply(score_color)
    return alt.Chart(fleet_df).mark_bar().encode(
        x=alt.X("test_number:O", title="Test Number"),
        y=alt.Y("score:Q", title="Health Score", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("color:N", scale=None),
    ).properties(title="Fleet Health Overview", height=350)


# ── Score badge (HTML) ───────────────────────────────────────────────────────

def score_badge_html(score: float, label: str = "Health Score") -> str:
    """Large score display with colored border."""
    color = score_color(score)
    return (
        f"<div style='text-align:center; padding:24px; "
        f"border:5px solid {color}; border-radius:18px;'>"
        f"<h1 style='color:{color}; font-size:3.5em; margin:0;'>{score:.0f}</h1>"
        f"<p style='font-size:1.2em; margin:4px 0 0 0;'>{label}</p></div>"
    )


def commissioning_badge_html(score: int, verdict: str) -> str:
    """Large commissioning badge with verdict."""
    color = COLOR_GREEN if verdict == "PASS" else (COLOR_AMBER if verdict == "MARGINAL" else COLOR_RED)
    return (
        f"<div style='text-align:center; padding:30px; "
        f"border:6px solid {color}; border-radius:20px; margin-bottom:20px;'>"
        f"<h1 style='color:{color}; font-size:4em; margin:0;'>{score}</h1>"
        f"<h2 style='color:{color}; margin:0;'>{verdict}</h2>"
        f"<p>Commissioning Quality Score</p></div>"
    )
