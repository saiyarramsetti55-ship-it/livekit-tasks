# import asyncio
# import logging
# import textwrap
# from datetime import datetime
# from pathlib import Path
# from time import perf_counter

# import httpx
# from dotenv import load_dotenv
# from . import rag
# from livekit.agents import (
#     Agent,
#     AgentServer,
#     AgentSession,
#     ConversationItemAddedEvent,
#     JobContext,
#     RunContext,
#     STTContextOptions,
#     TurnHandlingOptions,
#     cli,
#     function_tool,
#     inference,
#     room_io,
# )
# from livekit.agents.llm import ChatMessage
# from livekit.plugins import ai_coustics, langchain
# from livekit.plugins.groq import LLM as GroqLLM


# logger = logging.getLogger("citycare-agent")


# # Backend address (FastAPI)
# API = "http://127.0.0.1:8000"


# # Tool timings are saved here
# TIMING_FILE = Path(__file__).resolve().parent / "tool_times.csv"


# # How many policy results the RAG tool returns
# # 3 = normal, 10 = for the test
# TOP_K = 3


# # Step 10:
# # "long" = before
# # "short" = after
# PROMPT_MODE = "long"


# # Step 11:
# # "plain" = Groq without LangGraph
# # "langgraph" = Groq with LangGraph
# LLM_MODE = "plain"


# # Groq model
# GROQ_MODEL = "openai/gpt-oss-20b"

# # Load environment variables
# load_dotenv(".env.local")
# load_dotenv(".env")


# def log_tool_time(tool_name: str, start: float) -> None:
#     """Print and save how long a tool took, in milliseconds."""

#     ms = (perf_counter() - start) * 1000

#     print(f"TOOL  {tool_name} took {ms:.0f} ms")

#     new_file = not TIMING_FILE.exists()

#     with open(TIMING_FILE, "a", encoding="utf-8") as f:
#         if new_file:
#             f.write("time,tool,ms\n")

#         f.write(
#             f"{datetime.now().strftime('%H:%M:%S')},"
#             f"{tool_name},{ms:.0f}\n"
#         )


# # ---------------------------------------------------------------
# # LONG prompt
# # ---------------------------------------------------------------

# CLINIC_PROMPT_LONG = textwrap.dedent(
#     """
#     You are the front desk voice assistant for CityCare Clinic.

#     Clinic information:
#     - Name: CityCare Clinic
#     - Hours: Monday to Friday, 8:00 AM to 6:00 PM
#     - Saturday: 9:00 AM to 1:00 PM
#     - Sunday: Closed
#     - Address: 12 Park Road
#     - Services: general check-up, blood tests, vaccines, and children's doctor
#     - Parking: free parking behind the building
#     - Insurance: most major insurance plans are accepted

#     Voice response rules:
#     - Answer in 1 to 3 short sentences.
#     - Use natural spoken language.
#     - Do not use markdown, lists, emojis, or complicated formatting.
#     - Ask only one question at a time.
#     - Keep answers concise.

#     Scope:
#     - Only talk about CityCare Clinic and its services.
#     - If the user asks about something unrelated to the clinic,
#       politely say that you can only help with CityCare Clinic questions.

#     Medical safety:
#     - Never give medical advice.
#     - Never diagnose a medical condition.
#     - Never recommend a medicine or dosage.
#     - If the user asks for medical advice, politely say that you
#       cannot provide medical advice and suggest booking a visit
#       with a qualified healthcare professional.

#     If the user asks about clinic information, use only the
#     information provided above.

#     BOOKING RULE:
#     Before you call book_appointment, you must do these 3 things:
#     1. Repeat the service, date and time to the caller.
#     2. Ask: "Is this correct?"
#     3. Call book_appointment only after the caller says yes.
#     If the caller says no, ask what they want to change.

#     CHANGE AND CANCEL RULE:
#     1. Ask for the caller's phone number.
#     2. Call find_appointments to get the appointment id.
#     3. Repeat the appointment and ask: "Is this correct?"
#     4. Call change_appointment or cancel_appointment only after the caller says yes.
#     Never say the appointment id out loud unless the caller asks.

#     ERROR RULE:
#     If a tool returns an error or says the system is not available:
#     1. Say sorry in one short sentence.
#     2. Explain simply that the system is not working right now.
#     3. Offer to help with something else, or ask the caller to try again later.
#     Never invent appointment times, booking results, or any other data.
#     Never say technical words like "500" or "server error".

#     SLOW TOOL RULE:
#     The tool check_slow_system says its own waiting sentence.
#     Do not say any waiting sentence yourself before calling it.

#     POLICY RULE:
#     For questions about cancellation, late arrival, doctors, payment,
#     insurance, what to bring, blood tests, or parking, call search_policies.
#     Answer only with what the tool returns. If it does not contain the
#     answer, say you do not know and suggest calling the clinic.
#     """
# )


