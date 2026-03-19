"""
orchestrator.py — Central run coordinator.
Manages run state, coordinates commander → collector → analyzer pipeline.
Works for both Live and Replay modes. Prevents simultaneous runs.
"""

import time
from dataclasses import dataclass, field

import pandas as pd

from analyzer import torque_profile, health_score, health_diagnosis, commissioning_score
from baseline import baseline_profile_from_file, baseline_profile_from_df
from collector import query_by_test_number, query_all_test_numbers
from commander import run_sequence, send_setpoint
from fallback import load_replay, save_trace
from config import (
    SEQ_FREE_STROKE, SEQ_LOADED_STROKE, SEQ_STALL_POSITION, SEQ_STALL_DURATION,
    SEQ_STEP_DELAY, TN_BASELINE, TN_DEFAULT,
)


# ── Run states ───────────────────────────────────────────────────────────────
IDLE = "idle"
COMMANDING = "commanding"
COLLECTING = "collecting"
ANALYZING = "analyzing"
DONE = "done"
ERROR = "error"

_current_state = IDLE


def get_state() -> str:
    """Return current orchestrator run state."""
    return _current_state


def _set_state(state: str):
    global _current_state
    _current_state = state


def _guard():
    """Raise if a run is already in progress."""
    if _current_state not in (IDLE, DONE, ERROR):
        raise RuntimeError(
            f"A run is already in progress (state: {_current_state}). "
            "Wait for it to finish before starting another."
        )


@dataclass
class RunResult:
    """Result payload from a completed run."""
    trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    baseline_profile: pd.Series = field(default_factory=pd.Series)
    current_profile: pd.Series = field(default_factory=pd.Series)
    score: float = 0.0
    diagnostics: list[str] = field(default_factory=list)
    commissioning: dict | None = None
    error: str | None = None


# ── Live mode orchestration ──────────────────────────────────────────────────

def run_live_baseline(sequence_name: str = "free", progress_callback=None) -> str:
    """Run a baseline test sequence on the actuator. Returns status message."""
    _guard()
    _set_state(COMMANDING)
    try:
        if sequence_name == "free":
            seq = SEQ_FREE_STROKE
        elif sequence_name == "loaded":
            seq = SEQ_LOADED_STROKE
        elif sequence_name == "stall":
            send_setpoint(SEQ_STALL_POSITION, TN_BASELINE)
            for i in range(SEQ_STALL_DURATION):
                time.sleep(1)
                if progress_callback:
                    progress_callback(i + 1, SEQ_STALL_DURATION)
            _set_state(DONE)
            return "Stall test complete."
        else:
            _set_state(ERROR)
            return f"Unknown sequence: {sequence_name}"

        run_sequence(seq, TN_BASELINE, delay=SEQ_STEP_DELAY, progress_callback=progress_callback)
        _set_state(DONE)
        return f"{sequence_name.title()} stroke complete."
    except Exception as e:
        _set_state(ERROR)
        raise


def run_live_health_test(test_number: int, sequence: list[float] = None,
                         progress_callback=None) -> RunResult:
    """Run a live health test: command → collect → analyze."""
    _guard()
    result = RunResult()
    try:
        # Command
        if sequence:
            _set_state(COMMANDING)
            run_sequence(sequence, test_number, delay=SEQ_STEP_DELAY,
                         progress_callback=progress_callback)
            time.sleep(2)  # wait for last samples

        # Collect
        _set_state(COLLECTING)
        result.trace = query_by_test_number(test_number)
        if result.trace.empty:
            result.error = f"No data found for test_number={test_number}"
            _set_state(ERROR)
            return result

        # Analyze
        _set_state(ANALYZING)
        result.baseline_profile = baseline_profile_from_file()
        result.current_profile = torque_profile(result.trace)
        result.score = health_score(result.baseline_profile, result.current_profile)
        result.diagnostics = health_diagnosis(
            result.baseline_profile, result.current_profile, result.score,
            df=result.trace
        )
        _set_state(DONE)
    except Exception as e:
        result.error = str(e)
        _set_state(ERROR)
    return result


def run_live_commissioning(test_number: int, progress_callback=None) -> RunResult:
    """Run a live commissioning test."""
    _guard()
    result = RunResult()
    try:
        _set_state(COMMANDING)
        run_sequence(SEQ_FREE_STROKE, test_number, delay=SEQ_STEP_DELAY,
                     progress_callback=progress_callback)
        time.sleep(2)

        _set_state(COLLECTING)
        result.trace = query_by_test_number(test_number)
        if result.trace.empty:
            result.error = f"No data for test_number={test_number}"
            _set_state(ERROR)
            return result

        _set_state(ANALYZING)
        result.commissioning = commissioning_score(result.trace)
        _set_state(DONE)
    except Exception as e:
        result.error = str(e)
        _set_state(ERROR)
    return result


