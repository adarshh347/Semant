"""
HARNESS-002B — the deliberation steward: the missing human turn in an automated inquiry.

## What this package is

An inquiry that can only proceed or stop has no place for the person whose question it is. This
package is the third option: a pure, replayable state machine that receives forks somebody upstream
declared, settles the ones it may settle alone and RECORDS doing so, opens a concrete question when
a person's answer would change the work, and resumes the same session from their reply.

    candidates.py    an opaque mapping → a fork, with the kind READ and never inferred
    policy.py        whether to ask, from the contract's pause classification
    steward.py       the fork, worded; and the wall around a model that may reword it
    machine.py       the append-only transitions, the nine conflicts, and replay
    projections.py   what a workbench reads, derived from the log and never stored beside it
    conflicts.py     nine typed refusals, so 'stale' and 'unknown option' are not one thing
    fixtures.py      two domain-neutral fixtures that share no vocabulary

## Why this is not the Director's `Question`

`director/questions.py` names a verified-missing execution PARAM — currently a phrase — that a
person can supply so a blocked run resumes. It is narrow on purpose and it works. Its principles
are reused here in full: grounded in what exists, same-run continuation, append-only trace, and no
question when the system can answer itself.

What is NOT reused is the type. Semantic deliberation is choosing an interpretation, a scope, an
operationalisation, a judgement of a returned result or a direction — and none of those is a
missing parameter. Widening `Question` until it covered them would leave the Director's proven
narrow case sharing a shape with five things it has nothing to do with, and "missing_param" would
become a field that means nothing in most of its uses.

## What this package will not do

No persistence, no route, no frontend, no model call, no semantic compilation, and no clock it was
not handed. A session is a VALUE. Which store carries it, what HTTP maps onto the nine conflicts,
and which thinker role binds to `RequestFormatter` are the integration lane's decisions, and this
package is arranged so that none of them requires reopening it:

  · `to_dict`/`from_dict` round-trip losslessly, so persistence is a store and a load;
  · every conflict is typed and carries `recoverable`, so the 409/422 split is readable;
  · `RequestFormatter` is a Protocol with a fully capable deterministic implementation, so binding
    a model role is an addition rather than a replacement.

The goal engine's reconciliation already recommends `runs` via `run_store` for its sibling object
(`inquiry_engine/__init__.py`), and nothing here argues for a different one — an interaction state
is the same kind of thing: a session's continuity between requests.

## The one law worth stating twice

**A user's direction changes goals. It never becomes measured evidence.** A person saying "that is
a loggia, not a portico" adds a claim authored by a person; it does not edit the model's claim and
it does not make either one measured. Both halves are enforced rather than documented: an amendment
is a new object with `actor` frozen to `user`, and the provenance of both responses and amendments
refuses status keys outright — provenance being the only free-form dict on either object, and
therefore the only place a status could arrive.
"""
from __future__ import annotations

#: Where an interaction state should eventually be persisted, stated as a constant rather than left
#: in prose — the goal engine learned that a recommendation only in prose is one a persistence lane
#: can miss. NOTHING in this package writes there.
RECOMMENDED_SESSION_STORE = "runs"
RECOMMENDED_SESSION_STORE_MODULE = "backend.services.run_store"
