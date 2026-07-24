---
title: "The Orchestration Session"
category: technical / hybrid
status: emerging
summary: "A pure assembler that freezes the whole working context — image, selection, writing, evidence, what was asked, under what constraints — into one inspectable request that can be refused before anything is spent. Nothing is dispatched; that's deliberate."
source: frontend/src/orchestration/orchestrationSession.js · differential/perceptPacket.js
---

# The Orchestration Session

**Category:** technical / hybrid · **Status:** emerging (the assembler ships; no model call is wired to it yet — on purpose)

## Summary
Before you ask a model to read an image, there's a question almost no tool asks first: *what, exactly, is being asked — on what evidence, under what constraints — and is the request even valid?* The Orchestration Session is Semant's answer. It assembles the entire current circuit into one frozen, inspectable object **before** any dispatch, and it can refuse an invalid request **without spending anything.** It is not an agent and not a memory. It is a manifest.

## The problem it solves
Today, when something reaches a vision-language model, the model doesn't know it's about a *percept*, and whatever comes back doesn't know what it was asked about. The context is implicit, the constraints live in a prompt template someone can quietly edit, and a question resting on evidence that no longer exists still produces a confident answer about nothing. The expensive part — the model call — happens before anyone has checked that the request makes sense.

A research programme inside Semant (the rehearsals — see that note) paid many runs to learn one lesson: **the value is not in the call. It's in freezing what was asked, on what evidence, under what constraints — and being able to refuse a bad request before you pay for it.**

## What exists now
The session is a **pure assembler**: it calls nothing, sends nothing, mints no run id, persists nothing, and reaches for no clock it isn't handed. It widens the earlier single-percept "packet" to the whole working circuit — the image, the selection, the writing, the evidence, what was asked before, and what you said caught you — and it holds that as *data*, read once and discarded.

It is defined as much by what it is **not**:
- **not an agent** — no loop, no goals, no memory across images, cannot call out;
- **not persistent memory** — assembled on demand, read once, thrown away;
- **not a mutation path** — it holds *proposals*; applying one still goes through the grammar's validators and your hand;
- **not a prompt** — constraints travel as data, so the discipline can't be silently rewritten by whoever edits the next prompt template.

What makes it worth building before there's anything to dispatch to is a set of **honesty invariants** — listed in the code in order of how easily a careless later refactor would destroy them:

- **`unreadable[]`** names everything that was asked for and not obtained. *Silence must never be readable as absence.*
- **`external_claims: null`** means **not assessed** — not "assessed and found none." There is no assessor, so `null` is the only honest value; `[]` would be a lie.
- **`resolution_assessed: false`** means every "this evidence detached" flag carries *no information* — the system refuses to imply it checked when it didn't.
- **`citation_state: 'cites_nothing'`** is a *record* of what the markup shows — not `'unsupported'`, which would be a judgement the system cannot make.
- **`dispatch_state`** is stated *inside* the object so it can never be mistaken for a record that a dispatch happened.

The companion **Percept Packet** is the smaller, earlier version of the same discipline: a single percept turned into an inspectable operation request that carries its own **evidence state**, so a question resting on grounds that no longer resolve is visibly degraded *before* it's asked. It even names the **intents** a curator might have — read, challenge, compare, revise — as honest placeholders, because naming them is not the same as scheduling them.

## Why it's built this way
Almost every system builds the model call first and the accounting later. Semant inverts it: build the *manifest* first, prove you can refuse a bad request for free, and only then wire a model to the far end. Constraints-as-data (not prompt text) means the guardrails can't erode as prompts get edited; the honesty invariants mean the object never implies work it didn't do. When dispatch is finally added, it plugs into an object that already knows how to say "I couldn't get that," "I didn't assess this," and "this rests on nothing."

## Where this goes next
- **Dispatch, at last** — a model call on the far end of the session, returning results that know exactly what they were asked about, with the session preserved as the record of the ask.
- **Provenance on the return** — answers carrying the same receipts (what ran, on what, how long) the rest of the engine already demands.
- **Session as a shareable artifact** — a frozen ask others (or an agent) can inspect, re-run, or refuse.

*The session is Semant's bet that in a world of cheap model calls, the scarce, valuable thing is a request you can trust and refuse — assembled, and inspectable, before a cent is spent.*
