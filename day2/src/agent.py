import asyncio
import logging
import textwrap
from datetime import datetime
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv
from . import rag
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ConversationItemAddedEvent,
    JobContext,
    RunContext,
    STTContextOptions,
    TurnHandlingOptions,
    cli,
    function_tool,
    inference,
    room_io,
)
from livekit.agents.llm import ChatMessage
from livekit.plugins import ai_coustics, langchain
from livekit.plugins.groq import LLM as GroqLLM


logger = logging.getLogger("citycare-agent")


# Backend address (FastAPI)
API = "http://127.0.0.1:8000"


# Tool timings are saved here
TIMING_FILE = Path(__file__).resolve().parent / "tool_times.csv"


# How many policy results the RAG tool returns
# 3 = normal, 10 = for the test
TOP_K = 3


# Step 10:
# "long" = before
# "short" = after
PROMPT_MODE = "long"


# Step 11:
# "plain" = Groq without LangGraph
# "langgraph" = Groq with LangGraph
LLM_MODE = "plain"


# Groq model
GROQ_MODEL = "openai/gpt-oss-120b"


# Load environment variables
load_dotenv(".env.local")
load_dotenv(".env")


def log_tool_time(tool_name: str, start: float) -> None:
    """Print and save how long a tool took, in milliseconds."""

    ms = (perf_counter() - start) * 1000

    print(f"TOOL  {tool_name} took {ms:.0f} ms")

    new_file = not TIMING_FILE.exists()

    with open(TIMING_FILE, "a", encoding="utf-8") as f:
        if new_file:
            f.write("time,tool,ms\n")

        f.write(
            f"{datetime.now().strftime('%H:%M:%S')},"
            f"{tool_name},{ms:.0f}\n"
        )


# ---------------------------------------------------------------
# LONG prompt
# ---------------------------------------------------------------

CLINIC_PROMPT_LONG = textwrap.dedent(
    """
    You are the front desk voice assistant for CityCare Clinic.

    Clinic information:
    - Name: CityCare Clinic
    - Hours: Monday to Friday, 8:00 AM to 6:00 PM
    - Saturday: 9:00 AM to 1:00 PM
    - Sunday: Closed
    - Address: 12 Park Road
    - Services: general check-up, blood tests, vaccines, and children's doctor
    - Parking: free parking behind the building
    - Insurance: most major insurance plans are accepted

    Voice response rules:
    - Answer in 1 to 3 short sentences.
    - Use natural spoken language.
    - Do not use markdown, lists, emojis, or complicated formatting.
    - Ask only one question at a time.
    - Keep answers concise.

    Scope:
    - Only talk about CityCare Clinic and its services.
    - If the user asks about something unrelated to the clinic,
      politely say that you can only help with CityCare Clinic questions.

    Medical safety:
    - Never give medical advice.
    - Never diagnose a medical condition.
    - Never recommend a medicine or dosage.
    - If the user asks for medical advice, politely say that you
      cannot provide medical advice and suggest booking a visit
      with a qualified healthcare professional.

    If the user asks about clinic information, use only the
    information provided above.

    BOOKING RULE:
    Before you call book_appointment, you must do these 3 things:
    1. Repeat the service, date and time to the caller.
    2. Ask: "Is this correct?"
    3. Call book_appointment only after the caller says yes.
    If the caller says no, ask what they want to change.

    CHANGE AND CANCEL RULE:
    1. Ask for the caller's phone number.
    2. Call find_appointments to get the appointment id.
    3. Repeat the appointment and ask: "Is this correct?"
    4. Call change_appointment or cancel_appointment only after the caller says yes.
    Never say the appointment id out loud unless the caller asks.

    ERROR RULE:
    If a tool returns an error or says the system is not available:
    1. Say sorry in one short sentence.
    2. Explain simply that the system is not working right now.
    3. Offer to help with something else, or ask the caller to try again later.
    Never invent appointment times, booking results, or any other data.
    Never say technical words like "500" or "server error".

    SLOW TOOL RULE:
    The tool check_slow_system says its own waiting sentence.
    Do not say any waiting sentence yourself before calling it.

    POLICY RULE:
    For questions about cancellation, late arrival, doctors, payment,
    insurance, what to bring, blood tests, or parking, call search_policies.
    Answer only with what the tool returns. If it does not contain the
    answer, say you do not know and suggest calling the clinic.
    """
)


# ---------------------------------------------------------------
# SHORT prompt
# ---------------------------------------------------------------

