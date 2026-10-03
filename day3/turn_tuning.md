# Day 3 - Turn Taking Tuning

## Objective

The voice agent should have natural turn taking.

The agent should:

- Detect when the caller finishes speaking
- Handle interruptions
- Allow short acknowledgements
- Avoid unnecessary cutoffs
- Generate responses quickly

## Turn Detection

The agent uses LiveKit turn detection.

```python
turn_detection=inference.TurnDetector()