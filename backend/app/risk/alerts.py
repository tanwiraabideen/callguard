"""Decides when to alert the user, and remembers what they have dismissed.

Medium risk gives a visual alert, and high risk also gives a spoken whisper.
Each level alerts once. After a dismissal, the only thing that alerts again is
a higher level or a severe red flag not yet alerted on: dismissing pressure
tactics must not silence a later request for codes or money.
"""

import logging

from app.trace import trace_event

logger = logging.getLogger("uvicorn.error")

LEVEL_RANK = {"low": 0, "medium": 1, "high": 2}

# Most harmful first, so a whisper warns about the worst thing heard.
WHISPERS = {
    "codes_or_pins": "This may be a scam. Never share a code or PIN.",
    "safe_account": "This may be a scam. Banks never ask you to move money.",
    "gift_cards_or_crypto": "This may be a scam. No real organisation takes gift cards.",
    "remote_access": "This may be a scam. Don't install anything.",
    "secrecy": "This may be a scam. You can hang up and check.",
    "urgency_or_threats": "This may be a scam. Don't be rushed.",
}
DEFAULT_WHISPER = "This may be a scam. You can hang up and call back."


def whisper_for(categories: list[str]) -> str:
    for category, whisper in WHISPERS.items():
        if category in categories:
            return whisper
    return DEFAULT_WHISPER


class AlertManager:
    def __init__(self) -> None:
        self.alerts: dict[int, dict] = {}
        self.highest_rank = 0
        self.alerted_categories: set[str] = set()
        self.dismissals: list[dict] = []

    def check(self, update: dict, active_categories: list[str]) -> dict | None:
        """Return a new alert if this risk update calls for one."""
        rank = LEVEL_RANK[update["level"]]
        new_severe_flags = [
            hit
            for hit in update["rules"]
            if hit["severe"]
            and not hit["suppressed"]
            and hit["category"] not in self.alerted_categories
        ]
        is_realert = bool(self.dismissals and new_severe_flags)
        if not is_realert and rank <= self.highest_rank:
            return None

        self.highest_rank = max(self.highest_rank, rank, 1)
        categories = active_categories or ["llm"]
        self.alerted_categories.update(categories)
        level = "high" if rank == 2 else "medium"
        alert = {
            "type": "alert",
            "id": len(self.alerts) + 1,
            "level": level,
            "reason": update["reason"],
            "categories": categories,
            "time": update["time"],
            "score": update["score"],
            "is_realert": is_realert,
            "whisper": whisper_for(categories) if level == "high" else None,
        }
        self.alerts[alert["id"]] = alert
        return alert

    def dismiss(self, alert_id: object, time: float) -> tuple[dict, dict] | None:
        """Log a dismissal. Returns the alert and a trace entry, or None if unknown."""
        alert = self.alerts.get(alert_id) if isinstance(alert_id, int) else None
        if alert is None or alert.get("dismissed"):
            return None

        alert["dismissed"] = True
        record = {"alert_id": alert["id"], "categories": alert["categories"], "time": time}
        self.dismissals.append(record)
        logger.info("Alert dismissed: %s", record)
        return alert, trace_event(
            "dismissal", time, alert_id=alert["id"], categories=alert["categories"]
        )
