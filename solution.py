"""
ActuSpec — Belimo Actuator Intelligence
Clean medical / clinical Streamlit UI · START Hack 2026
"""

import time

import numpy as np
import pandas as pd
import streamlit as st

from baseline import baseline_profile_from_file, save_baseline
from charts import (
    baseline_profile_chart,
    commissioning_area_chart,
    commissioning_badge_html,
    fleet_bar_chart,
    phase_portrait,
    position_chart,
    profile_overlay_chart,
    score_badge_html,
    score_color,
    torque_time_chart,
)
from collector import query_recent
from commander import send_setpoint
from config import (
    DEFAULT_MODE,
    F_POSITION,
    F_POWER,
    F_TEMPERATURE,
    F_TIME,
    F_TORQUE,
    SEQ_FREE_STROKE,
    TN_BASELINE,
    TN_DEFAULT,
)
from fallback import load_replay
from orchestrator import (
    compute_fleet_scores,
    evaluate_commissioning_from_test_number,
    evaluate_health_from_test_number,
    export_trace,
    get_state,
    load_live_baseline,
    run_live_baseline,
    run_live_commissioning,
    run_live_health_test,
    run_replay_commissioning,
    run_replay_health,
)


# ═════════════════════════════════════════════════════════════════════════════
# CSS THEME — Clean medical / clinical
# ═════════════════════════════════════════════════════════════════════════════

def inject_theme():
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap');

.stApp {
    background: #f8fafc;
    font-family: 'Inter', system-ui, sans-serif;
}

div.block-container {
    max-width: 1320px;
    padding-top: 1rem;
}

h1, h2, h3 {
    font-family: 'Inter', sans-serif;
    color: #1e293b;
    letter-spacing: -0.01em;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #ffffff;
    border-right: 1px solid #e2e8f0;
}

/* Tabs — pill shape */
.stTabs [data-baseweb="tab-list"] { gap: 8px; margin-bottom: 8px; }
.stTabs [data-baseweb="tab"] {
    border-radius: 999px;
    border: 1px solid #e2e8f0;
    background: white;
    height: 40px;
    padding: 0 18px;
    color: #64748b;
    font-weight: 600;
    font-size: 13px;
}
.stTabs [aria-selected="true"] {
    border-color: #0d9488;
    color: #0d9488 !important;
    background: rgba(13,148,136,0.06);
}

/* Metrics */
[data-testid="stMetric"] {
    border-radius: 12px;
    padding: 12px 14px;
    background: white;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

/* Buttons — teal accent */
[data-testid="stButton"] button {
    border-radius: 10px;
    border: none;
    background: #0d9488;
    color: white;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 8px rgba(13,148,136,0.2);
    transition: all 0.15s;
}
[data-testid="stButton"] button:hover {
    background: #0f766e;
    box-shadow: 0 4px 12px rgba(13,148,136,0.3);
}

/* Inputs */
div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    border-color: #e2e8f0 !important;
    border-radius: 10px !important;
}

.stSlider [data-baseweb="slider"] div[role="slider"] {
    background: #0d9488;
}

/* Dividers */
hr { border: none; border-top: 1px solid #e2e8f0; }

/* Alerts */
.stAlert { border-radius: 12px; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 10px; }

/* DataFrames */
.stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }
</style>
    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def metric_card(label: str, value: str, subtitle: str = "", color: str = "#0d9488"):
    """Styled metric card with colored glow dot."""
    st.markdown(f"""
<div style="background:white; border:1px solid #e2e8f0; border-radius:14px;
  padding:18px 20px; box-shadow:0 1px 4px rgba(0,0,0,0.04); min-height:100px;">
  <div style="display:flex; align-items:center; gap:8px; margin-bottom:10px;">
    <span style="width:8px; height:8px; border-radius:50%; background:{color};
      box-shadow:0 0 8px {color}80;"></span>
    <span style="font-size:10px; text-transform:uppercase; letter-spacing:1.5px;
      color:#94a3b8; font-weight:700;">{label}</span>
  </div>
  <div style="font-size:1.6rem; font-weight:900; color:#1e293b; line-height:1;
    letter-spacing:-0.02em;">{value}</div>
  <div style="font-size:11px; color:#94a3b8; margin-top:6px;">{subtitle}</div>
</div>""", unsafe_allow_html=True)


