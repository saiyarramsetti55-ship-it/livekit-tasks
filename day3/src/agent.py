import asyncio
import logging
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

import httpx
from dotenv import load_dotenv
import chromadb
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

API = "http://127.0.0.1:8000"

TIMING_FILE = Path(__file__).resolve().parent / "tool_times.csv"

TOP_K = 3

LLM_MODE = "plain"

GROQ_MODEL = "openai/gpt-oss-120b"

load_dotenv(".env.local")
#load_dotenv(".env")


# ============================================================
# SHARED USER DATA
# ============================================================

@dataclass
class CallerData:
    name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    verified: bool = False


# ============================================================
# CLINIC PROMPT
# ============================================================

CLINIC_PROMPT = textwrap.dedent(
    """
    You are a voice assistant for CityCare Clinic.

    Clinic information:
    - Name: CityCare Clinic
    - Monday to Friday: 8:00 AM to 6:00 PM
    - Saturday: 9:00 AM to 1:00 PM
    - Sunday: Closed
    - Address: 12 Park Road
    - Services: general check-up, blood tests, vaccines, children's doctor
    - Free parking behind the building
    - Most major insurance plans are accepted.

    Voice rules:
    - Speak naturally.
    - Keep responses short.
    - Ask one question at a time.
    - Do not use markdown in spoken responses.
    - Never give medical advice.
    - Never diagnose a condition.
    - Never recommend medication or dosage.
    - Never invent appointment, billing, or clinic information.
    """
)


# ============================================================
# TOOL TIMING
# ============================================================

def log_tool_time(tool_name: str, start: float) -> None:
    """Print and save tool execution time."""

    ms = (perf_counter() - start) * 1000

    print(
        f"TOOL  {tool_name} took {ms:.0f} ms"
    )

    new_file = not TIMING_FILE.exists()

    with open(
        TIMING_FILE,
        "a",
        encoding="utf-8",
    ) as f:

        if new_file:
            f.write("time,tool,ms\n")

        f.write(
            f"{datetime.now().strftime('%H:%M:%S')},"
            f"{tool_name},{ms:.0f}\n"
        )


# ============================================================
# LLM
# ============================================================

def build_llm():

    if LLM_MODE == "langgraph":

        from .langgraph_llm import build_graph

        return langchain.LLMAdapter(
            build_graph(CLINIC_PROMPT)
        )

    return GroqLLM(
        model=GROQ_MODEL
    )


# ============================================================
# VERIFICATION HELPER
# ============================================================

def is_verified(
    context: RunContext[CallerData],
) -> bool:

    return context.session.userdata.verified


# ============================================================
# RECEPTION AGENT
# ============================================================

