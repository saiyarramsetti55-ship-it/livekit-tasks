
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import asyncio
import re
import os

from dotenv import load_dotenv
from livekit import api


from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parents[1] / ".env.local")

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

app = FastAPI(
    title="CityCare Clinic API",
    description="Backend API for CityCare Clinic Voice AI Agent",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/token")
async def get_token(name: str = Query(default="Guest", min_length=1, max_length=50)):
    if not LIVEKIT_URL or not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="LiveKit credentials are not configured.",
        )

    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(name.strip())
        .with_name(name.strip())
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room="citycare-clinic",
            )
        )
        .with_room_config(
            api.RoomConfiguration(
                agents=[
                    api.RoomAgentDispatch(agent_name="citycare")
                ]
            )
        )
    )

    return {
        "serverUrl": LIVEKIT_URL,
        "participantName": name.strip(),
        "roomName": "citycare-clinic",
        "participantToken": token.to_jwt(),
    }

# ============================================================
# CLINIC CONFIGURATION
# ============================================================

CLINIC_SERVICES = {
    "general check-up",
    "blood tests",
    "vaccines",
    "children's doctor",
}

DEFAULT_SLOTS = [
    "09:00",
    "10:00",
    "11:30",
    "14:00",
    "15:30",
]


# ============================================================
# MODELS
# ============================================================

class AppointmentCreate(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=3)
    date: str = Field(..., min_length=8)
    time: str = Field(..., min_length=4)
    service: str = Field(..., min_length=2)


class AppointmentUpdate(BaseModel):
    date: str = Field(..., min_length=8)
    time: str = Field(..., min_length=4)


# ============================================================
# DATA
# ============================================================

appointments: list[dict] = [
    {
        "id": "1",
        "name": "Sai",
        "phone": "9999999999",
        "date": "2026-10-05",
        "time": "09:00",
        "service": "general check-up",
    }
]

next_appointment_id = 2

slots_cache: dict[str, list[str]] = {}


# ============================================================
# MOCK BILLING DATA
# ============================================================

bills = {
    "9999999999": {
        "amount": "INR 1,500",
        "due_date": "2026-10-15",
        "status": "Due",
    },
    "8888888888": {
        "amount": "INR 2,500",
        "due_date": "2026-10-20",
        "status": "Due",
    },
}


# ============================================================
# HELPERS
# ============================================================

def normalize_phone(phone: str) -> str:
    """
    Keep digits only so that:
    9999999999
    +91 9999999999
    99999-99999

    can be compared consistently.
    """
    return re.sub(r"\D", "", phone)


def validate_phone(phone: str) -> str:
    """
    Validate Indian-style 10 digit phone numbers.

    Returns normalized digits.
    """

    normalized = normalize_phone(phone)

    if len(normalized) == 12 and normalized.startswith("91"):
        normalized = normalized[2:]

    if len(normalized) != 10:
        raise HTTPException(
            status_code=400,
            detail="Please provide a valid 10-digit phone number.",
        )

    return normalized


def validate_service(service: str) -> str:
    """
    Match the requested service against supported clinic services.
    """

    cleaned = service.strip().lower()

    aliases = {
        "check-up": "general check-up",
        "checkup": "general check-up",
        "general checkup": "general check-up",
        "blood test": "blood tests",
        "child doctor": "children's doctor",
        "pediatrician": "children's doctor",
        "paediatrician": "children's doctor",
    }

    cleaned = aliases.get(cleaned, cleaned)

    if cleaned not in CLINIC_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported service. Available services: "
                "general check-up, blood tests, vaccines, "
                "children's doctor."
            ),
        )

    return cleaned


def get_available_slots(date: str) -> list[str]:
    """
    Return slots for a date.
    """

    if date not in slots_cache:
        slots_cache[date] = DEFAULT_SLOTS.copy()

    booked_times = {
        item["time"]
        for item in appointments
        if item["date"] == date
    }

    return [
        slot
        for slot in slots_cache[date]
        if slot not in booked_times
    ]


def find_appointment(appointment_id: str) -> dict | None:
    for item in appointments:
        if item["id"] == appointment_id:
            return item

    return None


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():
    return {
        "message": "CityCare Clinic API is running.",
        "status": "ok",
    }


# ============================================================
# SLOTS
# ============================================================

@app.get("/slots")
async def get_slots(
    date: str,
):
    """
    Return available appointment slots for a date.
    """

    return get_available_slots(date)


# ============================================================
# CREATE APPOINTMENT
# ============================================================

@app.post("/appointments")
async def create_appointment(
    appointment: AppointmentCreate,
):
    global next_appointment_id

    phone = validate_phone(appointment.phone)

    service = validate_service(appointment.service)

    date = appointment.date.strip()

    time = appointment.time.strip()

    available_slots = get_available_slots(date)

    if time not in available_slots:
        raise HTTPException(
            status_code=409,
            detail=(
                f"The requested time {time} is not available. "
                f"Available slots: {available_slots}"
            ),
        )

    item = {
        "id": str(next_appointment_id),
        "name": appointment.name.strip(),
        "phone": phone,
        "date": date,
        "time": time,
        "service": service,
    }

    appointments.append(item)

    next_appointment_id += 1

    return item


# ============================================================
# UPDATE APPOINTMENT
# ============================================================

