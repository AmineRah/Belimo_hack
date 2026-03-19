# ActuSpec

ActuSpec is a hackathon MVP for the Belimo Smart Actuators case at START Hack 2026.

## What it does
ActuSpec compares actuator telemetry against a healthy baseline and produces:
- a health score
- a commissioning QA verdict
- a diagnostic explanation
- visual overlays of actuator behavior

## Quick start

### A) Verify the hardware pipeline

1. Connect your laptop to **`BELIMO-X`** Wi-Fi (password: `raspberry`)
   - `X` is the digit printed on the Raspberry Pi label
2. Open InfluxDB UI at **http://192.168.3.14:8086**
3. Login with `pi` / `raspberry`
4. Navigate to bucket **`actuator-data`**
5. Check that measurement **`measurements`** is receiving new rows

If `measurements` is updating, the Pi logger is running and the actuator is connected.
If it is not updating, the Pi or actuator may need to be power-cycled.

### B) Run the Belimo demo (optional — verify command path)

The official Belimo demo lives in `~/Documents/Belimo-START-Hack-2026-main/demo/`.
Use it to confirm that writing to `_process` actually moves the actuator.

**Build the container:**
```bash
cd ~/Documents/Belimo-START-Hack-2026-main/demo
docker build -t demo .
```

**Streamlit mode** (default — launches web UI):
```bash
docker run --rm -it -p 8501:8501 -v ${PWD}:/work demo
```
Then open http://localhost:8501

**CLI mode** (pass arguments — prints to terminal):
```bash
docker run --rm -it -v ${PWD}:/work demo \
  --waveform sine --frequency 0.1 --bias 50 --amplitude 30 --test-number 1
```

Once you see the actuator moving and telemetry flowing, the hardware pipeline is confirmed.

### C) Run ActuSpec

```bash
cd ~/Documents/Belimo_hack
pip install -r requirements.txt
streamlit run solution.py
```

ActuSpec starts in **Replay mode** by default — no Wi-Fi needed.
Switch to **Live mode** in the sidebar when connected to `BELIMO-X`.

### D) Demo walkthrough

| Step | Tab | What to do |
|------|-----|------------|
| 1 | 🔬 Healthy Baseline | Load the baseline (replay or live). This is the "healthy ECG." |
| 2 | ❤️ Health Score | Select **healthy** replay → Analyze. Score should be ~97. |
| 3 | ❤️ Health Score | Select **fault** replay → Analyze. Score drops to ~73. Note the spike at 62%. |
| 4 | 🏗️ Commissioning QA | Run commissioning replay → see pass/fail badge and diagnostic breakdown. |
| 5 | 📡 Live Monitor | (Live mode) Send a command, watch the actuator respond in real time. |

For the live demo with judges: run steps 2–4 with **Live mode** on real hardware.
If hardware is unreliable, Replay mode produces identical analysis — use it as the primary demo path.

## Modes
- **Live Mode**: writes commands to `_process` and reads telemetry from `measurements`
- **Replay Mode**: uses prerecorded traces for reliable demo fallback

## Project structure
- `solution.py` — Streamlit UI
- `orchestrator.py` — run coordination + state machine
- `collector.py` — telemetry retrieval from `measurements`
- `commander.py` — command writing to `_process`
- `analyzer.py` — metrics and diagnosis
- `baseline.py` — healthy reference logic
- `fallback.py` — replay trace loading and local persistence
- `charts.py` — visuals
- `config.py` — settings and thresholds

## Core principle
Replay mode is first-class. Live mode is a bonus, not a dependency.
