"""
Semant Writer W7 — the live proof. The alignment reading against the REAL model.

The suite stubs the model so a dropped flag, a thin passage and a taste-wall breach can be
forced deterministically. This script does the opposite, and it is the only way to know
whether the wall holds: it hands a real Groq model real prose and real declarations, and
checks that what comes back is bounded by what the author said.

Two of these checks are the whole gate, and both are about what the reading DOES NOT say:

  §8.2 THE TASTE WALL. Prose with an obvious, genuine craft problem that no operator and no
  `//` note names. A generic editor raises it and looks helpful. This one may not — no
  declared element covers it, so it is not the reading's to say. If the model volunteers it
  anyway, `ground_flags` must drop it before the author sees it, and the drop must show up
  in the diagnostics. A live PASS here means either the model held the line or the guard
  caught it; the diagnostics say which, and both are correct outcomes.

  §8.3 SILENCE. A passage whose operators say what they ARE but not what they should DO.
  There is nothing to measure, and the honest answer is to say so. The failure mode is
  invented advice, which is the same fabrication the render side spent five gates refusing.

DATA SAFETY. Runs ONLY against a manuscript `writer_fixture_manuscript.py` made, keyed on
its marker, and drops it at the end unless `--keep` is passed. Nothing here can write prose
in any case — that is §8.5, and it is asserted rather than assumed.

    python scripts/writer_w7_proof.py            # make fixture, prove, drop
    python scripts/writer_w7_proof.py --keep     # leave the fixture for inspection
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import manuscript_collection                    # noqa: E402
from backend.services.manuscript_service import manuscript_service    # noqa: E402
from backend.services.writer import alignment, instrument, readings   # noqa: E402
from backend.services.writer.operators import operator_registry       # noqa: E402
from backend.services.writer.render import OK                         # noqa: E402
from backend.services.writer.studio import run_block                  # noqa: E402
from scripts import writer_fixture_manuscript as fixture              # noqa: E402

FAILURES: list = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if detail:
        print(f"        {detail}")
    if not condition:
        FAILURES.append(label)


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 66 - len(title)))


def show(result: "alignment.AlignmentResult") -> None:
    print(f"        → {result.status}")
    for flag in result.flags:
        print(f"          [{flag['element']}] {flag['span'][:56]!r}")
        print(f"              {flag['divergence'][:70]}")
    for note in result.diagnostics:
        print(f"          (dropped) {note[:88]}")


#: The passage the whole proof reads. Written to honour `restraint` and `//avoid melodrama`.
ALIGNED_PROSE = (
    "The latch gave before she had decided to push it. She stood in the doorway with her "
    "hand still raised, and did not go in."
)

#: The same moment, written to break exactly the thing the author declared.
DIVERGENT_PROSE = (
    "Her heart shattered into a thousand aching pieces as the latch gave, and a tidal wave "
    "of grief crashed over her soul, drowning her in unbearable, endless sorrow."
)

#: A REAL craft problem — three sentences opening identically — that no operator and no
#: `//` note names. This is the §8.2 bait, and it is deliberately worth mentioning.
UNDECLARED_ISSUE_PROSE = (
    "She waited by the door. She waited while the hall clock counted. She waited until the "
    "light in the window had gone."
)


async def prove(keep: bool) -> int:
    section("fixture")
    await fixture.drop(quiet=True)
    ms = await manuscript_service.create_manuscript(
        "W7 fixture manuscript", synopsis="A scratch manuscript for the W7 live proof."
    )
    await manuscript_collection.update_one(
        {"_id": ms["id"]}, {"$set": {"fixture_marker": fixture.MARKER}}
    )
    ms = await manuscript_service.add_chapter(ms["id"], "Chapter one")
    scene = await manuscript_service.add_scene(ms["id"], ms["chapters"][0]["id"], "Scene one")
    manuscript_id, scene_id = ms["id"], scene["id"]
    project = manuscript_id
    print(f"  manuscript {manuscript_id}  scene {scene_id}")

    guard = await manuscript_collection.find_one({"_id": manuscript_id})
    if (guard or {}).get("fixture_marker") != fixture.MARKER:
        print("REFUSING: this manuscript is not a fixture this script made.")
        return 1

    try:
        # ── the ontology ─────────────────────────────────────────────────────
        section("the author's declarations")
        await operator_registry.create(
            project, "restraint",
            "what is withheld does more work than what is said",
            rendering_intent="say less than the moment wants; never name the feeling outright",
            negative_examples=["Her heart shattered into a thousand pieces."],
        )
        await operator_registry.create(
            project, "bare",
            "a threshold: a crossing noticed only once it is behind them",
        )
        ontology = await operator_registry.by_name(project)
        check("`restraint` declares a rendering intent and a negative example",
              bool(ontology["restraint"]["rendering_intent"])
              and bool(ontology["restraint"]["negative_examples"]))
        check("`bare` declares what it IS and nothing it should DO",
              not ontology["bare"].get("rendering_intent"))

        prov = {
            "operators": [{"name": "restraint", "version": 1, "source": "direct"}],
            "intents": [{"key": "avoid", "value": "melodrama"}],
        }
        elements = alignment.declared_elements(prov, ontology)
        ids = {e["id"] for e in elements}
        check("the standard is the intents + operator intents + negative examples",
              {"intent:avoid", "operator:restraint:intent", "operator:restraint:not:0"} <= ids,
              str(sorted(ids)))
        check("an operator DEFINITION is not part of the standard",
              "what is withheld" not in " ".join(e["declared"] for e in elements))

        # ── 1 · aligned, then a forced divergence ────────────────────────────
        section("1 · a rendered passage reads aligned; a divergent one is flagged")
        block = "// avoid: melodrama\n/ restraint(she stops in the doorway)\n"
        run = await run_block(project, block, manuscript_id=manuscript_id,
                              scene_id=scene_id, quarantine=False)
        rendered = next((r for r in run["results"] if r["status"] == OK), None)
        check("the render loop produced a passage to read", rendered is not None)

        if rendered is not None:
            print(f"        rendered: {rendered['text'][:110]!r}")
            live = await alignment.read_alignment(
                project, rendered["text"], rendered["provenance"], ontology)
            show(live)
            check("a real render is read without error",
                  live.status in (alignment.ALIGNED, alignment.FLAGGED))
            check("every flag on a REAL render cites a declared element",
                  all(f["element"] in ids for f in live.flags))

        # The author's own prose, deliberately honouring both declarations.
        clean = await alignment.read_alignment(project, ALIGNED_PROSE, prov, ontology)
        show(clean)
        check("prose that honours the declarations reads ALIGNED",
              clean.status == alignment.ALIGNED,
              f"status={clean.status}")

        divergent = await alignment.read_alignment(project, DIVERGENT_PROSE, prov, ontology)
        show(divergent)
        check("prose that breaks `//avoid melodrama` IS flagged",
              divergent.status == alignment.FLAGGED, f"status={divergent.status}")
        cited = {f["element"] for f in divergent.flags}
        check("the flag cites `//avoid melodrama` or `restraint` BY REFERENCE",
              bool(cited & {"intent:avoid", "operator:restraint:intent",
                            "operator:restraint:not:0"}),
              f"cited={sorted(cited)}")

        # ── 2 · THE TASTE WALL ───────────────────────────────────────────────
        section("2 · THE TASTE WALL — an undeclared quality issue is not raised")
        print(f"        bait: {UNDECLARED_ISSUE_PROSE!r}")
        print("        (three identical sentence openings — a real problem no element names)")
        bait = await alignment.read_alignment(project, UNDECLARED_ISSUE_PROSE, prov, ontology)
        show(bait)

        check("EVERY flag that reached the author cites a declared element id",
              all(f["element"] in ids for f in bait.flags),
              f"elements={[f['element'] for f in bait.flags]}")
        # The bait is repetition, and repetition is named by nothing the author declared.
        # A flag whose divergence is ABOUT the repetition, even wearing a real element id,
        # is the wall failing in the way that matters — so look at the words too.
        craft_words = ("repet", "repeat", "same way", "vary", "variety", "monoton",
                       "sentence length", "rhythm", "stronger verb")
        leaked = [f for f in bait.flags
                  if any(w in (f["divergence"] or "").lower() for w in craft_words)]
        check("no flag critiques the undeclared craft issue", not leaked,
              f"leaked={[f['divergence'][:60] for f in leaked]}")
        if bait.diagnostics:
            print("        (the guard did work — the model tried and was dropped)")

        # ── 3 · silence ──────────────────────────────────────────────────────
        section("3 · refusal as silence — a thin passage says so")
        thin_prov = {"operators": [{"name": "bare", "version": 1, "source": "direct"}],
                     "intents": []}
        thin = await alignment.read_alignment(project, ALIGNED_PROSE, thin_prov, ontology)
        show(thin)
        check("a passage with nothing declared to DO reports THIN",
              thin.status == alignment.THIN, f"status={thin.status}")
        check("and invents no advice", thin.flags == ())
        check("and says what would make it readable",
              "Little declared intent" in thin.detail)

        # ── 4 · scope ────────────────────────────────────────────────────────
        section("4 · scope — author-typed prose is not critiqued at all")
        typed = await alignment.read_alignment(project, DIVERGENT_PROSE, {}, ontology)
        show(typed)
        check("an unprovenanced span returns NO_PROVENANCE",
              typed.status == alignment.NO_PROVENANCE, f"status={typed.status}")
        check("even melodrama the author typed themselves is not flagged", typed.flags == ())
        check("`restraint` is never applied to prose it did not make",
              "restraint" not in typed.detail)

        # ── 5 · canon untouched ──────────────────────────────────────────────
        section("5 · canon untouched across the whole session (I1)")
        before = (await manuscript_service.export_manuscript(manuscript_id))["content"]

        stored = await readings.store(project, divergent, scene_id=scene_id,
                                      manuscript_id=manuscript_id)
        for extra in (clean, bait, thin, typed):
            await readings.store(project, extra, scene_id=scene_id,
                                 manuscript_id=manuscript_id)

        after = (await manuscript_service.export_manuscript(manuscript_id))["content"]
        check("the manuscript export is byte-identical after every reading", after == before,
              f"{len(before)} bytes")
        check("no reading result carries prose",
              all(not hasattr(r, "text") for r in (clean, divergent, bait, thin, typed)))
        check("no flag carries a rewrite",
              all("rewrite" not in f and "replacement" not in f
                  for r in (divergent, bait) for f in r.flags))

        # ── 6 · the reading is itself audited ────────────────────────────────
        section("6 · the reading is itself audited")
        audited = await readings.get(stored["id"])
        check("the reading records the elements it measured against",
              bool(audited["measured_against"]),
              str([e["id"] for e in audited["measured_against"]]))
        check("the reading records the model that made it", bool(audited["model"]),
              str(audited["model"]))
        check("every measured element resolves to something the author declared",
              all(e["id"] in ids and e["declared"] for e in audited["measured_against"]))
        for element in audited["measured_against"]:
            if element.get("operator"):
                pinned = await operator_registry.resolve_version(
                    project, element["operator"], element["operator_version"])
                check(f"cited {element['operator']}@{element['operator_version']} resolves",
                      pinned is not None)

        # ── 7 · the calibration signal ───────────────────────────────────────
        section("7 · the calibration signal — flag + author's response")
        flag = audited["flags"][0] if audited["flags"] else None
        check("the stored flag starts open", bool(flag) and flag["state"] == readings.OPEN)
        if flag:
            decided = await readings.decide(stored["id"], flag["id"], readings.ACTED)
            check("the author's decision sticks",
                  decided["flags"][0]["state"] == readings.ACTED)

            still = (await manuscript_service.export_manuscript(manuscript_id))["content"]
            check("deciding a flag changed no prose", still == before)
            ontology_after = await operator_registry.by_name(project)
            check("deciding a flag changed no operator", ontology_after == ontology)

        events = await instrument.usage_for_project(project, limit=500)
        kinds = {}
        for e in events:
            kinds[e["event"]] = kinds.get(e["event"], 0) + 1
        check("readings and the author's response were recorded",
              {alignment.READ, alignment.FLAG_ACTED} <= set(kinds), str(kinds))
        acted = next((e for e in events if e["event"] == alignment.FLAG_ACTED), None)
        check("the response names the operator/element the flag cited",
              bool(acted) and bool(acted["extra"].get("element")),
              str((acted or {}).get("extra")))

        print("\n" + "=" * 70)
        if FAILURES:
            print(f"FAILED — {len(FAILURES)} check(s): " + "; ".join(FAILURES))
        else:
            print("W7 PROVED — the reading critiques only in the author's own language.")
        print("=" * 70)
        return 1 if FAILURES else 0

    finally:
        if keep:
            print(f"\n(fixture kept: manuscript {manuscript_id})")
        else:
            await fixture.drop(quiet=True)
            print("\n(fixture dropped)")


if __name__ == "__main__":
    sys.exit(asyncio.run(prove(keep="--keep" in sys.argv)))
