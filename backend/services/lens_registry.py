"""
Aletheia's lens registry (Darshan Track C · §2/§3) — the reading's context trigger.

Aletheia used to read every image through the same three lenses (Phenomenological,
Semiotic, Atmospheric), hard-coded into the prompt. This module replaces that with a
**domain → lens registry**: a small, fixed, legible config the LLM *instantiates* over
a particular image, rather than a set of lenses the LLM invents per image. Fixed names
mean the UI can label them and Track D can build the lens↔region hover-highlight on a
stable vocabulary.

Selection reads three signals, all optional:
  · `domain`      — FashionCLIP's router first-cut (Track B): fashion | architecture | …
  · `parts` / `attributes` — what was actually detected in the image (Track A/B)
  · `persona_lenses` — the lenses that recurrently fire for this curator (Track C §6.3)

**The wildcard rule.** The persona prior makes readings personal; unchecked, it makes
them an echo chamber (always reading for drape). So one lens slot is always filled
*ignoring history entirely* — the image keeps its right to surprise. `select_lenses`
guarantees this, and reports which lens was the wildcard so the reading can disclose it.

Everything degrades: no domain and no context → the general three, i.e. exactly today's
reading. Nothing regresses when Track B hasn't run on an image.
"""

from typing import Dict, List, Optional, Sequence, Tuple

# --- The registry: lens name → what that lens attends to (the LLM's instruction) ----
# Names are the stable, user-visible vocabulary. Keep them short; the UI renders them.
LENS_DEFINITIONS: Dict[str, str] = {
    # general (today's three — the fallback set)
    "Phenomenological": "how it meets a lived body: weight, texture, temperature, movement, where the eye is pulled.",
    "Semiotic": "its denotation vs connotation; what it culturally signifies.",
    "Atmospheric": "the mood/Stimmung it radiates, the emotional temperature.",
    # fashion
    "Silhouette": "the outline the body cuts: line, volume, where the shape is severe or generous.",
    "Drape": "how the material falls, gives, resists — the physics of the cloth against the body.",
    "Era": "what period, subculture, or lineage this quotes, knowingly or not.",
    "Styling-logic": "the choices behind the assembly: what was put with what, and what that intends.",
    "Mood/Story": "the narrative the outfit proposes; who this person is being, in this frame.",
    # architecture
    "Structure": "line, load, and how the thing stands: what carries and what is carried.",
    "Material/Texture": "the surfaces and their grain — what the hand would feel.",
    "Light/Shadow": "how light enters, falls, and carves the space.",
    "Scale/Space": "the body's size against the space; enclosure, expanse, threshold.",
    # photography
    "Composition": "the frame's geometry: what is placed where, what is cropped away.",
    "Light": "the quality, direction, and temperature of the light itself.",
    "Subject/Gesture": "the posture, the held moment, what the body is doing.",
    "Colour": "the palette and its emotional work.",
}

# Domain → the lens set that replaces the fixed three.
DOMAIN_LENSES: Dict[str, List[str]] = {
    "fashion": ["Silhouette", "Drape", "Era", "Styling-logic", "Mood/Story"],
    "architecture": ["Structure", "Material/Texture", "Light/Shadow", "Scale/Space", "Atmospheric"],
    "photography": ["Composition", "Light", "Subject/Gesture", "Colour", "Atmospheric"],
}
GENERAL_LENSES: List[str] = ["Phenomenological", "Semiotic", "Atmospheric"]

# Detected part/attribute substrings that bias a lens upward. A region labelled
# "drape or fold" should make the Drape lens fire harder and attend to that region.
LENS_TRIGGERS: Dict[str, Sequence[str]] = {
    "Drape": ("drape", "fold", "pleated", "flowing", "ruffled", "silk", "satin", "sheer"),
    "Silhouette": ("silhouette", "fitted", "loose", "structured", "shoulder", "waistband", "bodice", "hem"),
    "Era": ("vintage", "retro", "embroidered", "lapel", "corset", "brocade"),
    "Styling-logic": ("accessory", "belt", "bag", "jewellery", "shoe", "layered"),
    "Material/Texture": ("texture", "matte", "glossy", "grain", "concrete", "wood", "brick"),
    "Colour": ("colour", "color", "striped", "floral print", "patterned", "solid colour"),
    "Light/Shadow": ("shadow", "highlight", "backlit", "glow"),
    "Composition": ("frame", "horizon", "symmetry"),
}

