import time

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel


app = FastAPI(title="CityCare Clinic API")


# ---------- Settings for Step 8 (cache) ----------
CACHE_SECONDS = 30          # set to 0 to turn the cache OFF
SIMULATED_DB_DELAY = 0.3    # TEST ONLY: simulates a slow database. Set to 0 to remove.

SLOTS_CACHE = {}            # date -> {"saved_at": time, "slots": list}


@app.middleware("http")
async def timing_middleware(request, call_next):
    start = time.perf_counter()

    response = await call_next(request)

    elapsed_ms = (time.perf_counter() - start) * 1000

    print(
        f"{request.method} {request.url.path} "
        f"took {elapsed_ms:.0f} ms"
    )

    return response


class Appointment(BaseModel):
    name: str
    phone: str
    date: str
    time: str
    service: str


class AppointmentUpdate(BaseModel):
    date: str | None = None
    time: str | None = None


appointments = {}
next_appointment_id = 1


AVAILABLE_SLOTS = [
    "09:00",
    "10:00",
    "11:00",
    "14:00",
    "15:00",
    "16:00",
]


def is_taken(date: str, slot_time: str, ignore_id: int | None = None) -> bool:
    """True if another appointment already uses this date and time."""
    for appointment_id, appt in appointments.items():
        if appointment_id == ignore_id:
            continue
        if appt["date"] == date and appt["time"] == slot_time:
            return True
    return False


# 1. Root
@app.get("/")
def root():
    return {"message": "CityCare Clinic API is running"}


# 2. Get available slots (with cache)
@app.get("/slots")
def get_slots(
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    now = time.time()
    cached = SLOTS_CACHE.get(date)

    # Cache hit: saved less than CACHE_SECONDS ago
    if cached and (now - cached["saved_at"]) < CACHE_SECONDS:
        print(f"CACHE HIT  /slots date={date}")
        return cached["slots"]

    # Cache miss: do the normal work
    print(f"CACHE MISS /slots date={date}")
    time.sleep(SIMULATED_DB_DELAY)  # TEST ONLY

    free_slots = [s for s in AVAILABLE_SLOTS if not is_taken(date, s)]

    SLOTS_CACHE[date] = {"saved_at": now, "slots": free_slots}
    return free_slots


# 3. Book appointment
@app.post("/appointments")
def create_appointment(appointment: Appointment):
    global next_appointment_id

    if is_taken(appointment.date, appointment.time):
        raise HTTPException(status_code=409, detail="This time is already booked")

    SLOTS_CACHE.clear()  # data changed, so the old cache is not correct

    appointment_id = next_appointment_id

    appointments[appointment_id] = appointment.model_dump()

    next_appointment_id += 1

    return {
        "id": appointment_id,
        "message": "Appointment booked successfully",
        "appointment": appointments[appointment_id],
    }


# 4. Change appointment
@app.patch("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: int,
    update: AppointmentUpdate,
):
    if appointment_id not in appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")

    current = appointments[appointment_id]
    new_date = update.date if update.date is not None else current["date"]
    new_time = update.time if update.time is not None else current["time"]

    if is_taken(new_date, new_time, ignore_id=appointment_id):
        raise HTTPException(status_code=409, detail="This time is already booked")

    SLOTS_CACHE.clear()  # data changed, so the old cache is not correct

    current["date"] = new_date
    current["time"] = new_time

    return {
        "message": "Appointment updated successfully",
        "appointment": {
            "id": appointment_id,
            **current,
        },
    }


# 5. Cancel appointment
@app.delete("/appointments/{appointment_id}")
def delete_appointment(appointment_id: int):
    if appointment_id not in appointments:
        raise HTTPException(status_code=404, detail="Appointment not found")

    SLOTS_CACHE.clear()  # data changed, so the old cache is not correct

    deleted_appointment = appointments.pop(appointment_id)

    return {
        "message": "Appointment cancelled successfully",
        "appointment": {
            "id": appointment_id,
            **deleted_appointment,
        },
    }


# 6. Find appointments by phone number
@app.get("/appointments")
def get_appointments(
    phone: str = Query(..., description="Patient phone number")
):
    results = []

    for appointment_id, appointment in appointments.items():
        if appointment["phone"] == phone:
            results.append({
                "id": appointment_id,
                **appointment,
            })

    return results

# 7. Get billing information
BILLS = {
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


@app.get("/bills")
def get_bill(
    phone: str = Query(..., description="Patient phone number")
):
    bill = BILLS.get(phone)

    if bill is None:
        raise HTTPException(
            status_code=404,
            detail="Billing information not found",
        )

    return {
        "phone": phone,
        **bill,
    }


# 7. Slow endpoint
@app.get("/slow")
def slow_endpoint():
    time.sleep(3)

    return {
        "message": "Slow endpoint completed",
        "delay_seconds": 3,
    }


# 8. Broken endpoint
@app.get("/broken")
def broken_endpoint():
    raise HTTPException(
        status_code=500,
        detail="This endpoint is intentionally broken",
    )