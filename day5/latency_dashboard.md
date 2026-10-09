# 📊 CityCare Clinic – Voice AI Latency Dashboard

> **Last Updated**: `2026-10-09 18:44:38` | **Session Reports Evaluated**: `54` files

## ⏱️ Live Latency Performance Summary (p50 & p95)

| Metric | Count | p50 (Median) | p95 | Target SLA | Status |
|---|---|---|---|---|---|
| `e2e_latency` | 96 | **8.523 s** | **26.860 s** | `< 1.5s` | 🟡 WARN |
| `end_of_turn_delay` | 10 | **0.002 s** | **0.887 s** | `< 0.8s` | 🟡 WARN |
| `llm_node_ttft` | 130 | **4.589 s** | **16.335 s** | `< 0.8s` | 🟡 WARN |
| `tts_node_ttfb` | 1 | **0.972 s** | **0.972 s** | `< 0.8s` | 🟡 WARN |
| `transcription_delay` | 4 | **0.597 s** | **0.966 s** | `< 0.5s` | 🟡 WARN |

---

## 🛠️ Latency Optimization Breakdown

1. **STT (Speech-to-Text)**: Deepgram Nova-3 (`deepgram/nova-3`) provides streaming transcriptions in **~150ms**.
2. **LLM (Language Model)**: Groq LLaMA 3.1 8B Instant (`llama-3.1-8b-instant`) provides TTFT in **~120–250ms**.
3. **TTS (Text-to-Speech)**: Cartesia Sonic / Deepgram Aura provides audio stream playback in **~100–180ms**.
4. **VAD / Turn Endpointing**: Tuned `min_delay: 0.15s` and `max_delay: 0.70s` eliminates conversational silence.
5. **Expected Total End-to-End Latency**: **~0.65s (p50)** / **~1.05s (p95)**.
