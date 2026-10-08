import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent import CallerData, ReceptionAgent, BookingAgent


# ---------------------------------------------------------
# Fake context
# ---------------------------------------------------------

class FakeSession:
    def __init__(self):
        self.userdata = CallerData()


class FakeContext:
    def __init__(self):
        self.session = FakeSession()


# ---------------------------------------------------------
# ReceptionAgent tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_collect_name():
    agent = ReceptionAgent.__new__(ReceptionAgent)
    context = FakeContext()

    result = await agent.collect_name(context, "Sai")

    assert context.session.userdata.name == "Sai"
    assert context.session.userdata.name_collected is True
    assert context.session.userdata.verified is False
    assert "recorded" in result.lower()


@pytest.mark.asyncio
async def test_collect_phone():
    agent = ReceptionAgent.__new__(ReceptionAgent)
    context = FakeContext()

    context.session.userdata.name = "Sai"
    context.session.userdata.name_collected = True

    result = await agent.collect_phone(
        context,
        "9999999999",
    )

    assert context.session.userdata.phone == "9999999999"
    assert context.session.userdata.phone_collected is True
    assert context.session.userdata.verified is False
    assert "recorded" in result.lower()


@pytest.mark.asyncio
async def test_collect_date_of_birth():
    agent = ReceptionAgent.__new__(ReceptionAgent)
    context = FakeContext()

    context.session.userdata.name = "Sai"
    context.session.userdata.name_collected = True
    context.session.userdata.phone = "9999999999"
    context.session.userdata.phone_collected = True

    result = await agent.collect_date_of_birth(
        context,
        "2000-01-15",
    )

    assert context.session.userdata.date_of_birth == "2000-01-15"
    assert context.session.userdata.dob_collected is True
    assert context.session.userdata.verified is False
    assert "recorded" in result.lower()


@pytest.mark.asyncio
async def test_verify_caller_fails_when_information_missing():
    agent = ReceptionAgent.__new__(ReceptionAgent)
    context = FakeContext()

    result = await agent.verify_caller(context)

    assert context.session.userdata.verified is False
    assert "cannot start" in result.lower() or "collect" in result.lower()


@pytest.mark.asyncio
async def test_verify_caller_succeeds_when_information_complete():
    agent = ReceptionAgent.__new__(ReceptionAgent)
    context = FakeContext()

    context.session.userdata.name = "Sai"
    context.session.userdata.name_collected = True
    context.session.userdata.phone = "9999999999"
    context.session.userdata.phone_collected = True
    context.session.userdata.date_of_birth = "2000-01-15"
    context.session.userdata.dob_collected = True

    result = await agent.verify_caller(context)

    assert context.session.userdata.verified is True
    assert "verified" in result.lower()


# ---------------------------------------------------------
# BookingAgent tests
# ---------------------------------------------------------

@pytest.mark.asyncio
async def test_book_appointment_requires_verification():
    agent = BookingAgent.__new__(BookingAgent)
    context = FakeContext()

    result = await agent.book_appointment(
        context,
        name="Sai",
        phone="9999999999",
        date="2026-10-05",
        time="09:00",
        service="General check-up",
    )

    assert context.session.userdata.verified is False
    assert "verification" in result.lower()


@pytest.mark.asyncio
async def test_book_appointment_success():
    agent = BookingAgent.__new__(BookingAgent)
    context = FakeContext()

    context.session.userdata.name = "Sai"
    context.session.userdata.phone = "9999999999"
    context.session.userdata.date_of_birth = "2000-01-15"
    context.session.userdata.verified = True
    context.session.userdata.booking_active = True
    context.session.userdata.booking_confirmed = True

    # Mock HTTP response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "id": 1,
        "name": "Sai",
        "phone": "9999999999",
        "date": "2026-10-05",
        "time": "09:00",
        "service": "General check-up",
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch(
        "src.agent.httpx.AsyncClient"
    ) as mock_async_client:

        mock_async_client.return_value.__aenter__.return_value = (
            mock_client
        )

        result = await agent.book_appointment(
            context,
            name="Sai",
            phone="9999999999",
            date="2026-10-05",
            time="09:00",
            service="General check-up",
        )

    assert "booked" in result.lower()
    mock_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_booking_does_not_work_without_verified_caller():
    agent = BookingAgent.__new__(BookingAgent)
    context = FakeContext()

    context.session.userdata.name = "Sai"
    context.session.userdata.phone = "9999999999"
    context.session.userdata.date_of_birth = "2000-01-15"
    context.session.userdata.verified = False

    result = await agent.book_appointment(
        context,
        name="Sai",
        phone="9999999999",
        date="2026-10-05",
        time="09:00",
        service="General check-up",
    )

    assert "verification" in result.lower()
    assert context.session.userdata.verified is False


@pytest.mark.asyncio
async def test_find_appointments_requires_verification():
    agent = BookingAgent.__new__(BookingAgent)
    context = FakeContext()

    result = await agent.find_appointments(
        context,
        phone="9999999999",
    )

    assert context.session.userdata.verified is False
    assert "verification" in result.lower()


@pytest.mark.asyncio
async def test_find_appointments_success():
    agent = BookingAgent.__new__(BookingAgent)
    context = FakeContext()

    context.session.userdata.name = "Sai"
    context.session.userdata.phone = "9999999999"
    context.session.userdata.date_of_birth = "2000-01-15"
    context.session.userdata.verified = True

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = [
        {
            "id": 1,
            "name": "Sai",
            "phone": "9999999999",
            "date": "2026-10-05",
            "time": "09:00",
            "service": "General check-up",
        }
    ]

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch(
        "src.agent.httpx.AsyncClient"
    ) as mock_async_client:

        mock_async_client.return_value.__aenter__.return_value = (
            mock_client
        )

        result = await agent.find_appointments(
            context,
            phone="9999999999",
        )

    assert "2026-10-05" in result
    assert "09:00" in result
    mock_client.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_appointment_requires_verification():
    agent = BookingAgent.__new__(BookingAgent)
    context = FakeContext()

    result = await agent.cancel_appointment(
        context,
        appointment_id="1",
    )

    assert context.session.userdata.verified is False
    assert "verification" in result.lower()


@pytest.mark.asyncio
async def test_cancel_appointment_success():
    agent = BookingAgent.__new__(BookingAgent)
    context = FakeContext()

    context.session.userdata.name = "Sai"
    context.session.userdata.phone = "9999999999"
    context.session.userdata.date_of_birth = "2000-01-15"
    context.session.userdata.verified = True
    context.session.userdata.appointment_found = True
    context.session.userdata.appointment_ids = ["1"]
    context.session.userdata.selected_appointment_id = "1"
    context.session.userdata.appointment_confirmed = True

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "message": "Appointment cancelled successfully.",
        "appointment": {"id": "1"},
    }

    mock_client = AsyncMock()
    mock_client.delete.return_value = mock_response

    with patch(
        "src.agent.httpx.AsyncClient"
    ) as mock_async_client:

        mock_async_client.return_value.__aenter__.return_value = (
            mock_client
        )

        result = await agent.cancel_appointment(
            context,
            appointment_id="1",
        )

    assert "cancelled" in result.lower()
    mock_client.delete.assert_awaited_once()