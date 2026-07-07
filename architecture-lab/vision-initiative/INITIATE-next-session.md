# Initiate prompt — next Darshan session

Paste this to start the next vision-pipeline session. Track E, the v2 two-sided strategy, and the Track A decisions are written; Track A's 7 questions are LOCKED, the 6 strategy forks await Adarsh.

---

You're continuing the **Darshan** vision-pipeline initiative in the Semant repo (`/home/adarsh-yadav/Documents/projects/semant`, GitHub `adarshh347/Semant`). You own the vision/annotation/AI pipeline; a separate thread owns the Drishya post-editor UI. Shared file is `PostDetailPage.jsx` — research phase has zero conflict; before any build touching it, `git pull` and tell Adarsh so he can serialize.

**Session start (do first):**
1. `git branch --show-current` must be `feat/frontend`. `git pull` / check log so you're on latest.
2. Re-read `architecture-lab/vision-initiative/decisions-darshan.md` (Track A locks + the 6 forks) and `architecture-lab/decisions-log.md`. Check the umbrella GitHub issue — **create it if still missing** ("Darshan — vision pipeline initiative (umbrella)", label `architecture`, checkboxes for tracks A–F, link #8/#9/#10).
3. Read, in order: `00-brief.md` (+ v2 addendum), `01-strategy-two-sided.md`, `model-integration-plan.md`, then `responses/track-E-purpose.findings.md`, `responses/fashion-market-research.md`, `responses/track-A-datamodel.findings.md` (the pre-revamp pass).

**State of decisions (all LOCKED — see `decisions-darshan.md`):**
- **Track A's 7 questions: LOCKED** — merge is near-free (0 rows of `bounding_box_tags`). Plus v2 graph-ready fields (`part`, `attributes[]`, `embedding_id`, `actor`).
- **6 strategy forks: LOCKED** — **true parallel** (creator + audience together), **phased full-stack models** (FashionCLIP→Fashionpedia→SAM2), **video/reels pulled into active scope**, **balanced B2B+B2C pitch**, Track F official, taste graph working-named **"Ruchi"**. This is the ambitious, high-surface-area path — keep the image loop independently shippable as the guardrail.

**Critical path (parallel build was chosen, so the shared spine goes first):**
1. **Track A-v2 FIRST** (fast, small, unblocks everyone) — extend the findings with the final graph-ready `Region` schema, the `actor`-field resolution (collapse `source`+`actor`?), and the embedding-storage plan (vectors out-of-row). Updated prompt: `track-A-datamodel.prompt.md`. Both creator and audience sides share this schema, so nothing parallel starts cleanly until it lands.
2. **Then B / C / D / F in parallel** (each a research findings pass, still no app code until Adarsh greenlights the build):
   - **Track B** — `model-integration-plan.md` → benchmarked, deploy-costed, fallback-laddered plan (Fashionpedia vs DeepFashion2, SAM2 image **+ video**, GPU-serving + on-device fallback, domain detection).
   - **Track C** — FashionCLIP taste-vector + RAG grounding; fashion-literate lenses; two readings (deep creator + short consumer feed hook).
   - **Track F** — B2C taste capture + creator→brand chain **+ the concrete video/reel plan** (now in scope).
   - **Track D** — creator Visual pane as the design source for the stripped consumer variant.

**Rules:** research + plan only until Adarsh greenlights the build; ground in real file+line refs; end findings with questions for Adarsh; conventional commits per `workflow-protocol.md`; verify UI by screenshot only; don't touch the other thread's dirty files (`decisions-log.md`, vault, `frontend-research/`).

**Recommended focus for this session:** **Track A-v2** (finalize the shared spine) — it's the critical-path unblocker for the parallel build. Then hand B/C/D/F to parallel sessions.
