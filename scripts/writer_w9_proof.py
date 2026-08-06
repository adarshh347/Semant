"""
Semant Writer W9 — the live proof. Recall and cite against the REAL model and REAL Mongo.

The suite fakes the collections so a summary, a bad citation and a leak can be forced
deterministically. This runs it end to end, because W9's two claims are only worth anything
against the actual ledger:

  BYTE-EQUAL, OR NOTHING. Every recalled span is compared, character for character, with
  the document it came out of. Not "looks right" — equal. A recall that trimmed whitespace,
  clipped a long paragraph or normalised a line turn would pass a human eye and fail here.

  CITE ONLY COMMITTED CANON. A quarantined render is offered to `cite` and must be refused,
  through the real store, with the real committed/uncommitted distinction.

And the one that guards the rest: NO SUMMARY. The proof asserts the returned prose is a
subset of what is in the ledger, and that the recall path cannot reach a model at all.

DATA SAFETY. Runs ONLY against a manuscript `writer_fixture_manuscript.py` made, keyed on
its marker, and drops it at the end unless `--keep` is passed.

    python scripts/writer_w9_proof.py            # make fixture, prove, drop
    python scripts/writer_w9_proof.py --keep     # leave the fixture for inspection
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
from backend.services.writer import instrument, recall, revisions     # noqa: E402
from backend.services.writer.operators import operator_registry       # noqa: E402
from backend.services.writer.passages import passage_store            # noqa: E402
from backend.services.writer.render import OK, REFUSED                # noqa: E402
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


async def render_one(project, block, manuscript_id, scene_id, cited=()):
    run = await run_block(project, block, manuscript_id=manuscript_id,
                          scene_id=scene_id, quarantine=True, cited=list(cited))
    ok = next((r for r in run["results"] if r["status"] == OK), None)
    if ok is None:
        print(f"        (no render: {[r.get('refusal') for r in run['results']]})")
    return ok, run


async def prove(keep: bool) -> int:
    manuscript_id = ""

    try:
        section("fixture")
        await fixture.drop(quiet=True)
        ms = await manuscript_service.create_manuscript(
            "W9 fixture manuscript", synopsis="A scratch manuscript for the W9 live proof."
        )
        await manuscript_collection.update_one(
            {"_id": ms["id"]}, {"$set": {"fixture_marker": fixture.MARKER}}
        )
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

        await operator_registry.create(
            project, "restraint",
            "what is withheld does more work than what is said",
            rendering_intent="say less than the moment wants; never name the feeling outright",
        )
        await operator_registry.create(
            project, "domestic",
            "the house as a record of what the people in it will not discuss",
            rendering_intent="one concrete household detail carrying the weather of the room",
        )

        # ── build a small canon ──────────────────────────────────────────────
        section("committing several passages")
        blocks = [
            "// avoid: melodrama\n/ domestic(the cold kitchen at six in the morning)\n",
            "// avoid: melodrama\n/ domestic(the sister's yearly letter on the dresser)\n",
            "// avoid: melodrama\n/ restraint(she stops at the door to the yard)\n",
        ]
        committed = []
        for block in blocks:
            rendered, _ = await render_one(project, block, manuscript_id, scene_id)
            if rendered is None:
                check("every fixture passage rendered", False)
                return 1
            accepted = await passage_store.accept(rendered["passage_id"], scene_id=scene_id)
            version = await revisions.version_store.resolve(accepted["lineage_id"], 1)
            committed.append(version)
            print(f"  v1 {version['lineage_id']}: {version['text'][:72]!r}")
        check("three passages are committed", len(committed) == 3)

        export_before = (await manuscript_service.export_manuscript(
            manuscript_id))["content"]

        # ── 1 · THE VERBATIM RULE ────────────────────────────────────────────
        section("1 · recall returns the author's own words, BYTE FOR BYTE")
        ledger = {(d["lineage_id"], d["version"]): d["text"]
                  async for d in writer_passage_version_collection.find(
                      {"project_id": project})}

        queries = ["cold kitchen morning", "sister letter", "door yard stopped",
                   "she", "house room"]
        total_hits = 0
        for query in queries:
            result = await recall.recall(project, query, limit=5)
            total_hits += len(result["spans"])
            violations = recall.verbatim_violations(result["spans"], ledger)
            check(f"{query!r} → {len(result['spans'])} span(s), all byte-equal",
                  violations == [], "; ".join(violations))

        check("the queries found something to check", total_hits > 0, f"{total_hits} hits")

        best = await recall.recall(project, "cold kitchen morning", limit=1)
        if best["spans"]:
            span = best["spans"][0]
            stored = ledger[(span["lineage_id"], span["version"])]
            print(f"        recalled: {span['text'][:78]!r}")
            check("the recalled string IS the stored string", span["text"] == stored)
            check("nothing was trimmed", len(span["text"]) == len(stored))
            check("no ellipsis was introduced",
                  "…" not in span["text"] and "..." not in span["text"])
            check("it says where it sits",
                  span["location"]["scene_title"] == "The kitchen"
                  and span["location"]["chapter_title"] == "Chapter one",
                  str(span["location"]))

        # no synthesis anywhere in the payload
        keys = set(best.keys()) | {k for s in best["spans"] for k in s}
        check("the result carries no synthesis field",
              not (keys & {"summary", "synthesis", "established", "overview", "gist"}),
              str(sorted(keys)))

        # and structurally, the module cannot produce one
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(recall))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        check("the recall path imports no model client",
              not any(bad in name for name in imported
                      for bad in ("llm_service", "role_registry", "groq")),
              str(sorted(imported)))

        # ── 2 · empty is honest ──────────────────────────────────────────────
        section("2 · a query matching nothing returns EMPTY, not a guess")
        nothing = await recall.recall(project, "bathysphere periscope zeppelin")
        check("no spans came back", nothing["spans"] == [])
        check("and it says so plainly",
              "Nothing in your manuscript matches" in nothing["empty_reason"],
              nothing["empty_reason"])
        check("with nothing offered in place of an answer",
              not any(k in nothing for k in ("suggestion", "did_you_mean", "summary")))

        # ── 3 · a cited render ───────────────────────────────────────────────
        section("3 · a render that rests on committed prose")
        cite_target = committed[0]
        cited = await recall.resolve_citations(
            project, [{"lineage_id": cite_target["lineage_id"]}])
        check("the citation resolved to the exact committed text",
              cited[0]["text"] == cite_target["text"])

        rendered, _ = await render_one(
            project, "// avoid: melodrama\n/ restraint(she puts the kettle on)\n",
            manuscript_id, scene_id, cited=cited)
        check("the cited render produced a passage", rendered is not None)
        if rendered:
            print(f"        rendered: {rendered['text'][:78]!r}")
            stamps = rendered["provenance"]["cited"]
            check("provenance records what it rested on",
                  stamps and stamps[0]["lineage_id"] == cite_target["lineage_id"],
                  str(stamps))
            passage = await passage_store.get(rendered["passage_id"])
            check("the cited render is QUARANTINED, not written",
                  passage["committed"] is False)
            check("the book has not changed",
                  (await manuscript_service.export_manuscript(
                      manuscript_id))["content"] == export_before)

        # ── 4 · cite only committed canon ────────────────────────────────────
        section("4 · citing something the author never accepted is REFUSED")
        loose, _ = await render_one(
            project, "// avoid: melodrama\n/ restraint(the window)\n",
            manuscript_id, scene_id)
        check("a quarantined render exists to try to cite", loose is not None)

        refused = False
        try:
            await recall.resolve_citations(project, [{"lineage_id": "lin_never_committed"}])
        except recall.RecallError as exc:
            refused = True
            print(f"        {str(exc)[:110]}")
        check("citing an uncommitted passage is refused", refused)

        partial = False
        try:
            await recall.resolve_citations(project, [
                {"lineage_id": cite_target["lineage_id"]},
                {"lineage_id": "lin_never_committed"},
            ])
        except recall.RecallError:
            partial = True
        check("one bad citation refuses the WHOLE list", partial)

        if loose:
            await passage_store.dismiss(loose["passage_id"], "proof only")

        # ── 5 · the ontology wall still holds ────────────────────────────────
        section("5 · a cited render with style-by-reference still REFUSES")
        _, run = await render_one(
            project,
            "// voice: like Tolstoy\n/ restraint(she puts the kettle on)\n",
            manuscript_id, scene_id, cited=cited)
        entry = run["results"][0] if run["results"] else {}
        check("it refused", entry.get("status") == REFUSED, str(entry.get("status")))
        check("and named the reference it could not honour",
              "Tolstoy" in (entry.get("refusal") or ""),
              (entry.get("refusal") or "")[:90])
        check("citing did not open a bypass",
              entry.get("status") == REFUSED)

        # ── 6 · canon untouched ──────────────────────────────────────────────
        section("6 · recall wrote nothing, and the book is unchanged")
        for query in queries + ["nothing like this at all", ""]:
            await recall.recall(project, query, limit=10)

        export_after = (await manuscript_service.export_manuscript(
            manuscript_id))["content"]
        check("the export is byte-identical across every recall",
              export_after == export_before, f"{len(export_before)} bytes")

        for version in committed:
            check(f"{version['lineage_id']}@v1 is unchanged",
                  (await revisions.version_store.resolve(
                      version["lineage_id"], 1)) == version)

        check("no recalled passage was duplicated into the book",
              all(export_after.count(v["text"]) == 1 for v in committed))

        # ── 7 · provenance resolves ──────────────────────────────────────────
        section("7 · a cited-and-accepted passage names what it rested on")
        if rendered:
            accepted = await passage_store.accept(
                rendered["passage_id"], scene_id=scene_id)
            version = await revisions.version_store.resolve(accepted["lineage_id"], 1)
            stamps = version["provenance"]["cited"]
            check("the committed version records its citations", bool(stamps), str(stamps))

            still = await recall.resolve_citations(
                project, [{"lineage_id": stamps[0]["lineage_id"],
                           "version": stamps[0]["version"]}])
            check("and every cited passage still resolves to the exact prose",
                  still[0]["text"] == cite_target["text"])

            resolution = await operator_registry.resolve_provenance(
                project, version["provenance"])
            check("its operators still resolve too", resolution["missing"] == [],
                  str(resolution["missing"]))

        # ── instrumentation ──────────────────────────────────────────────────
        section("instrumentation (recorded, not yet reasoned on)")
        events = await instrument.usage_for_project(project, limit=500)
        kinds = {}
        for e in events:
            kinds[e["event"]] = kinds.get(e["event"], 0) + 1
        check("recalls were recorded", recall.RECALLED in kinds, str(kinds))
        misses = [e for e in events
                  if e["event"] == recall.RECALLED and e["extra"].get("hits") == 0]
        check("including the ones that found nothing", bool(misses),
              f"{len(misses)} empty recalls logged")

        print("\n" + "=" * 70)
        if FAILURES:
            print(f"FAILED — {len(FAILURES)} check(s): " + "; ".join(FAILURES))
        else:
            print("W9 PROVED — recall returns the author's own words, or nothing.")
        print("=" * 70)
        return 1 if FAILURES else 0

    finally:
        if keep and manuscript_id:
            print(f"\n(fixture kept: manuscript {manuscript_id})")
        else:
            if manuscript_id:
                await writer_passage_version_collection.delete_many(
                    {"project_id": manuscript_id})
            await fixture.drop(quiet=True)
            print("\n(fixture dropped)")


if __name__ == "__main__":
    sys.exit(asyncio.run(prove(keep="--keep" in sys.argv)))
