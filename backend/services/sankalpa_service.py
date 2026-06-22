"""
Sankalpa — the will-detection engine.

Sankalpa (Sanskrit: संकल्प) is the intention/resolve formed in the heart. This
service infers the reader's *will* — not merely what they clicked, but what they
are reaching for — from a stream of feedback signals, and distils it into an
evolving "will profile" that steers the Research Article Agent's next topic and
composition.

Two layers of inference:
  1. Heuristic — fast, deterministic nudges from each signal (rating, section
     reaction, kept/dropped images, dwell, scroll).
  2. Reflective — an LLM (`llm_service.reflect_will`) reads the signals against
     the current portrait and proposes higher-order shifts in themes/tones/lenses.

The profile is a single evolving document (this is a single-reader studio).
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.database import sankalpa_collection
from backend.services.llm_service import llm_service


# Axis seeds. Themes grow from feedback; tones/lenses start neutral.
DEFAULT_TONES = ["lyrical", "analytical", "contemplative", "provocative", "intimate", "mythic"]
DEFAULT_LENSES = ["phenomenological", "semiotic", "atmospheric", "historical", "political", "archetypal"]

NUDGE = 12        # weighted-list reinforcement step
FORM_NUDGE = 8    # form scalar step
MAX_THEMES = 14   # keep the theme list from growing unbounded


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _reinforce(items: List[Dict[str, Any]], name: str, delta: float) -> None:
    """Bump (or create) a {name, weight} entry in a weighted list, in place."""
    name = (name or "").strip().lower()
    if not name:
        return
    for it in items:
        if it.get("name", "").lower() == name:
            it["weight"] = _clamp(it.get("weight", 50) + delta)
            return
    if delta > 0:  # only create on positive signal
        items.append({"name": name, "weight": _clamp(50 + delta)})


def _prune(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Drop near-dead entries and keep the strongest `limit`."""
    alive = [it for it in items if it.get("weight", 0) > 8]
    alive.sort(key=lambda it: it.get("weight", 0), reverse=True)
    return alive[:limit]


