

## Agents

The CityCare Clinic voice system contains three agents:

1. ReceptionAgent
2. BookingAgent
3. BillingAgent

## Main Flow

Caller
  |
  v
ReceptionAgent
  |
  +----> BookingAgent
  |
  +----> BillingAgent
  |
  v
ReceptionAgent
  |
  v
End Call

## ReceptionAgent

ReceptionAgent is the starting agent.

Responsibilities:

- Greet the caller
- Collect caller name
- Collect phone number
- Collect date of birth
- Verify caller identity
- Answer clinic policy questions
- Transfer the caller to BookingAgent
- Transfer the caller to BillingAgent

## BookingAgent

BookingAgent handles appointment operations.

Responsibilities:

- Check available slots
- Book appointments
- Find appointments
- Change appointments
- Cancel appointments

The caller must be verified before protected appointment operations.

## BillingAgent

BillingAgent handles billing operations.

Responsibilities:

- Get the caller's bill
- Return billing information

The caller must be verified before accessing billing information.

## Shared Caller Data

The agents share caller information using session userdata.

```python
@dataclass
class CallerData:
    name: str | None = None
    phone: str | None = None
    date_of_birth: str | None = None
    verified: bool = False