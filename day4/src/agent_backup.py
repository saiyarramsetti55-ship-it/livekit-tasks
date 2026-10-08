import asyncio
import logging
import textwrap
from dataclasses import dataclass
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
from livekit.plugins import ai_coustics
from livekit.plugins.groq import LLM as GroqLLM


logger = logging.getLogger("citycare-agent")

API = "http://127.0.0.1:8000"

TIMING_FILE = Path(__file__).resolve().parent / "tool_times.csv"

TOP_K = 3

LLM_MODE = "plain"

GROQ_MODEL = "openai/gpt-oss-120b"


load_dotenv(".env.local")


# ============================================================
# CALLER DATA
# ============================================================

@dataclass
class CallerData:
    name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None

    verified: bool = False

    # Identity state:
    # name -> phone -> dob -> ready -> verified
    identity_step: str = "name"

    # Booking state
    pending_service: str | None = None
    pending_date: str | None = None
    pending_time: str | None = None
    booking_confirmed: bool = False

    # Appointment state
    selected_appointment_id: str | None = None
    cancellation_confirmed: bool = False

    # Change appointment state
    change_confirmed: bool = False


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
    - Never invent appointment information.
    - Never invent billing information.
    - Never invent clinic information.

    Safety:

    - Protected appointment and billing information requires identity verification.
    - Never guess caller information.
    - Never use placeholder identity values.
    - Never claim an appointment was booked unless the booking tool succeeds.
    - Never claim an appointment was cancelled unless the cancellation tool succeeds.
    """
)


# ============================================================
# TOOL TIMING
# ============================================================

def log_tool_time(tool_name: str, start: float) -> None:
    ms = (perf_counter() - start) * 1000

    print(f"TOOL {tool_name} took {ms:.0f} ms")

    new_file = not TIMING_FILE.exists()

    with open(TIMING_FILE, "a", encoding="utf-8") as f:
        if new_file:
            f.write("time,tool,ms\n")

        f.write(
            f"{datetime.now().strftime('%H:%M:%S')},"
            f"{tool_name},"
            f"{ms:.0f}\n"
        )


# ============================================================
# LLM
# ============================================================

def build_llm():
    if LLM_MODE == "langgraph":
        from livekit.plugins import langchain
        from .langgraph_llm import build_graph

        return langchain.LLMAdapter(
            build_graph(CLINIC_PROMPT)
        )

    return GroqLLM(
        model=GROQ_MODEL,
        max_retries=1,
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def is_verified(context: RunContext[CallerData]) -> bool:
    return context.session.userdata.verified


def clear_pending_booking(data: CallerData) -> None:
    data.pending_service = None
    data.pending_date = None
    data.pending_time = None
    data.booking_confirmed = False


def clear_cancellation(data: CallerData) -> None:
    data.selected_appointment_id = None
    data.cancellation_confirmed = False


def normalize_phone(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())


def is_placeholder(value: str) -> bool:
    lowered = value.strip().casefold()

    return lowered in {
        "",
        "?",
        "unknown",
        "none",
        "null",
        "n/a",
        "na",
        "name",
        "full name",
        "your name",
        "phone",
        "phone number",
        "date of birth",
        "dob",
    }


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
                - Answer services questions.
                - Answer hours questions.
                - Answer address questions.
                - Answer parking questions.
                - Answer insurance questions.
                - Collect caller identity when required.
                - Verify caller identity.
                - Hand verified callers to BookingAgent.
                - Hand verified callers to BillingAgent.
                - Receive callers back from specialist agents.
                - Ask whether the caller needs anything else.

                GENERAL QUESTIONS:

                If the caller asks about services, hours, address, parking,
                or insurance, answer directly from the clinic information.

                Do NOT start identity verification for general clinic questions.

                IDENTITY VERIFICATION:

                Booking, appointment lookup, appointment changes,
                appointment cancellation, and billing require verification.

                Follow this exact order:

                1. Ask for full name.
                2. Wait for caller response.
                3. Collect the caller's actual name.
                4. Ask for phone number.
                5. Wait for caller response.
                6. Collect the caller's actual phone number.
                7. Ask for date of birth.
                8. Wait for caller response.
                9. Collect the caller's actual date of birth.
                10. Verify the caller.

                IMPORTANT:

                - Never invent identity information.
                - Never guess identity information.
                - Never reuse the agent's own question as an identity value.
                - Never pass "?", "unknown", "none", "n/a", or placeholder values.
                - Never call collect_phone immediately after asking for it.
                - Never call collect_date_of_birth immediately after asking for it.
                - Always wait for the caller's next turn.
                - Never call verify_caller until name, phone and DOB are valid.
                - Never hand off to booking or billing before verification succeeds.

                If verification fails:

                - Do not provide protected information.
                - Do not hand off to booking or billing.
                - Tell the caller that verification failed.
                - Ask them what they would like to do next.

                BOOKING:

                Booking must follow:

                verification
                -> service
                -> date
                -> time
                -> explicit confirmation
                -> booking tool

                Never book without explicit confirmation.

                If the caller says:

                "no"
                "stop"
                "cancel"
                "I changed my mind"
                "don't book it"
                "never mind"

                then do not book the appointment.

                Clear the pending booking and return to reception.

                CANCELLATION:

                Cancellation must follow:

                verification
                -> find appointment
                -> identify appointment
                -> confirm cancellation
                -> cancellation tool

                Never claim that an appointment was cancelled unless
                the cancellation tool succeeds.
                """
            ),
            llm=build_llm(),
        )

    # --------------------------------------------------------
    # GREETING
    # --------------------------------------------------------

    async def on_enter(self):

        await self.session.generate_reply(
            instructions=(
                "Greet the caller. "
                "Say CityCare Clinic. "
                "Ask how you can help."
            )
        )

    # --------------------------------------------------------
    # COLLECT NAME
    # --------------------------------------------------------

    @function_tool()
    async def collect_name(
        self,
        context: RunContext[CallerData],
        name: str,
    ) -> str:

        data = context.session.userdata

        if data.identity_step != "name":
            return (
                "Do not collect the name yet. "
                "Follow the current identity verification step."
            )

        value = (name or "").strip()

        if is_placeholder(value):
            return (
                "No valid caller name was provided. "
                "Ask the caller for their full name and wait for the answer."
            )

        lowered = value.casefold()

        instruction_fragments = (
            "please tell me",
            "please provide",
            "tell me your",
            "provide your",
            "what is your",
            "what's your",
            "what is the caller",
            "caller name",
        )

        if any(fragment in lowered for fragment in instruction_fragments):
            return (
                "No valid caller name was provided. "
                "Ask the caller for their full name and wait."
            )

        if len(value) < 2:
            return (
                "The name is too short. "
                "Ask the caller for their full name."
            )

        if any(ch.isdigit() for ch in value):
            return (
                "The name is not valid. "
                "Ask the caller for their full name."
            )

        data.name = value
        data.verified = False
        data.identity_step = "phone"

        return "Caller name recorded. Ask for the caller's phone number."


    # --------------------------------------------------------
    # COLLECT PHONE
    # --------------------------------------------------------

    @function_tool()
    async def collect_phone(
        self,
        context: RunContext[CallerData],
        phone: str,
    ) -> str:

        data = context.session.userdata

        if data.identity_step != "phone":
            return (
                "Do not collect the phone number yet. "
                "Follow the identity verification order."
            )

        if not data.name:
            return (
                "The caller's name must be collected first."
            )

        value = (phone or "").strip()

        if is_placeholder(value):
            return (
                "No valid phone number was provided. "
                "Ask the caller for their phone number and wait."
            )

        digits = normalize_phone(value)

        if not digits:
            return (
                "No valid phone number was provided. "
                "Ask the caller for their phone number."
            )

        if len(digits) < 10 or len(digits) > 15:
            return (
                "The phone number is not valid. "
                "Ask the caller for a valid phone number."
            )

        data.phone = digits
        data.verified = False
        data.identity_step = "dob"

        return (
            "Phone number recorded. "
            "Ask for the caller's date of birth."
        )


    # --------------------------------------------------------
    # COLLECT DOB
    # --------------------------------------------------------

    @function_tool()
    async def collect_date_of_birth(
        self,
        context: RunContext[CallerData],
        date_of_birth: str,
    ) -> str:

        data = context.session.userdata

        if data.identity_step != "dob":
            return (
                "Do not collect the date of birth yet. "
                "Follow the identity verification order."
            )

        if not data.name or not data.phone:
            return (
                "The caller's name and phone number must be collected first."
            )

        value = (date_of_birth or "").strip()

        if is_placeholder(value):
            return (
                "No valid date of birth was provided. "
                "Ask the caller for their date of birth and wait."
            )

        lowered = value.casefold()

        instruction_fragments = (
            "please tell me",
            "please provide",
            "tell me your",
            "provide your",
            "what is your",
            "what's your",
        )

        if any(fragment in lowered for fragment in instruction_fragments):
            return (
                "No valid date of birth was provided. "
                "Ask the caller for their date of birth."
            )

        normalized = (
            value
            .replace("/", "-")
            .replace(".", "-")
        )

        parsed = None

        formats = (
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m-%d-%Y",
        )

        for fmt in formats:
            try:
                parsed = datetime.strptime(
                    normalized,
                    fmt,
                )
                break
            except ValueError:
                continue

        if parsed is None:
            return (
                "The date of birth is not valid. "
                "Ask the caller to provide it again."
            )

        canonical = parsed.strftime("%Y-%m-%d")

        data.date_of_birth = canonical
        data.verified = False
        data.identity_step = "ready"

        return (
            "Date of birth recorded. "
            "Identity information is ready for verification."
        )


    # --------------------------------------------------------
    # VERIFY CALLER
    # --------------------------------------------------------

    @function_tool()
    async def verify_caller(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if data.identity_step != "ready":
            data.verified = False

            return (
                "Identity verification is incomplete. "
                "Collect the caller's name, phone number, and date of birth first."
            )

        if not data.name:
            data.verified = False
            return "The caller's name is missing."

        if not data.phone:
            data.verified = False
            return "The caller's phone number is missing."

        if not data.date_of_birth:
            data.verified = False
            return "The caller's date of birth is missing."

        expected = {
            "name": "sai",
            "phone": "9999999999",
            "date_of_birth": "2000-01-15",
        }

        name_matches = (
            data.name.strip().casefold()
            == expected["name"]
        )

        phone_matches = (
            data.phone
            == expected["phone"]
        )

        dob_matches = (
            data.date_of_birth
            == expected["date_of_birth"]
        )

        if not (
            name_matches
            and phone_matches
            and dob_matches
        ):
            data.verified = False

            return (
                "Identity verification failed. "
                "I cannot provide protected appointment or billing information."
            )

        data.verified = True
        data.identity_step = "verified"

        return "The caller's identity is verified."


    # --------------------------------------------------------
    # POLICY SEARCH
    # --------------------------------------------------------

    @function_tool()
    async def search_policies(
        self,
        context: RunContext[CallerData],
        question: str,
    ) -> str:

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
                    "search_policies failed: %s",
                    exc,
                )

                return (
                    "The policy search is not working right now."
                )

            if not results:
                return "No policy was found for that question."

            return "\n".join(results)

        finally:

            log_tool_time(
                "search_policies",
                start,
            )


    # --------------------------------------------------------
    # HANDOFF TO BOOKING
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_booking(
        self,
        context: RunContext[CallerData],
    ):

        if not is_verified(context):
            return (
                "The caller must complete identity verification "
                "before booking."
            )

        return (
            BookingAgent(),
            "The caller is verified. Continue with appointment assistance."
        )


    # --------------------------------------------------------
    # HANDOFF TO BILLING
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_billing(
        self,
        context: RunContext[CallerData],
    ):

        if not is_verified(context):
            return (
                "The caller must complete identity verification "
                "before billing."
            )

        return (
            BillingAgent(),
            "The caller is verified. Continue with billing assistance."
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

                IDENTITY:

                The caller must already be verified.

                If the caller is not verified, immediately return them
                to ReceptionAgent for verification.

                BOOKING:

                Before booking, collect:

                1. Service
                2. Date
                3. Time

                Then repeat the appointment details clearly.

                Ask:

                "Would you like me to book this appointment?"

                WAIT for the caller's response.

                Only explicit confirmation such as:

                yes
                yes please
                book it
                that's correct
                confirm
                go ahead

                allows confirmation.

                NEVER book after:

                no
                stop
                cancel
                never mind
                I changed my mind
                don't book
                not now

                If the caller changes their mind:

                - Do not call book_appointment.
                - Clear the pending booking.
                - Tell the caller no appointment was booked.
                - Return to ReceptionAgent.

                NEVER claim an appointment is booked unless
                book_appointment actually succeeds.

                CANCELLATION:

                Before cancelling:

                1. Caller must be verified.
                2. Find the caller's appointments.
                3. Identify the appointment.
                4. Ask for explicit confirmation.
                5. Only then call cancel_appointment.

                NEVER cancel without confirmation.

                NEVER claim cancellation succeeded unless
                cancel_appointment succeeds.

                CHANGE:

                Before changing:

                - Find the appointment.
                - Confirm the appointment.
                - Confirm the new date.
                - Confirm the new time.
                - Then call change_appointment.

                When finished, return to ReceptionAgent.
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

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.get(
                        f"{API}/slots",
                        params={"date": date},
                    )

                    response.raise_for_status()

                    slots = response.json()

            except Exception as exc:

                logger.error(
                    "get_available_slots failed: %s",
                    exc,
                )

                return (
                    "The booking system is not available right now."
                )

            if not slots:
                return "No free times on this date."

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
    # SET BOOKING DETAILS
    # --------------------------------------------------------

    @function_tool()
    async def set_booking_details(
        self,
        context: RunContext[CallerData],
        service: str,
        date: str,
        time: str,
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required before booking."
            )

        service = service.strip()
        date = date.strip()
        time = time.strip()

        if not service:
            return "The service is required."

        if not date:
            return "The appointment date is required."

        if not time:
            return "The appointment time is required."

        data.pending_service = service
        data.pending_date = date
        data.pending_time = time

        data.booking_confirmed = False

        return (
            f"Pending appointment: {service}, "
            f"{date} at {time}. "
            "Ask the caller for explicit confirmation before booking."
        )


    # --------------------------------------------------------
    # CONFIRM BOOKING
    # --------------------------------------------------------

    @function_tool()
    async def confirm_booking(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required before booking."
            )

        if not (
            data.pending_service
            and data.pending_date
            and data.pending_time
        ):
            return (
                "There is no complete pending appointment "
                "to confirm."
            )

        data.booking_confirmed = True

        return (
            "The caller explicitly confirmed the appointment. "
            "The booking may now be submitted."
        )


    # --------------------------------------------------------
    # CANCEL PENDING BOOKING
    # --------------------------------------------------------

    @function_tool()
    async def cancel_pending_booking(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        clear_pending_booking(data)

        return (
            "The pending booking was cancelled. "
            "No appointment was booked."
        )


    # --------------------------------------------------------
    # BOOK APPOINTMENT
    # --------------------------------------------------------

    @function_tool()
    async def book_appointment(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required before booking."
            )

        if not data.booking_confirmed:
            return (
                "The caller has not explicitly confirmed "
                "the appointment. Do not book."
            )

        if not (
            data.pending_service
            and data.pending_date
            and data.pending_time
        ):
            return (
                "The booking details are incomplete. "
                "Do not book the appointment."
            )

        if not data.name or not data.phone:
            return (
                "Verified caller information is incomplete."
            )

        start = perf_counter()

        try:

            try:

                payload = {
                    "name": data.name,
                    "phone": data.phone,
                    "date": data.pending_date,
                    "time": data.pending_time,
                    "service": data.pending_service,
                }

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.post(
                        f"{API}/appointments",
                        json=payload,
                    )

                    response.raise_for_status()

                    result = response.json()

            except Exception as exc:

                logger.error(
                    "book_appointment failed: %s",
                    exc,
                )

                return (
                    "The booking system is not available right now. "
                    "The appointment was not booked."
                )

            appointment_id = result.get("id")

            clear_pending_booking(data)

            return (
                "The appointment was booked successfully."
                if appointment_id is None
                else f"The appointment was booked successfully. "
                     f"Your appointment id is {appointment_id}."
            )

        finally:

            log_tool_time(
                "book_appointment",
                start,
            )


    # --------------------------------------------------------
    # FIND APPOINTMENTS
    # --------------------------------------------------------

    @function_tool()
    async def find_appointments(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required "
                "before viewing appointments."
            )

        if not data.phone:
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
                        f"{API}/appointments",
                        params={"phone": data.phone},
                    )

                    response.raise_for_status()

                    items = response.json()

            except Exception as exc:

                logger.error(
                    "find_appointments failed: %s",
                    exc,
                )

                return (
                    "The booking system is not available right now."
                )

            if not items:

                clear_cancellation(data)

                return (
                    "No appointments were found "
                    "for the verified caller."
                )

            # Store the first available appointment.
            # The agent can ask the caller to confirm it.
            first = items[0]

            data.selected_appointment_id = str(
                first.get("id")
            )

            data.cancellation_confirmed = False
            data.change_confirmed = False

            lines = []

            for appointment in items[:3]:

                lines.append(
                    f"appointment {appointment.get('id')}: "
                    f"{appointment.get('service')} "
                    f"on {appointment.get('date')} "
                    f"at {appointment.get('time')}"
                )

            return (
                "Appointments found: "
                + "; ".join(lines)
            )

        finally:

            log_tool_time(
                "find_appointments",
                start,
            )


    # --------------------------------------------------------
    # CONFIRM CANCELLATION
    # --------------------------------------------------------

    @function_tool()
    async def confirm_cancellation(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required "
                "before cancelling an appointment."
            )

        if not data.selected_appointment_id:
            return (
                "No appointment has been selected for cancellation."
            )

        data.cancellation_confirmed = True

        return (
            "The caller explicitly confirmed the cancellation. "
            "The cancellation may now be submitted."
        )


    # --------------------------------------------------------
    # CANCEL APPOINTMENT
    # --------------------------------------------------------

    @function_tool()
    async def cancel_appointment(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required "
                "before cancelling an appointment."
            )

        if not data.selected_appointment_id:
            return (
                "No appointment has been selected."
            )

        if not data.cancellation_confirmed:
            return (
                "The caller has not explicitly confirmed "
                "the cancellation. Do not cancel."
            )

        appointment_id = data.selected_appointment_id

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.delete(
                        f"{API}/appointments/{appointment_id}"
                    )

                    response.raise_for_status()

            except Exception as exc:

                logger.error(
                    "cancel_appointment failed: %s",
                    exc,
                )

                return (
                    "The cancellation system is not available "
                    "right now. The appointment was not cancelled."
                )

            clear_cancellation(data)

            return (
                "The appointment was cancelled successfully."
            )

        finally:

            log_tool_time(
                "cancel_appointment",
                start,
            )


    # --------------------------------------------------------
    # CHANGE APPOINTMENT
    # --------------------------------------------------------

    @function_tool()
    async def confirm_change(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required "
                "before changing an appointment."
            )

        if not data.selected_appointment_id:
            return (
                "No appointment has been selected."
            )

        data.change_confirmed = True

        return (
            "The caller explicitly confirmed the appointment change."
        )


    @function_tool()
    async def change_appointment(
        self,
        context: RunContext[CallerData],
        date: str,
        time: str,
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required "
                "before changing an appointment."
            )

        if not data.selected_appointment_id:
            return (
                "No appointment has been selected."
            )

        if not data.change_confirmed:
            return (
                "The caller has not explicitly confirmed "
                "the appointment change."
            )

        date = date.strip()
        time = time.strip()

        if not date or not time:
            return (
                "The new date and time are required."
            )

        appointment_id = data.selected_appointment_id

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.patch(
                        f"{API}/appointments/{appointment_id}",
                        json={
                            "date": date,
                            "time": time,
                        },
                    )

                    response.raise_for_status()

            except Exception as exc:

                logger.error(
                    "change_appointment failed: %s",
                    exc,
                )

                return (
                    "The booking system is not available right now. "
                    "The appointment was not changed."
                )

            data.change_confirmed = False
            data.selected_appointment_id = None

            return (
                f"The appointment was changed successfully "
                f"to {date} at {time}."
            )

        finally:

            log_tool_time(
                "change_appointment",
                start,
            )


    # --------------------------------------------------------
    # SLOW SYSTEM TEST
    # --------------------------------------------------------

    @function_tool()
    async def check_slow_system(
        self,
        context: RunContext[CallerData],
    ) -> str:

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
                    "check_slow_system failed: %s",
                    exc,
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
    # BROKEN SYSTEM TEST
    # --------------------------------------------------------

    @function_tool()
    async def check_broken_system(
        self,
        context: RunContext[CallerData],
    ) -> str:

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
                    "check_broken_system failed: %s",
                    exc,
                )

                return (
                    "The system is not working right now."
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
    # HANDOFF TO RECEPTION
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_reception(
        self,
        context: RunContext[CallerData],
    ):

        return (
            ReceptionAgent(),
            "Return to reception and ask whether the caller needs anything else."
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

                The caller must already be verified.

                Always use the verified caller phone number.

                Never ask the caller to provide another phone number
                for billing if a verified phone number already exists.

                Never invent a bill amount.

                Never invent a due date.

                Never invent billing status.

                Do not process payments.

                If no billing information exists, say that no billing
                information is available.

                When finished, return the caller to ReceptionAgent.
                """
            ),
            llm=build_llm(),
        )


    # --------------------------------------------------------
    # GET BILL
    # --------------------------------------------------------

    @function_tool()
    async def get_bill(
        self,
        context: RunContext[CallerData],
    ) -> str:

        data = context.session.userdata

        if not data.verified:
            return (
                "Identity verification is required "
                "before viewing billing information."
            )

        phone = data.phone

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
                        params={"phone": phone},
                    )

                    if response.status_code == 404:
                        return (
                            "No billing information is available "
                            "for the verified caller."
                        )

                    response.raise_for_status()

                    result = response.json()

            except Exception as exc:

                logger.error(
                    "get_bill failed: %s",
                    exc,
                )

                return (
                    "The billing system is not available right now."
                )

            amount = result.get("amount")
            due_date = result.get("due_date")
            status = result.get("status")

            if not amount or not due_date:
                return (
                    "No billing information is available "
                    "for the verified caller."
                )

            if status:
                return (
                    f"Your current bill is {amount}, "
                    f"due on {due_date}. "
                    f"Status: {status}."
                )

            return (
                f"Your current bill is {amount}, "
                f"due on {due_date}."
            )

        finally:

            log_tool_time(
                "get_bill",
                start,
            )


    # --------------------------------------------------------
    # HANDOFF
    # --------------------------------------------------------

    @function_tool()
    async def handoff_to_reception(
        self,
        context: RunContext[CallerData],
    ):

        return (
            ReceptionAgent(),
            "Return to reception and ask whether the caller needs anything else."
        )


# ============================================================
# SERVER
# ============================================================

server = AgentServer()


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):

    ctx.log_context_fields = {
        "room": ctx.room.name
    }

    print(
        f"Tool timings will be saved to: {TIMING_FILE}"
    )

    print(
        f"LLM mode: {LLM_MODE} ({GROQ_MODEL})"
    )

    # Build RAG index without blocking the event loop.
    await asyncio.to_thread(
        rag.build_index
    )

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
            turn_detection=inference.TurnDetector(),

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
    # CONVERSATION METRICS
    # --------------------------------------------------------

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
                "USER "
                f"end_of_turn={metrics.get('end_of_turn_delay')} "
                f"stt={metrics.get('transcription_delay')}"
            )

        elif ev.item.role == "assistant":

            print(
                "AGENT "
                f"e2e={metrics.get('e2e_latency')} "
                f"llm_ttft={metrics.get('llm_node_ttft')} "
                f"tts_ttfb={metrics.get('tts_node_ttfb')}"
            )


    # --------------------------------------------------------
    # START SESSION
    # --------------------------------------------------------

    await session.start(
        agent=ReceptionAgent(),
        room=ctx.room,

        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=ai_coustics.audio_enhancement(
                    model=ai_coustics.EnhancerModel.QUAIL_VF_S
                )
            )
        ),
    )

    await ctx.connect()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    cli.run_app(server)