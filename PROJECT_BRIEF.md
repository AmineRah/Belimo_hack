# Belimo Actuator Intelligence — Full Project Brief
## START Hack 2026 · Complete context for Claude Code

---

## What we are building

A full-stack web application that extracts actionable intelligence from Belimo
actuator signals (torque, motor position, temperature, power) streamed live via
InfluxDB on a Raspberry Pi. The system has three layers of intelligence and a
live dashboard to demo them.

**Tagline**: *"We gave actuators an ECG."*

---

## The problem

Belimo actuators generate continuous internal signals on every stroke:
- `motor_torque_Nmm` — torque in Newton-millimeters
- `feedback_position_%` — measured shaft position (0=closed, 100=open)
- `internal_temperature_deg_C` — PCB temperature
- `power_W` — electrical power consumption
- `setpoint_position_%` — commanded target position
- `rotation_direction` — 0=still, 1=opening, 2=closing

Today, 100% of this data is discarded. No insight, no diagnostics, no value.

---

## The core insight

An actuator's torque curve during a stroke is a **mechanical fingerprint**.
Like an ECG for a heart, a healthy actuator produces a predictable, stable
torque-vs-position signature. Degradation, obstruction, misalignment, and
installation errors all deform that signature in characteristic, detectable ways.

---

## The medical device analogy (central narrative — use this in the UI)

A cardiologist doesn't define a healthy heartbeat by averaging a patient's own
history — they compare against a certified, controlled baseline from healthy
subjects. We do the same for actuators:

1. Run controlled lab tests on a known-healthy actuator first
2. Certify that as the ground truth baseline
3. Score every future stroke against it

This eliminates the fundamental flaw of unsupervised anomaly detection:
learning a degraded state as "normal."

---

## The three-layer architecture

### Layer 1 — Mechanical Health Score

**What it does**: Computes a per-device health score (0–100) by comparing
the current torque-vs-position profile against the lab-certified healthy baseline.

**Algorithm**:
1. Bin the position range (0–100%) into N=20 equal buckets
2. For each bin, compute mean absolute torque → produces a 20-point "torque profile"
3. Compare current profile to baseline using RMS deviation
4. `health_score = max(0, 100 × (1 − RMS_deviation / baseline_max_torque))`

**Color coding**:
- Score ≥ 80 → GREEN `#1D9E75` → label "HEALTHY"
- Score 50–79 → AMBER `#EF9F27` → label "DEGRADED"
- Score < 50 → RED `#E24B4A` → label "CRITICAL"

**Failure modes detectable from signal patterns**:
| Signal pattern | Inferred condition |
|---|---|
| Torque increasing uniformly over time | Valve stem buildup / limescale |
| Torque spike at specific position angle | Mechanical obstruction at that angle |
| Position doesn't track setpoint (lag) | Actuator slippage / gear wear |
| Temperature rising with constant load | Motor inefficiency / bearing friction |
| High torque variance across strokes | Loose coupling / installation defect |

**Technical note**: This is purely statistical — no labeled fault data required.
The approach is robust to production variance because each device is compared
to the same physical baseline, not to its own potentially-degraded history.

---

### Layer 2 — Fleet Intelligence

**What it does**: Cross-compares health scores across multiple actuators in
the same building to reveal system-level patterns invisible at device level.

**Algorithm**:
1. Fetch all test numbers from InfluxDB over the past 24h
2. Compute health score for each test against the same baseline
3. Render a bar chart: test/actuator → health score, color-coded
4. Flag outliers >2σ below fleet mean

**The novel insight**:
A valve that consistently works harder at peak hours is not malfunctioning —
it's undersized for its zone. Without fleet comparison, this is invisible.
With it, a facility manager can proactively resize that zone.

**Environmental normalization (important for technical credibility)**:
By aggregating data from actuators across multiple buildings in the same
geographic area, we distinguish between:
- One actuator degrades while neighbors stay stable → internal fault
- Every actuator in the district shows increased torque on the same day → environmental (pressure change, temperature drop, peak demand)

**Soundbite**: *"The fleet is its own control group."*

---

### Layer 3 — Commissioning QA Badge

**What it does**: On the very first stroke after installation, automatically
evaluates installation quality and issues a pass/fail badge. Zero manual
inspection. No specialist engineer. No extra hardware.

**4 automated checks**:
1. **Range of motion** — did actuator reach ≥60% range? If not: mechanical
   obstruction or wrong torque sizing → deduct 30 points
