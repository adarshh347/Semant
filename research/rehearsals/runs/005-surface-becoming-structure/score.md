# 005 — Surface Becoming Structure: "does the surface pattern organise the composition?"

**Family:** R8 Surface Becoming Structure · **Mode:** instrumented · **A4 of the R2 breadth batch**
**Outcome: COMPLETED — the two probes CONTRADICT each other, and the contradiction is the finding.
Separately, A4 bounds spark-06: no anthropomorphism appeared.**

RESEARCH-ONLY. No production entity, schema, route, collection, or corpus write.

---

## Subject

Post `695be784a9ea58f1b6aef5ec` — a photograph of a tiled interior: a turquoise revetted niche with
a semi-domed head, three arched recesses, three square panels each centred on a rosette medallion,
and a fine star-and-cross dado band along the base. **`reproduction_vs_depiction: depiction`** —
an actual building, not a plate or a reproduction of another artwork.

**Clean slate:** 0 regions, 0 grounds, 0 percepts, 0 embeddings — nothing pre-annotated to bias the
reading. **453×680, so A4 ran at native resolution**, deliberately repairing A3's confound where a
3-image call forced a 256 px downscale and the model then mis-described its subject.

This restores the batch's only **aniconic** slot: runs 002, 002F, 003 and 004 were all figurative.

## The contradiction

**Probe 1** (1393.0 ms, 2021 tokens, `stop`) — the seed gesture, open:

> **The built structure organizes the composition — the pattern merely fills what the architecture
> provides.** […] Even the repeating geometric bands follow architectural lines rather than
> dictating them […] **The hierarchy is clear: structure first, pattern second.**

**Probe 2** (2527.9 ms, 2292 tokens, `stop`) — asked to name the single strongest dividing line and
say what makes it:

> The single strongest dividing line […] is the **horizontal band near the bottom** […] This
> division is made by a **change in surface pattern itself — not by a structural edge or joint.**
> […] They **disagree.**

**Asked in the abstract, the model asserts a hierarchy. Asked to point at one specific line, it
produces a counterexample to that hierarchy — and does not notice.** The general claim ("pattern
never dictates") and the particular observation ("the strongest division in the image is made by
pattern, not structure") cannot both stand.

*(Fable-pass reading.)* This is precisely what R8 is named for. "Surface becoming structure" is not
a claim that ornament is secretly load-bearing; it is the moment where surface **stops being infill
and starts doing compositional work** — and the model located that moment correctly while
simultaneously denying it was possible.

## The model was right about *where* — measured, no model

The largest relative change in pattern fineness across the whole image, by edge density per
horizontal band:

| band (y normalised) | edge density |
|---|---|
| 0.735 | 18.00 |
| **0.765** | **44.87** |
| 0.794 | 44.93 |

**A 149 % jump at y ≈ 0.765** — the single largest in the image, and exactly the line probe 2
named. The pattern below is more than twice as fine as the pattern above. The model's *location*
is independently confirmed.

*(Fable-pass, and stated as interpretation not measurement.)* Its *characterisation* is nearly
right. There is a border band at that line, so "not by a structural edge or joint" overstates the
case — but the wall does not change plane there, and no structural member interrupts it. The
strongest division in the composition is a **change of pattern regime on a continuous surface**.
That is the honest version of what probe 2 saw.

## spark-06 is BOUNDED — and my earlier claim was overstated

A4 was chosen partly as the sharpest available test of spark-06 (spontaneous anthropomorphism):
an aniconic, frontal, three-arched wall with a single lit opening on the centre axis — the most
face-suggestive configuration in the corpus. Neither prompt mentioned faces, eyes, gaze, or bodies.

**No face reading appeared. Neither probe anthropomorphised anything.**

This forces a correction to spark-06 as A3 recorded it. A3 called the behaviour *spontaneous*. It
was not: A3's probe asked where an image's **address** goes and whether another image "makes the
same kind of address" — a question that primes a viewer-facing reading. Given a question about
**organisation** instead, the same model on a more face-suggestive image invented nothing.

**Corrected claim: anthropomorphism here is question-conditional, not indiscriminate.** It is
elicited by address-framed questions, not by architecture as such. This materially improves A6's
prospects: a false-analogy test that never uses address language is less exposed than A3 suggested.
A6 must still not state the analogy — but the hazard is narrower and better understood.

## Where the model overreached anyway

Unprompted, probe 2 volunteered: *"a classic Islamic architectural device to demarcate zones of
ornamentation and structure."* Nothing was asked about culture, period, or tradition, and the
manifest sets `no_iconographic_identification: true`. The attribution may well be correct — it is
also **unverified, unrequested, and unsupported by anything in the frame**. Recorded as a live
instance of source overreach by the model rather than by the rehearsal.

Probe 2 also mislocated the band slightly, describing it as separating the wall from *the floor*;
the dado field sits between the upper wall and the floor, so there are two lines there, not one.
And it emitted decorative scaffolding (headers, a ✅ "Final Answer" block) that no prompt requested.

## Evaluation against the permitted outcomes

- **(a) SPARK** — yes, one: see `sparks.md`. Research-only.
- **(b) existing construct sufficient** — untested here; A4 produced no evidence about Grounds.
- **(c) stall** — **no, and this was the live possibility.** The manifest recorded in advance that
  pattern and built form announce the *same* divisions in this image, so the question might be
  undecidable from one photograph. It turned out decidable, because one division is announced by
  pattern *alone*.
- **(d) refusal** — none occurred, and none was prompted for.

## Provenance

| | |
|---|---|
| provider / model | groq / `qwen/qwen3.6-27b`, `reasoning_effort: "none"` |
| live VLM calls | **2** (budget 2), 35 s apart, no retries, no provider failures |
| resolution | **native 453×680, unscaled** |
| latency | 1393.0 ms, 2527.9 ms |
| tokens | 2021 + 2292 |
| finish_reason | `stop` both · no `<think>` leakage · raw text frozen, no parsing attempted |
| replay | **0 adapter calls, 0 sockets, key absent**; 3 observations, 4 events |
| production mutation | **none** — post read read-only, never written |
