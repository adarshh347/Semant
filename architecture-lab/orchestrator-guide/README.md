# Orchestrator's guide — how to understand & steer the build

You are directing multiple build sessions across frontend, backend, vision-AI, and infra. You don't have to *write* the code, but to steer well you need to (a) understand the **shape** of each change, (b) know it **serves the purpose**, and (c) be able to **verify it's real** — especially now that most work is backend/AI with no screen to look at.

This folder is your operating manual. Companion: `track-A-study.md` (a worked deep-dive of the first backend change, with diagrams).

---

## 1. The three questions to ask of any change

Reuse the project's own lens — **Purpose → Structure → Surface** — as a review checklist:

1. **Purpose** — *what job does this serve, and which later track does it unblock?* If a session can't answer this in one sentence, the change is either overhead or misaimed.
2. **Structure** — *what actually changed in the architecture?* Which files, which data shapes, which contracts. This is the part you study.
3. **Surface / Evidence** — *how do I know it's real and didn't break anything?* For UI = screenshot. For backend/AI = tests, endpoint round-trips, DB checks (§4).

---

## 2. How to study any update in ~20 minutes

A repeatable routine — you did the research, so the vocabulary is already yours:

1. **Read the handoff** the session gives you (commits, what changed, verification, honest flags, what's next).
2. **Read the findings doc it implements** (e.g. Track A build ⇐ `responses/track-A-datamodel.findings.md`). The plan explains the *why*; the code is just the plan made real.
3. **Read the diff of the one key file**, not everything: `git show <commit>:path` or `git diff feat/frontend..feat/vision-pipeline -- <file>`. For Track A that's `backend/schemas/post.py`.
4. **Ask for the diagram / one example.** "Show me one region before and after," "draw the data flow." (I keep these in this folder.)
5. **Confirm the verification** actually ran (§4) — don't accept "verified" without seeing the evidence.

If you can restate the change in your own words + name what it unblocks, you've understood it.

---

## 3. Concepts to educate yourself on (and why each matters *here*)

You don't need a CS degree's worth — you need the dozen ideas this project actually turns on. Each line: the concept · why it matters in Darshan · where to see it.

**Backend / data**
- **Typed schema (Pydantic model)** — a class that validates the shape of data at the door · it's how the `Region` contract is enforced so every producer agrees · `backend/schemas/post.py`.
- **`extra='allow'` (forward-compat)** — a strict model that still tolerates unknown keys · lets Track B/C add fields without breaking today's data · `Region.model_config`.
- **Normalized coordinates (0–1) vs pixels** — storing box positions as fractions of the image, not pixels · makes marks survive image resize (fixed a real drift bug) · `RegionBox`.
- **Schema migration + deprecation shim** — retiring an old field without breaking readers (keep it read-only for a release, no backfill) · how `bounding_box_tags` was retired safely · Track A study.
- **Provenance / `actor` field** — recording *who/what* created a row (auto vs creator vs audience) · the single field that makes the product two-sided · `Region.actor`.
- **Sidecar collection / out-of-row storage** — keeping big/heavy data (vectors) in a separate table keyed by a pointer · keeps post payloads light, lets us swap vector DBs later · `region_embeddings`, `embedding_id`.
- **Aggregation continuity (regression)** — proving an existing feature still returns identical results after a change · how we know the taste catalog didn't break · `anatomy_catalog_service`.

**AI / ML**
- **Segmentation** — models that outline *parts* of an image · the "mark" half of see→mark · `segmentation_service.py`.
  - **YOLO** = fast, coarse, on-device (person/object). **SAM2** = promptable, class-agnostic, does video. **Fashionpedia** = fashion parts + 294 attributes. **FashionCLIP** = turns image+text into comparable vectors.
- **Embeddings / vectors** — representing an image (or part) as a list of numbers so "similarity" becomes math · this is how taste becomes queryable, not just counted · `embedding_id` → Track B.
- **RAG (retrieval-augmented generation)** — fetch relevant context first, then let the LLM write with it · how the writer gets grounded in *this* image + your taste history · Track C.
- **LLM re-roling** — using the language model only for *meaning/reading*, not geometry · the plan hands geometry to CV models and keeps the LLM as the reader · `model-integration-plan.md`.
- **Serverless GPU / fallback ladder** — renting model compute per-call + graceful degradation when a model fails · keeps cost near zero while data is small · Track B.

---

## 4. How to review non-frontend work (no screen — so what *do* you check?)

Backend and AI changes can't be eyeballed. Your evidence ladder, strongest last:

1. **Read the commits.** `git log --oneline feat/frontend..feat/vision-pipeline` then `git show <hash>`. Small, well-scoped, conventionally-named commits are a good sign; one giant blob is a smell.
2. **Read the verification script the session wrote.** Every backend build should ship a script/test that *proves* its claim. Track A shipped one (commit `05f8509`). Ask: "point me at the script and its output."
3. **Make the session show evidence, not adjectives.** Not "catalog still works" but "here are the 143 buckets before and after, identical." Not "regions validate" but "all 269 live rows parsed as `Region`."
4. **Run it yourself (the real check).** You can do this without coding:
   - Start the backend, then hit an endpoint. Example: `curl -s localhost:8000/posts/<id> | python -m json.tool` and look at the `region_annotations` shape.
   - Count DB rows / spot-check one document (ask the session for the exact command; it'll give you a one-liner).
5. **Regression = the most important check.** "What existing behaviour could this have broken, and how did you prove it didn't?" (For Track A that was the taste catalog.)

**Red flags to escalate on:**
- A claim with no script behind it.
- Assumptions that went stale (Track A found the "0 rows" premise was actually 1 row — the session flagged it honestly; that's the behaviour you want).
- Destructive DB operations (deletes, full-array overwrites) — ask what was backed up / restored.
- Edits creeping into the shared `PostDetailPage.jsx` or the other thread's files.

**The standing rule:** UI is verified by **screenshot**; backend/AI is verified by **test + evidence**. Never accept "done" for backend without the evidence artifact.

---

## 5. Your cadence with each build session
End every build by requiring a **handoff** with: commits (hashes), what changed (files + contracts), verification evidence (script + results), honest flags (what's stale/risky), and what's next. Then you study it via §2, and it feeds the showcase lane (`/showcase`) as a real, verified achievement.