2. **Torque variability** — coefficient of variation (std/mean) > 1.5 flags
   obstruction or shaft misalignment → deduct 25 points
3. **Tracking error** — mean |setpoint − feedback| > 10% flags coupling
   failure or gear slip → deduct 20 points
4. **Temperature rise** — >5°C rise during commissioning flags motor
   overload or wrong actuator sizing → deduct 15 points

**Scoring**: Start at 100, subtract penalties. Pass ≥70. Marginal 50–69. Fail <50.

**Why this is original**: No HVAC product today auto-generates a QA score at
commissioning from the actuator's own signals alone. Zero config, instant,
works on existing data stream.

---

## Lab baseline protocol

Reserved test number: **999** (hardcoded, never used for field tests)

### Three controlled tests

**Test 1 — Free stroke** (pure mechanical signature)
- Command sequence: 0 → 25 → 50 → 75 → 100 → 75 → 50 → 25 → 0 %
- Actuator must be unloaded — nothing attached or blocking
- Captures: motor inertia, gear friction, spring return force
- Sleep 2s between each position command

**Test 2 — Loaded stroke** (simulated installation load)
- Command sequence: 0 → 50 → 100 → 50 → 0 %
- Apply gentle manual resistance to shaft during movement
- Captures: torque response under realistic working load
- Sleep 3s between each position command

**Test 3 — Stall test** (thermal and torque stability)
- Command: hold at 45% for 10 seconds, then return to 0%
- Do not apply external force
- Captures: torque drift under constant load, motor self-heating, position stability

All three tests write to InfluxDB with test_number = 999.

---

## InfluxDB data model

### Connection details
```
URL:    http://192.168.3.14:8086
User:   pi
Pass:   raspberry
Token:  raspberry  (or use pi:raspberry)
Bucket: actuator-data
Org:    (empty string — OSS instance)
```

### Measurement: `measurements` (read — written by Pi logger continuously)
| Field | Type | Unit | Notes |
|---|---|---|---|
| `feedback_position_%` | float | % | 0=closed, 100=open |
| `setpoint_position_%` | float | % | Commanded target |
| `motor_torque_Nmm` | float | N·mm | Use abs() — sign inconsistent |
| `internal_temperature_deg_C` | float | °C | PCB temperature |
| `power_W` | float | W | Electrical power |
| `rotation_direction` | int | — | 0=still, 1=opening, 2=closing |
| `test_number` | float | — | Experiment tag |

### Measurement: `_process` (write — to move the actuator)
| Field | Type | Notes |
|---|---|---|
| `setpoint_position_%` | float | Target 0–100, clipped |
| `test_number` | float | Experiment identifier |
| timestamp | fixed | Always `datetime.fromtimestamp(0, tz=timezone.utc)` |

### Reserved test numbers
| Range | Purpose |
|---|---|
| `999` | Lab baseline — healthy reference — NEVER overwrite |
| `1–100` | Field health tests |
| `200–300` | Commissioning / installation tests |
| `-1` | Default / untagged (Belimo demo app default) |

### Important: no data persistence on Pi reboot
InfluxDB wipes on reboot. Export baseline data to laptop after running lab tests.

### Flux query pattern (pivot is essential)
```flux
from(bucket: "actuator-data")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "measurements")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
```

### Write command pattern (Python)
```python
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime, timezone
import numpy as np

client = InfluxDBClient(url="http://192.168.3.14:8086", token="raspberry", org="")
write_api = client.write_api(write_options=SYNCHRONOUS)
point = (
    Point("_process")
    .field("setpoint_position_%", float(np.clip(position, 0, 100)))
    .field("test_number", float(test_number))
    .time(datetime.fromtimestamp(0, tz=timezone.utc))
)
write_api.write(bucket="actuator-data", record=point)
```

---

## Tech stack

```
influxdb-client
streamlit
altair
pandas
numpy
scipy
```

Run with:
```bash
pip install influxdb-client altair pandas streamlit numpy scipy
streamlit run solution.py
```

---

## UI/UX — 4-tab Streamlit app

### Tab 1 · Live Monitor
- Auto-refresh every 2 seconds using st.rerun()
- Time window slider (1–10 minutes)
- Metric row: last values of torque, position, temperature, power
- Time-series line chart (user selects which signal to plot)
- Phase portrait: torque (Y) vs position (X) scatter — this is the "fingerprint" visual
- Makes the concept tangible: you can see the ECG shape in real time

