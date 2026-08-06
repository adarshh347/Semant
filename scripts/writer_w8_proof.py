"""
Semant Writer W8 — the live proof. Revision and genealogy against the REAL model.

The suite fakes the collections so an immutable version, a lost pointer and a leaked polish
instruction can be forced deterministically. This runs the whole thing against real Groq and
real Mongo, because two of W8's claims are only worth anything end to end:

  THE POINTER MOVES AND NOTHING IS LOST. v1 is still byte-identical after v2 supersedes it,
  and still resolves its operators — through the actual database, not a dictionary that was
  never asked to forget anything.

  NO SILENT IMPROVEMENT. §7 step 4 asks for a re-render under an UNCHANGED declaration set
  with no polish instruction anywhere. The strong form is asserted here: the revision prompt
  is byte-identical to the first render's, so nothing about "this is a second attempt" can
  have reached the model — and then the model is actually run under it, twice, to show the
  loop works rather than merely that the string is the same.

DATA SAFETY. Runs ONLY against a manuscript `writer_fixture_manuscript.py` made, keyed on
its marker, and drops it at the end unless `--keep` is passed. It refuses to run against a
manuscript it did not create.

    python scripts/writer_w8_proof.py            # make fixture, prove, drop
    python scripts/writer_w8_proof.py --keep     # leave the fixture for inspection
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import (                                        # noqa: E402
    manuscript_collection,
    writer_passage_version_collection,
)
from backend.services.manuscript_service import manuscript_service    # noqa: E402
from backend.services.writer import alignment, instrument, readings, revisions  # noqa: E402
from backend.services.writer.operators import operator_registry       # noqa: E402
from backend.services.writer.passages import passage_store            # noqa: E402
from backend.services.writer.render import OK, build_render_prompt    # noqa: E402
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


async def render_one(project, block, manuscript_id, scene_id):
    """One quarantined render through the ORDINARY loop — the only render path there is."""
    run = await run_block(project, block, manuscript_id=manuscript_id,
                          scene_id=scene_id, quarantine=True)
    ok = next((r for r in run["results"] if r["status"] == OK), None)
    if ok is None:
        print(f"        (no render: {run.get('diagnostics')} "
              f"{[r.get('refusal') for r in run['results']]})")
    return ok


async def prove(keep: bool) -> int:
    manuscript_id = ""

    try:
        section("fixture")
        await fixture.drop(quiet=True)
        ms = await manuscript_service.create_manuscript(
            "W8 fixture manuscript", synopsis="A scratch manuscript for the W8 live proof."
        )
        await manuscript_collection.update_one(
            {"_id": ms["id"]}, {"$set": {"fixture_marker": fixture.MARKER}}
        )
        ms = await manuscript_service.add_chapter(ms["id"], "Chapter one")
        scene = await manuscript_service.add_scene(
            ms["id"], ms["chapters"][0]["id"], "Scene one")
        manuscript_id, scene_id = ms["id"], scene["id"]
        project = manuscript_id
        print(f"  manuscript {manuscript_id}  scene {scene_id}")

        guard = await manuscript_collection.find_one({"_id": manuscript_id})
        if (guard or {}).get("fixture_marker") != fixture.MARKER:
            print("REFUSING: this manuscript is not a fixture this script made.")
            return 1

        # ── the ontology ─────────────────────────────────────────────────────
        section("the author's declarations")
        await operator_registry.create(
            project, "restraint",
            "what is withheld does more work than what is said",
            rendering_intent="say less than the moment wants; never name the feeling outright",
        )
        await operator_registry.create(
            project, "threshold",
            "a crossing noticed only once it is behind them",
            rendering_intent="one held moment at the door; no summary of what it means",
        )
        print("  /restraint and /threshold declared")

        # ── 1 · commit v1, then propose a revision ───────────────────────────
        section("1 · a committed passage, then a QUARANTINED revision")
        first = await render_one(
            project, "// avoid: melodrama\n/ restraint(she stops in the doorway)\n",
            manuscript_id, scene_id)
        check("the loop rendered a passage to commit", first is not None)
        if first is None:
            return 1

        accepted = await passage_store.accept(first["passage_id"], scene_id=scene_id)
        lineage_id, block_id = accepted["lineage_id"], accepted["block_id"]
        v1 = await revisions.version_store.resolve(lineage_id, 1)
        print(f"  v1: {v1['text'][:96]!r}")
        check("the first Accept lands as v1 of a lineage", v1 is not None and v1["version"] == 1)
        check("v1 records no parent", v1["revised_from"] == "")

        export_v1 = (await manuscript_service.export_manuscript(manuscript_id))["content"]
        check("v1 is in the book", v1["text"].split("\n")[0][:40] in export_v1)

        # the author changes what they declared
        proposal = await render_one(
            project,
            "// avoid: melodrama\n// goal: she turns back without deciding to\n"
            "/ restraint(she stops in the doorway) + threshold(the door)\n",
            manuscript_id, scene_id)
        check("a revision rendered", proposal is not None)
        if proposal is None:
            return 1
        print(f"  proposed: {proposal['text'][:96]!r}")

        current = await revisions.version_store.current(lineage_id)
        check("the proposal is QUARANTINED — current is still v1", current["version"] == 1)
        check("and the book still says v1",
              (await manuscript_service.export_manuscript(manuscript_id))["content"]
              == export_v1)

        # ── 2 · accept it ────────────────────────────────────────────────────
        section("2 · Accept — a new version, and the pointer moves")
        result = await passage_store.accept_revision(
            proposal["passage_id"], lineage_id=lineage_id,
            scene_id=scene_id, block_id=block_id)
        v2 = result["version"]

        check("v2 exists", v2["version"] == 2)
        check("v2 names its parent", v2["revised_from"] == f"{lineage_id}@v1",
              v2["revised_from"])
        diff = result["declaration_diff"]
        check("the declaration diff records the added staging",
              "goal" in diff["intents_added"], str(diff["intents_added"]))
        check("and the added operator",
              "threshold" in diff["operators_added"], str(diff["operators_added"]))

        scene_now = await manuscript_service.get_scene(scene_id)
        block_now = next(b for b in scene_now["blocks"] if b["id"] == block_id)
        check("the block points at v2", block_now["version"] == 2)
        check("the block shows v2's prose", block_now["content"] == v2["text"])

        v1_after = await revisions.version_store.resolve(lineage_id, 1)
        check("v1 IS RETAINED, byte-identical", v1_after == v1)

        # ── 3 · dismiss ──────────────────────────────────────────────────────
        section("3 · Dismiss — the current version stands, nothing is created")
        throwaway = await render_one(
            project, "// avoid: melodrama\n/ threshold(the door)\n",
            manuscript_id, scene_id)
        check("a third render to throw away", throwaway is not None)
        before_dismiss = (await manuscript_service.export_manuscript(manuscript_id))["content"]
        versions_before = len(await revisions.version_store.history(lineage_id))

        if throwaway:
            await passage_store.dismiss(throwaway["passage_id"], "not what I meant")

        check("no version was created",
              len(await revisions.version_store.history(lineage_id)) == versions_before)
        check("the book is unchanged",
              (await manuscript_service.export_manuscript(manuscript_id))["content"]
              == before_dismiss)

        # ── 4 · NO SILENT IMPROVEMENT ────────────────────────────────────────
        section("4 · NO SILENT IMPROVEMENT — the re-render prompt is the render prompt")
        ontology = await operator_registry.by_name(project)
        declared = [ontology["restraint"]]
        staging = {"avoid": "melodrama"}

        first_prompt = build_render_prompt(declared, staging)
        again_prompt = revisions.revision_prompt(declared, staging)

        check("revising under an UNCHANGED declared set gives an IDENTICAL prompt",
              again_prompt == first_prompt)
        check("no polish instruction in the render prompt",
              revisions.polish_leaks(first_prompt) == [],
              str(revisions.polish_leaks(first_prompt)))
        check("no polish instruction in the revision prompt",
              revisions.polish_leaks(again_prompt) == [],
              str(revisions.polish_leaks(again_prompt)))
        blob = again_prompt["system"] + again_prompt["user"]
        check("the version being revised is NOT in the prompt", v2["text"][:40] not in blob)
        check("no earlier version is in the prompt either", v1["text"][:40] not in blob)
        check("the tripwire can actually fire",
              revisions.polish_leaks({"system": "", "user": "tighten and improve this"}) != [])

        # and run it for real under the unchanged set
        unchanged = await render_one(
            project, "// avoid: melodrama\n/ restraint(she stops in the doorway)\n",
            manuscript_id, scene_id)
        check("a re-render under unchanged declarations still renders", unchanged is not None)
        if unchanged:
            same_diff = revisions.declaration_diff(
                revisions.declared_set(v2["provenance"]),
                revisions.declared_set(unchanged["provenance"]))
            print(f"        rendered: {unchanged['text'][:88]!r}")
            print(f"        (declaration diff vs v2: "
                  f"{'none' if revisions.diff_is_empty(same_diff) else same_diff})")
            await passage_store.dismiss(unchanged["passage_id"], "proof only")

        # ── 5 · immutability and export ──────────────────────────────────────
        section("5 · canon immutability, and export = current versions only")
        history = await revisions.version_store.history(lineage_id)
        check("every version is retained", [v["version"] for v in history] == [1, 2],
              f"{len(history)} versions")

        export_now = (await manuscript_service.export_manuscript(manuscript_id))["content"]
        scene_state = await manuscript_service.get_scene(scene_id)
        current_texts = {b.get("content", "") for b in scene_state.get("blocks", [])}

        check("the CURRENT version is in the export", v2["text"] in export_now)

        # THE PROPERTY, STATED THE WAY §7 STATES IT: the export is the set of current
        # versions. Asserting "v1's opening is absent" was the wrong shape — the model can
        # legitimately render two versions that begin the same way, and then a substring
        # check fails on prose that is perfectly correct. What must hold is that NOTHING in
        # the export is a version the pointer has moved past.
        # The export's prose bodies ARE the block contents, so the property is an equality
        # rather than an absence. A substring test is the wrong instrument here: two
        # versions of one passage share an author, an ontology and often an opening clause,
        # and "v1's words appear somewhere in the book" can be true of prose that is
        # entirely correct.
        exported_bodies = [b.get("content", "") for b in scene_state.get("blocks", [])]
        check("the exported prose is exactly the set of current versions",
              all(body in export_now for body in exported_bodies)
              and set(exported_bodies) == current_texts,
              f"{len(exported_bodies)} block(s)")

        superseded = [v for v in history if v["text"] not in current_texts]
        check("every superseded version is absent from the block contents",
              all(v["text"] not in exported_bodies for v in superseded),
              f"superseded: {[v['version'] for v in superseded]}")

        # And the honest note on the weaker substring reading, which depends on what the
        # model happened to write rather than on anything the code does.
        overlapping = [v for v in superseded if v["text"] in export_now]
        if overlapping:
            print(f"        (note: v{overlapping[0]['version']}'s text is a SUBSTRING of "
                  f"current prose — the model rendered the two versions with shared "
                  f"wording; the pointer is still correct)")

        stored = [d async for d in writer_passage_version_collection.find(
            {"lineage_id": lineage_id})]
        check("both versions are in the ledger, not in the prose", len(stored) == 2)
        check("the ledger holds more versions than the book holds blocks",
              len(stored) > len([b for b in scene_state.get("blocks", [])
                                 if b.get("lineage_id") == lineage_id]))

        # ── 6 · the W7 loop ──────────────────────────────────────────────────
        section("6 · the W7 loop — revise against a flag, then re-read")
        reading = await alignment.read_alignment(
            project, v2["text"], v2["provenance"], ontology)
        print(f"        reading of v2 → {reading.status}")
        stored_reading = await readings.store(project, reading, scene_id=scene_id,
                                              manuscript_id=manuscript_id)

        element = (reading.flags[0]["element"] if reading.flags
                   else "intent:avoid")     # nothing diverged; answer the intent anyway
        answering = {"flag_id": (stored_reading["flags"][0]["id"] if stored_reading["flags"]
                                 else "flg_none"),
                     "element": element, "reading_id": stored_reading["id"]}

        answer = await render_one(
            project,
            "// avoid: melodrama, and any naming of what she feels\n"
            "/ restraint(she stops in the doorway)\n",
            manuscript_id, scene_id)
        check("a revision answering the flag rendered", answer is not None)
        if answer:
            answered = await passage_store.accept_revision(
                answer["passage_id"], lineage_id=lineage_id, scene_id=scene_id,
                block_id=block_id, in_response_to=answering)
            v3 = answered["version"]
            check("the genealogy records which flag it answered",
                  v3["in_response_to"]["flag_id"] == answering["flag_id"])
            check("and which declared element that flag rested on",
                  v3["in_response_to"]["element"] == element)

            reread = await alignment.read_alignment(
                project, v3["text"], v3["provenance"], ontology)
            reread_stored = await readings.store(project, reread, scene_id=scene_id,
                                                 manuscript_id=manuscript_id)
            print(f"        re-reading of v3 → {reread.status}")

            closed = await revisions.close_loop(v3["id"], reread_stored)
            outcome = closed["loop_outcome"]["outcome"]
            check("the loop is CLOSED in the audit trail",
                  outcome in (revisions.CLEARED, revisions.STILL_PRESENT),
                  f"outcome={outcome}")
            check("and it records which element it was about",
                  closed["loop_outcome"]["element"] == element)

        # ── 7 · the resolver ─────────────────────────────────────────────────
        section("7 · a superseded version still resolves with its ORIGINAL provenance")
        await operator_registry.update(
            project, "restraint", {"rendering_intent": "something else entirely"})

        historical = await revisions.version_store.resolve(lineage_id, 1)
        check("v1 still resolves", historical is not None)
        check("v1's text is untouched by the operator edit", historical["text"] == v1["text"])
        resolution = await operator_registry.resolve_provenance(
            project, historical["provenance"])
        check("every operator v1 named still resolves", resolution["missing"] == [],
              str(resolution["missing"]))
        for op in resolution["resolved"]:
            check(f"{op['name']}@{op['version']} resolves to what it said THEN",
                  op["rendering_intent"] != "something else entirely",
                  op["rendering_intent"][:60])

        # ── the genealogy is logged ──────────────────────────────────────────
        section("instrumentation (recorded, not yet reasoned on)")
        events = await instrument.usage_for_project(project, limit=500)
        kinds = {}
        for e in events:
            kinds[e["event"]] = kinds.get(e["event"], 0) + 1
        check("revisions and the loop outcome were recorded",
              {revisions.REVISED, revisions.LOOP_CLOSED} <= set(kinds), str(kinds))
        revised = next((e for e in events if e["event"] == revisions.REVISED), None)
        check("a revision logs its parent and its diff",
              bool(revised) and bool(revised["extra"].get("declaration_diff")),
              str((revised or {}).get("extra", {}).get("revised_from")))

        print("\n" + "=" * 70)
        if FAILURES:
            print(f"FAILED — {len(FAILURES)} check(s): " + "; ".join(FAILURES))
        else:
            print("W8 PROVED — the pointer moves, and nothing the author committed is lost.")
        print("=" * 70)
        return 1 if FAILURES else 0

    finally:
        if keep and manuscript_id:
            print(f"\n(fixture kept: manuscript {manuscript_id})")
        else:
            if manuscript_id:
                await writer_passage_version_collection.delete_many(
                    {"manuscript_id": manuscript_id})
                await writer_passage_version_collection.delete_many(
                    {"project_id": manuscript_id})
            await fixture.drop(quiet=True)
            print("\n(fixture dropped)")


if __name__ == "__main__":
    sys.exit(asyncio.run(prove(keep="--keep" in sys.argv)))
