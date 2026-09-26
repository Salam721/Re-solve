"""In-memory stores for the demo: feed, pending analyses, moderator queue.

Privacy: comments that are never posted or escalated are not stored. Pending
analyses keep only a hash of the text plus the masked version (10-minute TTL),
and moderator items are deleted after FLAG_RETENTION_HOURS.
"""
import hashlib
import threading
import time
import uuid

from app import config

_lock = threading.Lock()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()


# ---------- Feed ----------

FEED = {
    "post": {
        "id": "p1", "author": "Maya Chen", "handle": "@mayadraws",
        "text": "Finished my first digital painting after three months of practice. Still learning, but I'm proud of this one.",
        "created_at": time.time() - 3600,
    },
    "comments": [
        {"id": "c1", "author": "Jordan", "text": "The colors in the sky are so good. What brushes did you use?", "created_at": time.time() - 3000},
        {"id": "c2", "author": "Priya", "text": "Three months?! This is a huge jump from your sketches.", "created_at": time.time() - 2400},
    ],
}


def add_comment(text: str, author: str = "You") -> dict:
    comment = {"id": uuid.uuid4().hex[:8], "author": author, "text": text, "created_at": time.time()}
    with _lock:
        FEED["comments"].append(comment)
    return comment


# ---------- Pending analyses ----------

_PENDING: dict[str, dict] = {}


def save_pending(analysis_id: str, text: str, analysis: dict) -> None:
    with _lock:
        _purge_pending()
        _PENDING[analysis_id] = {
            "text_hash": text_hash(text), "created_at": time.time(),
            "tier": analysis["tier"], "escalation": analysis["escalation"],
            "category": analysis["category"], "reason": analysis["reason"],
            "moderator_summary": analysis["moderator_summary"], "masked_text": analysis["masked_text"],
        }


def get_pending(analysis_id: str) -> dict | None:
    with _lock:
        _purge_pending()
        return _PENDING.get(analysis_id)


def drop_pending(analysis_id: str) -> None:
    with _lock:
        _PENDING.pop(analysis_id, None)


def _purge_pending() -> None:
    cutoff = time.time() - config.PENDING_TTL_SECONDS
    for key in [k for k, v in _PENDING.items() if v["created_at"] < cutoff]:
        del _PENDING[key]


# ---------- Moderator queue ----------

_FLAGS: list[dict] = []


def add_flag(kind: str, pending: dict) -> dict:
    flag = {
        "id": uuid.uuid4().hex[:8], "created_at": time.time(), "kind": kind,
        "tier": pending["tier"], "category": pending["category"], "reason": pending["reason"],
        "moderator_summary": pending["moderator_summary"], "masked_text": pending["masked_text"],
        "status": "open",
    }
    with _lock:
        _FLAGS.append(flag)
    return flag


def list_flags() -> list[dict]:
    with _lock:
        cutoff = time.time() - config.FLAG_RETENTION_HOURS * 3600
        _FLAGS[:] = [f for f in _FLAGS if f["created_at"] >= cutoff]
        return [f for f in _FLAGS if f["status"] == "open"][::-1]


def resolve_flag(flag_id: str) -> bool:
    with _lock:
        for i, f in enumerate(_FLAGS):
            if f["id"] == flag_id:
                del _FLAGS[i]  # resolved items are deleted, not archived
                return True
    return False


def reset() -> None:
    """Used by tests."""
    with _lock:
        _PENDING.clear()
        _FLAGS.clear()
        del FEED["comments"][2:]