### Tab 2 · Lab Baseline
- Three buttons: Free stroke / Loaded stroke / Stall test
- Each button sends commands to InfluxDB _process with test_number=999
- Show a spinner with instructions during the test
- "View baseline profile" button: fetch test_number=999 data, plot torque profile
- Torque profile = mean |torque| binned by position, plotted as line chart
- Color: orange #D85A30 for baseline

### Tab 3 · Health Score
- Number input: field test number (1–100)
- "Run test stroke" button: sweep 0→50→100→50→0, test_number=user_input
- "Compute health score" button:
  - Fetch baseline (test 999) and current test data
  - Compute torque profiles for both
  - Compute RMS deviation → health score 0–100
  - Show large color-coded score badge
  - Show overlay chart: baseline (orange) vs current (purple) torque profiles
  - Show deviation % and health label
- Fleet bar chart: all test numbers vs same baseline, green/amber/red bars

### Tab 4 · Commissioning QA
- Number input: commissioning test number (200–300)
- "Run first installation stroke" button: sweep 0→100→0, sleep 3s between
- After stroke: auto-compute 4 checks, show badge
- Badge: large score, color border, PASS/MARGINAL/FAIL label
- Diagnostic list: show which checks passed/failed with explanations
- First-stroke torque fingerprint chart (area chart, color matches badge)

### Color system
| Color | Hex | Meaning |
|---|---|---|
| Green | `#1D9E75` | Healthy, score ≥ 80, PASS |
| Amber | `#EF9F27` | Degraded, score 50–79, MARGINAL |
| Red | `#E24B4A` | Critical, score < 50, FAIL |
| Orange | `#D85A30` | Baseline reference curve |
| Purple | `#7F77DD` | Current / field test curve |

### Sidebar
Pre-filled connection config:
- URL: http://192.168.3.14:8086
- Token: raspberry
- Org: (empty)
- Bucket: actuator-data
Note about reserved test numbers.

---

## Business case

### The cost comparison

**Current model — human inspection**
- HVAC technician: €60–120/hour in Europe
- Fault diagnosis visit: 2–4 hours (travel + inspection + report)
- Cost per callout: €200–500
- Large commercial building (hundreds of actuators), annual inspection: €10,000–50,000/year
- Emergency callout (unplanned failure): 2–3× more expensive + downtime cost

**Our model — edge intelligence + cloud sync**
- InfluxDB Cloud: ~€50–200/month for a full building
- Sync agent: runs on existing hardware, €0 marginal cost
- Cellular modem if no internet: ~€20/month
- Total: ~€100–250/month per building → €1,200–3,000/year

**ROI soundbite**: *"One avoided emergency callout pays for the system for a year."*

### Human model vs our model
| Human model | Our model |
|---|---|
| Technician visits → inspects → guesses | Data detects → diagnoses → technician confirms |
| Finds problem after failure | Predicts problem 2–6 weeks before failure |
| Checks 10 valves per day | Monitors 500 valves simultaneously |
| Knowledge leaves when technician retires | Knowledge encoded in baseline forever |

### Cloud architecture (Phase 2 roadmap)
- Buildings with internet: lightweight sync agent pushes InfluxDB data to InfluxDB Cloud
- Buildings without internet: data lives at the edge, exported during maintenance visits
- Cellular modem option: 4G dongle on Pi, Belimo-controlled connection
- Factory receives live feed from all deployed actuators worldwide
- Factory-certified baselines pushed down to new devices at commissioning

**Key point**: The system works fully offline. Cloud adds cross-building aggregation,
not core functionality. Edge-first is a feature — works in industrial environments
with no internet.

### Revenue model
- SaaS subscription per device: €5–15/device/month
- A 500-actuator building: €2,500–7,500/month
- Belimo has millions of deployed actuators worldwide → massive TAM
- Upsell: premium analytics, API access for integrators, white-label for OEMs

---

## Pitch narrative (full script)

### Opening
"Every time a Belimo actuator moves, it silently records its own mechanical
story — torque, position, temperature, power. Today, 100% of that data is
thrown away. We're here to change that."

### The insight
"An actuator's torque curve is a mechanical fingerprint. Like an ECG for a
heart, a healthy device produces a stable, predictable signature. Degradation,
obstruction, wear — they all deform that signature in detectable ways."