class SankalpaService:
    """Infers and stores the reader's evolving will profile."""

    def _default_profile(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "key": "primary",  # single-reader studio
            "themes": [],
            "tones": [{"name": t, "weight": 45} for t in DEFAULT_TONES],
            "lenses": [{"name": l, "weight": 45} for l in DEFAULT_LENSES],
            "form": {"length": 50, "image_density": 50, "depth": 50},
            "reading": "A reader still unfolding — no strong leanings inferred yet.",
            "signals_count": 0,
            "created_at": now,
            "updated_at": now,
        }

    async def get_profile(self) -> Dict[str, Any]:
        """Load the will profile, creating a neutral seed if none exists."""
        doc = await sankalpa_collection.find_one({"key": "primary"})
        if not doc:
            doc = self._default_profile()
            await sankalpa_collection.insert_one(dict(doc))
        doc.pop("_id", None)
        return doc

    def portrait(self, profile: Dict[str, Any]) -> str:
        """A compact natural-language portrait for use inside agent prompts."""
        def top(items, n=4):
            ranked = sorted(items, key=lambda it: it.get("weight", 0), reverse=True)[:n]
            return ", ".join(f"{it['name']} ({int(it['weight'])})" for it in ranked) or "none yet"

        form = profile.get("form", {})

        def band(v, low, high):
            return low if v < 40 else (high if v > 60 else "balanced")

        return (
            f"Leaning themes: {top(profile.get('themes', []))}. "
            f"Tones they respond to: {top(profile.get('tones', []))}. "
            f"Interpretive lenses: {top(profile.get('lenses', []))}. "
            f"Form: length {band(form.get('length', 50), 'short', 'long')}, "
            f"image density {band(form.get('image_density', 50), 'sparse', 'image-rich')}, "
            f"depth {band(form.get('depth', 50), 'skimmable', 'deep')}. "
            f"Portrait: {profile.get('reading', '')}"
        )

    def _apply_heuristics(
        self,
        profile: Dict[str, Any],
        signals: List[Dict[str, Any]],
        article: Optional[Dict[str, Any]],
    ) -> None:
        """Fast deterministic nudges from raw signals. Mutates `profile`."""
        article = article or {}
        article_tags = [t.lower() for t in (article.get("source_tags") or [])]
        article_lens = (article.get("angle") or "").lower()
        # map section_id -> heading text for theme attribution
        section_head = {s.get("section_id"): s.get("heading", "") for s in article.get("sections", [])}

        themes = profile.setdefault("themes", [])
        tones = profile.setdefault("tones", [])
        lenses = profile.setdefault("lenses", [])
        form = profile.setdefault("form", {"length": 50, "image_density": 50, "depth": 50})

        for sig in signals:
            stype = sig.get("type")
            p = sig.get("payload", {}) or {}

            if stype == "rating":
                val = float(p.get("value", 3))
                delta = (val - 3) * (NUDGE / 2)  # 1->-1nudge .. 5->+1nudge
                for tag in article_tags:
                    _reinforce(themes, tag, delta)
                if article_lens:
                    _reinforce(lenses, article_lens, delta)

            elif stype == "section":
                reaction = p.get("reaction")
                head = section_head.get(p.get("section_id"), "")
                first_word = head.split()[0].lower() if head else ""
                if reaction == "resonates":
                    _reinforce(themes, first_word, NUDGE)
                elif reaction == "go_deeper":
                    _reinforce(themes, first_word, NUDGE)
                    form["depth"] = _clamp(form.get("depth", 50) + FORM_NUDGE)
                    form["length"] = _clamp(form.get("length", 50) + FORM_NUDGE / 2)
                elif reaction == "not_me":
                    _reinforce(themes, first_word, -NUDGE)
                    for tag in article_tags:
                        _reinforce(themes, tag, -NUDGE / 2)

            elif stype == "image":
                kept = p.get("kept", True)
                form["image_density"] = _clamp(
                    form.get("image_density", 50) + (FORM_NUDGE if kept else -FORM_NUDGE)
                )

            elif stype == "linger":
                # lingering on an image -> wants more images
                if float(p.get("ms", 0)) > 2500:
                    form["image_density"] = _clamp(form.get("image_density", 50) + FORM_NUDGE / 2)

            elif stype == "dwell":
                ms = float(p.get("ms", 0))
                if ms > 9000:
                    form["depth"] = _clamp(form.get("depth", 50) + FORM_NUDGE / 2)
                    head = section_head.get(p.get("section_id"), "")
                    if head:
                        _reinforce(themes, head.split()[0].lower(), NUDGE / 2)
                elif 0 < ms < 1500:
                    form["depth"] = _clamp(form.get("depth", 50) - FORM_NUDGE / 3)

            elif stype == "scroll":
                depth = float(p.get("depth", 0))
                if depth > 85:
                    form["length"] = _clamp(form.get("length", 50) + FORM_NUDGE / 2)
                elif 0 < depth < 35:
                    form["length"] = _clamp(form.get("length", 50) - FORM_NUDGE / 2)

            # "mcq" signals are folded into the reflective LLM step below.

        profile["themes"] = _prune(themes, MAX_THEMES)

    def _apply_reflection(self, profile: Dict[str, Any], reflection: Dict[str, Any]) -> None:
        """Apply the LLM's higher-order will shifts. Mutates `profile`."""
        if not reflection:
            return
        direction = {"up": NUDGE, "down": -NUDGE, "same": 0}

        for entry in reflection.get("themes", []) or []:
            _reinforce(profile.setdefault("themes", []), entry.get("name", ""),
                       direction.get(entry.get("direction", "same"), 0))
        for entry in reflection.get("tones", []) or []:
            _reinforce(profile.setdefault("tones", []), entry.get("name", ""),
                       direction.get(entry.get("direction", "same"), 0))
        for entry in reflection.get("lenses", []) or []:
            _reinforce(profile.setdefault("lenses", []), entry.get("name", ""),
                       direction.get(entry.get("direction", "same"), 0))

        form = profile.setdefault("form", {"length": 50, "image_density": 50, "depth": 50})
        for key, mv in (reflection.get("form", {}) or {}).items():
            if key in form:
                form[key] = _clamp(form[key] + direction.get(mv, 0))

        if reflection.get("reading"):
            profile["reading"] = str(reflection["reading"]).strip()

        profile["themes"] = _prune(profile.get("themes", []), MAX_THEMES)

    def _summarize_signals(self, signals: List[Dict[str, Any]], article: Optional[Dict[str, Any]]) -> str:
        """Human-readable digest of the signal batch for the reflective prompt."""
        article = article or {}
        section_head = {s.get("section_id"): s.get("heading", "") for s in article.get("sections", [])}
        lines = []
        for sig in signals:
            p = sig.get("payload", {}) or {}
            t = sig.get("type")
            if t == "rating":
                lines.append(f"- Rated the article {p.get('value')}/5.")
            elif t == "section":
                lines.append(f'- On section "{section_head.get(p.get("section_id"), "?")}" they reacted: {p.get("reaction")}.')
            elif t == "mcq":
                lines.append(f'- Steering question "{p.get("question")}" → chose "{p.get("choice")}".')
            elif t == "image":
                lines.append(f"- {'Kept' if p.get('kept', True) else 'Dropped'} an image.")
            elif t == "dwell":
                lines.append(f'- Dwelled {int(p.get("ms", 0))}ms on "{section_head.get(p.get("section_id"), "?")}".')
            elif t == "linger":
                lines.append(f"- Lingered {int(p.get('ms', 0))}ms on an image.")
            elif t == "scroll":
                lines.append(f"- Scrolled to {int(p.get('depth', 0))}% of the article.")
        return "\n".join(lines) or "(no notable signals)"

    async def ingest(
        self,
        signals: List[Dict[str, Any]],
        article: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fold a batch of feedback signals into the will profile and persist it.
        Returns the updated profile.
        """
        profile = await self.get_profile()

        # 1) Fast heuristic nudges
        self._apply_heuristics(profile, signals, article)

        # 2) Reflective LLM step (run blocking client off the event loop)
        try:
            summary = self._summarize_signals(signals, article)
            reflection = await asyncio.to_thread(
                llm_service.reflect_will,
                self.portrait(profile),
                summary,
                (article or {}).get("topic") or (article or {}).get("title", "an article"),
            )
            self._apply_reflection(profile, reflection)
        except Exception as e:
            print(f"⚠️ Sankalpa reflection skipped: {e}")

        profile["signals_count"] = profile.get("signals_count", 0) + len(signals)
        profile["updated_at"] = datetime.now(timezone.utc)

        await sankalpa_collection.update_one(
            {"key": "primary"},
            {"$set": {k: v for k, v in profile.items() if k != "_id"}},
            upsert=True,
        )
        return profile


sankalpa_service = SankalpaService()