CLINIC_PROMPT_SHORT = textwrap.dedent(
    """
    You are the front desk voice assistant for CityCare Clinic.
    Hours: Mon-Fri 8 AM to 6 PM, Sat 9 AM to 1 PM, Sunday closed.
    Address: 12 Park Road.
    Services: general check-up, blood tests, vaccines, children's doctor.

    Style: 1 to 3 short spoken sentences, no lists or markdown,
    one question at a time. Only talk about CityCare Clinic.
    Never give medical advice or diagnosis; suggest seeing a doctor.

    Booking: before book_appointment, repeat service, date and time,
    ask "Is this correct?", and book only after a yes.

    Change or cancel: ask the phone number, call find_appointments,
    confirm, then call change_appointment or cancel_appointment
    only after a yes. Do not say the appointment id unless asked.

    Policies (cancellation, late arrival, doctors, payment, insurance,
    what to bring, blood tests, parking): call search_policies and answer
    only from the result. If unknown, suggest calling the clinic.

    Errors: if a tool fails, say sorry, explain simply that the system
    is not working, and never invent data or say technical words.

    check_slow_system says its own waiting sentence, so do not say one.
    """
)


CLINIC_PROMPT = (
    CLINIC_PROMPT_LONG
    if PROMPT_MODE == "long"
    else CLINIC_PROMPT_SHORT
)


def build_llm():
    """Choose the LLM. Both modes use the same Groq model."""

    if LLM_MODE == "langgraph":
        from langgraph_llm import build_graph

        # Graph: classify intent -> answer
        # Uses Groq inside langgraph_llm.py
        return langchain.LLMAdapter(
            build_graph(CLINIC_PROMPT)
        )

    # Plain mode: use Groq directly
    # This replaces the old openai.LLM.with_groq() approach
    return GroqLLM(model=GROQ_MODEL)


class FrontDesk(Agent):

    def __init__(self) -> None:
        super().__init__(
            instructions=CLINIC_PROMPT,
            llm=build_llm(),
        )

    async def on_enter(self):
        await self.session.generate_reply(
            instructions=(
                "Greet the caller. Say the clinic name. "
                "Ask how you can help."
            )
        )

    @function_tool()
    async def get_available_slots(
        self,
        context: RunContext,
        date: str,
    ) -> str:
        """Find free appointment times on a date.
        Use this before you book. date format: YYYY-MM-DD.
        """

        start = perf_counter()

        try:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(
                        f"{API}/slots",
                        params={"date": date},
                    )

                    response.raise_for_status()
                    slots = response.json()

            except Exception as e:
                logger.error(f"get_available_slots failed: {e}")

                return "The booking system is not available right now."

            if not slots:
                return "No free times on this date."

            return "Free times: " + ", ".join(slots[:5])

        finally:
            log_tool_time(
                "get_available_slots",
                start,
            )

    @function_tool()
    async def book_appointment(
        self,
        context: RunContext,
        name: str,
        phone: str,
        date: str,
        time: str,
        service: str,
    ) -> str:
        """Book an appointment.
        Call this ONLY after the caller has confirmed the date and time.
        date format: YYYY-MM-DD, time format: HH:MM.
        """

        start = perf_counter()

        try:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.post(
                        f"{API}/appointments",
                        json={
                            "name": name,
                            "phone": phone,
                            "date": date,
                            "time": time,
                            "service": service,
                        },
                    )

                    response.raise_for_status()
                    data = response.json()

            except Exception as e:
                logger.error(f"book_appointment failed: {e}")

                return "The booking system is not available right now."

            return f"Booked. The appointment id is {data.get('id')}."

        finally:
            log_tool_time(
                "book_appointment",
                start,
            )

    @function_tool()
    async def find_appointments(
        self,
        context: RunContext,
        phone: str,
    ) -> str:
        """Find the appointments of a caller by phone number.
        Use this before you change or cancel an appointment.
        """

        start = perf_counter()

        try:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(
                        f"{API}/appointments",
                        params={"phone": phone},
                    )

                    response.raise_for_status()
                    items = response.json()

            except Exception as e:
                logger.error(f"find_appointments failed: {e}")

                return "The booking system is not available right now."

            if not items:
                return "No appointments found for this phone number."

            lines = [
                f"id {a.get('id')}: "
                f"{a.get('service')} on "
                f"{a.get('date')} at "
                f"{a.get('time')}"
                for a in items[:3]
            ]

            return "Appointments: " + "; ".join(lines)

        finally:
            log_tool_time(
                "find_appointments",
                start,
            )

    @function_tool()
    async def change_appointment(
        self,
        context: RunContext,
        appointment_id: str,
        date: str,
        time: str,
    ) -> str:
        """Change the date and time of an existing appointment.
        Call this ONLY after the caller confirmed the new date and time.
        date format: YYYY-MM-DD, time format: HH:MM.
        """

        start = perf_counter()

        try:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.patch(
                        f"{API}/appointments/{appointment_id}",
                        json={
                            "date": date,
                            "time": time,
                        },
                    )

                    response.raise_for_status()

            except Exception as e:
                logger.error(f"change_appointment failed: {e}")

                return "The booking system is not available right now."

            return (
                f"Done. The appointment is now on "
                f"{date} at {time}."
            )

        finally:
            log_tool_time(
                "change_appointment",
                start,
            )

    @function_tool()
    async def cancel_appointment(
        self,
        context: RunContext,
        appointment_id: str,
    ) -> str:
        """Cancel an appointment.
        Call this ONLY after the caller confirmed they want to cancel.
        """

        start = perf_counter()

        try:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.delete(
                        f"{API}/appointments/{appointment_id}",
                    )

                    response.raise_for_status()

            except Exception as e:
                logger.error(f"cancel_appointment failed: {e}")

                return "The booking system is not available right now."

            return "The appointment is cancelled."

        finally:
            log_tool_time(
                "cancel_appointment",
                start,
            )

    @function_tool()
    async def check_slow_system(
        self,
        context: RunContext,
    ) -> str:
        """Run a slow system check.
        Use this only when the caller asks for a slow system check.
        """

        start = perf_counter()

        try:
            # Say the filler first so the caller does not hear silence
            await context.session.say(
                "One moment, let me check that for you.",
                allow_interruptions=False,
            )

            try:
                # /slow waits 3 seconds
                async with httpx.AsyncClient(timeout=6.0) as client:
                    response = await client.get(
                        f"{API}/slow"
                    )

                    response.raise_for_status()

            except Exception as e:
                logger.error(
                    f"check_slow_system failed: {e}"
                )

                return "The system is not available right now."

            return "The check is done. The system is working."

        finally:
            log_tool_time(
                "check_slow_system",
                start,
            )

    @function_tool()
    async def check_broken_system(
        self,
        context: RunContext,
    ) -> str:
        """Run a broken system check.
        Use this only when the caller asks for a broken system check.
        """

        start = perf_counter()

        try:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get(
                        f"{API}/broken"
                    )

                    response.raise_for_status()

            except Exception as e:
                logger.error(
                    f"check_broken_system failed: {e}"
                )

                return (
                    "ERROR: the system is not working right now. "
                    "No data is available. Do not guess any result."
                )

            return "The check is done. The system is working."

        finally:
            log_tool_time(
                "check_broken_system",
                start,
            )

    @function_tool()
    async def search_policies(
        self,
        context: RunContext,
        question: str,
    ) -> str:
        """Search the clinic policies.
        Use this for questions about cancellation, late arrival, doctors,
        payment, insurance, what to bring, blood tests, or parking.
        """

        start = perf_counter()

        try:
            try:
                results = await asyncio.to_thread(
                    rag.search,
                    question,
                    TOP_K,
                )

            except Exception as e:
                logger.error(
                    f"search_policies failed: {e}"
                )

                return (
                    "ERROR: the policy search is not working. "
                    "Do not guess the policy."
                )

            if not results:
                return "No policy found for this question."

            return "\n".join(results)

        finally:
            log_tool_time(
                "search_policies",
                start,
            )