# # ---------------------------------------------------------------
# # SHORT prompt
# # ---------------------------------------------------------------

# CLINIC_PROMPT_SHORT = textwrap.dedent(
#     """
#     You are the front desk voice assistant for CityCare Clinic.
#     Hours: Mon-Fri 8 AM to 6 PM, Sat 9 AM to 1 PM, Sunday closed.
#     Address: 12 Park Road.
#     Services: general check-up, blood tests, vaccines, children's doctor.

#     Style: 1 to 3 short spoken sentences, no lists or markdown,
#     one question at a time. Only talk about CityCare Clinic.
#     Never give medical advice or diagnosis; suggest seeing a doctor.

#     Booking: before book_appointment, repeat service, date and time,
#     ask "Is this correct?", and book only after a yes.

#     Change or cancel: ask the phone number, call find_appointments,
#     confirm, then call change_appointment or cancel_appointment
#     only after a yes. Do not say the appointment id unless asked.

#     Policies (cancellation, late arrival, doctors, payment, insurance,
#     what to bring, blood tests, parking): call search_policies and answer
#     only from the result. If unknown, suggest calling the clinic.

#     Errors: if a tool fails, say sorry, explain simply that the system
#     is not working, and never invent data or say technical words.

#     check_slow_system says its own waiting sentence, so do not say one.
#     """
# )


# CLINIC_PROMPT = (
#     CLINIC_PROMPT_LONG
#     if PROMPT_MODE == "long"
#     else CLINIC_PROMPT_SHORT
# )


# def build_llm():
#     """Choose the LLM. Both modes use the same Groq model."""

#     if LLM_MODE == "langgraph":
#         from langgraph_llm import build_graph

#         # Graph: classify intent -> answer
#         # Uses Groq inside langgraph_llm.py
#         return langchain.LLMAdapter(
#             build_graph(CLINIC_PROMPT)
#         )

#     # Plain mode: use Groq directly
#     # This replaces the old openai.LLM.with_groq() approach
#     return GroqLLM(model=GROQ_MODEL)


# class FrontDesk(Agent):

#     def __init__(self) -> None:
#         super().__init__(
#             instructions=CLINIC_PROMPT,
#             llm=build_llm(),
#         )

#     async def on_enter(self):
#         await self.session.generate_reply(
#             instructions=(
#                 "Greet the caller. Say the clinic name. "
#                 "Ask how you can help."
#             )
#         )

#     @function_tool()
#     async def get_available_slots(
#         self,
#         context: RunContext,
#         date: str,
#     ) -> str:
#         """Find free appointment times on a date.
#         Use this before you book. date format: YYYY-MM-DD.
#         """

#         start = perf_counter()

#         try:
#             try:
#                 async with httpx.AsyncClient(timeout=2.0) as client:
#                     response = await client.get(
#                         f"{API}/slots",
#                         params={"date": date},
#                     )

#                     response.raise_for_status()
#                     slots = response.json()

#             except Exception as e:
#                 logger.error(f"get_available_slots failed: {e}")

#                 return "The booking system is not available right now."

#             if not slots:
#                 return "No free times on this date."

#             return "Free times: " + ", ".join(slots[:5])

#         finally:
#             log_tool_time(
#                 "get_available_slots",
#                 start,
#             )

#     @function_tool()
#     async def book_appointment(
#         self,
#         context: RunContext,
#         name: str,
#         phone: str,
#         date: str,
#         time: str,
#         service: str,
#     ) -> str:
#         """Book an appointment.
#         Call this ONLY after the caller has confirmed the date and time.
#         date format: YYYY-MM-DD, time format: HH:MM.
#         """

#         start = perf_counter()

#         try:
#             try:
#                 async with httpx.AsyncClient(timeout=2.0) as client:
#                     response = await client.post(
#                         f"{API}/appointments",
#                         json={
#                             "name": name,
#                             "phone": phone,
#                             "date": date,
#                             "time": time,
#                             "service": service,
#                         },
#                     )

#                     response.raise_for_status()
#                     data = response.json()

#             except Exception as e:
#                 logger.error(f"book_appointment failed: {e}")

#                 return "The booking system is not available right now."

#             return f"Booked. The appointment id is {data.get('id')}."

#         finally:
#             log_tool_time(
#                 "book_appointment",
#                 start,
#             )

#     @function_tool()
#     async def find_appointments(
#         self,
#         context: RunContext,
#         phone: str,
#     ) -> str:
#         """Find the appointments of a caller by phone number.
#         Use this before you change or cancel an appointment.
#         """

#         start = perf_counter()

#         try:
#             try:
#                 async with httpx.AsyncClient(timeout=2.0) as client:
#                     response = await client.get(
#                         f"{API}/appointments",
#                         params={"phone": phone},
#                     )

