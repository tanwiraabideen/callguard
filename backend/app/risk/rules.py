"""Tier 1: weighted red-flag checks, run on every caller sentence.

A rule fires when any of its patterns matches, unless its guard also matches.
Guards stop reassurance from counting as a threat, such as a real bank saying
"we will never ask for your PIN".
"""

import re
from dataclasses import dataclass

from app.config import settings

NEVER_ASKS = r"\b(never|won'?t|will not|wouldn'?t|don'?t|do not)\b.{0,20}\b(ask|request|need)\b"
NOT_URGENT = r"\b(no|not|nothing|isn'?t)\s+(\w+\s+)?(urgent|rush|hurry)"


@dataclass(frozen=True)
class Rule:
    category: str
    label: str
    weight: float
    patterns: tuple[str, ...]
    guard: str | None = None


RULES = (
    Rule(
        category="codes_or_pins",
        label="asks for a code, PIN or card details",
        weight=settings.rule_weight_codes_or_pins,
        guard=NEVER_ASKS,
        patterns=(
            r"\b(one[- ]?time|\w+[- ]digit|verification|security|authori[sz]ation|sms)\s+(pass)?code\b",
            r"\b(passcode|password|pin|cvv|cvc)\b",
            r"\b(give|tell|read)\b.{0,25}\bcode\b",
            r"\bwhat'?s the code\b",
            r"\bread (it|that|them)( out)? to me\b",
            r"\bcard (details|number)\b",
            r"\b(long|full) number on\b",
            r"\bexpiry date\b",
            r"\b(three|3) digits on the back\b",
        ),
    ),
    Rule(
        category="safe_account",
        label="asks to move money to a 'safe' account",
        weight=settings.rule_weight_safe_account,
        guard=NEVER_ASKS,
        patterns=(
            r"\b(safe|secure|holding|protected)\s+account\b",
            r"\b(move|transfer|send|wire)\b.{0,30}\b(money|funds|savings)\b",
            r"\bwithdraw\b.{0,20}\b(cash|money)\b",
        ),
    ),
    Rule(
        category="gift_cards_or_crypto",
        label="asks for gift cards or crypto",
        weight=settings.rule_weight_gift_cards_or_crypto,
        patterns=(
            r"\bgift\s?(card|voucher|certificate)s?\b",
            r"\b(itunes|amazon|google play|steam)\s+(card|voucher)s?\b",
            r"\b(bitcoin|crypto(currency)?|ethereum|usdt)\b",
            r"\bcodes? on the back\b",
        ),
    ),
    Rule(
        category="secrecy",
        label="demands secrecy or discourages checking",
        weight=settings.rule_weight_secrecy,
        patterns=(
            r"\b(don'?t|do not)\s+(tell|mention|speak to|talk to|inform)\b",
            r"\b(don'?t|do not)\s+(hang up|end the call|put the phone down)\b",
            r"\bkeep (this|it) (between|confidential|secret|quiet)\b",
            r"\bbetween (us|you and me)\b",
            r"\bstay on (this|the) line\b",
        ),
    ),
    Rule(
        category="urgency_or_threats",
        label="uses urgency or threats",
        weight=settings.rule_weight_urgency_or_threats,
        guard=NOT_URGENT,
        patterns=(
            r"\b(warrant|arrest(ed)?|bailiffs?|prosecut\w+|deport\w*)\b",
            r"\b(court|legal) action\b",
            r"\b(right now|immediately|straight away|urgent(ly)?)\b",
            r"\bact (quickly|now|fast)\b",
            r"\b(no time|every second|last chance|be quick|within the hour)\b",
            r"\blose everything\b",
            r"\bat midnight\b",
            r"\bpaid now\b",
            r"\bunless\b.{0,40}\b(today|now)\b",
        ),
    ),
    Rule(
        category="remote_access",
        label="asks to install a remote-access app",
        weight=settings.rule_weight_remote_access,
        patterns=(
            r"\b(anydesk|teamviewer|quicksupport|rustdesk|logmein|ultraviewer)\b",
            r"\bremote (access|desktop|control|support)\b",
            r"\bshare your screen\b",
            r"\b(download|install) (this|an|the)\b.{0,15}\bapp\b",
        ),
    ),
)


def find_rule_hits(sentence: str) -> list[dict]:
    hits = []
    for rule in RULES:
        if rule.guard and re.search(rule.guard, sentence, re.IGNORECASE):
            continue
        for pattern in rule.patterns:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                hits.append(
                    {
                        "category": rule.category,
                        "label": rule.label,
                        "weight": rule.weight,
                        "matched": match.group(0),
                    }
                )
                break
    return hits