class ReceptionAgent(Agent):

    def __init__(self) -> None:

        super().__init__(
            instructions=CLINIC_PROMPT
            + textwrap.dedent(
                """
                You are the ReceptionAgent.

                Your responsibilities:

                - Greet the caller.
                - Understand what the caller needs.
                - Answer general clinic questions.
                - Collect caller identity information.
                - Verify caller identity.
                - Answer clinic policy questions.
                - Hand verified callers to BookingAgent.
                - Hand verified callers to BillingAgent.
                - Receive the caller back from specialist agents.
                - Ask whether the caller needs anything else.

                Do not perform appointment operations yourself.

                Do not provide billing information yourself.

                Booking and billing require identity verification.
                """
            ),
            llm=build_llm(),
        )

    async def on_enter(self):

        await self.session.generate_reply(
            instructions=(
                "Greet the caller. "
                "Say CityCare Clinic. "
                "Ask how you can help."
            )
        )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    @function_tool()
    async def collect_name(
        self,
        context: RunContext[CallerData],
        name: str,
    ) -> str:
        """Store the caller's confirmed name."""

        context.session.userdata.name = name.strip()

        context.session.userdata.verified = False

        return (
            f"Name recorded as "
            f"{context.session.userdata.name}."
        )

    # --------------------------------------------------------
    # PHONE
    # --------------------------------------------------------

    @function_tool()
    async def collect_phone(
        self,
        context: RunContext[CallerData],
        phone: str,
    ) -> str:
        """Store the caller's confirmed phone number."""

        context.session.userdata.phone = phone.strip()

        context.session.userdata.verified = False

        return (
            f"Phone number recorded as "
            f"{context.session.userdata.phone}."
        )

    # --------------------------------------------------------
    # DOB
    # --------------------------------------------------------

    @function_tool()
    async def collect_date_of_birth(
        self,
        context: RunContext[CallerData],
        date_of_birth: str,
    ) -> str:
        """Store the caller's confirmed date of birth."""

        context.session.userdata.date_of_birth = (
            date_of_birth.strip()
        )

        context.session.userdata.verified = False

        return (
            "Date of birth recorded as "
            f"{context.session.userdata.date_of_birth}."
        )

    # --------------------------------------------------------
    # VERIFY
    # --------------------------------------------------------

    @function_tool()
    async def verify_caller(
        self,
        context: RunContext[CallerData],
    ) -> str:
        """Verify caller identity."""

        data = context.session.userdata

        if (
            not data.name
            or not data.phone
            or not data.date_of_birth
        ):

            data.verified = False

            return (
                "Identity verification is incomplete. "
                "Please collect the caller's name, "
                "phone number, and date of birth."
            )

        data.verified = True

        return "The caller's identity is verified."

    # --------------------------------------------------------
    # RAG POLICIES
    # --------------------------------------------------------

    @function_tool()
    async def search_policies(
        self,
        context: RunContext[CallerData],
        question: str,
    ) -> str:
        """Search CityCare policies."""

        start = perf_counter()

        try:

            try:

                results = await asyncio.to_thread(
                    rag.search,
                    question,
                    TOP_K,
                )

            except Exception as exc:

                logger.error(
                    f"search_policies failed: {exc}"
                )

                return (
                    "The policy search is not "
                    "working right now."
                )

            if not results:

                return (
                    "No policy was found "
                    "for that question."
                )

            return "\n".join(results)

        finally:

            log_tool_time(
                "search_policies",
                start,
            )

    # --------------------------------------------------------
    # RECEPTION -> BOOKING
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_booking(
        self,
        context: RunContext[CallerData],
    ):

        if not is_verified(context):

            return (
                "The caller must complete identity "
                "verification before booking."
            )

        return (
            BookingAgent(),
            "The caller is verified. "
            "Continue with appointment assistance.",
        )

    # --------------------------------------------------------
    # RECEPTION -> BILLING
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_billing(
        self,
        context: RunContext[CallerData],
    ):

        if not is_verified(context):

            return (
                "The caller must complete identity "
                "verification before billing."
            )

        return (
            BillingAgent(),
            "The caller is verified. "
            "Continue with billing assistance.",
        )


# ============================================================
# BOOKING AGENT
# ============================================================