#                     response.raise_for_status()
#                     items = response.json()

#             except Exception as e:
#                 logger.error(f"find_appointments failed: {e}")

#                 return "The booking system is not available right now."

#             if not items:
#                 return "No appointments found for this phone number."

#             lines = [
#                 f"id {a.get('id')}: "
#                 f"{a.get('service')} on "
#                 f"{a.get('date')} at "
#                 f"{a.get('time')}"
#                 for a in items[:3]
#             ]

#             return "Appointments: " + "; ".join(lines)

#         finally:
#             log_tool_time(
#                 "find_appointments",
#                 start,
#             )

#     @function_tool()
#     async def change_appointment(
#         self,
#         context: RunContext,
#         appointment_id: str,
#         date: str,
#         time: str,
#     ) -> str:
#         """Change the date and time of an existing appointment.
#         Call this ONLY after the caller confirmed the new date and time.
#         date format: YYYY-MM-DD, time format: HH:MM.
#         """

#         start = perf_counter()

#         try:
#             try:
#                 async with httpx.AsyncClient(timeout=2.0) as client:
#                     response = await client.patch(
#                         f"{API}/appointments/{appointment_id}",
#                         json={
#                             "date": date,
#                             "time": time,
#                         },
#                     )

#                     response.raise_for_status()

#             except Exception as e:
#                 logger.error(f"change_appointment failed: {e}")

#                 return "The booking system is not available right now."

#             return (
#                 f"Done. The appointment is now on "
#                 f"{date} at {time}."
#             )

#         finally:
#             log_tool_time(
#                 "change_appointment",
#                 start,
#             )

#     @function_tool()
#     async def cancel_appointment(
#         self,
#         context: RunContext,
#         appointment_id: str,
#     ) -> str:
#         """Cancel an appointment.
#         Call this ONLY after the caller confirmed they want to cancel.
#         """

#         start = perf_counter()

#         try:
#             try:
#                 async with httpx.AsyncClient(timeout=2.0) as client:
#                     response = await client.delete(
#                         f"{API}/appointments/{appointment_id}",
#                     )

#                     response.raise_for_status()

#             except Exception as e:
#                 logger.error(f"cancel_appointment failed: {e}")

#                 return "The booking system is not available right now."

#             return "The appointment is cancelled."

#         finally:
#             log_tool_time(
#                 "cancel_appointment",
#                 start,
#             )

#     @function_tool()
#     async def check_slow_system(
#         self,
#         context: RunContext,
#     ) -> str:
#         """Run a slow system check.
#         Use this only when the caller asks for a slow system check.
#         """

#         start = perf_counter()

#         try:
#             # Say the filler first so the caller does not hear silence
#             await context.session.say(
#                 "One moment, let me check that for you.",
#                 allow_interruptions=False,
#             )

#             try:
#                 # /slow waits 3 seconds
#                 async with httpx.AsyncClient(timeout=6.0) as client:
#                     response = await client.get(
#                         f"{API}/slow"
#                     )

#                     response.raise_for_status()

#             except Exception as e:
#                 logger.error(
#                     f"check_slow_system failed: {e}"
#                 )

#                 return "The system is not available right now."

#             return "The check is done. The system is working."

#         finally:
#             log_tool_time(
#                 "check_slow_system",
#                 start,
#             )

#     @function_tool()
#     async def check_broken_system(
#         self,
#         context: RunContext,
#     ) -> str:
#         """Run a broken system check.
#         Use this only when the caller asks for a broken system check.
#         """

#         start = perf_counter()

#         try:
#             try:
#                 async with httpx.AsyncClient(timeout=2.0) as client:
#                     response = await client.get(
#                         f"{API}/broken"
#                     )

#                     response.raise_for_status()

#             except Exception as e:
#                 logger.error(
#                     f"check_broken_system failed: {e}"
#                 )

#                 return (
#                     "ERROR: the system is not working right now. "
#                     "No data is available. Do not guess any result."
#                 )

#             return "The check is done. The system is working."

#         finally:
#             log_tool_time(
#                 "check_broken_system",
#                 start,
#             )

#     @function_tool()
#     async def search_policies(
#         self,
#         context: RunContext,
#         question: str,
#     ) -> str:
#         """Search the clinic policies.
#         Use this for questions about cancellation, late arrival, doctors,
#         payment, insurance, what to bring, blood tests, or parking.
#         """

#         start = perf_counter()

#         try:
#             try:
#                 results = await asyncio.to_thread(
#                     rag.search,
#                     question,
#                     TOP_K,
#                 )

#             except Exception as e:
#                 logger.error(
#                     f"search_policies failed: {e}"
#                 )

#                 return (
#                     "ERROR: the policy search is not working. "
#                     "Do not guess the policy."
#                 )

