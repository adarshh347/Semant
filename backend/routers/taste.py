"""
Anuraṇana — the audience side (Darshan Track F).

Three audiences, one store, three very different contracts:

  · the **consumer** writes signals (opt-in only) and reads/deletes their own taste;
  · the **brand** reads anonymized aggregates and contractable-creator matches, never
    a consumer;
  · the **creator** is untouched here — audience taste never flows into the persona.

Identity is an opaque session or account id supplied in `X-Taste-Subject`. No account
is required to enjoy the hook and its forks; an account is the upsell that makes the
portfolio persist (F3 — identity as upsell, not toll). The header is validated to be
opaque, so a client cannot use an email or handle as the key even if it tries.
"""

from fastapi import APIRouter, Header, HTTPException, Query
from typing import List, Optional

from backend.schemas.taste import (
    ConsentRequest, ConsentState, TasteSignalBatch, is_opaque_subject,
)
from backend.services import taste_signal_service as taste
from backend.services.taste_signal_service import ConsentRequired, RateLimited

# Two routers, two trust levels. The consumer surface is public by design — a viewer
# pausing on an image has no curator API key, and demanding one would make identity a
# toll rather than an upsell (F3). The brand surface is mounted behind the API-key gate
# in main.py: aggregate taste intelligence is the product brands pay for, not something
# the open internet reads.
router = APIRouter()
brand_router = APIRouter()


def _subject(x_taste_subject: Optional[str]) -> str:
    """Resolve and validate the opaque subject. Rejecting non-opaque ids here means the
    store can never hold a personal identifier, rather than merely being asked not to."""
    if not x_taste_subject:
        raise HTTPException(status_code=400, detail="X-Taste-Subject header required")
    if not is_opaque_subject(x_taste_subject):
        raise HTTPException(
            status_code=400,
            detail="X-Taste-Subject must be an opaque session/account id "
                   "(8-64 chars, [A-Za-z0-9_-] only — no emails or handles)",
        )
    return x_taste_subject


# ---------------------------------------------------------------------------
# Consent (F4 — explicit opt-in; recommended default, pending Adarsh's confirm)
# ---------------------------------------------------------------------------
@router.get("/consent", response_model=ConsentState)
async def read_consent(x_taste_subject: Optional[str] = Header(default=None)):
    subject = _subject(x_taste_subject)
    return ConsentState(subject=subject, opted_in=await taste.get_consent(subject))


@router.post("/consent", response_model=ConsentState)
async def write_consent(request: ConsentRequest,
                        x_taste_subject: Optional[str] = Header(default=None)):
    """Opt in or out. Nothing is captured before opt-in; opting out stops capture but
    does not itself erase history — `DELETE /taste/signals` does that, deliberately as
    a separate, explicit act."""
    subject = _subject(x_taste_subject)
    state = await taste.set_consent(subject, request.opted_in)
    return ConsentState(**state)


# ---------------------------------------------------------------------------
# The audience write path (F1/F5)
# ---------------------------------------------------------------------------
@router.post("/signals")
async def post_signals(batch: TasteSignalBatch,
                       x_taste_subject: Optional[str] = Header(default=None)):
    """
    Record a batch of audience reactions — a region tap or an Aletheia fork tap.

    These become lightweight `taste_signals` events referencing a real region, never
    `Region` rows. Deferred rungs (dwell, zoom, save_reason, replay) are rejected by the
    schema rather than silently stored: we don't keep data we don't yet aggregate.
    """
    subject = _subject(x_taste_subject)
    try:
        return await taste.record_signals(subject, batch.signals)
    except ConsentRequired as e:
        raise HTTPException(status_code=403, detail=str(e))
    except RateLimited as e:
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# The audience read path — taste given back, not harvested
# ---------------------------------------------------------------------------
@router.get("/portfolio")
async def get_portfolio(x_taste_subject: Optional[str] = Header(default=None)):
    """This subject's own eye, reflected back. Leans are thresholded — one tap is noise."""
    subject = _subject(x_taste_subject)
    try:
        return await taste.portfolio(subject)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/signals")
async def clear_my_taste(x_taste_subject: Optional[str] = Header(default=None)):
    """"Clear my taste" — a real delete of this subject's signals and consent."""
    subject = _subject(x_taste_subject)
    try:
        return await taste.delete_subject(subject)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# The brand tier (F6) — the privacy line the whole thesis rests on
# ---------------------------------------------------------------------------
@brand_router.get("/trends")
async def brand_trends(min_subjects: int = Query(taste.BRAND_MIN_SUBJECTS, ge=1)):
    """Which parts/attributes/lenses are rising, and how many distinct people stand
    behind each — never who. Buckets under the k-anonymity threshold are withheld."""
    return await taste.brand_trends(min_subjects=min_subjects)


@brand_router.get("/creator-matches")
async def brand_creator_matches(
    part: Optional[List[str]] = Query(None, description="Campaign aesthetic, e.g. part=drape&part=hem"),
    limit: int = Query(10, ge=1, le=50),
    min_subjects: int = Query(taste.BRAND_MIN_SUBJECTS, ge=1),
):
    """Match a campaign's aesthetic to **contractable creators**. The only identity in
    this response is a creator handle; consumers appear as counts and nothing else."""
    return await taste.brand_creator_matches(
        parts=part, limit=limit, min_subjects=min_subjects)
