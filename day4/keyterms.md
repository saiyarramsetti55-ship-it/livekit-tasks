

## Objective

Improve speech recognition for important CityCare Clinic terms.

## Keyterms

The configured keyterms are:

- CityCare Clinic
- CityCare
- Dr. Smith
- Dr. Patel
- Dr. Williams
- general check-up
- blood tests
- children's doctor

## STT Configuration

The keyterms are configured in the STT options.

```python
STTContextOptions(
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
    }
)