#             if not results:
#                 return "No policy found for this question."

#             return "\n".join(results)

#         finally:
#             log_tool_time(
#                 "search_policies",
#                 start,
#             )


# server = AgentServer()


# @server.rtc_session(agent_name="my-agent")
# async def my_agent(ctx: JobContext):

#     ctx.log_context_fields = {
#         "room": ctx.room.name,
#     }

#     print(
#         f"Tool timings will be saved to: {TIMING_FILE}"
#     )

#     print(
#         f"Prompt mode: {PROMPT_MODE}, "
#         f"words: {len(CLINIC_PROMPT.split())}"
#     )

#     print(
#         f"LLM mode: {LLM_MODE} "
#         f"({GROQ_MODEL})"
#     )

#     # Build the RAG index before the caller speaks
#     await asyncio.to_thread(
#         rag.build_index
#     )

#     session = AgentSession(
#         stt=inference.STT(
#             model="assemblyai/universal-3-5-pro",
#             language="en",
#         ),

#         stt_context_options=STTContextOptions(
#             keyterms=["CityCare Clinic"],
#             keyterm_detection={
#                 "enabled": True
#             },
#         ),

#         tts=inference.TTS(
#             model="fishaudio/s2.1-pro",
#             voice="fa4c9eb3dccc4806b382b40d61c6b10a",
#         ),

#         turn_handling=TurnHandlingOptions(
#             turn_detection=inference.TurnDetector(),

#             interruption={
#                 "mode": "adaptive"
#             },

#             preemptive_generation={
#                 "enabled": True
#             },
#         ),

#         expressive=True,
#     )

#     # Day 1 latency logging
#     @session.on("conversation_item_added")
#     def on_item(
#         ev: ConversationItemAddedEvent,
#     ):

#         if not isinstance(
#             ev.item,
#             ChatMessage,
#         ):
#             return

#         metrics = ev.item.metrics

#         if ev.item.role == "user":
#             print(
#                 f"USER  end_of_turn: "
#                 f"{metrics.get('end_of_turn_delay')}  "
#                 f"stt: "
#                 f"{metrics.get('transcription_delay')}"
#             )

#         if ev.item.role == "assistant":
#             print(
#                 f"AGENT e2e: "
#                 f"{metrics.get('e2e_latency')}  "
#                 f"llm_ttft: "
#                 f"{metrics.get('llm_node_ttft')}  "
#                 f"tts_ttfb: "
#                 f"{metrics.get('tts_node_ttfb')}"
#             )

#     # Create the agent
#     # Tools inside the class are picked up automatically
#     agent = FrontDesk()

#     await session.start(
#         agent=agent,
#         room=ctx.room,

#         room_options=room_io.RoomOptions(
#             audio_input=room_io.AudioInputOptions(
#                 noise_cancellation=ai_coustics.audio_enhancement(
#                     model=ai_coustics.EnhancerModel.QUAIL_VF_S
#                 ),
#             ),
#         ),
#     )

#     await ctx.connect()


# if __name__ == "__main__":
#     cli.run_app(server)




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
from livekit.plugins import ai_coustics, langchain
from livekit.plugins.groq import LLM as GroqLLM


logger = logging.getLogger("citycare-agent")


# ===============================================================
# CONFIGURATION
# ===============================================================

API = "http://127.0.0.1:8000"

TIMING_FILE = Path(__file__).resolve().parent / "tool_times.csv"

TOP_K = 3

PROMPT_MODE = "long"

LLM_MODE = "plain"

GROQ_MODEL = "openai/gpt-oss-20b"


load_dotenv(".env.local")
load_dotenv(".env")


# ===============================================================
# SESSION STATE
# ===============================================================

@dataclass
class CallerData:
    name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None

    verified: bool = False

    # Current appointment workflow
    intent: str | None = None

    # Booking data
    service: str | None = None
    booking_date: str | None = None
    booking_time: str | None = None

    # Appointment selected for change/cancel
    appointment_id: str | None = None

    # Whether user confirmed the action
    confirmation_received: bool = False


# ===============================================================
# TOOL TIMING
# ===============================================================

def log_tool_time(tool_name: str, start: float) -> None:
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


# ===============================================================
# HELPER: RECENT USER TEXT
# ===============================================================

def recent_user_text(agent: Agent) -> str:
    """
    Return the latest user messages from the conversation.

    This is used as a safety check so the LLM cannot simply invent
    identity information such as 'John Doe'.
    """

    try:
        items = agent.chat_ctx.items

        messages = []

        for item in items[-8:]:
            if getattr(item, "type", None) != "message":
                continue

            if getattr(item, "role", None) != "user":
                continue

            text = getattr(item, "text_content", None)

            if text:
                messages.append(text)

        return " ".join(messages)

    except Exception:
        return ""


# ===============================================================
# MAIN PROMPT
# ===============================================================

