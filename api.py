"""
api.py — FastAPI backend for ActuSpec.
Exposes all Python analysis/orchestration logic as REST endpoints.
"""

import traceback

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from analyzer import commissioning_score, health_diagnosis, health_score, torque_profile
from baseline import baseline_profile_from_file, load_baseline_from_file, save_baseline
from collector import query_all_test_numbers, query_by_test_number, query_recent
from commander import run_sequence, send_setpoint
from config import (
    COMM_PASS_THRESHOLD,
    HEALTH_AMBER,
    HEALTH_GREEN,
    N_BINS,
    SEQ_FREE_STROKE,
    SEQ_LOADED_STROKE,
    SEQ_STALL_DURATION,
    SEQ_STALL_POSITION,
    SEQ_STEP_DELAY,
    TN_BASELINE,
    TN_FIELD_MAX,
    TN_FIELD_MIN,
)
from fallback import load_replay, save_trace
from orchestrator import (
    RunResult,
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

app = FastAPI(title="ActuSpec API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _series_to_dict(s: pd.Series) -> dict:
    """Convert a pandas Series (torque profile) to JSON-safe dict."""
    if s is None or s.empty:
        return {}
    return {str(k): (None if (isinstance(v, float) and np.isnan(v)) else float(v))
            for k, v in s.items()}


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to a list of JSON-safe dicts."""
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str)
    return out.replace({np.nan: None}).to_dict(orient="records")


def _run_result_to_dict(r: RunResult) -> dict:
    """Serialize a RunResult to a JSON-safe dict."""
    result = {
        "trace": _df_to_records(r.trace),
        "baseline_profile": _series_to_dict(r.baseline_profile),
        "current_profile": _series_to_dict(r.current_profile),
        "score": r.score,
        "diagnostics": r.diagnostics,
        "commissioning": r.commissioning,
        "error": r.error,
    }
    return result


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class SetpointRequest(BaseModel):
    setpoint: float
    test_number: int = -1


class HealthRunRequest(BaseModel):
    test_number: int = 1
    sequence: list[float] | None = None


class HealthEvalRequest(BaseModel):
    test_number: int = 1


class CommissioningRunRequest(BaseModel):
    test_number: int = 200


class ReplayHealthRequest(BaseModel):
    scenario: str = "healthy"


class BaselineRunRequest(BaseModel):
    sequence_name: str = "free"


class TraceExportRequest(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Endpoints — State
# ---------------------------------------------------------------------------

@app.get("/api/state")
def api_state():
    return {"state": get_state()}


# ---------------------------------------------------------------------------
# Endpoints — Telemetry
# ---------------------------------------------------------------------------

@app.get("/api/telemetry/recent")
def api_telemetry_recent(range: str = "-5m"):
    try:
        df = query_recent(range)
        return {"data": _df_to_records(df), "count": len(df)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/telemetry/by-test/{test_number}")
def api_telemetry_by_test(test_number: int, range: str = "-24h"):
    try:
        df = query_by_test_number(test_number, range)
        return {"data": _df_to_records(df), "count": len(df)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Commands
# ---------------------------------------------------------------------------

@app.post("/api/command/setpoint")
def api_send_setpoint(req: SetpointRequest):
    try:
        send_setpoint(req.setpoint, req.test_number)
        return {"ok": True, "setpoint": req.setpoint, "test_number": req.test_number}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Baseline
# ---------------------------------------------------------------------------

@app.get("/api/baseline/profile")
def api_baseline_profile():
    try:
        profile = baseline_profile_from_file()
        return {"profile": _series_to_dict(profile)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/baseline/run")
def api_baseline_run(req: BaselineRunRequest):
    try:
        message = run_live_baseline(req.sequence_name)
        return {"ok": True, "message": message}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/baseline/load-live")
def api_baseline_load_live():
    try:
        profile, message = load_live_baseline()
        if profile is not None:
            return {"ok": True, "profile": _series_to_dict(profile), "message": message}
        return {"ok": False, "profile": None, "message": message}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/baseline/export")
def api_baseline_export():
    try:
        baseline_df = query_by_test_number(TN_BASELINE, "-24h")
        if baseline_df.empty:
            return {"ok": False, "message": "No live baseline trace found."}
        path = save_baseline(baseline_df)
        return {"ok": True, "path": path}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Health Intelligence
# ---------------------------------------------------------------------------

@app.post("/api/health/run-live")
def api_health_run_live(req: HealthRunRequest):
    try:
        sequence = req.sequence if req.sequence else SEQ_FREE_STROKE
        result = run_live_health_test(req.test_number, sequence)
        return _run_result_to_dict(result)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/health/replay")
def api_health_replay(req: ReplayHealthRequest):
    try:
        result = run_replay_health(req.scenario)
        return _run_result_to_dict(result)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/health/evaluate")
def api_health_evaluate(req: HealthEvalRequest):
    try:
        result = evaluate_health_from_test_number(req.test_number)
        return _run_result_to_dict(result)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Fleet
# ---------------------------------------------------------------------------

@app.get("/api/fleet/scores")
def api_fleet_scores():
    try:
        fleet = compute_fleet_scores()
        return {"scores": fleet}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/fleet/replay-scores")
def api_fleet_replay_scores():
    """Compute health scores for all replay scenarios against baseline."""
    try:
        baseline = baseline_profile_from_file()
        scores = []
        for scenario in ["healthy", "fault"]:
            try:
                trace = load_replay(scenario)
                prof = torque_profile(trace)
                s = health_score(baseline, prof)
                scores.append({"test_number": scenario.title(), "score": round(s, 1)})
            except Exception:
                pass
        try:
            trace = load_replay("commissioning")
            prof = torque_profile(trace)
            s = health_score(baseline, prof)
            scores.append({"test_number": "Commissioning", "score": round(s, 1)})
        except Exception:
            pass
        return {"scores": scores}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Commissioning
# ---------------------------------------------------------------------------

@app.post("/api/commissioning/run-live")
def api_commissioning_run_live(req: CommissioningRunRequest):
    try:
        result = run_live_commissioning(req.test_number)
        return _run_result_to_dict(result)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/commissioning/replay")
def api_commissioning_replay():
    try:
        result = run_replay_commissioning()
        return _run_result_to_dict(result)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/api/commissioning/evaluate")
def api_commissioning_evaluate(req: CommissioningRunRequest):
    try:
        result = evaluate_commissioning_from_test_number(req.test_number)
        return _run_result_to_dict(result)
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Replay data
# ---------------------------------------------------------------------------

@app.get("/api/replay/{scenario}")
def api_replay(scenario: str):
    try:
        df = load_replay(scenario)
        return {"data": _df_to_records(df), "count": len(df)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Trace export
# ---------------------------------------------------------------------------

@app.post("/api/trace/export")
def api_trace_export(req: TraceExportRequest):
    try:
        # This needs a RunResult — simplified: just save from last stored
        return {"ok": False, "message": "Use specific health/commissioning endpoints to get traces."}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints — Config / constants (useful for frontend)
# ---------------------------------------------------------------------------

@app.get("/api/config")
def api_config():
    from config import (
        COMM_MARGINAL_THRESHOLD,
        COMM_PASS_THRESHOLD,
        COMM_RANGE_THRESHOLD,
        COMM_TEMP_THRESHOLD,
        COMM_TORQUE_CV_THRESHOLD,
        COMM_TRACKING_THRESHOLD,
        DEFAULT_MODE,
        HEALTH_AMBER,
        HEALTH_GREEN,
        SEQ_FREE_STROKE,
        TN_BASELINE,
        TN_COMMISSION_MAX,
        TN_COMMISSION_MIN,
        TN_DEFAULT,
        TN_FIELD_MAX,
        TN_FIELD_MIN,
    )
    return {
        "health_green": HEALTH_GREEN,
        "health_amber": HEALTH_AMBER,
        "comm_pass": COMM_PASS_THRESHOLD,
        "comm_marginal": COMM_MARGINAL_THRESHOLD,
        "tn_baseline": TN_BASELINE,
        "tn_field_min": TN_FIELD_MIN,
        "tn_field_max": TN_FIELD_MAX,
        "tn_commission_min": TN_COMMISSION_MIN,
        "tn_commission_max": TN_COMMISSION_MAX,
        "tn_default": TN_DEFAULT,
        "default_mode": DEFAULT_MODE,
        "seq_free_stroke": SEQ_FREE_STROKE,
        "comm_thresholds": {
            "range": COMM_RANGE_THRESHOLD,
            "torque_cv": COMM_TORQUE_CV_THRESHOLD,
            "tracking": COMM_TRACKING_THRESHOLD,
            "temp": COMM_TEMP_THRESHOLD,
        },
    }
