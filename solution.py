"""
ActuSpec — Belimo Actuator Intelligence
Streamlit UI entrypoint · START Hack 2026
"""

import time

import pandas as pd
import streamlit as st

from config import (
    F_POSITION, F_SETPOINT, F_TORQUE, F_TEMPERATURE, F_POWER, F_TIME,
    SEQ_FREE_STROKE, SEQ_LOADED_STROKE, SEQ_STEP_DELAY,
    TN_BASELINE, TN_DEFAULT,
    COLOR_GREEN, COLOR_AMBER, COLOR_RED, COLOR_ORANGE, COLOR_PURPLE,
    DEFAULT_MODE,
)
from charts import (
    position_chart, torque_time_chart, phase_portrait,
    baseline_profile_chart, profile_overlay_chart,
    fleet_bar_chart, score_badge_html, commissioning_badge_html,
    score_color,
)
from orchestrator import (
    run_live_baseline, run_live_health_test, run_live_commissioning,
    run_replay_health, run_replay_commissioning,
    compute_fleet_scores,
    evaluate_health_from_test_number,
    evaluate_commissioning_from_test_number,
    load_live_baseline,
    export_trace,
    get_state,
)
from collector import query_recent
from commander import send_setpoint
from baseline import baseline_profile_from_file, save_baseline


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="ActuSpec", page_icon="🫀", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Belimo_logo.svg/1200px-Belimo_logo.svg.png", width=160)
    st.title("ActuSpec")
    st.caption("*We gave actuators an ECG.*")
    st.divider()
    mode = st.radio("Mode", ["🟢 Live", "🔁 Replay"], index=0 if DEFAULT_MODE == "live" else 1)
    is_live = mode.startswith("🟢")
    st.divider()
    st.markdown(
        "**Live** — reads real actuator telemetry\n\n"
        "**Replay** — uses prerecorded traces for reliable demo"
    )


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📡 Live Monitor",
    "🔬 Healthy Baseline",
    "❤️ Health Score",
    "🏗️ Commissioning QA",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Live Monitor
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("📡 Live Monitor")

    if not is_live:
        st.info("Switch to **Live** mode in the sidebar to see real-time telemetry.")
        # Show replay data as a preview
        from fallback import load_replay
        demo_df = load_replay("healthy")
        st.subheader("Preview: Healthy Replay Trace")
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(phase_portrait(demo_df, "Phase Portrait (Replay)"), use_container_width=True)
        with c2:
            if F_TORQUE in demo_df.columns and F_TIME in demo_df.columns:
                st.altair_chart(torque_time_chart(demo_df), use_container_width=True)
    else:
        # Run state indicator
        state = get_state()
        state_labels = {
            "idle": ("⚪", "Idle"),
            "commanding": ("🟡", "Commanding actuator..."),
            "collecting": ("🟡", "Collecting telemetry..."),
            "analyzing": ("🟡", "Analyzing trace..."),
            "done": ("🟢", "Last run complete"),
            "error": ("🔴", "Last run had an error"),
        }
        icon, label = state_labels.get(state, ("⚪", state))
        st.caption(f"{icon} **Run state:** {label}")

        col_ctrl, col_status = st.columns([1, 3])

        with col_ctrl:
            st.subheader("Manual Control")
            setpoint = st.slider("Setpoint (%)", 0, 100, 50, key="live_setpoint")
            if st.button("Send Command", key="live_send"):
                send_setpoint(setpoint, TN_DEFAULT)
                st.success(f"Sent setpoint={setpoint}%")
            auto_refresh = st.checkbox("Auto-refresh (2s)", value=False)

        with col_status:
            refresh = st.button("🔄 Refresh", key="live_refresh")

            if refresh or auto_refresh:
                df = query_recent("-5m")
                if df.empty:
                    st.info("No data in the last 5 minutes. Is the actuator connected?")
                else:
                    latest = df.iloc[-1]
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Position", f"{latest.get(F_POSITION, 0):.1f}%")
                    m2.metric("Torque", f"{latest.get(F_TORQUE, 0):.0f} N·mm")
                    m3.metric("Power", f"{latest.get(F_POWER, 0):.1f} W")
                    m4.metric("Temperature", f"{latest.get(F_TEMPERATURE, 0):.1f}°C")

                    c1, c2 = st.columns(2)
                    with c1:
                        if F_POSITION in df.columns and F_TIME in df.columns:
                            st.altair_chart(position_chart(df), use_container_width=True)
                    with c2:
                        if F_TORQUE in df.columns and F_TIME in df.columns:
                            st.altair_chart(torque_time_chart(df), use_container_width=True)

                    if F_POSITION in df.columns and F_TORQUE in df.columns:
                        st.subheader("Phase Portrait — Mechanical Fingerprint")
                        st.altair_chart(phase_portrait(df), use_container_width=True)

                if auto_refresh:
                    time.sleep(2)
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Healthy Baseline
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("🔬 Healthy Baseline")
    st.markdown(
        "The baseline is a **certified healthy reference** — like an ECG from a healthy heart. "
        "Every future stroke is compared against this ground truth."
    )

    base_ctrl, base_view = st.columns([1, 2])

    with base_ctrl:
        if is_live:
            st.subheader("Run Baseline Tests")
            st.caption("All tests use `test_number=999`")

            st.markdown("**Test 1 — Free Stroke**")
            st.caption("Sequence: 0→25→50→75→100→75→50→25→0")
            if st.button("▶ Run Free Stroke", key="bl_free"):
                progress = st.progress(0)
                msg = run_live_baseline("free", lambda i, t: progress.progress(i / t))
                st.success(msg)

            st.divider()
            st.markdown("**Test 2 — Loaded Stroke**")
            st.caption("Sequence: 0→50→100→50→0 (apply manual resistance)")
            if st.button("▶ Run Loaded Stroke", key="bl_loaded"):
                progress = st.progress(0)
                msg = run_live_baseline("loaded", lambda i, t: progress.progress(i / t))
                st.success(msg)

            st.divider()
            st.markdown("**Test 3 — Stall Test**")
            st.caption("Hold at 45% for 10 seconds")
            if st.button("▶ Run Stall Test", key="bl_stall"):
                progress = st.progress(0)
                msg = run_live_baseline("stall", lambda i, t: progress.progress(i / t))
                st.success(msg)

            st.divider()
            if st.button("🔄 Load Live Baseline", key="bl_load_live"):
                profile, message = load_live_baseline()
                if profile is not None:
                    st.session_state["baseline_profile"] = profile
                    st.session_state["baseline_source"] = "live"
                    st.success(message)
                else:
                    st.warning(message)
        else:
            st.subheader("Baseline Source")
            st.info("Using **prerecorded** healthy baseline.")
            if st.button("📂 Load Replay Baseline", key="bl_load_replay"):
                profile = baseline_profile_from_file()
                st.session_state["baseline_profile"] = profile
                st.session_state["baseline_source"] = "replay"
                st.success("Loaded prerecorded baseline.")

    with base_view:
        st.subheader("Baseline Torque Profile")
        # Auto-load on first visit
        if "baseline_profile" not in st.session_state:
            try:
                profile = baseline_profile_from_file()
                st.session_state["baseline_profile"] = profile
                st.session_state["baseline_source"] = "replay"
            except Exception:
                pass

        if "baseline_profile" in st.session_state:
            profile = st.session_state["baseline_profile"]
            source = st.session_state.get("baseline_source", "unknown")
            st.caption(f"Source: **{source}**")
            st.altair_chart(baseline_profile_chart(profile), use_container_width=True)
            st.success("✅ Baseline ready. Proceed to Health Score or Commissioning.")

            if is_live:
                st.divider()
                st.caption("Save this baseline locally so it survives Pi reboots.")
                if st.button("💾 Export Baseline to Local", key="bl_export"):
                    try:
                        from baseline import load_baseline_from_file
                        # Re-query the live baseline trace for saving
                        from collector import query_by_test_number
                        df_base = query_by_test_number(TN_BASELINE, "-24h")
                        if df_base.empty:
                            st.warning("No live baseline data to export.")
                        else:
                            path = save_baseline(df_base)
                            st.success(f"Baseline exported to `{path}`")
                    except Exception as e:
                        st.error(f"Export failed: {e}")
        else:
            st.warning("No baseline loaded. Click a load button on the left.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — Health Score & Fleet Intelligence
# ═════════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("❤️ Health Score & Fleet Intelligence")

    score_col, fleet_col = st.columns([1, 1])

    with score_col:
        st.subheader("Single Stroke Analysis")

        if is_live:
            tn = st.number_input("Test number (1–100)", 1, 100, 1, key="hs_tn")
            h1, h2 = st.columns(2)
            with h1:
                h_sp = st.slider("Setpoint (%)", 0, 100, 50, key="hs_sp")
                if st.button("Send Stroke", key="hs_send"):
                    send_setpoint(h_sp, tn)
                    st.success(f"Sent setpoint={h_sp}%")
            with h2:
                if st.button("Run Full Stroke (0→100→0)", key="hs_full"):
                    progress = st.progress(0)
                    result = run_live_health_test(
                        int(tn), SEQ_FREE_STROKE,
                        lambda i, t: progress.progress(i / t)
                    )
                    if result.error:
                        st.error(result.error)
                    else:
                        st.session_state["health_result"] = result

            if st.button("📊 Compute Score (existing data)", key="hs_compute"):
                bp = st.session_state.get("baseline_profile")
                if bp is None:
                    st.error("No baseline! Go to Healthy Baseline tab first.")
                else:
                    result = evaluate_health_from_test_number(int(tn), baseline_profile=bp)
                    if result.error:
                        st.warning(result.error)
                    else:
                        st.session_state["health_result"] = result
        else:
            st.markdown("**Select replay scenario:**")
            scenario = st.selectbox("Scenario", ["healthy", "fault"], key="hs_scenario")
            if st.button("📊 Analyze Replay Trace", key="hs_replay"):
                result = run_replay_health(scenario)
                if result.error:
                    st.error(result.error)
                else:
                    st.session_state["health_result"] = result

        # Display result
        if "health_result" in st.session_state:
            r = st.session_state["health_result"]
            if r.error:
                st.error(r.error)
            else:
                st.markdown(score_badge_html(r.score), unsafe_allow_html=True)
                st.altair_chart(
                    profile_overlay_chart(r.baseline_profile, r.current_profile),
                    use_container_width=True,
                )
                st.subheader("Diagnosis")
                for d in r.diagnostics:
                    st.markdown(f"- {d}")

                if not r.trace.empty and F_POSITION in r.trace.columns and F_TORQUE in r.trace.columns:
                    st.altair_chart(
                        phase_portrait(r.trace, "Phase Portrait — This Stroke"),
                        use_container_width=True,
                    )

                # Persist trace locally
                if not r.trace.empty:
                    st.divider()
                    save_name = st.text_input(
                        "Trace name", value=f"trace_score_{r.score:.0f}",
                        key="hs_save_name",
                    )
                    if st.button("💾 Save Trace Locally", key="hs_save_trace"):
                        try:
                            path = export_trace(r, save_name)
                            st.success(f"Trace saved to `{path}`")
                        except Exception as e:
                            st.error(f"Save failed: {e}")

    with fleet_col:
        st.subheader("Fleet Intelligence")
        st.caption("Cross-device health comparison (last 24h)")

        if is_live:
            if st.button("📊 Compute Fleet Scores", key="fleet_btn"):
                fleet = compute_fleet_scores()
                if not fleet:
                    st.info("No field test data found.")
                else:
                    fleet_df = pd.DataFrame(fleet)
                    st.altair_chart(fleet_bar_chart(fleet_df), use_container_width=True)
                    avg = fleet_df["score"].mean()
                    worst = fleet_df.loc[fleet_df["score"].idxmin()]
                    st.metric("Fleet Average", f"{avg:.0f}")
                    st.warning(f"Lowest: Test #{int(worst['test_number'])} at {worst['score']:.0f}")
        else:
            st.info(
                "Fleet intelligence requires **Live** mode with multiple test runs. "
                "In a production deployment, this tab would show health scores across "
                "all actuators in a building — revealing system-level patterns like "
                "undersized valves or systematic overload at peak hours."
            )
            # Show a mock fleet for demo purposes
            mock_fleet = pd.DataFrame([
                {"test_number": 1, "score": 94},
                {"test_number": 2, "score": 87},
                {"test_number": 3, "score": 72},
                {"test_number": 4, "score": 91},
                {"test_number": 5, "score": 45},
                {"test_number": 6, "score": 88},
                {"test_number": 7, "score": 63},
                {"test_number": 8, "score": 95},
            ])
            st.altair_chart(fleet_bar_chart(mock_fleet), use_container_width=True)
            st.caption("⬆ Simulated fleet data for demonstration")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — Commissioning QA Badge
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    st.header("🏗️ Commissioning QA Badge")
    st.markdown(
        "On the **first stroke after installation**, ActuSpec automatically evaluates "
        "installation quality. No manual configuration, no engineer needed."
    )

    qa_ctrl, qa_result = st.columns([1, 2])

    with qa_ctrl:
        st.subheader("Run Test")

        if is_live:
            comm_tn = st.number_input("Test number (200–300)", 200, 300, 200, key="qa_tn")
            if st.button("▶ Run Commissioning Stroke", key="qa_run"):
                progress = st.progress(0)
                result = run_live_commissioning(
                    int(comm_tn),
                    lambda i, t: progress.progress(i / t),
                )
                if result.error:
                    st.error(result.error)
                else:
                    st.session_state["comm_result"] = result
                    st.success("Commissioning stroke complete!")

            if st.button("📋 Evaluate Existing Data", key="qa_eval"):
                result = evaluate_commissioning_from_test_number(int(comm_tn))
                if result.error:
                    st.warning(result.error)
                else:
                    st.session_state["comm_result"] = result
        else:
            st.info("Using **prerecorded** commissioning trace.")
            if st.button("📊 Analyze Replay Commissioning", key="qa_replay"):
                result = run_replay_commissioning()
                if result.error:
                    st.error(result.error)
                else:
                    st.session_state["comm_result"] = result

    with qa_result:
        st.subheader("QA Result")

        if "comm_result" in st.session_state:
            r = st.session_state["comm_result"]
            if r.error:
                st.error(r.error)
            elif r.commissioning:
                comm = r.commissioning
                st.markdown(
                    commissioning_badge_html(comm["score"], comm["verdict"]),
                    unsafe_allow_html=True,
                )

                st.subheader("Diagnostic Breakdown")
                for name, info in comm["checks"].items():
                    status = "✅" if info["passed"] else "❌"
                    penalty_text = f" (−{info['penalty']} pts)" if info["penalty"] > 0 else ""
                    st.markdown(
                        f"{status} **{info['label']}**: {info['value']}{info['unit']} "
                        f"(threshold: {info['threshold']}{info['unit']}){penalty_text}"
                    )

                st.subheader("Recommendations")
                for d in comm["diagnostics"]:
                    st.markdown(f"- {d}")

                if not r.trace.empty and F_POSITION in r.trace.columns and F_TORQUE in r.trace.columns:
                    st.subheader("Commissioning Phase Portrait")
                    st.altair_chart(
                        phase_portrait(r.trace, "Installation Stroke Fingerprint"),
                        use_container_width=True,
                    )
        else:
            st.info("Run a commissioning stroke or load a replay to see results.")
