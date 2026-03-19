"""
charts.py — Visualization helpers using Altair.
Clean medical / clinical theme for ActuSpec.
"""

import altair as alt
import pandas as pd

from config import (
    HEALTH_GREEN,
    HEALTH_AMBER,
    F_POSITION,
    F_SETPOINT,
    F_TORQUE,
    F_TEMPERATURE,
    F_DIRECTION,
    F_TIME,
)

# ── Clinical palette ─────────────────────────────────────────────────────────
TEAL = "#0d9488"          # primary accent (medical teal)
TEAL_LIGHT = "#99f6e4"
TEAL_SOFT = "rgba(13,148,136,0.08)"
SLATE_700 = "#334155"
SLATE_500 = "#64748b"
SLATE_300 = "#cbd5e1"
SLATE_100 = "#f1f5f9"
WHITE = "#ffffff"
GREEN = "#1D9E75"
AMBER = "#EF9F27"
RED = "#E24B4A"
BASELINE_COLOR = "#D85A30"
CURRENT_COLOR = "#7F77DD"

CHART_BG = WHITE
GRID_COLOR = "#e2e8f0"
AXIS_COLOR = "#94a3b8"
TITLE_COLOR = "#1e293b"


def _style(chart: alt.Chart) -> alt.Chart:
    """Apply clean clinical theme to chart."""
    return (
        chart.configure_view(stroke="#e2e8f0", fill=CHART_BG, cornerRadius=12)
        .configure_title(color=TITLE_COLOR, fontSize=14, anchor="start", fontWeight=700, font="Inter")
        .configure_axis(
            labelColor=AXIS_COLOR, titleColor=SLATE_500, gridColor=GRID_COLOR,
            gridOpacity=1, labelFontSize=11, titleFontSize=11,
            domainColor="#e2e8f0", tickColor="#e2e8f0",
            labelFont="Inter", titleFont="Inter",
        )
        .configure_legend(
            labelColor=SLATE_500, titleColor=SLATE_500, labelFontSize=11,
            titleFontSize=11, symbolSize=100, orient="top",
            labelFont="Inter", titleFont="Inter",
        )
    )


def score_color(score: float) -> str:
    if score >= HEALTH_GREEN:
        return GREEN
    elif score >= HEALTH_AMBER:
        return AMBER
    return RED


def health_label(score: float) -> str:
    if score >= HEALTH_GREEN:
        return "HEALTHY"
    elif score >= HEALTH_AMBER:
        return "DEGRADED"
    return "CRITICAL"


# ── Live monitor charts ──────────────────────────────────────────────────────

def position_chart(df: pd.DataFrame) -> alt.LayerChart:
    """Position + setpoint vs time."""
    base = alt.Chart(df).encode(
        x=alt.X(f"{F_TIME}:T", title="Time"),
        tooltip=[
            alt.Tooltip(f"{F_TIME}:T", title="Time"),
            alt.Tooltip(f"{F_POSITION}:Q", title="Position (%)", format=".1f"),
        ],
    )
    pos = base.mark_line(color=TEAL, strokeWidth=2.5, interpolate="monotone").encode(
        y=alt.Y(f"{F_POSITION}:Q", title="Position (%)", scale=alt.Scale(domain=[0, 100])),
    )
    layers = [pos]
    if F_SETPOINT in df.columns:
        sp = base.mark_line(color=SLATE_300, strokeWidth=1.5, strokeDash=[6, 4]).encode(
            y=f"{F_SETPOINT}:Q",
        )
        layers.append(sp)
    chart = alt.layer(*layers).properties(title="Position Tracking", height=260)
    return _style(chart)


