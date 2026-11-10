"""One entry in the "behind the scenes" log shown on the page."""


def trace_event(event: str, time: float, **details: object) -> dict:
    return {"type": "trace", "event": event, "time": round(time, 2), **details}