class BookingAgent(Agent):

    def __init__(self) -> None:

        super().__init__(
            instructions=CLINIC_PROMPT
            + textwrap.dedent(
                """
                You are the BookingAgent.

                You handle:

                - Appointment availability
                - Appointment booking
                - Finding appointments
                - Changing appointments
                - Cancelling appointments

                Before booking:
                - Confirm service.
                - Confirm date.
                - Confirm time.
                - Ask if the information is correct.

                Before changing or cancelling:
                - Find the appointment.
                - Confirm it with the caller.

                Never expose appointment IDs unless requested.

                When finished, return the caller to ReceptionAgent.
                """
            ),
            llm=build_llm(),
        )

    # --------------------------------------------------------
    # AVAILABLE SLOTS
    # --------------------------------------------------------

    @function_tool()
    async def get_available_slots(
        self,
        context: RunContext[CallerData],
        date: str,
    ) -> str:
        """Find free appointment times."""

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.get(
                        f"{API}/slots",
                        params={
                            "date": date
                        },
                    )

                    response.raise_for_status()

                    slots = response.json()

            except Exception as exc:

                logger.error(
                    f"get_available_slots failed: {exc}"
                )

                return (
                    "The booking system is not "
                    "available right now."
                )

            if not slots:

                return (
                    "No free times on this date."
                )

            return (
                "Free times: "
                + ", ".join(slots[:5])
            )

        finally:

            log_tool_time(
                "get_available_slots",
                start,
            )

    # --------------------------------------------------------
    # BOOK
    # --------------------------------------------------------

    @function_tool()
    async def book_appointment(
        self,
        context: RunContext[CallerData],
        name: str,
        phone: str,
        date: str,
        time: str,
        service: str,
    ) -> str:
        """Book an appointment."""

        if not is_verified(context):

            return (
                "Identity verification is "
                "required before booking."
            )

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

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

            except Exception as exc:

                logger.error(
                    f"book_appointment failed: {exc}"
                )

                return (
                    "The booking system is not "
                    "available right now."
                )

            return (
                "Booked. "
                f"The appointment id is "
                f"{data.get('id')}."
            )

        finally:

            log_tool_time(
                "book_appointment",
                start,
            )

    # --------------------------------------------------------
    # FIND
    # --------------------------------------------------------

    @function_tool()
    async def find_appointments(
        self,
        context: RunContext[CallerData],
        phone: str,
    ) -> str:
        """Find caller appointments."""

        if not is_verified(context):

            return (
                "Identity verification is "
                "required before viewing appointments."
            )

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.get(
                        f"{API}/appointments",
                        params={
                            "phone": phone
                        },
                    )

                    response.raise_for_status()

                    items = response.json()

            except Exception as exc:

                logger.error(
                    f"find_appointments failed: {exc}"
                )

                return (
                    "The booking system is not "
                    "available right now."
                )

            if not items:

                return (
                    "No appointments found "
                    "for this phone number."
                )

            lines = [
                f"id {a.get('id')}: "
                f"{a.get('service')} on "
                f"{a.get('date')} at "
                f"{a.get('time')}"
                for a in items[:3]
            ]

            return (
                "Appointments: "
                + "; ".join(lines)
            )

        finally:

            log_tool_time(
                "find_appointments",
                start,
            )

    # --------------------------------------------------------
    # CHANGE
    # --------------------------------------------------------

    @function_tool()
    async def change_appointment(
        self,
        context: RunContext[CallerData],
        appointment_id: str,
        date: str,
        time: str,
    ) -> str:
        """Change appointment date and time."""

        if not is_verified(context):

            return (
                "Identity verification is "
                "required before changing an appointment."
            )

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.patch(
                        f"{API}/appointments/"
                        f"{appointment_id}",
                        json={
                            "date": date,
                            "time": time,
                        },
                    )

                    response.raise_for_status()

            except Exception as exc:

                logger.error(
                    f"change_appointment failed: {exc}"
                )

                return (
                    "The booking system is not "
                    "available right now."
                )

            return (
                "Done. The appointment is now on "
                f"{date} at {time}."
            )

        finally:

            log_tool_time(
                "change_appointment",
                start,
            )

    # --------------------------------------------------------
    # CANCEL
    # --------------------------------------------------------

    @function_tool()
    async def cancel_appointment(
        self,
        context: RunContext[CallerData],
        appointment_id: str,
    ) -> str:
        """Cancel an appointment."""

        if not is_verified(context):

            return (
                "Identity verification is "
                "required before cancelling an appointment."
            )

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.delete(
                        f"{API}/appointments/"
                        f"{appointment_id}"
                    )

                    response.raise_for_status()

            except Exception as exc:

                logger.error(
                    f"cancel_appointment failed: {exc}"
                )

                return (
                    "The booking system is not "
                    "available right now."
                )

            return (
                "The appointment is cancelled."
            )

        finally:

            log_tool_time(
                "cancel_appointment",
                start,
            )

    # --------------------------------------------------------
    # SLOW SYSTEM
    # --------------------------------------------------------

    @function_tool()
    async def check_slow_system(
        self,
        context: RunContext[CallerData],
    ) -> str:
        """Run the slow system check."""

        start = perf_counter()

        try:

            await context.session.say(
                "One moment, let me check that for you.",
                allow_interruptions=False,
            )

            try:

                async with httpx.AsyncClient(
                    timeout=6.0
                ) as client:

                    response = await client.get(
                        f"{API}/slow"
                    )

                    response.raise_for_status()

            except Exception as exc:

                logger.error(
                    f"check_slow_system failed: {exc}"
                )

                return (
                    "The system is not available right now."
                )

            return (
                "The check is done. "
                "The system is working."
            )

        finally:

            log_tool_time(
                "check_slow_system",
                start,
            )

    # --------------------------------------------------------
    # BROKEN SYSTEM
    # --------------------------------------------------------

    @function_tool()
    async def check_broken_system(
        self,
        context: RunContext[CallerData],
    ) -> str:
        """Run the broken system check."""

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.get(
                        f"{API}/broken"
                    )

                    response.raise_for_status()

            except Exception as exc:

                logger.error(
                    f"check_broken_system failed: {exc}"
                )

                return (
                    "The system is not "
                    "working right now."
                )

            return (
                "The check is done. "
                "The system is working."
            )

        finally:

            log_tool_time(
                "check_broken_system",
                start,
            )

    # --------------------------------------------------------
    # BOOKING -> RECEPTION
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_reception(
        self,
        context: RunContext[CallerData],
    ):

        return (
            ReceptionAgent(),
            "Return to reception and ask "
            "whether the caller needs anything else.",
        )


