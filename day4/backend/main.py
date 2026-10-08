
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import asyncio
import re


app = FastAPI(
    title="CityCare Clinic API",
    description="Backend API for CityCare Clinic Voice AI Agent",
    version="1.0.0",
)


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

appointments: list[dict] = []

next_appointment_id = 1

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
