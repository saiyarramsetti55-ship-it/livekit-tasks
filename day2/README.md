# Day 2: CityCare Clinic Voice Agent (Tools, Backend, RAG, LangGraph)

## Folders
- `backend/main.py`: FastAPI backend (in-memory data, slots cache)
- `src/agent.py`: LiveKit agent with all tools
- `src/rag.py`: policy search (Chroma vector store)
- `src/langgraph_llm.py`: LangGraph graph (classify intent -> answer)
- `policies.md`: clinic rules used for RAG
- `tool_latency.md`: the 4 latency tables

## Setup
1. Create and activate a virtual environment:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
2. Install packages:
   pip install -r requirements.txt
3. Create `src/.env.local` with your own keys (do not commit it):
   LIVEKIT_URL=...
   LIVEKIT_API_KEY=...
   LIVEKIT_API_SECRET=...
   GROQ_API_KEY=...

## Start the backend (terminal 1, from the day2 folder)
uvicorn backend.main:app --reload

Test it at http://127.0.0.1:8000/docs

## Start the agent (terminal 2, from day2/src)
python agent.py dev

## Settings in agent.py
- `TOP_K`: number of policy results (3 normal, 10 for the test)
- `PROMPT_MODE`: "long" or "short" prompt
- `LLM_MODE`: "plain" (tools work) or "langgraph" (for Table 4 only)

Final setting for the booking test: LLM_MODE = "plain".

## Settings in backend/main.py
- `CACHE_SECONDS`: 30 (0 turns the cache off)
- `SIMULATED_DB_DELAY`: 0.3 (test only, simulates a slow database)