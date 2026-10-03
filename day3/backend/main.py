from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


app = FastAPI(
    title="CityCare Clinic API"
)


# ============================================================
# MODELS
# ============================================================

class AppointmentCreate(BaseModel):

    name: str
    phone: str
    date: str
    time: str
    service: str


class AppointmentUpdate(BaseModel):

    date: str
    time: str


# ============================================================
# DATA
# ============================================================

appointments: list[dict] = []

next_appointment_id = 1

slots_cache: dict[str, list[str]] = {}


# Mock billing data
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
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "message":
        "CityCare Clinic API is running."
    }


# ============================================================
# SLOTS
# ============================================================

@app.get("/slots")
async def get_slots(
    date: str,
):

    if date not in slots_cache:

        slots_cache[date] = [
            "09:00",
            "10:00",
            "11:30",
            "14:00",
            "15:30",
        ]

    return slots_cache[date]


# ============================================================
# CREATE APPOINTMENT
# ============================================================

@app.post("/appointments")
async def create_appointment(
    appointment: AppointmentCreate,
):

    global next_appointment_id

    item = {

        "id": str(
            next_appointment_id
        ),

        "name": appointment.name,

        "phone": appointment.phone,

        "date": appointment.date,

        "time": appointment.time,

        "service": appointment.service,
    }

    appointments.append(item)

    next_appointment_id += 1

    return item


# ============================================================
# UPDATE APPOINTMENT
# ============================================================

@app.patch(
    "/appointments/{appointment_id}"
)
async def update_appointment(

    appointment_id: str,

    appointment: AppointmentUpdate,
):

    for item in appointments:

        if item["id"] == appointment_id:

            item["date"] = appointment.date

            item["time"] = appointment.time

            return item

    raise HTTPException(
        status_code=404,
        detail="Appointment not found",
    )


# ============================================================
# DELETE APPOINTMENT
# ============================================================

@app.delete(
    "/appointments/{appointment_id}"
)
async def delete_appointment(
    appointment_id: str,
):

    for index, item in enumerate(
        appointments
    ):

        if item["id"] == appointment_id:

            deleted = appointments.pop(
                index
            )

            return {

                "message":
                "Appointment cancelled",

                "appointment":
                deleted,
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

    return [

        item

        for item in appointments

        if item["phone"] == phone
    ]


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

    bill = bills.get(phone)

    if bill is None:

        bill = {

            "amount":
            "INR 1,250",

            "due_date":
            "2026-10-31",

            "status":
            "Due",
        }

    return {

        "phone": phone,

        **bill,
    }


# ============================================================
# SLOW SYSTEM
# ============================================================

@app.get("/slow")
async def slow_system():

    import asyncio

    await asyncio.sleep(3)

    return {
        "status": "ok"
    }


# ============================================================
# BROKEN SYSTEM
# ============================================================

@app.get("/broken")
async def broken_system():

    raise HTTPException(
        status_code=503,
        detail="Mock system failure",
    )