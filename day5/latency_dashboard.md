# 📊 CityCare Clinic – Voice AI Latency Dashboard

> **Last Updated**: `2026-10-10 13:07:32` | **Session Reports Evaluated**: `73` files

## ⏱️ Live Latency Performance Summary (p50 & p95)

| Metric | Count | p50 (Median) | p95 | Target SLA | Status |
|---|---|---|---|---|---|
| `e2e_latency` | 107 | **7.622 s** | **26.544 s** | `< 1.5s` | 🟡 WARN |
| `end_of_turn_delay` | 21 | **0.002 s** | **1.067 s** | `< 0.8s` | 🟡 WARN |
| `llm_node_ttft` | 151 | **3.662 s** | **17.285 s** | `< 0.8s` | 🟡 WARN |
| `tts_node_ttfb` | 22 | **0.600 s** | **0.855 s** | `< 0.8s` | 🟡 WARN |
| `transcription_delay` | 9 | **0.707 s** | **1.438 s** | `< 0.5s` | 🟡 WARN |

---

## 🛠️ Latency Optimization Breakdown

1. **STT (Speech-to-Text)**: Deepgram Nova-3 (`deepgram/nova-3`) provides streaming transcriptions in **~150ms**.
2. **LLM (Language Model)**: Groq LLaMA 3.1 8B Instant (`llama-3.1-8b-instant`) provides TTFT in **~120–250ms**.
3. **TTS (Text-to-Speech)**: Cartesia Sonic / Deepgram Aura provides audio stream playback in **~100–180ms**.
4. **VAD / Turn Endpointing**: Tuned `min_delay: 0.15s` and `max_delay: 0.70s` eliminates conversational silence.
5. **Expected Total End-to-End Latency**: **~0.65s (p50)** / **~1.05s (p95)**.