### The medical device analogy
"But here's the key insight: a cardiologist doesn't define a healthy heartbeat
by averaging a patient's own history. They compare against a certified,
controlled baseline. We do the same — run lab tests on a known-healthy
actuator first, certify that baseline, then score every future stroke against
it. This eliminates the core flaw of anomaly detection: learning a degraded
state as normal."

### Layer 1
"Layer 1: every stroke gets a health score from 0 to 100. Green is healthy,
red is critical. Facility managers see exactly which valves need attention —
weeks before failure, not after."

### Layer 2
"Layer 2: fleet intelligence. By comparing actuators across a building —
and across buildings in the same area — we distinguish internal faults from
environmental effects. If one actuator degrades while its neighbors stay
stable, that's a mechanical problem. If every actuator in the district shows
increased torque on the same day, that's weather, not wear.
The fleet is its own control group."

### Layer 3
"Layer 3: commissioning QA. The moment a new actuator completes its very
first stroke, it automatically gets a pass/fail installation badge. Four
checks: range of motion, torque variability, tracking accuracy, temperature.
No engineer, no manual inspection, no phone call. The installer knows
instantly."

### Business case
"One avoided emergency callout pays for the system for an entire year.
Instead of a technician inspecting 10 valves a day, you monitor 500
simultaneously. And as Belimo deploys more connected actuators, every
device becomes a data point in a global health network."

### Close
"We didn't add any new hardware. We didn't change the actuator.
We just started listening to what it was already trying to tell us."

---

## Judge Q&A prep

**Q: What about production variance between actuators?**
A: The baseline is per-model-class. We use relative deviation from the
per-model baseline, not absolute thresholds. Production variance is the
same for all devices of the same model, so it cancels out.

**Q: What if the baseline itself is corrupted?**
A: Three independent tests. Any corrupted test is detectable as an outlier
in the baseline profile. In production, the baseline is factory-certified
before the device ships — the customer receives a device with its health
passport already embedded.

**Q: How is this different from Belimo's Facilio partnership?**
A: Facilio operates at the BMS integration layer — needs cloud connectivity,
enterprise software, cross-system data. Our solution works with only the
actuator's own InfluxDB stream. Zero BMS integration. Zero config.
Device-native intelligence, not platform analytics.

**Q: No labeled fault data — how do you know what deviations mean?**
A: Physics tells us. Increasing torque = friction buildup. Position lag =
gear wear. Torque spike at fixed angle = obstruction at that mechanical
position. Temperature rise = motor overload. No labels needed — the
signal shape maps directly to a physical cause.

**Q: What if there's no internet in the building?**
A: The core system is fully offline. All three layers run on the local Pi.
Cloud sync adds cross-building aggregation but is not required for the
health score, fleet view within a building, or commissioning badge.
Edge-first is a deliberate design choice — it works in industrial
environments where internet is unreliable or unavailable.

**Q: How do you get data to the factory?**
A: Three options depending on connectivity:
1. Internet available: sync agent pushes to InfluxDB Cloud periodically
2. No internet: technician exports CSV during maintenance visit
3. No internet + always-on: 4G cellular modem on the Pi, ~€20/month
The intelligence works in all three cases.

---

## Live demo script (for judges)

1. **Tab 1 — Live Monitor**
   Say: "This is the actuator's live fingerprint. Watch the phase portrait —
   this is what a healthy stroke looks like in real time."
   Action: Move the actuator physically, show the chart update.

2. **Tab 2 — Lab Baseline**
   Say: "This morning we ran our three lab tests on this healthy actuator.
   This is our certified ground truth — the ECG of a healthy device."
   Action: Show the baseline torque profile chart.

3. **Tab 3 — Health Score**
   Say: "Now we run a field test stroke and score it against the baseline."
   Action: Run test stroke → compute health score → show overlay chart.
   Say: "See that deviation at 60°? That's exactly where we applied
   resistance. The system caught it immediately."

4. **Tab 4 — Commissioning QA**
   Say: "Now imagine this actuator was just installed five minutes ago.
   First stroke complete — here's the automatic installation report."
   Action: Run commissioning stroke → show badge appear.
   Say: "Pass. 87 out of 100. The installer knows immediately.
   No phone call, no engineer, no waiting."

5. **Fleet view**
   Say: "Scale this to a 500-actuator building and you have a complete
   health map of every valve, updated in real time, for less than the
   cost of a single emergency callout."