# ============================================================
# BILLING AGENT
# ============================================================

class BillingAgent(Agent):

    def __init__(self) -> None:

        super().__init__(
            instructions=CLINIC_PROMPT
            + textwrap.dedent(
                """
                You are the BillingAgent.

                You handle billing questions only.

                Use the verified caller phone number.

                Never invent a bill amount or due date.

                Do not process payments.

                When finished, return the caller to ReceptionAgent.
                """
            ),
            llm=build_llm(),
        )

    # --------------------------------------------------------
    # BILL
    # --------------------------------------------------------

    @function_tool()
    async def get_bill(
        self,
        context: RunContext[CallerData],
    ) -> str:
        """Get the caller's bill."""

        if not is_verified(context):

            return (
                "Identity verification is "
                "required before viewing billing information."
            )

        phone = context.session.userdata.phone

        if not phone:

            return (
                "A verified phone number is required."
            )

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.get(
                        f"{API}/bills",
                        params={
                            "phone": phone
                        },
                    )

                    response.raise_for_status()

                    data = response.json()

            except Exception as exc:

                logger.error(
                    f"get_bill failed: {exc}"
                )

                return (
                    "The billing system is "
                    "not available right now."
                )

            return (
                f"Your current bill is "
                f"{data.get('amount')}, "
                f"due on {data.get('due_date')}."
            )

        finally:

            log_tool_time(
                "get_bill",
                start,
            )

    # --------------------------------------------------------
    # BILLING -> RECEPTION
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_reception(
        self,
        context: RunContext[CallerData],
    ):

        return (
            ReceptionAgent(),
            "Return to reception and ask "
            "whether the caller needs anything else.",
        )


# ============================================================
# SERVER
# ============================================================

server = AgentServer()


@server.rtc_session(
    agent_name="my-agent"
)
async def my_agent(
    ctx: JobContext,
):

    ctx.log_context_fields = {
        "room": ctx.room.name
    }

    print(
        f"Tool timings will be saved to: "
        f"{TIMING_FILE}"
    )

    print(
        f"LLM mode: {LLM_MODE} "
        f"({GROQ_MODEL})"
    )

    # Build RAG index before caller speaks.

    await asyncio.to_thread(
        rag.build_index
    )

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    session = AgentSession[CallerData](
        userdata=CallerData(),

        stt=inference.STT(
            model="assemblyai/universal-3-5-pro",
            language="en",
        ),

        stt_context_options=STTContextOptions(
            keyterms=[
                "CityCare Clinic",
                "CityCare",
                "Dr. Smith",
                "Dr. Patel",
                "Dr. Williams",
                "general check-up",
                "blood tests",
                "children's doctor",
            ],

            keyterm_detection={
                "enabled": True
            },
        ),

        tts=inference.TTS(
            model="fishaudio/s2.1-pro",
            voice="fa4c9eb3dccc4806b382b40d61c6b10a",
        ),

        turn_handling=TurnHandlingOptions(

            turn_detection=(
                inference.TurnDetector()
            ),

            endpointing={
                "mode": "fixed",
                "min_delay": 0.5,
                "max_delay": 3.0,
            },

            interruption={
                "mode": "adaptive"
            },

            preemptive_generation={
                "enabled": True
            },
        ),

        expressive=True,
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    @session.on(
        "conversation_item_added"
    )
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
                f"USER "
                f"end_of_turn="
                f"{metrics.get('end_of_turn_delay')} "
                f"stt="
                f"{metrics.get('transcription_delay')}"
            )

        elif ev.item.role == "assistant":

            print(
                f"AGENT "
                f"e2e="
                f"{metrics.get('e2e_latency')} "
                f"llm_ttft="
                f"{metrics.get('llm_node_ttft')} "
                f"tts_ttfb="
                f"{metrics.get('tts_node_ttfb')}"
            )

    # --------------------------------------------------------
    # START WITH RECEPTION
    # --------------------------------------------------------

    await session.start(
        agent=ReceptionAgent(),

        room=ctx.room,

        room_options=room_io.RoomOptions(

            audio_input=(
                room_io.AudioInputOptions(

                    noise_cancellation=(
                        ai_coustics.audio_enhancement(
                            model=(
                                ai_coustics
                                .EnhancerModel
                                .QUAIL_VF_S
                            )
                        )
                    )
                )
            )
        ),
    )

    await ctx.connect()


if __name__ == "__main__":

    cli.run_app(server)