# Weights. Kept small and explicit so the prior can never dominate the image's own
# evidence: a trigger the image actually produced outweighs a habit of the curator's.
_W_BASE = 1.0        # membership in the domain's set
_W_TRIGGER = 0.5     # per matching detected part/attribute (capped)
_W_HINT = 1.0        # the curator's free-text lens intention
_W_PRIOR = 0.4       # this curator's recurring lens (bounded; see PRIOR_CAP)
_TRIGGER_CAP = 1.5   # a single lens can gain at most this much from triggers
PRIOR_CAP = 0.4      # a lens gains the prior at most once — history nudges, never decides

# The prior is DATA-GATED (settled: "prior + wildcard, data-gated"). Two readings do not
# establish that someone reads for drape; they establish that a model said "drape" twice.
# So the prior's strength ramps with the corpus: zero below the floor, linear to full.
# The mechanism is built once and self-activates as taste actually accrues.
PRIOR_RAMP_FLOOR = 3    # fewer structured readings than this → no prior at all
PRIOR_RAMP_FULL = 12    # at/above this → the prior carries its full (still capped) weight

MAX_LENSES_DEEP = 4
MAX_LENSES_HOOK = 1


def prior_strength(reading_count: int) -> float:
    """How much this curator's history is allowed to bias the next reading, in [0, 1].

    Cold start is exactly 0: on a thin corpus the "recurring" lenses are noise, and
    biasing on them would manufacture a taste rather than observe one.
    """
    if reading_count < PRIOR_RAMP_FLOOR:
        return 0.0
    if reading_count >= PRIOR_RAMP_FULL:
        return 1.0
    span = PRIOR_RAMP_FULL - PRIOR_RAMP_FLOOR
    return (reading_count - PRIOR_RAMP_FLOOR) / span


def _trigger_score(lens: str, haystack: str) -> float:
    """How strongly the image's own detected parts/attributes call for this lens."""
    triggers = LENS_TRIGGERS.get(lens, ())
    hits = sum(1 for t in triggers if t in haystack)
    return min(hits * _W_TRIGGER, _TRIGGER_CAP)


def select_lenses(
    domain: Optional[str] = None,
    parts: Optional[Sequence[str]] = None,
    attributes: Optional[Sequence[str]] = None,
    persona_lenses: Optional[Sequence[str]] = None,
    lens_hint: str = "",
    depth: str = "deep",
    prior_strength: float = 1.0,
) -> Tuple[List[str], dict]:
    """
    Choose which lenses fire for this image.

    `prior_strength` in [0, 1] scales how much `persona_lenses` may bias the choice —
    see `prior_strength()`, which ramps it with the size of the curator's corpus. At 0
    the prior is inert in every respect, including the wildcard preference.

    Returns `(lens_names, provenance)`. `provenance` records what drove the choice —
    `{base, wildcard, prior_applied, prior_strength, triggered}` — so the reading can
    disclose when the curator's history (not the image) put a lens on the page.

    Guarantees:
      · The wildcard slot is scored on the image alone — the prior is never consulted
        for it — and prefers a lens outside the curator's habits.
      · Consequently: **if the domain offers any lens this curator's history does not
        favour, the chosen set contains at least one** (it either won a slot on its own
        evidence, or it is preferred into the wildcard slot). An accrued taste can bias
        the reading; it cannot close it.
      · A lens the image actually evidences outranks a lens the curator merely favours
        (`PRIOR_CAP` < `_W_TRIGGER`): history nudges, evidence decides.
      · With no domain and no context, returns the general three — today's behavior.
    """
    base = DOMAIN_LENSES.get((domain or "").lower(), GENERAL_LENSES)
    haystack = " ".join(str(x).lower() for x in list(parts or []) + list(attributes or []))
    hint = (lens_hint or "").lower()
    strength = max(0.0, min(1.0, float(prior_strength)))
    # A zero-strength prior is no prior: it must not even steer the wildcard away from
    # a lens, or a cold-start persona would silently shape the reading it cannot justify.
    prior = {str(p) for p in (persona_lenses or [])} if strength > 0 else set()
    prior_weight = min(_W_PRIOR, PRIOR_CAP) * strength

    # Two scores per lens: the honest one (image only) and the personalized one.
    image_score, full_score = {}, {}
    for lens in base:
        s = _W_BASE + _trigger_score(lens, haystack)
        if hint and lens.lower() in hint:
            s += _W_HINT
        image_score[lens] = s
        full_score[lens] = s + (prior_weight if lens in prior else 0.0)

    if depth == "hook":
        # One distilled lens; the hook is a taste of the reading, not the reading.
        best = max(full_score, key=lambda l: (full_score[l], -base.index(l)))
        return [best], {"base": base, "wildcard": None, "prior_applied": best in prior,
                        "prior_strength": strength,
                        "triggered": [l for l in base if _trigger_score(l, haystack) > 0]}

    k = min(MAX_LENSES_DEEP, len(base))
    # Rank by the personalized score, but hold the last slot open.
    ranked = sorted(base, key=lambda l: (-full_score[l], base.index(l)))
    chosen = ranked[: max(1, k - 1)]

    # The wildcard slot. Scored on IMAGE evidence alone, and drawn from lenses the
    # curator's history did NOT favour — so every reading carries at least one lens
    # their habits didn't put there. Only if the prior covers every remaining lens do
    # we fall back to the best image score outright. With no prior (the common case)
    # this is simply the next-best lens: no behavior change.
    remaining = [l for l in base if l not in chosen]
    unhabitual = [l for l in remaining if l not in prior] or remaining
    wildcard = None
    if remaining:
        wildcard = max(unhabitual, key=lambda l: (image_score[l], -base.index(l)))
        chosen.append(wildcard)

    return chosen, {
        "base": base,
        "wildcard": wildcard,
        "prior_applied": sorted(l for l in chosen if l in prior),
        "prior_strength": strength,
        "triggered": [l for l in chosen if _trigger_score(l, haystack) > 0],
    }


