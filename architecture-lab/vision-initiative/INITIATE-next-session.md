# Initiate prompt — next Darshan session

Paste this to start the next vision-pipeline session. It assumes Track E + the v2 two-sided strategy are written and awaiting Adarsh's decisions.

---

You're continuing the **Darshan** vision-pipeline initiative in the Semant repo (`/home/adarsh-yadav/Documents/projects/semant`, GitHub `adarshh347/Semant`). You own the vision/annotation/AI pipeline; a separate thread owns the Drishya post-editor UI. Shared file is `PostDetailPage.jsx` — research phase has zero conflict; before any build touching it, `git pull` and tell Adarsh so he can serialize.

**Session start (do first):**
1. `git branch --show-current` must be `feat/frontend`. `git pull` / check log so you're on latest.
2. Re-read `architecture-lab/decisions-log.md` and the umbrella GitHub issue (create it if still missing — "Darshan — vision pipeline initiative (umbrella)", label `architecture`, with A–F as checkboxes; link #8/#9/#10).
3. Read, in order: `architecture-lab/vision-initiative/00-brief.md` (+ its v2 addendum), `01-strategy-two-sided.md`, `model-integration-plan.md`, then `responses/track-E-purpose.findings.md`, `responses/fashion-market-research.md`, `responses/track-A-datamodel.findings.md`.

**Then, gated on Adarsh's decisions:**
- If Adarsh has **answered the strategy §8 forks + Track A's 7 questions** → record the locks in `decisions-log.md`, then proceed to the chosen next track.
- If **not yet answered** → do not build. Run the next *research* track instead (recommended order: **Track B** — segmentation/model adoption, since the model stack is the biggest unknown and unblocks the demo — or **Track C** if Adarsh prioritizes the reading/taste-vector). Both are parallel-safe and research-only. Write `responses/track-{B|C}-*.findings.md` per the track's Output contract (incl. its v2 addendum), end with questions for Adarsh, commit `docs(arch-lab): …`, and stop.
- **Track F** (B2C) is research-safe anytime but most useful *after* A/C findings — pick it up once those land, or if Adarsh greenlights the consumer direction.

**Rules:** research + plan only until Adarsh locks decisions; ground every claim in real file+line refs; end each findings file with questions for Adarsh; conventional commits per `workflow-protocol.md`; verify any UI by screenshot, never by reading CSS. Don't edit the other thread's dirty files.

**Recommended focus for this session:** Track B (model-integration deep plan) — turn `model-integration-plan.md` into a benchmarked, deploy-costed, fallback-laddered segmentation plan.