# ── Replay mode orchestration ────────────────────────────────────────────────

def run_replay_health(scenario: str = "healthy") -> RunResult:
    """Run health analysis on a prerecorded trace."""
    result = RunResult()
    try:
        _set_state(ANALYZING)
        result.trace = load_replay(scenario)
        result.baseline_profile = baseline_profile_from_file()
        result.current_profile = torque_profile(result.trace)
        result.score = health_score(result.baseline_profile, result.current_profile)
        result.diagnostics = health_diagnosis(
            result.baseline_profile, result.current_profile, result.score,
            df=result.trace
        )
        _set_state(DONE)
    except Exception as e:
        result.error = str(e)
        _set_state(ERROR)
    return result


def run_replay_commissioning() -> RunResult:
    """Run commissioning analysis on prerecorded trace."""
    result = RunResult()
    try:
        _set_state(ANALYZING)
        result.trace = load_replay("commissioning")
        result.commissioning = commissioning_score(result.trace)
        _set_state(DONE)
    except Exception as e:
        result.error = str(e)
        _set_state(ERROR)
    return result


# ── Evaluate existing data (no commands) ─────────────────────────────────────

def evaluate_health_from_test_number(test_number: int,
                                     baseline_profile: pd.Series = None) -> RunResult:
    """Score existing test data against baseline, without running commands."""
    result = RunResult()
    try:
        _set_state(COLLECTING)
        result.trace = query_by_test_number(test_number)
        if result.trace.empty:
            result.error = f"No data found for test_number={test_number}"
            _set_state(ERROR)
            return result

        _set_state(ANALYZING)
        result.baseline_profile = baseline_profile if baseline_profile is not None \
            else baseline_profile_from_file()
        result.current_profile = torque_profile(result.trace)
        result.score = health_score(result.baseline_profile, result.current_profile)
        result.diagnostics = health_diagnosis(
            result.baseline_profile, result.current_profile, result.score,
            df=result.trace
        )
        _set_state(DONE)
    except Exception as e:
        result.error = str(e)
        _set_state(ERROR)
    return result


def evaluate_commissioning_from_test_number(test_number: int) -> RunResult:
    """Score existing commissioning data without running commands."""
    result = RunResult()
    try:
        _set_state(COLLECTING)
        result.trace = query_by_test_number(test_number)
        if result.trace.empty:
            result.error = f"No data for test_number={test_number}"
            _set_state(ERROR)
            return result

        _set_state(ANALYZING)
        result.commissioning = commissioning_score(result.trace)
        _set_state(DONE)
    except Exception as e:
        result.error = str(e)
        _set_state(ERROR)
    return result


def load_live_baseline(test_number: int = TN_BASELINE,
                       range_str: str = "-24h") -> tuple:
    """Load baseline from live InfluxDB data. Returns (profile, message)."""
    try:
        _set_state(COLLECTING)
        df = query_by_test_number(test_number, range_str)
        if df.empty:
            _set_state(IDLE)
            return None, f"No baseline data (test_number={test_number}). Run the tests first."
        profile = baseline_profile_from_df(df)
        _set_state(DONE)
        return profile, f"Loaded {len(df)} live baseline samples."
    except Exception as e:
        _set_state(ERROR)
        return None, f"Error loading live baseline: {e}"


# ── Trace persistence ────────────────────────────────────────────────────────

def export_trace(result: RunResult, name: str) -> str:
    """Save a RunResult's trace to local data/ folder. Returns file path."""
    if result.trace.empty:
        raise ValueError("No trace data to export.")
    return save_trace(result.trace, name)


# ── Fleet analysis ───────────────────────────────────────────────────────────

def compute_fleet_scores() -> list[dict]:
    """Compute health scores for all test numbers in last 24h."""
    baseline = baseline_profile_from_file()
    df_all = query_all_test_numbers("-24h")
    if df_all.empty or "test_number" not in df_all.columns:
        return []

    test_nums = df_all["test_number"].dropna().unique()
    test_nums = sorted([int(t) for t in test_nums if int(t) not in (TN_DEFAULT, TN_BASELINE)])

    scores = []
    for t in test_nums:
        t_df = df_all[df_all["test_number"] == t]
        if len(t_df) > 5:
            prof = torque_profile(t_df)
            s = health_score(baseline, prof)
            scores.append({"test_number": t, "score": s})
    return scores
