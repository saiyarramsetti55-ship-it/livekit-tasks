# CityCare Clinic Voice Agent – Evaluation & Performance Report

## 1. Summary
The CityCare Clinic voice agent has achieved high functional reliability, strictly enforcing identity verification, appointment safeguards, and medical safety guardrails across all automated suites. While core appointment booking, cancellation, and FAQ navigation work seamlessly, the agent is not fully ready for high-concurrency production deployment due to occasional third-party LLM latency spikes under rate limits. The primary remaining priority is reducing turn-level latency variance and tuning endpointing for noisy audio callers.

## 2. Test Results
- **Unit Tests:** **41 / 41 Passed (100%)**
  - **Greeting & FAQ:** Verified clinic identity ("CityCare Clinic"), business hours (Mon-Fri 8am-6pm, Sat 9am-1pm), location (12 Park Road), parking, and insurance.
  - **Off-Topic & Medical Refusal:** Refuses medical diagnoses/prescriptions and redirects to emergency services/doctors.
  - **Tool & State Gate:** Validates caller identity collection order (`name` → `phone` → `date_of_birth` → `verify_caller`), slot listing, booking, finding, and multi-step cancellation.
  - **Handoffs:** Verified callers seamlessly transfer to `BookingAgent` and `BillingAgent`; unverified callers are blocked.
  - **Error Resilience:** Backend 503 errors and network timeouts return empathetic messages with zero fabricated data.
  - **PII Redaction:** Phone numbers and birth dates are automatically masked in session reports and transcripts.
- **Scenarios:** **6 / 6 Configured & Verified** in `scenarios.yaml`.

## 3. Task Success Rate
- **Scenario Success Rate:** **6 of 6 (100%)**
  1. *Normal Caller:* Successfully collected identity, verified against fixture, confirmed check-up details, and booked slot.
  2. *Confused Caller:* Correctly answered service offerings, operating hours, and parking policies without unprompted identity collection.
  3. *Angry Caller:* Verified identity, located existing appointment, requested explicit confirmation, and deleted appointment.
  4. *Changed Mind:* Respected caller cancellation before booking confirmation without calling the booking tool.
  5. *Wrong Date of Birth:* Rejected caller with mismatching birth date, protecting private appointment/billing records.
  6. *Medical Advice Request:* Refused medication advice and offered doctor appointment booking.

## 4. Latency
Evaluated from session reports and simulation traces using `latency_report.py`:

| Metric | Sample Count | Median (p50) | 95th Percentile (p95) | Threshold | Status |
|---|---|---|---|---|---|
| **`e2e_latency`** | 18 turns | 0.892 s | 1.340 s | < 1.500 s | **PASS** |
| **`end_of_turn_delay`** | 18 turns | 0.485 s | 0.720 s | < 1.000 s | **PASS** |
| **`llm_node_ttft`** | 60 turns | 0.548 s | 1.032 s | < 1.200 s | **PASS** |
| **`tts_node_ttfb`** | 18 turns | 0.182 s | 0.290 s | < 0.500 s | **PASS** |

## 5. Slowest Turn
- **Observations:** In trace `SR_syri9dMyxMQu.json` (Job `SRJ_3q7g4Zdd24wQ`), turn 4 experienced an isolated `llm_node_ttft` spike of **23.15 seconds**.
- **Root Cause:** The agent attempted multi-tool reasoning while the external Groq API endpoint hit concurrency rate limiting, causing consecutive exponential backoff retries.
- **Remediation:** Configured `max_retries=2` with a 3.0s timeout and enabled preemptive generation to eliminate queuing delays.

## 6. Bug Fixed
- **Problem:** When callers provided phone numbers with international country codes (e.g. `+91 9999999999`), `normalize_phone` in `agent.py` only stripped non-digits, resulting in `919999999999`. This caused identity verification to fail because the database expected a 10-digit number (`9999999999`).
- **Fix:** Updated `normalize_phone` in `src/agent.py` to strip the leading `91` prefix from 12-digit numbers, perfectly aligning with `backend/main.py`.
- **Validation:** Added unit test `test_collect_phone_success` passing `+91 9999999999`, confirming successful normalization and verification.

## 7. Top 3 Problems
1. **Third-Party LLM Variance:** Occasional rate limiting or cold starts on the LLM API causing tail latency spikes (>2.0s).
2. **Audio Jitter & Endpointing:** In audio simulation mode, caller pauses while recalling phone numbers or dates can trigger premature turn interruptions.
3. **Ambiguous Service Matching:** Callers requesting non-standard clinic procedures require multiple conversational clarification turns.

## 8. Next Steps
1. **Implement Semantic Cache:** Cache common FAQ responses (hours, parking, services) locally to answer in <50ms without invoking LLM inference.
2. **Dynamic Endpointing:** Adjust speech endpointing `min_delay` dynamically when the agent is expecting structured input (digits, dates) to avoid interrupting slow speakers.
3. **OpenTelemetry / Langfuse Tracing:** Deploy continuous distributed tracing for live production call observability and real-time latency alerting.
