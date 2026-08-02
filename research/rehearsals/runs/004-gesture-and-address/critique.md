# 004 — Critique (meta-observation)

Adversarial pass over A3's own conduct.

---

## Where the rehearsal is weak

**1. The two probes read the same painting differently, and one of them is probably wrong.**
Probe 1 (768 px) described "the turned head […] averted posture". Probe 2 (256 px) described
"the **downward tilt** of the head and the obscuring **lace** veil". The head in this painting is
thrown *back*, not down, and the fabric is a heavy bow, not lace. **Probe 2's description of
IMAGE 1 is less accurate than probe 1's**, and the most likely cause is the aggressive downscale
forced by the token ceiling. This matters: the comparison in Result 2 was made at 256 px, so the
match was judged on a degraded view of all three images. The finding is not overturned — a
head-back self-contained pose is what both probes converged on — but the resolution confound is
real and must be recorded rather than glossed.

**2. Three images cost ~7200 tokens regardless of size, so A3 was shaped by the rate limit.**
Groq charges a roughly fixed ~2400 tokens per image; shrinking 384 px → 256 px did not
meaningfully reduce it. The three-image comparison therefore had to run with `max_tokens: 380`,
which is why probe 2's answer is terse. A better-resourced A3 would have compared at full
resolution with room to reason. This is a budget artifact, not a finding.

**3. The negative was under-specified.** It was chosen as "palette-adjacent, no figure ⇒ no address
possible." The model found an address anyway (windows as eyes). That is a *better* result than
planned, but it means the control did not test what it was built to test. A true negative for
address would need something with no frontality and no facing at all — a texture, a fragment, an
aerial view.

**4. Only one neighbour, one negative, one subject.** Every claim here is n = 1 per role. The
cross-medium match is suggestive, not established.

**5. The seed gesture is leading in a subtle way.** "Where does this gesture's address go?"
presupposes that there *is* an address and that it *goes* somewhere. A figure with no particular
address would still get one described. Probe 1's answer may partly reflect that presupposition.
A control asking "does this figure address anyone?" was not run.

## Where it held

- **Amendment 1 honoured.** No refusal token named in either prompt. Probe 2 was explicitly framed
  to avoid a forced choice ("judge each on its own terms; do not assume both must match or both
  must differ") — and it did in fact split its verdict, which is evidence the framing worked.
- **Amendment 2 honoured, and extended.** `reproduction_vs_depiction` is recorded **per image**,
  which A3 required because it mixes a painting reproduction with two photographs.
- **The budget held at 2 live calls.** The temptation to re-run the already-successful probe 1
  after the aborted attempt was declined; it was adopted from disk instead (below).
- **The embedding counterfactual was NOT claimed.** The manifest recorded in advance that it is
  untestable, and the score states it plainly, including the fact that the naive version of the
  argument is contradicted by the chromaticity numbers.
- **Portfolio error caught before running,** not after: the "garment" is a painting.
- Production was read, never written. Nothing graduated.

## Substrate findings (surfaced, not silently absorbed)

- **Groq returns HTTP 413 — "Request too large … Limit 8000, Requested 8113" — when a single
  request's TOTAL token requirement exceeds the per-minute limit.** It is not a byte-size limit and
  not a transient 429: the request can *never* be served and no tokens are consumed. Three separate
  413s were spent discovering this because the adapter swallowed the response body. **Fixed:** the
  adapter now raises with the provider's own message, and the three distinct Groq failure modes
  (403 + `error code: 1010` = Cloudflare agent ban; 413 = unservable; 429 = temporarily over) are
  documented at the call site.
- **The runner gained `reuse_frozen`.** An aborted multi-probe capture leaves earlier observations
  already frozen on disk. Re-running would have spent live budget to re-obtain evidence already
  held — so a probe step can now adopt a frozen observation, provided the file exists and
  validates. It never invents one, and the trace records the provenance as `:reused_frozen` so a
  reader can see which events were captured in a prior attempt.
- **Multi-image probes send images as separate ordered content parts**, never composited into one
  sheet. Compositing would introduce exactly the reproduction artifact run 002 was about and would
  make `image_order` a fiction.