@app.patch("/appointments/{appointment_id}")
async def update_appointment(
    appointment_id: str,
    appointment: AppointmentUpdate,
):
    item = find_appointment(appointment_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    date = appointment.date.strip()

    time = appointment.time.strip()

    available_slots = get_available_slots(date)

    # If the caller keeps the same date/time, allow it.
    if date == item["date"] and time == item["time"]:
        available = True
    else:
        available = time in available_slots

    if not available:
        raise HTTPException(
            status_code=409,
            detail=(
                f"The requested time {time} is not available. "
                f"Available slots: {available_slots}"
            ),
        )

    item["date"] = date
    item["time"] = time

    return item


# ============================================================
# DELETE / CANCEL APPOINTMENT
# ============================================================

@app.delete("/appointments/{appointment_id}")
async def delete_appointment(
    appointment_id: str,
):
    for index, item in enumerate(appointments):

        if item["id"] == appointment_id:

            deleted = appointments.pop(index)

            return {
                "message": "Appointment cancelled successfully.",
                "appointment": deleted,
            }

    raise HTTPException(
        status_code=404,
        detail="Appointment not found",
    )


# ============================================================
# FIND APPOINTMENTS
# ============================================================

@app.get("/appointments")
async def get_appointments(
    phone: str = Query(
        ...,
        min_length=3,
    ),
):
    """
    Find appointments using a phone number.
    """

    normalized_phone = validate_phone(phone)

    return [
        item
        for item in appointments
        if item["phone"] == normalized_phone
    ]


# ============================================================
# GET SINGLE APPOINTMENT
# ============================================================

@app.get("/appointments/{appointment_id}")
async def get_appointment(
    appointment_id: str,
):
    item = find_appointment(appointment_id)

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    return item


# ============================================================
# DAY 3 BILLING
# ============================================================

@app.get("/bills")
async def get_bill(
    phone: str = Query(
        ...,
        min_length=3,
    ),
):
    """
    Return mock billing information.
    """

    normalized_phone = validate_phone(phone)

    bill = bills.get(normalized_phone)

    if bill is None:
        bill = {
            "amount": "INR 1,250",
            "due_date": "2026-10-31",
            "status": "Due",
        }

    return {
        "phone": normalized_phone,
        **bill,
    }


# ============================================================
# CAPSTONE: PRESCRIPTION REFILLS
# ============================================================

class PrescriptionRefillRequest(BaseModel):
    name: str = Field(..., min_length=2)
    phone: str = Field(..., min_length=3)
    medication: str = Field(..., min_length=2)
    pharmacy: str = Field(default="CityCare In-House Pharmacy", min_length=2)


prescriptions: list[dict] = [
    {
        "id": "rx-101",
        "patient_name": "Sai",
        "phone": "9999999999",
        "medication": "Amoxicillin 500mg",
        "refills_remaining": 2,
        "prescribing_doctor": "Dr. Smith",
        "last_filled": "2026-09-10",
        "status": "Active",
    },
    {
        "id": "rx-102",
        "patient_name": "Sai",
        "phone": "9999999999",
        "medication": "Lisinopril 10mg",
        "refills_remaining": 1,
        "prescribing_doctor": "Dr. Patel",
        "last_filled": "2026-08-20",
        "status": "Active",
    },
    {
        "id": "rx-103",
        "patient_name": "Sai",
        "phone": "9999999999",
        "medication": "Metformin 500mg",
        "refills_remaining": 0,
        "prescribing_doctor": "Dr. Williams",
        "last_filled": "2026-07-15",
        "status": "Expired - No Refills Left",
    },
]

SUPPORTED_PHARMACIES = [
    "CityCare In-House Pharmacy",
    "Walgreens Downtown",
    "CVS Main Street",
    "Apollo Pharmacy",
]


@app.get("/prescriptions")
async def get_prescriptions(
    phone: str = Query(..., min_length=3),
):
    """
    Return active prescriptions for verified caller phone.
    """
    normalized_phone = validate_phone(phone)
    patient_rx = [
        rx for rx in prescriptions
        if rx["phone"] == normalized_phone
    ]
    return patient_rx


@app.get("/prescriptions/pharmacies")
async def get_pharmacies():
    """
    Return list of network pharmacies.
    """
    return SUPPORTED_PHARMACIES


@app.post("/prescriptions/refill")
async def refill_prescription(
    refill: PrescriptionRefillRequest,
):
    """
    Process prescription refill request for a verified patient.
    """
    normalized_phone = validate_phone(refill.phone)
    med_lower = refill.medication.strip().casefold()

    matched_rx = None
    for rx in prescriptions:
        if rx["phone"] == normalized_phone and (
            med_lower in rx["medication"].casefold()
            or rx["medication"].casefold() in med_lower
        ):
            matched_rx = rx
            break

    if matched_rx is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active prescription found matching '{refill.medication}' for this patient.",
        )

    if matched_rx["refills_remaining"] <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"No refills remaining for {matched_rx['medication']}. Please schedule an appointment with {matched_rx['prescribing_doctor']} for renewal.",
        )

    matched_rx["refills_remaining"] -= 1

    pharmacy = refill.pharmacy.strip() if refill.pharmacy else "CityCare In-House Pharmacy"

    return {
        "refill_id": f"refill-50{matched_rx['refills_remaining'] + 1}",
        "patient_name": matched_rx["patient_name"],
        "medication": matched_rx["medication"],
        "pharmacy": pharmacy,
        "refills_remaining": matched_rx["refills_remaining"],
        "status": "Approved and submitted to pharmacy",
        "estimated_ready": "Today in 2 hours",
    }


# ============================================================
# SLOW SYSTEM
# ============================================================

@app.get("/slow")
async def slow_system():
    """
    Mock slow backend for error/recovery testing.
    """

    await asyncio.sleep(3)

    return {
        "status": "ok",
        "message": "Slow system recovered successfully.",
    }


# ============================================================
# BROKEN SYSTEM
# ============================================================

@app.get("/broken")
async def broken_system():
    """
    Mock backend failure for agent error-handling tests.
    """

    raise HTTPException(
        status_code=503,
        detail="Mock system failure",
    )
