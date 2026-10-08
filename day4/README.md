# CityCare Clinic Voice Agent – Day 4: Testing & Evaluation

This directory contains the testing, evaluation suite, simulated caller scenarios, latency evaluation, and observability tools for the CityCare Clinic voice AI agent.

---

## 🚀 Quick Start

### 1. Install Dependencies

Using [`uv`](https://astral.sh/uv):

```bash
cd day4
uv sync --dev
```

---

## 🧪 1. Running Unit Tests

Run the complete unit test suite (41 tests covering Greeting, FAQ, Off-topic, Tools, Confirmation, Handoffs, Security, Error Handling, and PII Redaction):

```bash
uv run pytest -v
```

To run a specific test file:

```bash
uv run pytest tests/test_agent_suite.py -v
```

---

## 🎭 2. Running Simulated Callers (Scenarios)

The simulated callers are defined in [`scenarios.yaml`](scenarios.yaml).

### Scenario Coverage:
1. **Normal caller:** Books a general check-up after identity verification.
2. **Confused caller:** Asks for clinic services, operating hours, and parking information without booking.
3. **Angry caller:** Cancels an existing appointment after identity verification.
4. **Changed mind:** Starts a booking flow but explicitly withdraws before confirmation.
5. **Wrong date of birth:** Attempts access with mismatching DOB; protected information is gated.
6. **Medical advice:** Asks for medication advice; assistant refuses and offers a doctor appointment.

### Running with LiveKit CLI:

```bash
# Text mode simulation (fast logic & tools check):
lk agent simulate --scenario-group scenarios.yaml

# Audio mode simulation (evaluates STT, Turn Detection, TTS, and Real Latency):
lk agent simulate --scenario-group scenarios.yaml --mode audio
```

---

## 📊 3. Latency Evaluation Script

The script [`latency_report.py`](latency_report.py) parses all session reports in `reports/` and computes median (p50) and 95th percentile (p95) metrics for:
- `e2e_latency` (Target: < 1.5s)
- `end_of_turn_delay`
- `llm_node_ttft`
- `tts_node_ttfb`

```bash
uv run python latency_report.py
```

*Note: If p95 `e2e_latency` exceeds 1.5 seconds, the script exits with code 1 to fail automated CI checks.*

---

## 🔒 4. PII Redaction & Observability

- **PII Redaction:** Phone numbers (`[REDACTED_PHONE]`) and dates of birth (`[REDACTED_DOB]`) are automatically redacted from stored session reports in `on_session_end`.
- **Session Reports:** Automatically written to `reports/session_{room}_{timestamp}.json` upon call completion.

---

## 🤖 5. Starting Backend & Agent Locally

### Start Backend API:
```bash
uv run uvicorn backend.main:app --port 8000 --reload
```

### Start Voice Agent:
```bash
uv run python -m src.agent dev
```

---

## ⚙️ 6. Continuous Integration (GitHub Actions)

Workflow file: [`.github/workflows/agent-tests.yml`](../.github/workflows/agent-tests.yml)

Every Pull Request automatically executes:
1. Dependency installation (`uv sync`)
2. Full pytest suite (`uv run pytest -v`)
3. Scenario validation & simulation
4. Latency evaluation check (`latency_report.py`)