"""
Semant Writer W1 — the live proof. The executable-document loop, end to end, on Groq.

The test suite stubs the model so refusals and leaks can be forced deterministically.
This script does the opposite: it runs the REAL loop against the REAL model and checks
that the invariants hold when nothing is staged. It proves, in order:

  1. an operator is authored from the author's description (`#create`: propose → confirm);
  2. a block with `// goal` + two `/` directives renders QUARANTINED passages, in the
     author's own declared voice, each carrying operator + intent provenance;
  3. a contradictory orchestration REFUSES with a reason — not with filler prose;
  4. an undefined operator refuses before the model is ever contacted;
  5. Accept grows the manuscript, and nothing else ever wrote to it;
  6. no `//` orchestration reached the committed passage.

DATA SAFETY. It runs ONLY against a manuscript `writer_fixture_manuscript.py` made, and
drops it at the end unless `--keep` is passed. It will refuse to run against a manuscript
it did not create.

    python scripts/writer_w1_proof.py            # make fixture, prove, drop
    python scripts/writer_w1_proof.py --keep     # leave the fixture for inspection
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import manuscript_collection                    # noqa: E402
from backend.services.manuscript_service import manuscript_service    # noqa: E402
from backend.services.writer import instrument                        # noqa: E402
from backend.services.writer.operators import operator_registry       # noqa: E402
from backend.services.writer.passages import passage_store            # noqa: E402
from backend.services.writer.render import REFUSED                    # noqa: E402
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


async def prove(keep: bool) -> int:
    section("fixture")
    # `fixture.make()` only prints the ids; build the same thing inline so the proof can
    # hold on to them. The marker it stamps is the one `fixture.drop()` matches on.
    await fixture.drop(quiet=True)
    ms = await manuscript_service.create_manuscript(
        "W1 fixture manuscript", synopsis="A scratch manuscript for the W1 live proof."
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
    if guard.get("fixture_marker") != fixture.MARKER:
        raise SystemExit("refusing to run: this manuscript is not a fixture")

    try:
        # ── 1. author an operator from dialogue ──────────────────────────────
        section("1 · #create — the author authors an operator")
        proposal = operator_registry.propose(
            "threshold",
            "a crossing the character notices only after it is already behind them; the "
            "prose stays in the body and never explains the change",
        )
        check("propose returns an UNSAVED operator", proposal["committed"] is False)
        check("nothing stored before confirmation",
              await operator_registry.get(project, "threshold") is None)

        threshold = await operator_registry.create(
            project,
            proposal["name"],
            proposal["definition"],
            rendering_intent="one held moment; no summary of what it means",
            examples=["The latch gave before she had decided to push it."],
            negative_examples=["She stepped through the door, changed forever."],
        )
        check("the author's confirmation stored it at v1", threshold["version"] == 1)

        await operator_registry.create(
            project, "interiority",
            "what the body knows before the mind admits it — pulse, breath, the hands",
            rendering_intent="never name the feeling; only what the body does",
        )
        print("  operators: threshold, interiority")

        # ── 2. script a block: // goal + two / directives ────────────────────
        section("2 · a scripted block renders QUARANTINED passages")
        block = (
            "// goal: she arrives at the door she has been avoiding\n"
            "// voice: close third, past tense\n"
            "// avoid: weather openings, and naming the emotion outright\n"
            "/ threshold(the door at the end of the hall)\n"
            "/ threshold + interiority\n"
        )
        out = await run_block(project, block, manuscript_id=manuscript_id, scene_id=scene_id)

        check("both directives produced a passage", out["rendered"] == 2,
              f"rendered={out['rendered']} refused={out['refused']}")
        if out["rendered"] != 2:
            for r in out["results"]:
                print(f"        line {r['line']}: {r['status']} — {r['refusal'] or r['text'][:80]}")

        for r in out["results"]:
            if r["status"] != "ok":
                continue
            print(f"\n  line {r['line']}  /{'+'.join(r['operators'])}")
            for line in r["text"].splitlines():
                print(f"    │ {line}")
            prov = r["provenance"]
            print(f"    provenance: operators="
                  f"{[(o['name'], 'v%s' % o['version']) for o in prov['operators']]} "
                  f"intents={[i['key'] for i in prov['intents']]} model={prov.get('model')}")

        first = out["results"][0]
        check("passage carries operator provenance with versions",
              bool(first["provenance"]["operators"]) and
              all("version" in o for o in first["provenance"]["operators"]))
        check("passage carries the // intents that produced it",
              {i["key"] for i in first["provenance"]["intents"]} == {"goal", "voice", "avoid"})

        passage = await passage_store.get(first["passage_id"])
        check("the passage is QUARANTINED, not committed", passage["committed"] is False)

        scene_now = await manuscript_service.get_scene(scene_id)
        check("nothing auto-wrote to the manuscript", scene_now["blocks"] == [],
              f"scene has {len(scene_now['blocks'])} block(s) before Accept")

        # ── 3. a contradictory orchestration must REFUSE ─────────────────────
        section("3 · refusal is a return value, not filler prose")
        contradiction = (
            "// goal: render a long interior passage about what she is feeling\n"
            "// avoid: interiority\n"
            "/ interiority\n"
        )
        refusal_run = await run_block(
            project, contradiction, manuscript_id=manuscript_id, scene_id=scene_id
        )
        entry = refusal_run["results"][0]
        check("a contradictory orchestration refuses", entry["status"] == REFUSED)
        check("the refusal produced NO prose", not entry["text"])
        check("the refusal carries a reason", bool(entry["refusal"]))
        print(f"    reason: {entry['refusal']}")

        section("3b · the ontology wall: style by reference is refused")
        # Measured: with only the prompt forbidding it, the model happily rendered "the
        # ornate omniscience of a 19th-century Russian novel" — inventing a Russian name
        # and addressing the reader. So the wall is structural, and this proves it holds.
        borrowed = await run_block(
            project,
            "// voice: the ornate third-person omniscience of a 19th-century Russian novel\n"
            "/ threshold\n",
            manuscript_id=manuscript_id, scene_id=scene_id,
        )
        entry = borrowed["results"][0]
        check("a voice borrowed from outside the author's work refuses",
              entry["status"] == REFUSED)
        check("it rendered no prose from the borrowed corpus", not entry["text"])
        print(f"    reason: {entry['refusal']}")

        described = await run_block(
            project,
            "// voice: close third, past tense, short declaratives\n/ threshold\n",
            manuscript_id=manuscript_id, scene_id=scene_id,
        )
        check("a voice described in the author's own words still renders",
              described["results"][0]["status"] == "ok",
              described["results"][0]["refusal"])

        section("4 · an undefined operator refuses before the model is contacted")
        undefined = await run_block(
            project, "/ ekstasis\n", manuscript_id=manuscript_id, scene_id=scene_id
        )
        entry = undefined["results"][0]
        check("undefined operator refuses", entry["status"] == REFUSED)
        check("the reason names the missing operator", "ekstasis" in entry["refusal"])
        check("it did not quarantine anything", entry["passage_id"] is None)
        print(f"    reason: {entry['refusal']}")

        # ── 5. Accept ────────────────────────────────────────────────────────
        section("5 · Accept — the only path into the sacred manuscript")
        before = len((await manuscript_service.get_scene(scene_id))["blocks"])
        accepted = await passage_store.accept(first["passage_id"])
        scene_after = await manuscript_service.get_scene(scene_id)

        check("the manuscript grew by exactly one block",
              len(scene_after["blocks"]) == before + 1,
              f"{before} → {len(scene_after['blocks'])}")
        committed = scene_after["blocks"][-1]
        check("the committed block is stamped user_confirmed",
              committed["origin"] == "user_confirmed")
        check("the committed block kept its provenance",
              committed["provenance"]["operators"][0]["name"] == "threshold" and
              committed["provenance"]["passage_id"] == first["passage_id"])
        check("the passage is now committed",
              (await passage_store.get(first["passage_id"]))["committed"] is True)

        second = out["results"][1]
        still = await passage_store.get(second["passage_id"])
        check("the un-accepted passage stayed quarantined", still["committed"] is False)

        # ── 6. the / ÷ // wall on committed prose ────────────────────────────
        section("6 · no // orchestration reached the manuscript")
        export = await manuscript_service.export_manuscript(manuscript_id)
        body = export["content"]
        check("no `//` notation in the committed manuscript", "//" not in body)
        check("no orchestration key narrated as prose",
              not any(f"\n{k}:" in body.lower() for k in ("goal", "voice", "avoid", "arc", "priority")))
        for note in ("she arrives at the door she has been avoiding",
                     "close third, past tense", "weather openings"):
            check(f"the staging {note[:34]!r}… is not on the page", note.lower() not in body.lower())

        # ── instrumentation ──────────────────────────────────────────────────
        section("instrumentation (recorded, not yet reasoned on)")
        events = await instrument.usage_for_project(project)
        kinds = {}
        for e in events:
            kinds[e["event"]] = kinds.get(e["event"], 0) + 1
        check("renders, refusals and the accept were all recorded",
              {"render", "refusal", "accept"} <= set(kinds), str(kinds))
        pairs = [p for e in events for p in e.get("operator_pairs", [])]
        check("operator co-occurrence captured from day one", "interiority|threshold" in pairs,
              f"pairs={sorted(set(pairs))}")

        print("\n" + "=" * 70)
        if FAILURES:
            print(f"FAILED — {len(FAILURES)} check(s): " + "; ".join(FAILURES))
        else:
            print("W1 PROVED — the executable-document loop holds end to end.")
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
