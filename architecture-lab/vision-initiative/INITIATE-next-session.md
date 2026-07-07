# Initiate prompt — next Darshan session

Paste this to start the next vision-pipeline session. Track E, the v2 two-sided strategy, and the Track A decisions are written; Track A's 7 questions are LOCKED, the 6 strategy forks await Adarsh.

---

You're continuing the **Darshan** vision-pipeline initiative in the Semant repo (`/home/adarsh-yadav/Documents/projects/semant`, GitHub `adarshh347/Semant`). You own the vision/annotation/AI pipeline; a separate thread owns the Drishya post-editor UI. Shared file is `PostDetailPage.jsx` — research phase has zero conflict; before any build touching it, `git pull` and tell Adarsh so he can serialize.

**Session start (do first):**
1. `git branch --show-current` must be `feat/frontend`. `git pull` / check log so you're on latest.
2. Re-read `architecture-lab/vision-initiative/decisions-darshan.md` (Track A locks + the 6 forks) and `architecture-lab/decisions-log.md`. Check the umbrella GitHub issue — **create it if still missing** ("Darshan — vision pipeline initiative (umbrella)", label `architecture`, checkboxes for tracks A–F, link #8/#9/#10).
3. Read, in order: `00-brief.md` (+ v2 addendum), `01-strategy-two-sided.md`, `model-integration-plan.md`, then `responses/track-E-purpose.findings.md`, `responses/fashion-market-research.md`, `responses/track-A-datamodel.findings.md` (the pre-revamp pass).

**State of decisions:**
- **Track A's 7 questions: LOCKED** (`decisions-darshan.md` Part 1) — merge is near-free (0 rows of `bounding_box_tags`). Plus the v2 graph-ready fields (`part`, `attributes[]`, `embedding_id`, `actor`).
- **6 strategy forks: check whether Adarsh has answered** (`decisions-darshan.md` Part 2). If yes → record the locks in `decisions-darshan.md`/`decisions-log.md` first.

**Then, research-only (no build until Adarsh says go):** pick the highest-value track and write `responses/track-{X}-*.findings.md` per its Output contract, ground every claim in real file+line refs, end with questions for Adarsh, commit `docs(arch-lab): …`, and stop. Recommended order:
- **Track A-v2** (fast, small) — extend the findings with the final graph-ready `Region` schema, the `actor`-field resolution, and the embedding-storage plan (updated prompt: `track-A-datamodel.prompt.md`). Do this first if you want the spine finalized.
- **Track B** (biggest unknown) — turn `model-integration-plan.md` into a benchmarked, deploy-costed, fallback-laddered segmentation plan (Fashionpedia vs DeepFashion2, SAM2 prompt strategy, GPU-serving + on-device fallback, domain detection).
- **Track C** — FashionCLIP-as-taste-vector + RAG grounding; fashion-literate lenses; the two readings (deep creator + short consumer feed hook).
- **Track F** — B2C taste capture + creator→brand chain (best *after* A-v2 + C land).

**Rules:** research + plan only until Adarsh locks the forks; ground in real file+line refs; end findings with questions for Adarsh; conventional commits per `workflow-protocol.md`; verify UI by screenshot only; don't touch the other thread's dirty files (`decisions-log.md`, vault, `frontend-research/`).

**Recommended focus for this session:** **Track A-v2** (finalize the spine) → then **Track B** (model deep-plan). A-v2 is small and unblocks everything; B is the biggest technical unknown.
