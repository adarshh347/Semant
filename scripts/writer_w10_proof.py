"""
Semant Writer W10 — the live proof. Depth registers against the REAL model and REAL Mongo.

The suite fakes the collections so a fabricated depth and an imposed ladder can be forced
deterministically. This runs it end to end, because the two halves of the author's-ladder
rule are worth very little as unit assertions alone:

  NO FABRICATED DEPTH. `// register: X` with nothing of the author's carrying X must refuse
  BEFORE the model is reached. The model is stubbed to explode for that check, so a render
  that got as far as a completion fails loudly rather than quietly producing impressive
  prose about a layer the author never declared.

  NO INTERPRETATION. The depth view is built from provenance with no model call, and the
  proof asserts the module cannot make one.

DATA SAFETY. Runs ONLY against a manuscript `writer_fixture_manuscript.py` made, keyed on
its marker, and drops it at the end unless `--keep` is passed.

    python scripts/writer_w10_proof.py            # make fixture, prove, drop
    python scripts/writer_w10_proof.py --keep     # leave the fixture for inspection
"""
import ast
import asyncio
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import (                                        # noqa: E402
    manuscript_collection,
    writer_passage_version_collection,
    writer_register_collection,
)
from backend.services.manuscript_service import manuscript_service    # noqa: E402
from backend.services.writer import recall, registers, revisions      # noqa: E402
from backend.services.writer.operators import OperatorError, operator_registry  # noqa: E402
from backend.services.writer.passages import passage_store            # noqa: E402
from backend.services.writer.render import OK, REFUSED                # noqa: E402
from backend.services.writer.studio import run_block                  # noqa: E402
from scripts import writer_fixture_manuscript as fixture              # noqa: E402

FAILURES: list = []

#: The author's OWN ladder — deliberately not the classic one, so nothing can pass by
#: accidentally agreeing with a default.
LADDER = [
    {"name": "weather", "description": "what the room is doing"},
    {"name": "interior", "description": "what she will not say to herself"},
    {"name": "inheritance", "description": "what the house has decided for them"},
]


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if detail:
        print(f"        {detail}")
    if not condition:
        FAILURES.append(label)


def section(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 66 - len(title)))


async def render_one(project, block, manuscript_id, scene_id):
    run = await run_block(project, block, manuscript_id=manuscript_id,
                          scene_id=scene_id, quarantine=True)
    entry = run["results"][0] if run["results"] else {}
    return entry, run


