"""Privacy-safe recipient and approval-content normalization helpers."""

import hashlib
import json
import re
from typing import Any

EMAIL_PATTERN = re.compile(r"^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$")
RECIPIENT_SEPARATOR = re.compile(r"[,;\n]")


class RecipientValidationError(ValueError):
    pass


def normalize_recipients(value: str | None, *, required: bool) -> str | None:
    candidate = value.strip() if isinstance(value, str) else ""
    if not candidate:
        if required:
            raise RecipientValidationError("A To recipient is required.")
        return None
    # Empty list elements are deliberately not silently discarded.
    parts = RECIPIENT_SEPARATOR.split(candidate)
    if any(not part.strip() for part in parts):
        raise RecipientValidationError("Enter valid recipient email addresses.")
    addresses = [part.strip() for part in parts]
    if any(not EMAIL_PATTERN.fullmatch(address) for address in addresses):
        raise RecipientValidationError("Enter valid recipient email addresses.")
    return ", ".join(addresses)


def approval_content_hash(record: dict[str, Any]) -> str:
    outreach = record.get("outreach_items") or record.get("outreach_item")
    if not isinstance(outreach, dict):
        raise ValueError("Draft content is unavailable.")
    subject = _normalize_text(record.get("subject"))
    body = _normalize_text(record.get("body"))
    resume_id = outreach.get("selected_resume_id")
    payload = {
        "to": normalize_recipients(outreach.get("recipient_to"), required=True),
        "cc": normalize_recipients(outreach.get("recipient_cc"), required=False),
        "subject": subject,
        "body": body,
        "resume_id": resume_id,
    }
    if not subject.strip() or not body.strip() or not resume_id:
        raise ValueError("Draft content is unavailable.")
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: object) -> str:
    return value if isinstance(value, str) else ""