def render_lens_block(lens_names: Sequence[str]) -> str:
    """The prompt's LENSES section — the chosen lenses and what each attends to."""
    lines = []
    for i, name in enumerate(lens_names, 1):
        desc = LENS_DEFINITIONS.get(name, "read the image through this lens.")
        lines.append(f"   {i}. {name} — {desc}")
    return "\n".join(lines)


def render_context_header(
    domain: Optional[str] = None,
    parts: Optional[Sequence[str]] = None,
    attributes: Optional[Sequence[str]] = None,
    regions: Optional[Sequence[dict]] = None,
) -> str:
    """
    The context the lenses stand on: what the detectors actually found. Region ids are
    listed so the model can anchor each claim to a real part (§3's `region_ids`), and
    we only ever offer ids that exist on the post — a claim can't cite a phantom.
    """
    if not any([domain, parts, attributes, regions]):
        return ""
    lines = ["CONTEXT (what the detectors found in THIS image — ground your claims here):"]
    if domain:
        lines.append(f"- Domain: {domain}")
    if parts:
        lines.append(f"- Salient parts: {', '.join(dict.fromkeys(str(p) for p in parts))[:400]}")
    if attributes:
        lines.append(f"- Attributes: {', '.join(dict.fromkeys(str(a) for a in attributes))[:400]}")
    if regions:
        listed = ", ".join(
            f"{r.get('id')}({r.get('label') or r.get('part') or r.get('category') or '?'})"
            for r in regions[:14] if r.get("id")
        )
        # Imperative, not permissive: a lens whose claim points at no part cannot be
        # highlighted on the image, and the reading↔geometry link is the whole point.
        lines.append(
            f"- PART IDS — every lens MUST cite 1–3 of these in its `region_ids`, "
            f"choosing the parts its claim actually rests on: {listed}"
        )
    return "\n".join(lines)


def recurring_lenses(local_contexts: Sequence[dict], top_n: int = 3) -> List[str]:
    """
    Which lenses habitually fire for this curator, weighted by how strongly they spoke
    (§6.3's prior). Reads the structured readings the persona now keeps; returns [] for
    a persona that predates the structured roll-up, so the prior is simply absent.
    """
    weight: Dict[str, float] = {}
    for lc in local_contexts or []:
        for lens in ((lc.get("reading") or {}).get("lenses") or []):
            name = str(lens.get("name") or "").strip()
            if name in LENS_DEFINITIONS:
                weight[name] = weight.get(name, 0.0) + max(0, int(lens.get("intensity") or 0))
    return [n for n, _ in sorted(weight.items(), key=lambda kv: -kv[1])[:top_n]]
