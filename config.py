"""
config.py — Central constants, credentials, thresholds, field names.
"""

# ── InfluxDB ─────────────────────────────────────────────────────────────────
INFLUX_URL = "http://192.168.3.14:8086"
INFLUX_TOKEN = "pf-OGC6AQFmKy64gOzRM12DZrCuavnWeMgRZ2kDMOk8LYK22evDJnoyKGcmY49EgT8HnMDE9GPQeg30vXeHsRQ=="
INFLUX_ORG = "belimo"
INFLUX_BUCKET = "actuator-data"
INFLUX_MEASUREMENT = "measurements"
INFLUX_PROCESS = "_process"

# ── Field names (must match InfluxDB schema) ─────────────────────────────────
F_POSITION = "feedback_position_%"
F_SETPOINT = "setpoint_position_%"
F_TORQUE = "motor_torque_Nmm"
F_TEMPERATURE = "internal_temperature_deg_C"
F_POWER = "power_W"
F_DIRECTION = "rotation_direction"
F_TEST_NUMBER = "test_number"
F_TIME = "_time"

# Fields required for analysis (collector validates these)
REQUIRED_FIELDS = [F_POSITION, F_TORQUE, F_TEMPERATURE, F_SETPOINT]

# ── Test number ranges ───────────────────────────────────────────────────────
TN_BASELINE = 999
TN_FIELD_MIN = 1
TN_FIELD_MAX = 100
TN_COMMISSION_MIN = 200
TN_COMMISSION_MAX = 300
TN_DEFAULT = -1

# ── Analysis parameters ──────────────────────────────────────────────────────
N_BINS = 20  # torque profile bins

# ── Commissioning thresholds ─────────────────────────────────────────────────
COMM_RANGE_THRESHOLD = 60       # minimum range of motion (%)
COMM_RANGE_PENALTY = 30
COMM_TORQUE_CV_THRESHOLD = 1.5  # coefficient of variation
COMM_TORQUE_CV_PENALTY = 25
COMM_TRACKING_THRESHOLD = 10    # mean tracking error (%)
COMM_TRACKING_PENALTY = 20
COMM_TEMP_THRESHOLD = 5         # temperature rise (°C)
COMM_TEMP_PENALTY = 15
COMM_PASS_THRESHOLD = 70
COMM_MARGINAL_THRESHOLD = 50

# ── Health score thresholds ──────────────────────────────────────────────────
HEALTH_GREEN = 80
HEALTH_AMBER = 50

# ── Colours ──────────────────────────────────────────────────────────────────
COLOR_GREEN = "#1D9E75"
COLOR_AMBER = "#EF9F27"
COLOR_RED = "#E24B4A"
COLOR_ORANGE = "#D85A30"   # baseline reference
COLOR_PURPLE = "#7F77DD"   # current / field data

# ── Command sequences ───────────────────────────────────────────────────────
SEQ_FREE_STROKE = [0, 25, 50, 75, 100, 75, 50, 25, 0]
SEQ_LOADED_STROKE = [0, 50, 100, 50, 0]
SEQ_STALL_POSITION = 45
SEQ_STALL_DURATION = 10  # seconds
SEQ_STEP_DELAY = 3       # seconds between steps

# ── Replay data paths ───────────────────────────────────────────────────────
DATA_DIR = "data"
BASELINE_FILE = "baseline_healthy.json"
REPLAY_HEALTHY_FILE = "replay_healthy.json"
REPLAY_FAULT_FILE = "replay_fault.json"
REPLAY_COMMISSIONING_FILE = "replay_commissioning.json"

# ── Default mode ─────────────────────────────────────────────────────────────
DEFAULT_MODE = "replay"  # "live" or "replay"