def state_pill(state: str):
    """Colored state indicator pill."""
    styles = {
        "idle":       ("#94a3b8", "#f1f5f9", "#94a3b8", "Standby"),
        "commanding": ("#EF9F27", "#fffbeb", "#EF9F27", "Commanding..."),
        "collecting": ("#EF9F27", "#fffbeb", "#EF9F27", "Collecting..."),
        "analyzing":  ("#EF9F27", "#fffbeb", "#EF9F27", "Analyzing..."),
        "done":       ("#1D9E75", "#ecfdf5", "#1D9E75", "Complete"),
        "error":      ("#E24B4A", "#fef2f2", "#E24B4A", "Error"),
    }
    border, bg, text_c, label = styles.get(state, ("#94a3b8", "#f1f5f9", "#94a3b8", state))
    st.markdown(
        f"<span style='display:inline-flex; align-items:center; gap:6px; padding:4px 14px;"
        f" border-radius:999px; border:1px solid {border}40; background:{bg};"
        f" font-size:11px; font-weight:700; color:{text_c}; text-transform:uppercase;"
        f" letter-spacing:1px;'>"
        f"<span style='width:6px;height:6px;border-radius:50%;background:{text_c};"
        f" box-shadow:0 0 6px {text_c}60;'></span>{label}</span>",
        unsafe_allow_html=True,
    )


def panel_start():
    st.markdown("<div style='background:white; border:1px solid #e2e8f0; border-radius:16px;"
                " padding:20px 22px; box-shadow:0 1px 4px rgba(0,0,0,0.04); margin-bottom:14px;'>",
                unsafe_allow_html=True)