def torque_time_chart(df: pd.DataFrame) -> alt.Chart:
    """Torque vs time area chart."""
    chart = (
        alt.Chart(df)
        .mark_area(
            color=TEAL_SOFT, opacity=0.5,
            line={"color": TEAL, "strokeWidth": 2.5},
        )
        .encode(
            x=alt.X(f"{F_TIME}:T", title="Time"),
            y=alt.Y(f"{F_TORQUE}:Q", title="Torque (N·mm)"),
            tooltip=[
                alt.Tooltip(f"{F_TIME}:T", title="Time"),
                alt.Tooltip(f"{F_TORQUE}:Q", title="Torque", format=".1f"),
            ],
        )
        .properties(title="Torque Over Time", height=260)
    )
    return _style(chart)


def phase_portrait(df: pd.DataFrame, title: str = "Mechanical Fingerprint") -> alt.Chart:
    """Torque vs position scatter — the ECG."""
    base = alt.Chart(df).encode(
        x=alt.X(f"{F_POSITION}:Q", title="Position (%)"),
        y=alt.Y(f"{F_TORQUE}:Q", title="Torque (N·mm)"),
        tooltip=[
            alt.Tooltip(f"{F_POSITION}:Q", title="Position", format=".1f"),
            alt.Tooltip(f"{F_TORQUE}:Q", title="Torque", format=".1f"),
        ],
    )
    if F_DIRECTION in df.columns:
        scatter = base.mark_circle(size=40, opacity=0.65).encode(
            color=alt.Color(f"{F_DIRECTION}:N", title="Direction",
                            scale=alt.Scale(domain=[1, 2], range=[TEAL, CURRENT_COLOR])),
        )
    else:
        scatter = base.mark_circle(size=40, opacity=0.65, color=TEAL)
    chart = scatter.properties(title=title, height=300)
    return _style(chart)


# ── Torque profile charts ────────────────────────────────────────────────────

def _profile_to_df(profile: pd.Series, series_name: str) -> pd.DataFrame:
    d = profile.reset_index()
    d.columns = ["position_bin", "torque"]
    d["position_bin"] = d["position_bin"].astype(float)
    d["series"] = series_name
    return d


def baseline_profile_chart(profile: pd.Series) -> alt.Chart:
    """Single baseline torque profile."""
    df = _profile_to_df(profile, "Baseline")
    chart = (
        alt.Chart(df)
        .mark_line(point=alt.OverlayMarkDef(size=50), color=BASELINE_COLOR, strokeWidth=2.5)
        .encode(
            x=alt.X("position_bin:Q", title="Position Bin (%)"),
            y=alt.Y("torque:Q", title="Mean |Torque| (N·mm)"),
            tooltip=[
                alt.Tooltip("position_bin:Q", title="Bin", format=".1f"),
                alt.Tooltip("torque:Q", title="Torque", format=".1f"),
            ],
        )
        .properties(title="Certified Healthy Baseline", height=340)
    )
    return _style(chart)


def profile_overlay_chart(baseline: pd.Series, current: pd.Series) -> alt.Chart:
    """Baseline vs current overlaid."""
    b_df = _profile_to_df(baseline, "Baseline")
    c_df = _profile_to_df(current, "Current")
    overlay = pd.concat([b_df, c_df], ignore_index=True)
    chart = (
        alt.Chart(overlay)
        .mark_line(point=alt.OverlayMarkDef(size=44), strokeWidth=2.5)
        .encode(
            x=alt.X("position_bin:Q", title="Position Bin (%)"),
            y=alt.Y("torque:Q", title="Mean |Torque| (N·mm)"),
            color=alt.Color("series:N",
                            scale=alt.Scale(domain=["Baseline", "Current"],
                                            range=[BASELINE_COLOR, CURRENT_COLOR]),
                            legend=alt.Legend(title=None)),
            tooltip=[
                alt.Tooltip("series:N", title="Series"),
                alt.Tooltip("position_bin:Q", title="Bin", format=".1f"),
                alt.Tooltip("torque:Q", title="Torque", format=".1f"),
            ],
        )
        .properties(title="Torque Overlay: Baseline vs Current", height=340)
    )
    return _style(chart)


# ── Fleet chart ──────────────────────────────────────────────────────────────

