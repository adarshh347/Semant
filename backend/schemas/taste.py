"""
Audience taste signals (Darshan Track F) — the consumer side of Anuraṇana.

The load-bearing call: **an audience tap is not a Region.** A consumer who taps "the
drape moved me" must not mint a researcher-grade `Region` row — that would put
consumer friction into the creator's curated array and bloat every post payload. So a
tap is a lightweight event that *references* an existing `region_id`/`embedding_id`.
`Region.actor="audience"` stays reserved for the rare case where an audience member
marks a genuinely new spot.

Because the signal points at a real `embedding_id`, an audience tap and a creator's
`user_note` resolve to the same FashionCLIP vector — audience taste and creator taste
are comparable in one space, distinguished only by `actor`. That comparability is the
whole two-sided premise.

**No PII.** A subject is an opaque session or account id and nothing else. There is no
name, no email, no IP, no user-agent in this store.

**Video-ready today, video-free today.** `frame_ts` + `media_type` exist so a reel's
region×moment signal lands in this exact schema when B6 unblocks — no migration. The
video *capture* path is deliberately not built here.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The first cut (F5): region tap + Aletheia fork. Highest signal-per-friction, both
# nearly free to serve. Dwell is noisy alone and save_reason adds a tap — deferred, and
# the write path REJECTS them rather than silently accepting data we don't yet aggregate.
SIGNAL_REGION_TAP = "region_tap"
SIGNAL_FORK = "fork"
ACCEPTED_SIGNALS = {SIGNAL_REGION_TAP, SIGNAL_FORK}

# Named now so the schema is stable when they ship; not accepted by the write path yet.
DEFERRED_SIGNALS = {"dwell", "zoom", "save_reason", "replay"}
KNOWN_SIGNALS = ACCEPTED_SIGNALS | DEFERRED_SIGNALS

# A subject id is opaque. This pattern is a hard gate against a client "helpfully"
# passing an email or handle as the session key — the store must not be able to hold
# one even by accident.
SUBJECT_MIN, SUBJECT_MAX = 8, 64
_SUBJECT_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")

MAX_BATCH = 50          # client batches events; one POST must not carry a session's flood
MAX_CHOICE_CHARS = 160


def is_opaque_subject(subject: str) -> bool:
    """True when `subject` looks like a session/account id and nothing else.

    Rejects '@' and '.' outright, which is what an email or an instagram handle would
    carry. Deliberately strict: a signal store that cannot express a person's identity
    cannot leak one.
    """
    if not subject or not (SUBJECT_MIN <= len(subject) <= SUBJECT_MAX):
        return False
    return all(c in _SUBJECT_ALLOWED for c in subject)


class TasteSignalIn(BaseModel):
    """One audience reaction. Everything but `post_id` and `signal_type` is optional,
    because the point is that the consumer never fills anything in."""

    model_config = ConfigDict(extra="forbid")   # a client cannot smuggle extra fields in

    post_id: str
    signal_type: str
    region_id: Optional[str] = None      # rung 2: which part
    lens: Optional[str] = None           # rung 3: which lens the fork came from
    prompt: Optional[str] = None         # the fork's question
    choice: Optional[str] = None         # the option they tapped
    choice_index: Optional[int] = None
    # Video-readiness (B6). Present in the schema, unused by the image loop.
    media_type: str = "image"            # image | video
    frame_ts: Optional[float] = None     # seconds into the reel

    @field_validator("signal_type")
    @classmethod
    def _known_and_accepted(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in KNOWN_SIGNALS:
            raise ValueError(f"unknown signal_type '{v}'")
        if v not in ACCEPTED_SIGNALS:
            raise ValueError(
                f"signal_type '{v}' is deferred (first cut is {sorted(ACCEPTED_SIGNALS)})"
            )
        return v

    @field_validator("choice", "prompt", "lens")
    @classmethod
    def _bounded_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip()[:MAX_CHOICE_CHARS]

    @field_validator("media_type")
    @classmethod
    def _media(cls, v: str) -> str:
        v = (v or "image").strip().lower()
        if v not in {"image", "video"}:
            raise ValueError("media_type must be image or video")
        return v


class TasteSignalBatch(BaseModel):
    """Clients batch events and POST periodically — never one request per tap."""
    model_config = ConfigDict(extra="forbid")

    signals: List[TasteSignalIn] = Field(default_factory=list, max_length=MAX_BATCH)


class ConsentRequest(BaseModel):
    """Explicit opt-in (F4). Nothing is captured until this is true; withdrawing it
    stops capture, and `DELETE /taste/signals` empties what was captured."""
    model_config = ConfigDict(extra="forbid")

    opted_in: bool


class ConsentState(BaseModel):
    subject: str
    opted_in: bool
    updated_at: Optional[datetime] = None