CLINIC_PROMPT_LONG = textwrap.dedent(
    """
    You are the front desk voice assistant for CityCare Clinic.

    CLINIC INFORMATION:
    - Name: CityCare Clinic
    - Hours: Monday to Friday, 8:00 AM to 6:00 PM
    - Saturday: 9:00 AM to 1:00 PM
    - Sunday: Closed
    - Address: 12 Park Road
    - Services: general check-up, blood tests, vaccines, and children's doctor
    - Parking: free parking behind the building
    - Insurance: most major insurance plans are accepted

    VOICE STYLE:
    - Speak naturally.
    - Use 1 to 3 short sentences.
    - No markdown.
    - No lists.
    - Ask only one question at a time.
    - Do not leave the caller waiting after a tool result.
    - After every tool result, continue the conversation with a short spoken response.

    SCOPE:
    - Only help with CityCare Clinic.
    - If unrelated, politely say that you can only help with CityCare Clinic.

    MEDICAL SAFETY:
    - Never diagnose.
    - Never give medical advice.
    - Never recommend medicine or dosage.
    - If asked for medical advice, say you cannot provide medical advice and
      suggest speaking with a qualified healthcare professional.
    - Do not call search_policies for medical advice.

    PUBLIC CLINIC INFORMATION:
    - Answer clinic name, hours, address, services, parking, and general
      clinic information directly from the information above.
    - DO NOT call search_policies for hours or services.
    - search_policies is only for specific policy questions.

    ===============================================================
    IDENTITY RULE
    ===============================================================

    NEVER invent the caller's name.

    NEVER invent the caller's phone number.

    NEVER invent the caller's date of birth.

    If the caller has not provided a required identity field, ASK for it.

    If a tool rejects an identity value because it was not spoken by the caller,
    ask the caller for that information.

    For protected appointment actions, collect:

    1. Name
    2. Phone number
    3. Date of birth

    Then call verify_identity.

    Do not say that the caller is verified unless verify_identity returns success.

    ===============================================================
    BOOKING WORKFLOW
    ===============================================================

    When the caller wants to book:

    Step 1:
    Ask for the caller's name if it is not known.

    Step 2:
    Ask for the phone number if it is not known.

    Step 3:
    Ask for date of birth if it is not known.

    Step 4:
    Verify the identity.

    Step 5:
    Ask what service they want if it is not known.

    Step 6:
    Ask for the appointment date if it is not known.

    Step 7:
    Call get_available_slots.

    Step 8:
    Ask for a time from the available times.

    Step 9:
    Repeat:
    service, date, and time.

    Step 10:
    Ask exactly:
    "Is this correct?"

    Step 11:
    Only after the caller clearly says yes, call book_appointment.

    If the caller says no:
    - Do not book.
    - Ask what they want to change.

    If the caller says they changed their mind, cancel the booking workflow
    and do not call book_appointment.

    ===============================================================
    CHANGE WORKFLOW
    ===============================================================

    When the caller wants to change an appointment:

    1. Verify identity first.
    2. Ask for phone number if needed.
    3. Call find_appointments.
    4. Tell the caller the matching appointment details.
    5. Ask what new date/time they want.
    6. Repeat the new date/time.
    7. Ask "Is this correct?"
    8. Only after yes, call change_appointment.

    Never say the appointment ID unless the caller asks.

    ===============================================================
    CANCEL WORKFLOW
    ===============================================================

    When the caller wants to cancel:

    1. Verify identity first.
    2. Ask for phone number if needed.
    3. Call find_appointments.
    4. Identify the appointment.
    5. Repeat the appointment details.
    6. Ask if they want to cancel it.
    7. Only after yes, call cancel_appointment.

    If the caller is angry, remain calm and concise.

    If the caller says they do not want to cancel, do not call
    cancel_appointment.

    ===============================================================
    TOOL RULE
    ===============================================================

    Never fabricate tool arguments.

    If you do not know a value, ask the caller.

    Do not use placeholder values such as:
    John Doe
    9999999999
    2000-01-01

    ===============================================================
    POLICY RULE
    ===============================================================

    Use search_policies only for:

    - cancellation policy
    - late arrival
    - doctors
    - payment
    - insurance details
    - what to bring
    - blood test policy
    - parking policy

    Answer only from the tool result.

    ===============================================================
    ERROR RULE
    ===============================================================

    If a tool fails:

    Say:
    "Sorry, the system is not working right now."

    Do not invent data.

    Do not mention technical error codes.

    ===============================================================
    SLOW TOOL
    ===============================================================

    check_slow_system already speaks its waiting sentence.

    Do not speak another waiting sentence before calling it.
    """
)