def panel_end():
    st.markdown("</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE INIT
# ═════════════════════════════════════════════════════════════════════════════

st.set_page_config(page_title="ActuSpec", page_icon="🫀", layout="wide")
inject_theme()


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
  <div style="width:36px; height:36px; border-radius:10px; background:#0d9488;
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 2px 8px rgba(13,148,136,0.3);">
    <span style="font-size:18px; color:white; font-weight:900;">A</span>
  </div>
  <div>
    <div style="font-weight:900; font-size:16px; color:#1e293b;">ActuSpec</div>
    <div style="font-size:11px; color:#94a3b8;">Actuator Diagnostics</div>
  </div>
</div>
    """, unsafe_allow_html=True)

    st.divider()
    mode = st.radio("Acquisition Mode", ["Live", "Replay"],
                    index=0 if DEFAULT_MODE == "live" else 1,
                    help="Live reads/writes InfluxDB on the Pi. Replay uses local traces.")
    is_live = mode == "Live"

    st.divider()
    with st.expander("Connection"):
        st.code("URL:    192.168.3.14:8086\nBucket: actuator-data\nOrg:    belimo\nWi-Fi:  BELIMO-X", language=None)
    with st.expander("Test numbers"):
        st.markdown("| Range | Purpose |\n|---|---|\n| `999` | Baseline |\n| `1–100` | Health |\n| `200–300` | Commissioning |\n| `-1` | Default |")
    st.caption("_\"We gave actuators an ECG.\"_")


# ── Hero banner ──────────────────────────────────────────────────────────────
current_state = get_state()
health_snap = st.session_state.get("health_result")
comm_snap = st.session_state.get("comm_result")

st.markdown(f"""
<div style="background:white; border:1px solid #e2e8f0; border-radius:18px;
  padding:24px 28px; box-shadow:0 2px 12px rgba(0,0,0,0.04); margin-bottom:14px;
  border-left:4px solid #0d9488;">
  <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
    <h2 style="margin:0; font-weight:900; letter-spacing:-0.02em;">Diagnostic Console</h2>
    <span style="display:inline-flex; align-items:center; gap:6px; background:{'#ecfdf5' if is_live else '#f1f5f9'};
      border:1px solid {'#0d948830' if is_live else '#e2e8f0'}; border-radius:999px; padding:3px 12px;
      font-size:10px; text-transform:uppercase; letter-spacing:1.5px;
      color:{'#0d9488' if is_live else '#94a3b8'}; font-weight:700;">
      <span style="width:6px;height:6px;border-radius:50%;background:{'#0d9488' if is_live else '#94a3b8'};
        box-shadow:0 0 6px {'#0d948880' if is_live else 'transparent'};"></span>
      {'System Live' if is_live else 'Replay Mode'}</span>
  </div>
  <p style="margin:8px 0 0 0; color:#64748b; font-size:14px;">
    Real-time telemetry analysis for installer decisions, commissioning quality gates, and measurable HVAC value.</p>
</div>
""", unsafe_allow_html=True)


# ── KPI strip ────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)
with k1:
    metric_card("Mode", "Live" if is_live else "Replay", "Pipeline context")
with k2:
    metric_card("Run State", current_state.upper(), "Orchestrator",
                color="#EF9F27" if current_state in ("commanding", "collecting", "analyzing") else "#0d9488")
with k3:
    hs_val = f"{health_snap.score:.0f}" if health_snap and not health_snap.error else "—"
    hs_color = score_color(health_snap.score) if health_snap and not health_snap.error else "#94a3b8"
    metric_card("Health Score", hs_val, "Latest result", color=hs_color)
with k4:
    cs_val = "—"
    cs_verdict = "Pending"
    if comm_snap and not comm_snap.error and comm_snap.commissioning:
        cs_val = str(comm_snap.commissioning["score"])
        cs_verdict = comm_snap.commissioning["verdict"]
    metric_card("Commissioning", cs_val, cs_verdict)


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "Operations Deck",
    "Baseline Lab",
    "Health Intelligence",
    "Commissioning Gate",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Operations Deck
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("Operations Deck")
    state_pill(current_state)

    if not is_live:
        panel_start()
        st.markdown("**Replay mode active.** Demonstrating behavior with prerecorded traces.")
        healthy_df = load_replay("healthy")
        fault_df = load_replay("fault")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Healthy Trace")
            st.altair_chart(phase_portrait(healthy_df, "Healthy Fingerprint"), use_container_width=True)
        with c2:
            st.subheader("Fault Trace")
            st.altair_chart(phase_portrait(fault_df, "Fault Fingerprint"), use_container_width=True)

        m1, m2, m3 = st.columns(3)
        with m1:
            metric_card("Healthy Avg Torque", f"{healthy_df[F_TORQUE].mean():.1f}", "N·mm")
        with m2:
            metric_card("Fault Avg Torque", f"{fault_df[F_TORQUE].mean():.1f}", "N·mm", color="#EF9F27")
        with m3:
            delta = fault_df[F_TORQUE].mean() - healthy_df[F_TORQUE].mean()
            metric_card("Torque Shift", f"{delta:+.1f}", "Fault vs healthy", color="#E24B4A" if delta > 5 else "#94a3b8")
        panel_end()
    else:
        left, right = st.columns([1, 2])
        with left:
            panel_start()
            st.subheader("Manual Control")
            manual_tn = st.number_input("Test number", -1, 500, TN_DEFAULT, key="ops_tn")
            setpoint = st.slider("Setpoint (%)", 0, 100, 50, key="live_sp")
            if st.button("Send Command", key="live_send"):
                try:
                    send_setpoint(setpoint, int(manual_tn))
                    st.success(f"Sent setpoint={setpoint}% / tn={int(manual_tn)}")
                except (ConnectionError, Exception) as e:
                    st.error(f"Command failed: {e}")
            quick = st.columns(3)
            for i, pct in enumerate([0, 50, 100]):
                with quick[i]:
                    if st.button(f"{pct}%", key=f"q_{pct}"):
                        try:
                            send_setpoint(pct, int(manual_tn))
                            st.info(f"→ {pct}%")
                        except (ConnectionError, Exception) as e:
                            st.error(f"Command failed: {e}")
            st.caption("Commands written to `_process`; Pi logger applies via MP-Bus.")
            panel_end()

        with right:
            panel_start()
            st.subheader("Live Telemetry")
            tw_col, auto_col = st.columns([1, 1])
            with tw_col:
                time_window = st.slider("Window (min)", 1, 10, 5, key="tw")
            with auto_col:
                auto_refresh = st.checkbox("Auto-refresh (2s)", value=False)
            refresh = st.button("Refresh", key="live_refresh")

            if refresh or auto_refresh:
                df = query_recent(f"-{time_window}m")
                if df.empty:
                    st.warning("No telemetry. Check BELIMO-X connection.")
                else:
                    latest = df.iloc[-1]
                    m1, m2, m3, m4 = st.columns(4)
                    with m1:
                        metric_card("Position", f"{latest.get(F_POSITION, 0):.1f}%", "Shaft")
                    with m2:
                        metric_card("Torque", f"{latest.get(F_TORQUE, 0):.1f}", "N·mm")
                    with m3:
                        metric_card("Power", f"{latest.get(F_POWER, 0):.2f}", "W")
                    with m4:
                        metric_card("Temp", f"{latest.get(F_TEMPERATURE, 0):.1f}°C", "PCB")

                    ch1, ch2 = st.columns(2)
                    with ch1:
                        if F_TIME in df.columns and F_POSITION in df.columns:
                            st.altair_chart(position_chart(df), use_container_width=True)
                    with ch2:
                        if F_TIME in df.columns and F_TORQUE in df.columns:
                            st.altair_chart(torque_time_chart(df), use_container_width=True)

                    if F_POSITION in df.columns and F_TORQUE in df.columns:
                        st.altair_chart(phase_portrait(df, "Live Mechanical Fingerprint"), use_container_width=True)

                if auto_refresh:
                    time.sleep(2)
                    st.rerun()
            panel_end()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Baseline Lab
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Baseline Lab")
    st.markdown("Certify a healthy actuator fingerprint — the reference for all future scoring.")

    action_col, view_col = st.columns([1, 2])

    with action_col:
        panel_start()
        st.subheader("Baseline Actions")
        if is_live:
            st.caption("Tests use `test_number=999`")
            if st.button("Run Free Stroke", key="bl_free"):
                try:
                    progress = st.progress(0)
                    msg = run_live_baseline("free", lambda i, t: progress.progress(i / t))
                    st.success(msg)
                except Exception as e:
                    st.error(f"Baseline stroke failed. Check BELIMO-X connection. ({e})")
            if st.button("Run Loaded Stroke", key="bl_loaded"):
                try:
                    progress = st.progress(0)
                    msg = run_live_baseline("loaded", lambda i, t: progress.progress(i / t))
                    st.success(msg)
                except Exception as e:
                    st.error(f"Baseline stroke failed. Check BELIMO-X connection. ({e})")
            if st.button("Run Stall Test", key="bl_stall"):
                try:
                    progress = st.progress(0)
                    msg = run_live_baseline("stall", lambda i, t: progress.progress(i / t))
                    st.success(msg)
                except Exception as e:
                    st.error(f"Baseline stroke failed. Check BELIMO-X connection. ({e})")
            st.divider()
            if st.button("Load Live Baseline", key="bl_load_live"):
                try:
                    profile, message = load_live_baseline()
                    if profile is not None:
                        st.session_state["baseline_profile"] = profile
                        st.session_state["baseline_source"] = "live"
                        st.success(message)
                    else:
                        st.warning(message)
                except Exception as e:
                    st.error(f"Could not load live baseline. Check BELIMO-X connection. ({e})")
        else:
            st.caption("Load certified baseline from local data.")
            if st.button("Load Replay Baseline", key="bl_load_replay"):
                profile = baseline_profile_from_file()
                st.session_state["baseline_profile"] = profile
                st.session_state["baseline_source"] = "replay"
                st.success("Replay baseline loaded.")
        panel_end()

    with view_col:
        panel_start()
        st.subheader("Baseline Profile")
        if "baseline_profile" not in st.session_state:
            try:
                st.session_state["baseline_profile"] = baseline_profile_from_file()
                st.session_state["baseline_source"] = "replay"
            except Exception:
                pass

        if "baseline_profile" in st.session_state:
            profile = st.session_state["baseline_profile"]
            source = st.session_state.get("baseline_source", "unknown")
            st.caption(f"Source: **{source}**")
            st.altair_chart(baseline_profile_chart(profile), use_container_width=True)

            b1, b2, b3 = st.columns(3)
            peak_bin = float(profile.idxmax()) if not profile.empty else 0.0
            peak_val = float(profile.max()) if not profile.empty else 0.0
            coverage = int(profile.notna().sum())
            with b1:
                metric_card("Peak Position", f"{peak_bin:.0f}%", "Highest stress bin")
            with b2:
                metric_card("Peak Torque", f"{peak_val:.1f}", "N·mm")
            with b3:
                metric_card("Coverage", f"{coverage}", "Valid bins")

            if is_live:
                st.divider()
                if st.button("Export Baseline to Local", key="bl_export"):
                    try:
                        from collector import query_by_test_number
                        df_b = query_by_test_number(TN_BASELINE, "-24h")
                        if df_b.empty:
                            st.warning("No live baseline to export.")
                        else:
                            path = save_baseline(df_b)
                            st.success(f"Saved: `{path}`")
                    except Exception as e:
                        st.error(f"Export failed: {e}")
        else:
            st.warning("No baseline loaded.")
        panel_end()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — Health Intelligence
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("Health Intelligence")

    controls, results = st.columns([1, 2])

    with controls:
        panel_start()
        st.subheader("Analysis Controls")
        if is_live:
            tn = st.number_input("Test number (1–100)", 1, 100, 1, key="hs_tn")
            c1, c2 = st.columns(2)
            with c1:
                sp = st.slider("Setpoint (%)", 0, 100, 50, key="hs_sp")
                if st.button("Send Step", key="hs_send"):
                    try:
                        send_setpoint(sp, int(tn))
                        st.success(f"Sent {sp}%")
                    except (ConnectionError, Exception) as e:
                        st.error(f"Command failed: {e}")
            with c2:
                if st.button("Run Full Stroke", key="hs_full"):
                    try:
                        progress = st.progress(0)
                        result = run_live_health_test(int(tn), SEQ_FREE_STROKE,
                                                      lambda i, t: progress.progress(i / t))
                        if result.error:
                            st.error(result.error)
                        else:
                            st.session_state["health_result"] = result
                    except Exception as e:
                        st.error(f"Health test failed. Check BELIMO-X connection. ({e})")
            if st.button("Score Existing Data", key="hs_compute"):
                bp = st.session_state.get("baseline_profile")
                if bp is None:
                    st.error("Load a baseline first.")
                else:
                    result = evaluate_health_from_test_number(int(tn), baseline_profile=bp)
                    if result.error:
                        st.warning(result.error)
                    else:
                        st.session_state["health_result"] = result
        else:
            scenario = st.selectbox("Replay scenario", ["healthy", "fault"], key="hs_scenario")
            if st.button("Analyze Replay Trace", key="hs_replay"):
                result = run_replay_health(scenario)
                if result.error:
                    st.error(result.error)
                else:
                    st.session_state["health_result"] = result
        panel_end()

    with results:
        panel_start()
        st.subheader("Analysis Output")
        if "health_result" in st.session_state:
            r = st.session_state["health_result"]
            if r.error:
                st.error(r.error)
            else:
                # Deviation %
                _dev_pct = None
                try:
                    _common = r.baseline_profile.dropna().index.intersection(r.current_profile.dropna().index)
                    if len(_common) > 0:
                        _b = r.baseline_profile[_common].values.astype(float)
                        _c = r.current_profile[_common].values.astype(float)
                        _rms = np.sqrt(np.mean((_b - _c) ** 2))
                        _dev_pct = (_rms / _b.max() * 100) if _b.max() > 0 else 0.0
                except Exception:
                    pass

                st.markdown(score_badge_html(r.score, deviation_pct=_dev_pct), unsafe_allow_html=True)
                st.altair_chart(profile_overlay_chart(r.baseline_profile, r.current_profile),
                                use_container_width=True)
                st.markdown("#### Diagnostics")
                for d in r.diagnostics:
                    st.markdown(f"- {d}")

                if not r.trace.empty and F_POSITION in r.trace.columns and F_TORQUE in r.trace.columns:
                    st.altair_chart(phase_portrait(r.trace, "Current Stroke Fingerprint"),
                                    use_container_width=True)

                st.divider()
                save_name = st.text_input("Trace name", value=f"trace_score_{r.score:.0f}", key="hs_save")
                if st.button("Save Trace Locally", key="hs_save_btn"):
                    try:
                        path = export_trace(r, save_name)
                        st.success(f"Saved: `{path}`")
                    except Exception as e:
                        st.error(f"Save failed: {e}")
        else:
            st.info("Run a health analysis to see results.")
        panel_end()

    # Fleet section
    panel_start()
    st.subheader("Fleet Intelligence")
    st.caption("Cross-test health benchmarking")

    def _show_fleet(fleet_df):
        st.altair_chart(fleet_bar_chart(fleet_df), use_container_width=True)
        avg = fleet_df["score"].mean()
        std = fleet_df["score"].std()
        threshold = avg - 2 * std if std > 0 else 0
        outliers = fleet_df[fleet_df["score"] < threshold]
        f1, f2 = st.columns(2)
        with f1:
            metric_card("Fleet Average", f"{avg:.0f}", f"± {std:.0f} std")
        with f2:
            worst = fleet_df.loc[fleet_df["score"].idxmin()]
            metric_card("Lowest", f"#{int(worst['test_number'])}", f"Score {worst['score']:.0f}",
                        color=score_color(worst['score']))
        if not outliers.empty:
            for _, row in outliers.iterrows():
                st.error(f"**Outlier**: Test #{int(row['test_number'])} scores {row['score']:.0f} "
                         f"— >2σ below fleet mean. Inspect this device.")

    if is_live:
        if st.button("Compute Fleet Scores", key="fleet_btn"):
            try:
                fleet = compute_fleet_scores()
            except Exception as e:
                st.error(f"Fleet query failed. Check BELIMO-X connection. ({e})")
                fleet = []
            if not fleet:
                st.info("No field test data in last 24h.")
            else:
                _show_fleet(pd.DataFrame(fleet))
    else:
        mock = pd.DataFrame([
            {"test_number": 1, "score": 94}, {"test_number": 2, "score": 87},
            {"test_number": 3, "score": 72}, {"test_number": 4, "score": 91},
            {"test_number": 5, "score": 45}, {"test_number": 6, "score": 88},
            {"test_number": 7, "score": 63}, {"test_number": 8, "score": 95},
        ])
        _show_fleet(mock)
        st.caption("Simulated fleet values (replay mode)")
    panel_end()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — Commissioning Gate
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("Commissioning Gate")
    st.markdown("Grade installation quality on first stroke. Immediate pass/fail verdict.")

    qa_ctrl, qa_result = st.columns([1, 2])

    with qa_ctrl:
        panel_start()
        st.subheader("Run / Evaluate")
        if is_live:
            comm_tn = st.number_input("Test number (200–300)", 200, 300, 200, key="qa_tn")
            if st.button("Run Commissioning Stroke", key="qa_run"):
                try:
                    progress = st.progress(0)
                    result = run_live_commissioning(int(comm_tn), lambda i, t: progress.progress(i / t))
                    if result.error:
                        st.error(result.error)
                    else:
                        st.session_state["comm_result"] = result
                        st.success("Commissioning complete.")
                except Exception as e:
                    st.error(f"Commissioning failed. Check BELIMO-X connection. ({e})")
            if st.button("Evaluate Existing Data", key="qa_eval"):
                try:
                    result = evaluate_commissioning_from_test_number(int(comm_tn))
                    if result.error:
                        st.warning(result.error)
                    else:
                        st.session_state["comm_result"] = result
                except Exception as e:
                    st.error(f"Evaluation failed. Check BELIMO-X connection. ({e})")
        else:
            if st.button("Analyze Replay Commissioning", key="qa_replay"):
                result = run_replay_commissioning()
                if result.error:
                    st.error(result.error)
                else:
                    st.session_state["comm_result"] = result
        panel_end()

    with qa_result:
        panel_start()
        st.subheader("Commissioning Verdict")
        if "comm_result" in st.session_state:
            r = st.session_state["comm_result"]
            if r.error:
                st.error(r.error)
            elif r.commissioning:
                comm = r.commissioning
                st.markdown(commissioning_badge_html(comm["score"], comm["verdict"]),
                            unsafe_allow_html=True)

                # Checks as data table
                rows = []
                for check in comm["checks"].values():
                    rows.append({
                        "Check": check["label"],
                        "Value": f"{check['value']}{check['unit']}",
                        "Threshold": f"{check['threshold']}{check['unit']}",
                        "Status": "PASS" if check["passed"] else "FAIL",
                        "Penalty": check["penalty"],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                st.markdown("#### Recommendations")
                for d in comm["diagnostics"]:
                    st.markdown(f"- {d}")

                if not r.trace.empty and F_POSITION in r.trace.columns and F_TORQUE in r.trace.columns:
                    st.altair_chart(commissioning_area_chart(r.trace, comm["verdict"]),
                                    use_container_width=True)
        else:
            st.info("Run or evaluate a commissioning trace to see the verdict.")
        panel_end()