def fleet_bar_chart(fleet_df: pd.DataFrame) -> alt.Chart:
    """Bar chart of health scores across test numbers."""
    chart = (
        alt.Chart(fleet_df)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("test_number:O", title="Test Number", sort="-y"),
            y=alt.Y("score:Q", title="Health Score", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("score:Q",
                            scale=alt.Scale(domain=[0, 50, 80, 100],
                                            range=[RED, AMBER, GREEN, TEAL]),
                            legend=None),
            tooltip=[
                alt.Tooltip("test_number:O", title="Test"),
                alt.Tooltip("score:Q", title="Score", format=".1f"),
            ],
        )
        .properties(title="Fleet Health Overview", height=340)
    )
    return _style(chart)


def commissioning_area_chart(df: pd.DataFrame, verdict: str) -> alt.Chart:
    """Torque vs position area chart, color matches verdict."""
    color = GREEN if verdict == "PASS" else (AMBER if verdict == "MARGINAL" else RED)
    chart = (
        alt.Chart(df)
        .mark_area(opacity=0.3, color=color,
                   line={"color": color, "strokeWidth": 2.5})
        .encode(
            x=alt.X(f"{F_POSITION}:Q", title="Position (%)"),
            y=alt.Y(f"{F_TORQUE}:Q", title="Torque (N·mm)"),
        )
        .properties(title="Installation Stroke Fingerprint", height=300)
    )
    return _style(chart)


# ── Score badges (HTML) ──────────────────────────────────────────────────────

def score_badge_html(score: float, deviation_pct: float = None) -> str:
    """Clean medical-style score card with colored accent."""
    color = score_color(score)
    label = health_label(score)
    dev_line = ""
    if deviation_pct is not None:
        dev_line = (
            f"<p style='font-size:13px; color:#94a3b8; margin:6px 0 0 0;'>"
            f"RMS deviation: {deviation_pct:.1f}%</p>"
        )
    return (
        f"<div style='text-align:center; padding:32px 24px; border-radius:16px;"
        f" background:white; border:2px solid {color};"
        f" box-shadow:0 4px 24px rgba(0,0,0,0.06);'>"
        f"<p style='font-size:11px; text-transform:uppercase; letter-spacing:2px;"
        f" color:#94a3b8; font-weight:700; margin:0 0 8px 0;'>Health Score</p>"
        f"<h1 style='color:{color}; font-size:3.5em; margin:0; font-weight:900;"
        f" letter-spacing:-0.02em;'>{score:.0f}</h1>"
        f"<span style='display:inline-block; background:{color}18; color:{color};"
        f" border:1px solid {color}40; border-radius:999px; padding:4px 16px;"
        f" font-size:11px; text-transform:uppercase; letter-spacing:1.5px;"
        f" font-weight:700; margin-top:8px;'>{label}</span>"
        f"{dev_line}"
        f"</div>"
    )


def commissioning_badge_html(score: int, verdict: str) -> str:
    """Clean medical-style commissioning badge."""
    color = GREEN if verdict == "PASS" else (AMBER if verdict == "MARGINAL" else RED)
    return (
        f"<div style='text-align:center; padding:32px 24px; border-radius:16px;"
        f" background:white; border:2px solid {color};"
        f" box-shadow:0 4px 24px rgba(0,0,0,0.06); margin-bottom:16px;'>"
        f"<p style='font-size:11px; text-transform:uppercase; letter-spacing:2px;"
        f" color:#94a3b8; font-weight:700; margin:0 0 8px 0;'>Commissioning Quality</p>"
        f"<h1 style='color:{color}; font-size:4em; margin:0; font-weight:900;'>{score}</h1>"
        f"<span style='display:inline-block; background:{color}18; color:{color};"
        f" border:1px solid {color}40; border-radius:999px; padding:6px 20px;"
        f" font-size:13px; text-transform:uppercase; letter-spacing:2px;"
        f" font-weight:800; margin-top:8px;'>{verdict}</span>"
        f"</div>"
    )