CLINIC_PROMPT_SHORT = textwrap.dedent(
    """
    You are the front desk voice assistant for CityCare Clinic.

    Speak naturally in 1 to 3 short sentences.

    Never invent caller information.

    Ask for the caller's name, phone number, and date of birth before
    protected appointment actions.

    Verify identity before booking, changing, or cancelling.

    Never call book_appointment before:
    service + date + time are confirmed by the caller.

    Before booking:
    repeat service, date and time and ask:
    "Is this correct?"

    Only book after a clear yes.

    If caller changes their mind, stop the booking workflow.

    For hours and services, answer directly from clinic information.
    Do not use policy RAG for those questions.

    Never give medical advice.

    Use search_policies only for actual clinic policy questions.

    Never invent names, phone numbers, dates of birth, appointments,
    or appointment results.

    If a tool fails, apologize and say the system is not working.
    """
)


CLINIC_PROMPT = (
    CLINIC_PROMPT_LONG
    if PROMPT_MODE == "long"
    else CLINIC_PROMPT_SHORT
)


# ===============================================================
# LLM
# ===============================================================

def build_llm():

    if LLM_MODE == "langgraph":

        from langgraph_llm import build_graph

        return langchain.LLMAdapter(
            build_graph(CLINIC_PROMPT)
        )

    return GroqLLM(
        model=GROQ_MODEL
    )


# ===============================================================
# FRONT DESK AGENT
# ===============================================================

