# Track F — Consumer (B2C) taste layer & the creator→brand chain (research + plan only)

**Read first:** `00-brief.md`, `01-strategy-two-sided.md`, `model-integration-plan.md`. **Do not edit code.** Write `responses/track-F-consumer.findings.md`. Web search allowed.
**Depends on:** Track A (graph-ready `Region` schema) + Track C (reading engine). Research is parallel-safe; a *build* waits on A/C.

> **LOCKED 2026-07-08 (`decisions-darshan.md`):** Track F is **official** and runs **in parallel** with B/C/D (not after) — Adarsh chose the true-parallel two-sided path. And **video/reels is pulled into active scope this cycle** (not Phase-later): Q5 below is now a *primary* deliverable, not a boundary-drawing exercise — produce a concrete SAM2-video + replay-signal plan with GPU-serving cost/latency. Keep the image-first audience hook independently shippable as the guardrail.

## Mission
Design the **audience side** of Darshan and the **value chain** that connects audiences → creators → brands — the half that makes the project two-sided (strategy §1–§5). The hard constraint (Adarsh): **consumers must not do researcher-grade annotation.** Capture sophisticated taste signal through low-friction interaction that already feels good.

## Answer
1. **Low-friction taste capture — design the signal ladder.** Concretely: implicit signals (dwell, region taps/zoom, reel replay/rewatch), one-tap Aletheia forks (reuse `vision_service.py:594-631` MCQs as taste forks), save-with-a-reason-lite (chips, not text). What is captured, how it maps to the taste graph, what it costs the user (must be ≈0). Which signals are worth the plumbing vs noise.
2. **The Aletheia-in-feed hook.** How the deep reading engine (Track C) produces a *short, beautiful* consumer reading + a fork or two, rendered in a feed/pause context — the "read this image deeper" moment that is the B2C MVP. Where it lives relative to the creator studio (shared engine, different surface).
3. **The taste graph as the bridge.** How audience signal, creator annotations, and brand queries share one schema (strategy §4). What an audience "taste portfolio" is and why a user would value it (their taste given back, not harvested).
4. **The creator→brand chain / monetization.** How accrued part-level taste intelligence becomes: creator taste-signatures, trend-with-reason, and **creator↔brand matching by aesthetic taste** (the funded market: Vamp CAST, Linqia/CreatorIQ/Upfluence; niche creators 3.5× conversion). What Darshan uniquely offers that like-based platforms can't (part-level *why*, not follower counts). Sketch the B2C-free / creator-sub / brand-intelligence tiers.
5. **The video/reel path (scope, don't overbuild).** What SAM2-video + replay signals make possible for "which slice of a reel is loved," the cost/latency reality, and why it's Phase-later. Draw the boundary so the image-first MVP isn't blocked.
6. **Privacy / trust posture.** The pitch is "taste given back, not harvested for ads." What data model + user-facing promises make that real and differentiated (esp. vs the platforms we're a "level up" from).

## Output contract → `responses/track-F-consumer.findings.md`
Signal ladder (capture design) · Aletheia-in-feed MVP spec · taste-graph bridge (shared schema, actor/source) · creator→brand chain + monetization tiers · video/reel scope + boundary · privacy/trust posture · what this demands of Track A/C · questions for Adarsh.