server = AgentServer()


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):

    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    print(
        f"Tool timings will be saved to: {TIMING_FILE}"
    )

    print(
        f"Prompt mode: {PROMPT_MODE}, "
        f"words: {len(CLINIC_PROMPT.split())}"
    )

    print(
        f"LLM mode: {LLM_MODE} "
        f"({GROQ_MODEL})"
    )

    # Build the RAG index before the caller speaks
    await asyncio.to_thread(
        rag.build_index
    )

    session = AgentSession(
        stt=inference.STT(
            model="assemblyai/universal-3-5-pro",
            language="en",
        ),

        stt_context_options=STTContextOptions(
            keyterms=["CityCare Clinic"],
            keyterm_detection={
                "enabled": True
            },
        ),

        tts=inference.TTS(
            model="fishaudio/s2.1-pro",
            voice="fa4c9eb3dccc4806b382b40d61c6b10a",
        ),

        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),

            interruption={
                "mode": "adaptive"
            },

            preemptive_generation={
                "enabled": True
            },
        ),

        expressive=True,
    )

    # Day 1 latency logging
    @session.on("conversation_item_added")
    def on_item(
        ev: ConversationItemAddedEvent,
    ):

        if not isinstance(
            ev.item,
            ChatMessage,
        ):
            return

        metrics = ev.item.metrics

        if ev.item.role == "user":
            print(
                f"USER  end_of_turn: "
                f"{metrics.get('end_of_turn_delay')}  "
                f"stt: "
                f"{metrics.get('transcription_delay')}"
            )

        if ev.item.role == "assistant":
            print(
                f"AGENT e2e: "
                f"{metrics.get('e2e_latency')}  "
                f"llm_ttft: "
                f"{metrics.get('llm_node_ttft')}  "
                f"tts_ttfb: "
                f"{metrics.get('tts_node_ttfb')}"
            )

    # Create the agent
    # Tools inside the class are picked up automatically
    agent = FrontDesk()

    await session.start(
        agent=agent,
        room=ctx.room,

        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S
                ),
            ),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(server)
