"""
Generate synthetic replay traces for demo fallback mode.
Run once: python generate_replay_data.py
"""

import json
import numpy as np

np.random.seed(42)


def generate_trace(n_points=200, torque_base=80, torque_noise=5,
                   tracking_error=1.5, temp_start=28.0, temp_rise=1.5,
                   spike_position=None, spike_magnitude=0,
                   torque_offset=0, restricted_range=False):
    """Generate a synthetic actuator stroke trace."""
    # Position sweeps 0→100→0
    if restricted_range:
        up = np.linspace(10, 55, n_points // 2)
        down = np.linspace(55, 10, n_points // 2)
    else:
        up = np.linspace(0, 100, n_points // 2)
        down = np.linspace(100, 0, n_points // 2)
    position = np.concatenate([up, down])

    # Setpoint leads position slightly
    setpoint = position + np.random.normal(0, tracking_error, len(position))
    setpoint = np.clip(setpoint, 0, 100)

    # Torque: base level with position-dependent variation + noise
    torque = (torque_base + torque_offset) + 15 * np.sin(position * np.pi / 100) + \
             np.random.normal(0, torque_noise, len(position))

    # Add localised spike if specified
    if spike_position is not None:
        spike_mask = np.abs(position - spike_position) < 8
        torque[spike_mask] += spike_magnitude

    # Direction
    direction = np.concatenate([
        np.ones(n_points // 2),   # opening
        np.full(n_points // 2, 2)  # closing
    ])

    # Temperature: gradual rise
    temp = temp_start + np.linspace(0, temp_rise, len(position)) + \
           np.random.normal(0, 0.1, len(position))

    # Power: proportional to torque
    power = torque * 0.015 + np.random.normal(0, 0.05, len(position))

    # Timestamps (relative, ~0.1s apart)
    timestamps = [f"2026-03-19T10:00:{i * 0.15:06.3f}Z" for i in range(len(position))]

    records = []
    for i in range(len(position)):
        records.append({
            "_time": timestamps[i],
            "feedback_position_%": round(float(position[i]), 2),
            "setpoint_position_%": round(float(setpoint[i]), 2),
            "motor_torque_Nmm": round(float(torque[i]), 1),
            "internal_temperature_deg_C": round(float(temp[i]), 2),
            "power_W": round(float(power[i]), 3),
            "rotation_direction": int(direction[i]),
        })
    return records


# ── Baseline: healthy actuator ───────────────────────────────────────────────
baseline = generate_trace(
    n_points=300,
    torque_base=80,
    torque_noise=3,
    tracking_error=1.0,
    temp_start=27.5,
    temp_rise=1.0,
)

# ── Replay healthy: very similar to baseline ─────────────────────────────────
replay_healthy = generate_trace(
    n_points=250,
    torque_base=82,
    torque_noise=4,
    tracking_error=1.2,
    temp_start=28.0,
    temp_rise=1.2,
)

# ── Replay fault: obstruction at ~60%, elevated torque ───────────────────────
replay_fault = generate_trace(
    n_points=250,
    torque_base=80,
    torque_noise=6,
    tracking_error=3.0,
    temp_start=29.0,
    temp_rise=3.5,
    spike_position=60,
    spike_magnitude=45,
    torque_offset=12,
)

# ── Replay commissioning: decent install but limited range ───────────────────
replay_commissioning = generate_trace(
    n_points=200,
    torque_base=75,
    torque_noise=4,
    tracking_error=2.0,
    temp_start=26.0,
    temp_rise=1.8,
)

# ── Write files ──────────────────────────────────────────────────────────────
for name, data in [
    ("data/baseline_healthy.json", baseline),
    ("data/replay_healthy.json", replay_healthy),
    ("data/replay_fault.json", replay_fault),
    ("data/replay_commissioning.json", replay_commissioning),
]:
    with open(name, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Written {name} ({len(data)} points)")

print("Done.")