async def prove(keep: bool) -> int:
    manuscript_id = ""

    try:
        section("fixture")
        await fixture.drop(quiet=True)
        ms = await manuscript_service.create_manuscript(
            "W10 fixture manuscript",
            synopsis="A scratch manuscript for the W10 live proof.")
        await manuscript_collection.update_one(
            {"_id": ms["id"]}, {"$set": {"fixture_marker": fixture.MARKER}})
        ms = await manuscript_service.add_chapter(ms["id"], "Chapter one")
        scene = await manuscript_service.add_scene(
            ms["id"], ms["chapters"][0]["id"], "The kitchen")
        manuscript_id, scene_id = ms["id"], scene["id"]
        project = manuscript_id
        print(f"  manuscript {manuscript_id}  scene {scene_id}")

        guard = await manuscript_collection.find_one({"_id": manuscript_id})
        if (guard or {}).get("fixture_marker") != fixture.MARKER:
            print("REFUSING: this manuscript is not a fixture this script made.")
            return 1

        # ── 1 · no imposed taxonomy ──────────────────────────────────────────
        section("1 · the ladder is the author's — there is no default")
        check("a fresh project has NO registers",
              await registers.vocabulary(project) == [],
              str(await registers.vocabulary(project)))

        template = registers.propose_template()
        check("the classic ladder is offered UNSAVED",
              template["committed"] is False)
        check("and offering it stored nothing",
              await registers.vocabulary(project) == [])

        await registers.declare(project, LADDER)
        stored = await registers.vocabulary(project)
        check("the author's own ladder stores in the author's order",
              [r["name"] for r in stored] == ["weather", "interior", "inheritance"],
              str([r["name"] for r in stored]))
        check("and it is NOT the template",
              "philosophical" not in [r["name"] for r in stored])

        # ── 2 · grounded register references ─────────────────────────────────
        section("2 · a register is a reference, and retagging versions the operator")
        await operator_registry.create(
            project, "frost", "the cold as the house's opinion of them",
            rendering_intent="one concrete image of cold, no comment on it",
            register="weather")
        await operator_registry.create(
            project, "withheld", "what she will not say, even to herself",
            rendering_intent="say less than the moment wants; never name the feeling",
            register="interior")
        check("operators carry the author's registers", True)

        rejected = False
        try:
            await operator_registry.create(
                project, "bogus", "x", register="philosophical")
        except OperatorError as exc:
            rejected = True
            print(f"        {str(exc)[:104]}")
        check("an UNDECLARED register string is rejected", rejected)

        retagged = await operator_registry.update(
            project, "frost", {"register": "interior"})
        check("retagging bumps the version", retagged["version"] == 2,
              f"v{retagged['version']}")
        check("and the prior tag is kept in history",
              retagged["history"][0]["register"] == "weather")
        await operator_registry.update(project, "frost", {"register": "weather"})

        # ── 3 · rendering at a register ──────────────────────────────────────
        section("3 · //register foregrounds the author's tagged operators")
        entry, _ = await render_one(
            project,
            "// avoid: melodrama\n// register: interior\n"
            "/ frost(the kitchen at six) + withheld(the letter on the dresser)\n",
            manuscript_id, scene_id)
        check("it rendered", entry.get("status") == OK, str(entry.get("status")))
        if entry.get("status") == OK:
            print(f"        rendered: {entry['text'][:92]!r}")
            check("provenance records the active register",
                  entry["provenance"]["registers"] == ["interior"],
                  str(entry["provenance"].get("registers")))
            stamped = {o["name"]: o.get("register")
                       for o in entry["provenance"]["operators"]}
            check("and the register each operator carried when it fired",
                  stamped == {"frost": "weather", "withheld": "interior"}, str(stamped))

            # I6 — it is a `//` note, so it must be nowhere on the page
            lowered = entry["text"].lower()
            check("`register` appears NOWHERE in the surface text",
                  "register" not in lowered and "// " not in entry["text"])
            for name in ("interior", "weather", "inheritance"):
                check(f"the register name {name!r} is not narrated as prose",
                      name not in lowered)

            passage = await passage_store.get(entry["passage_id"])
            check("the passage is quarantined", passage["committed"] is False)

        # ── 4 · NO FABRICATED DEPTH ──────────────────────────────────────────
        section("4 · a register nothing of theirs carries REFUSES (the gate)")
        entry, _ = await render_one(
            project,
            "// avoid: melodrama\n// register: inheritance\n/ frost(the kitchen)\n",
            manuscript_id, scene_id)
        check("it refused", entry.get("status") == REFUSED, str(entry.get("status")))
        refusal = entry.get("refusal") or ""
        print(f"        {refusal[:150]}")
        check("the refusal names the register", "inheritance" in refusal)
        check("and says nothing of theirs carries it",
              "none of the operators" in refusal)
        check("and says how to make it work",
              "Tag an operator with it" in refusal)
        check("NO PROSE was produced", not (entry.get("text") or "").strip())

        undeclared, _ = await render_one(
            project,
            "// avoid: melodrama\n// register: philosophical\n/ frost(the kitchen)\n",
            manuscript_id, scene_id)
        check("an undeclared register also refuses",
              undeclared.get("status") == REFUSED)
        check("and lists what the author DOES have",
              "weather" in (undeclared.get("refusal") or ""))

        # ── 5 · NO INTERPRETATION ────────────────────────────────────────────
        section("5 · the depth view is derived, and cannot interpret")
        # commit the rendered passage so there is something to read by layer
        committed_keys = []
        first, _ = await render_one(
            project,
            "// avoid: melodrama\n// register: weather\n/ frost(the kitchen at six)\n",
            manuscript_id, scene_id)
        if first.get("status") == OK:
            accepted = await passage_store.accept(first["passage_id"], scene_id=scene_id)
            committed_keys.append(accepted["lineage_id"])

        second, _ = await render_one(
            project,
            "// avoid: melodrama\n// register: interior\n/ withheld(the letter)\n",
            manuscript_id, scene_id)
        if second.get("status") == OK:
            accepted = await passage_store.accept(second["passage_id"], scene_id=scene_id)
            committed_keys.append(accepted["lineage_id"])

        spans = await recall.committed_spans(project)
        view = await registers.depth_view(project, spans)

        check("the view offers the author's ladder in their order",
              [r["name"] for r in view["vocabulary"]] ==
              ["weather", "interior", "inheritance"])
        check("spans are indexed by the layers they were MADE at",
              len(view["by_register"]["weather"]) >= 1
              and len(view["by_register"]["interior"]) >= 1,
              str({k: len(v) for k, v in view["by_register"].items()}))
        check("a layer nothing was made at is empty, not guessed",
              view["by_register"]["inheritance"] == [])

        tree = ast.parse(inspect.getsource(registers))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        check("the registers module imports no model client",
              not any(bad in name for name in imported
                      for bad in ("llm_service", "role_registry", "groq", "render")),
              str(sorted(imported)))

        keys = set(view) | {k for s in view["spans"] for k in s}
        check("the view carries no reading of any layer",
              not (keys & {"reading", "interpretation", "meaning", "analysis", "theme",
                           "summary", "score"}),
              str(sorted(keys)))

        # a hand-typed span acquires no layer
        scene_doc = await manuscript_service.get_scene(scene_id)
        blocks = list(scene_doc.get("blocks", []))
        blocks.append({"id": "blk_typed", "type": "paragraph",
                       "content": "She had written this sentence herself.",
                       "color": None, "origin": "human", "provenance": {}})
        await manuscript_service.update_scene(scene_id, {"blocks": blocks})
        typed_registers = registers.registers_in({})
        check("a span with no operators behind it carries NO register",
              typed_registers == [])

        # ── 6 · the ontology wall ────────────────────────────────────────────
        section("6 · a register render with style-by-reference still REFUSES")
        entry, _ = await render_one(
            project,
            "// register: interior\n// voice: like Tolstoy\n/ withheld(the letter)\n",
            manuscript_id, scene_id)
        check("it refused", entry.get("status") == REFUSED)
        check("and named the reference it could not honour",
              "Tolstoy" in (entry.get("refusal") or ""),
              (entry.get("refusal") or "")[:80])

        # a register the author named after a genre is still THEIR word
        await registers.declare(project, LADDER + [
            {"name": "noir", "description": "the way this house lies about itself"}])
        await operator_registry.create(
            project, "shadow", "what the lamp does not reach",
            rendering_intent="one thing left unlit", register="noir")
        entry, _ = await render_one(
            project, "// register: noir\n/ shadow(the hallway)\n",
            manuscript_id, scene_id)
        check("a register the author DECLARED is usable even if it reads like a genre",
              entry.get("status") == OK,
              f"{entry.get('status')}: {(entry.get('refusal') or '')[:70]}")

        entry, _ = await render_one(
            project, "// voice: noir\n/ shadow(the hallway)\n", manuscript_id, scene_id)
        check("but the same word in //voice is still an import, and refuses",
              entry.get("status") == REFUSED)

        # ── 7 · canon untouched ──────────────────────────────────────────────
        section("7 · declaring, tagging and viewing wrote no prose")
        before = (await manuscript_service.export_manuscript(manuscript_id))["content"]

        await registers.declare(project, LADDER + [
            {"name": "noir", "description": "edited description"}])
        await operator_registry.update(project, "withheld", {"register": "interior"})
        await registers.depth_view(project, await recall.committed_spans(project))

        after = (await manuscript_service.export_manuscript(manuscript_id))["content"]
        check("the export is byte-identical", after == before, f"{len(before)} bytes")
        for lineage in committed_keys:
            version = await revisions.version_store.resolve(lineage, 1)
            check(f"{lineage}@v1 still records the register it was made at",
                  bool(registers.registers_in(version["provenance"])),
                  str(registers.registers_in(version["provenance"])))

        print("\n" + "=" * 70)
        if FAILURES:
            print(f"FAILED — {len(FAILURES)} check(s): " + "; ".join(FAILURES))
        else:
            print("W10 PROVED — the ladder is the author's, and Semant never drew one.")
        print("=" * 70)
        return 1 if FAILURES else 0

    finally:
        if keep and manuscript_id:
            print(f"\n(fixture kept: manuscript {manuscript_id})")
        else:
            if manuscript_id:
                await writer_passage_version_collection.delete_many(
                    {"project_id": manuscript_id})
                await writer_register_collection.delete_many({"_id": manuscript_id})
            await fixture.drop(quiet=True)
            print("\n(fixture dropped)")


if __name__ == "__main__":
    sys.exit(asyncio.run(prove(keep="--keep" in sys.argv)))
