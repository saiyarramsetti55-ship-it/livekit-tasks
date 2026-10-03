# CityCare Clinic - Day 3

## Goal

Day 3 changes the Day 2 single-agent system into a multi-agent
voice workflow.

## Agents

### ReceptionAgent

Responsible for:

- Greeting
- General clinic information
- Identity collection
- Identity verification
- Policy questions
- Routing

### BookingAgent

Responsible for:

- Available appointment slots
- Booking
- Finding appointments
- Changing appointments
- Cancelling appointments

### BillingAgent

Responsible for:

- Retrieving mock billing information

## Flow

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
End conversation

## Shared userdata

The session uses:

```python
AgentSession[CallerData]