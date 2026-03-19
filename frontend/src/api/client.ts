// ActuSpec API client — all backend calls go through here

import type { TelemetryRow, RunResult, FleetScore, TorqueProfile, AppConfig } from '../types';

const BASE = '/api';

async function fetchJSON<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, opts);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

function post<T>(url: string, body?: object): Promise<T> {
  return fetchJSON<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
}

// --- State ---
export async function getState(): Promise<string> {
  const r = await fetchJSON<{ state: string }>(`${BASE}/state`);
  return r.state;
}

// --- Telemetry ---
export async function getRecentTelemetry(range = '-5m'): Promise<TelemetryRow[]> {
  const r = await fetchJSON<{ data: TelemetryRow[]; count: number }>(
    `${BASE}/telemetry/recent?range=${encodeURIComponent(range)}`
  );
  return r.data;
}

export async function getTelemetryByTest(testNumber: number, range = '-24h'): Promise<TelemetryRow[]> {
  const r = await fetchJSON<{ data: TelemetryRow[]; count: number }>(
    `${BASE}/telemetry/by-test/${testNumber}?range=${encodeURIComponent(range)}`
  );
  return r.data;
}

// --- Commands ---
export async function sendSetpoint(setpoint: number, testNumber = -1): Promise<void> {
  await post(`${BASE}/command/setpoint`, { setpoint, test_number: testNumber });
}

// --- Baseline ---
export async function getBaselineProfile(): Promise<TorqueProfile> {
  const r = await fetchJSON<{ profile: TorqueProfile }>(`${BASE}/baseline/profile`);
  return r.profile;
}

export async function runBaseline(sequenceName = 'free'): Promise<string> {
  const r = await post<{ ok: boolean; message: string }>(`${BASE}/baseline/run`, { sequence_name: sequenceName });
  return r.message;
}

export async function loadLiveBaseline(): Promise<{ ok: boolean; profile: TorqueProfile | null; message: string }> {
  return post(`${BASE}/baseline/load-live`);
}

export async function exportBaseline(): Promise<{ ok: boolean; message?: string; path?: string }> {
  return post(`${BASE}/baseline/export`);
}

// --- Health ---
export async function runLiveHealth(testNumber: number, sequence?: number[]): Promise<RunResult> {
  return post(`${BASE}/health/run-live`, { test_number: testNumber, sequence });
}

export async function runReplayHealth(scenario = 'healthy'): Promise<RunResult> {
  return post(`${BASE}/health/replay`, { scenario });
}

export async function evaluateHealth(testNumber: number): Promise<RunResult> {
  return post(`${BASE}/health/evaluate`, { test_number: testNumber });
}

// --- Fleet ---
export async function getFleetScores(): Promise<FleetScore[]> {
  const r = await fetchJSON<{ scores: FleetScore[] }>(`${BASE}/fleet/scores`);
  return r.scores;
}

export async function getReplayFleetScores(): Promise<FleetScore[]> {
  const r = await fetchJSON<{ scores: FleetScore[] }>(`${BASE}/fleet/replay-scores`);
  return r.scores;
}

// --- Commissioning ---
export async function runLiveCommissioning(testNumber: number): Promise<RunResult> {
  return post(`${BASE}/commissioning/run-live`, { test_number: testNumber });
}

export async function runReplayCommissioning(): Promise<RunResult> {
  return post(`${BASE}/commissioning/replay`);
}

export async function evaluateCommissioning(testNumber: number): Promise<RunResult> {
  return post(`${BASE}/commissioning/evaluate`, { test_number: testNumber });
}

// --- Replay ---
export async function getReplayTrace(scenario: string): Promise<TelemetryRow[]> {
  const r = await fetchJSON<{ data: TelemetryRow[]; count: number }>(`${BASE}/replay/${scenario}`);
  return r.data;
}

// --- Config ---
export async function getConfig(): Promise<AppConfig> {
  return fetchJSON(`${BASE}/config`);
}