class FrontDesk(Agent):

    def __init__(self) -> None:

        super().__init__(
            instructions=CLINIC_PROMPT,
            llm=build_llm(),
        )

    async def on_enter(self):

        await self.session.generate_reply(
            instructions=(
                "Greet the caller by saying they have reached "
                "CityCare Clinic. Ask how you can help."
            )
        )

    # ===========================================================
    # IDENTITY: NAME
    # ===========================================================

    @function_tool()
    async def collect_name(
        self,
        context: RunContext,
        name: str,
    ) -> str:

        """
        Record the caller's name only when the caller has actually
        spoken their name. Never invent a name.
        """

        caller_text = recent_user_text(self)

        name_clean = name.strip()

        if not name_clean:
            return "I still need the caller's name."

        # Prevent common hallucinated placeholders.
        forbidden = {
            "john doe",
            "jane doe",
            "caller",
            "unknown",
            "user",
            "customer",
            "test",
            "test user",
        }

        if name_clean.lower() in forbidden:
            return (
                "Do not use a placeholder name. "
                "Ask the caller for their name."
            )

        # Check that the proposed name is plausibly present
        # in the recent caller speech.
        if name_clean.lower() not in caller_text.lower():
            return (
                "The caller has not clearly provided that name. "
                "Ask the caller for their name."
            )

        context.userdata.name = name_clean
        context.userdata.verified = False

        return f"Name recorded as {name_clean}. Ask for the phone number."

    # ===========================================================
    # IDENTITY: PHONE
    # ===========================================================

    @function_tool()
    async def collect_phone(
        self,
        context: RunContext,
        phone: str,
    ) -> str:

        """
        Record the caller's phone number only when the caller has
        actually provided it. Never invent a phone number.
        """

        caller_text = recent_user_text(self)

        phone_clean = (
            phone.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
            .strip()
        )

        if not phone_clean:
            return "Ask the caller for their phone number."

        digits = "".join(
            ch for ch in phone_clean
            if ch.isdigit()
        )

        if len(digits) < 7:
            return "The phone number is incomplete. Ask again."

        # Make sure some of the digits occur in recent user speech.
        caller_digits = "".join(
            ch for ch in caller_text
            if ch.isdigit()
        )

        if digits not in caller_digits:
            return (
                "The caller has not clearly provided that phone number. "
                "Ask for the phone number."
            )

        context.userdata.phone = digits
        context.userdata.verified = False

        return "Phone number recorded. Ask for the date of birth."

    # ===========================================================
    # IDENTITY: DOB
    # ===========================================================

    @function_tool()
    async def collect_date_of_birth(
        self,
        context: RunContext,
        date_of_birth: str,
    ) -> str:

        """
        Record the caller's date of birth only when the caller
        actually provides it. Expected format: YYYY-MM-DD.
        """

        caller_text = recent_user_text(self)

        dob = date_of_birth.strip()

        try:
            parsed = datetime.strptime(
                dob,
                "%Y-%m-%d",
            )

            if parsed > datetime.now():
                return "That date of birth is invalid. Ask again."

        except ValueError:
            return (
                "The date of birth must be in YYYY-MM-DD format. "
                "Ask the caller again."
            )

        # Check date components are actually present in recent
        # caller speech.
        parts = [
            parsed.strftime("%Y"),
            parsed.strftime("%m"),
            parsed.strftime("%d"),
        ]

        if not all(part in caller_text for part in parts):
            return (
                "The caller has not clearly provided that date of birth. "
                "Ask the caller for their date of birth."
            )

        context.userdata.date_of_birth = dob
        context.userdata.verified = False

        return (
            "Date of birth recorded. "
            "Now call verify_identity."
        )

    # ===========================================================
    # VERIFY IDENTITY
    # ===========================================================

    @function_tool()
    async def verify_identity(
        self,
        context: RunContext,
    ) -> str:

        """
        Verify the caller using the collected name, phone,
        and date of birth.

        Do not call until all three values have been collected.
        """

        data = context.userdata

        if not data.name:
            return "Identity incomplete. Ask for the caller's name."

        if not data.phone:
            return "Identity incomplete. Ask for the phone number."

        if not data.date_of_birth:
            return (
                "Identity incomplete. "
                "Ask for the date of birth."
            )

        start = perf_counter()

        try:

            # Use the backend identity endpoint if available.
            async with httpx.AsyncClient(timeout=3.0) as client:

                response = await client.post(
                    f"{API}/verify",
                    json={
                        "name": data.name,
                        "phone": data.phone,
                        "date_of_birth": data.date_of_birth,
                    },
                )

                response.raise_for_status()

                result = response.json()

        except Exception as e:

            logger.error(
                f"verify_identity failed: {e}"
            )

            data.verified = False

            return (
                "I could not verify the identity right now. "
                "Please try again later."
            )

        finally:
            log_tool_time(
                "verify_identity",
                start,
            )

        verified = bool(
            result.get("verified", False)
        )

        data.verified = verified

        if not verified:

            return (
                "The identity details did not match. "
                "Please check the name, phone number, and date of birth."
            )

        return (
            "Identity verified. "
            "You can now continue with the appointment request."
        )

    # ===========================================================
    # AVAILABLE SLOTS
    # ===========================================================

    @function_tool()
    async def get_available_slots(
        self,
        context: RunContext,
        date: str,
    ) -> str:

        """
        Find available appointment times.

        Use only after the caller has provided an appointment date.
        """

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

            except Exception as e:

                logger.error(
                    f"get_available_slots failed: {e}"
                )

                return (
                    "The booking system is not available right now."
                )

            if not slots:

                return (
                    "There are no free times on that date. "
                    "Ask the caller for another date."
                )

            return (
                "Available times are: "
                + ", ".join(slots[:5])
            )

        finally:

            log_tool_time(
                "get_available_slots",
                start,
            )

    # ===========================================================
    # BOOK
    # ===========================================================

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

        """
        Book an appointment.

        This tool is allowed only after:
        1. identity verification
        2. caller confirmation of service/date/time
        """

        data = context.userdata

        if not data.verified:

            return (
                "Identity has not been verified. "
                "Verify the caller before booking."
            )

        if not data.confirmation_received:

            return (
                "The caller has not confirmed the appointment yet. "
                "Repeat the service, date, and time and ask "
                "Is this correct?"
            )

        if not name or not phone or not date or not time or not service:

            return (
                "Booking information is incomplete. "
                "Ask for the missing information."
            )

        # Do not allow arbitrary LLM-generated identity values.
        if name != data.name:
            return "Use the verified caller name."

        if phone != data.phone:
            return "Use the verified caller phone number."

        start = perf_counter()

        try:

            try:

                async with httpx.AsyncClient(
                    timeout=2.0
                ) as client:

                    response = await client.post(
                        f"{API}/appointments",
                        json={
                            "name": data.name,
                            "phone": data.phone,
                            "date": date,
                            "time": time,
                            "service": service,
                        },
                    )

                    response.raise_for_status()

                    result = response.json()

            except Exception as e:

                logger.error(
                    f"book_appointment failed: {e}"
                )

                return (
                    "The booking system is not available right now."
                )

            appointment_id = result.get("id")

            return (
                "Your appointment is booked successfully."
            )

        finally:

            log_tool_time(
                "book_appointment",
                start,
            )

    # ===========================================================
    # FIND APPOINTMENTS
    # ===========================================================

    @function_tool()
    async def find_appointments(
        self,
        context: RunContext,
        phone: str,
    ) -> str:

        """
        Find appointments for the verified caller.

        Use before changing or cancelling an appointment.
        """

        data = context.userdata

        if not data.verified:

            return (
                "Identity has not been verified. "
                "Verify the caller first."
            )

        if phone != data.phone:

            return (
                "Use the verified caller phone number."
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
                            "phone": data.phone
                        },
                    )

                    response.raise_for_status()

                    items = response.json()

            except Exception as e:

                logger.error(
                    f"find_appointments failed: {e}"
                )

                return (
                    "The booking system is not available right now."
                )

            if not items:

                return (
                    "No appointments were found for this phone number."
                )

            lines = []

            for appointment in items[:3]:

                lines.append(
                    f"{appointment.get('service')} on "
                    f"{appointment.get('date')} at "
                    f"{appointment.get('time')}"
                )

            # Store first appointment internally.
            data.appointment_id = str(
                items[0].get("id")
            )

            return (
                "Appointments found: "
                + "; ".join(lines)
                + ". Ask the caller which one they want to manage."
            )

        finally:

            log_tool_time(
                "find_appointments",
                start,
            )

    # ===========================================================
    # CHANGE APPOINTMENT
    # ===========================================================

    @function_tool()
    async def change_appointment(
        self,
        context: RunContext,
        appointment_id: str,
        date: str,
        time: str,
    ) -> str:

        """
        Change an appointment only after the caller confirms
        the new date and time.
        """

        data = context.userdata

        if not data.verified:

            return (
                "Identity has not been verified."
            )

        if not data.confirmation_received:

            return (
                "The caller has not confirmed the new appointment time."
            )

        if (
            data.appointment_id
            and appointment_id != data.appointment_id
        ):

            return (
                "Use the appointment selected from the caller's "
                "verified appointments."
            )

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

            except Exception as e:

                logger.error(
                    f"change_appointment failed: {e}"
                )

                return (
                    "The booking system is not available right now."
                )

            return (
                f"The appointment is now on {date} at {time}."
            )

        finally:

            log_tool_time(
                "change_appointment",
                start,
            )

    # ===========================================================
    # CANCEL APPOINTMENT
    # ===========================================================

    @function_tool()
    async def cancel_appointment(
        self,
        context: RunContext,
        appointment_id: str,
    ) -> str:

        """
        Cancel an appointment only after the caller has confirmed
        that they want to cancel.
        """

        data = context.userdata

        if not data.verified:

            return (
                "Identity has not been verified."
            )

        if not data.confirmation_received:

            return (
                "The caller has not confirmed the cancellation."
            )

        if (
            data.appointment_id
            and appointment_id != data.appointment_id
        ):

            return (
                "Use the appointment selected from the caller's "
                "verified appointments."
            )

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

            except Exception as e:

                logger.error(
                    f"cancel_appointment failed: {e}"
                )

                return (
                    "The booking system is not available right now."
                )

            return (
                "The appointment has been cancelled."
            )

        finally:

            log_tool_time(
                "cancel_appointment",
                start,
            )

    # ===========================================================
    # SLOW SYSTEM
    # ===========================================================

    @function_tool()
    async def check_slow_system(
        self,
        context: RunContext,
    ) -> str:

        """
        Run the slow system check only when the caller explicitly
        asks for it.
        """

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

            except Exception as e:

                logger.error(
                    f"check_slow_system failed: {e}"
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

    # ===========================================================
    # BROKEN SYSTEM
    # ===========================================================

    @function_tool()
    async def check_broken_system(
        self,
        context: RunContext,
    ) -> str:

        """
        Run the broken system check only when explicitly requested.
        """

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

            except Exception as e:

                logger.error(
                    f"check_broken_system failed: {e}"
                )

                return (
                    "The system is not working right now. "
                    "No data is available."
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

    # ===========================================================
    # POLICY RAG
    # ===========================================================

    @function_tool()
    async def search_policies(
        self,
        context: RunContext,
        question: str,
    ) -> str:

        """
        Search clinic policies.

        Use only for cancellation policy, late arrival,
        doctors, payment, insurance, what to bring,
        blood test policy, or parking policy.

        Do not use for normal clinic hours or services.
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
                    "The policy search is not working right now."
                )

            if not results:

                return (
                    "I could not find a policy for that question."
                )

            return "\n".join(results)

        finally:

            log_tool_time(
                "search_policies",
                start,
            )


# ===============================================================
# SERVER
# ===============================================================

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

    # Build RAG index.
    await asyncio.to_thread(
        rag.build_index
    )

    # ===========================================================
    # SESSION
    # ===========================================================

    session = AgentSession[CallerData](
        userdata=CallerData(),

        stt=inference.STT(
            model="assemblyai/universal-3-5-pro",
            language="en",
        ),

        stt_context_options=STTContextOptions(
            keyterms=[
                "CityCare Clinic"
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

            interruption={
                "mode": "adaptive"
            },

            preemptive_generation={
                "enabled": True
            },
        ),

        expressive=True,
    )

    # ===========================================================
    # LATENCY LOGGING
    # ===========================================================

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

        elif ev.item.role == "assistant":

            print(
                f"AGENT e2e: "
                f"{metrics.get('e2e_latency')}  "
                f"llm_ttft: "
                f"{metrics.get('llm_node_ttft')}  "
                f"tts_ttfb: "
                f"{metrics.get('tts_node_ttfb')}"
            )

    # ===========================================================
    # AGENT
    # ===========================================================

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


# ===============================================================
# MAIN
# ===============================================================

if __name__ == "__main__":
    cli.run_app(server)