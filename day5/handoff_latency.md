

## Objective

Measure the time required to transfer the conversation between agents.

Target:

First handoff response should be less than 1.5 seconds.

## Handoffs

The following handoffs are tested:

1. ReceptionAgent -> BookingAgent
2. ReceptionAgent -> BillingAgent
3. BookingAgent -> ReceptionAgent
4. BillingAgent -> ReceptionAgent

## Test Results

| Test | Handoff | Latency |
|---|---|---:|
| 1 | Reception -> Booking | ___ ms |
| 2 | Reception -> Billing | ___ ms |
| 3 | Booking -> Reception | ___ ms |
| 4 | Billing -> Reception | ___ ms |
| 5 | Reception -> Booking | ___ ms |
| 6 | Reception -> Billing | ___ ms |
| 7 | Booking -> Reception | ___ ms |
| 8 | Billing -> Reception | ___ ms |
| 9 | Reception -> Booking | ___ ms |
| 10 | Reception -> Billing | ___ ms |

## Summary

Number of handoffs tested: 10

Minimum latency: ___ ms

Maximum latency: ___ ms

Median latency: ___ ms

## Target

First handoff response:

< 1.5 seconds

## Notes

Issues found during testing:

- __________________________
- __________________________

## Final Result

Measured first handoff response: ___ seconds