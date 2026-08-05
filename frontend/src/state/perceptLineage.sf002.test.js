/**
 * SF-002 Part 0 (frontend half) — the filter that stands between a draft and the database.
 *
 * `SF-001B` measured that no `percept_draft`-shaped proposal has ever reached `post.percepts` — 12
 * rows, all expression percepts, zero drafts. The backend guard
 * (`backend/tests/test_percept_lineage_sf002.py`) shows there is no server-side door. This shows
 * why there is no client-side one either, which is the door that actually exists: `regionStore`
 * writes `percepts: perceptsRef.current.filter(isExpressionPercept)` on every autosave, and reads
 * `(post.percepts || []).filter(isExpressionPercept)` on every hydrate.
 *
 * So `isExpressionPercept` IS the guarantee. These tests hold it to the two shapes it must
 * separate, written exactly as their producers mint them:
 *   - `makeExpressionPercept` here            → the curator's durable act of noticing
 *   - `compose_percept` (real_actuators.py)   → the director's proposal, which becomes a MARK
 *
 * The predicate's authoritative twin is `classify_percept_row`
 * (`backend/services/percept_lineage.py`); the third case below is the one that would drift first
 * if the two ever disagreed.
 */
import { describe, it, expect } from 'vitest';
import { makeExpressionPercept, isExpressionPercept } from './perceptMentions';

/** The dict `_run_compose_percept` appends to `ctx.suggestions`, key for key. */
const perceptDraft = (extra = {}) => ({
    producer: 'planner',
    type: 'percept_draft',
    role: null,
    label: 'the light pools',
    draft_text: 'the light pools',
    source_ref: 'run_1:percept:0',
    ground_refs: ['run_1:brush_field:0'],
    geometry: null,                      // a percept has no extent
    linked_ground_ids: [],
    ...extra,
});

describe('SF-002 Part 0 — a director proposal never passes for a durable percept', () => {
    it('a percept_draft is not an expression percept', () => {
        expect(isExpressionPercept(perceptDraft())).toBe(false);
    });

    it('the save filter drops a draft that somehow reached session state', () => {
        // The realistic failure: an accept path pushes a proposal into the percepts array instead
        // of minting a mark. The autosave payload must still carry only the curator's own.
        const mine = makeExpressionPercept({ expression: 'the light pools', ground_ids: ['gnd_1'] });
        const sessionState = [mine, perceptDraft(), perceptDraft({ label: 'another' })];

        const persisted = sessionState.filter(isExpressionPercept);

        expect(persisted).toEqual([mine]);
    });

    it('the hydrate filter drops one that somehow reached the database', () => {
        // Fail-closed in both directions: if a draft were ever written, reading it back must not
        // resurrect it as a percept the curator appears to have made.
        const stored = [perceptDraft(), makeExpressionPercept({ id: 'pctx_1', expression: 'x' })];
        expect(stored.filter(isExpressionPercept).map((p) => p.id)).toEqual(['pctx_1']);
    });

    it('a draft that borrowed the label of a percept is still a draft', () => {
        // The near-miss worth pinning: same words, same visible content — and still the wrong
        // lineage, because what makes it durable is the mint, not the sentence.
        const words = 'the light pools where the wool folds';
        expect(isExpressionPercept(perceptDraft({ label: words, draft_text: words }))).toBe(false);
        expect(isExpressionPercept(makeExpressionPercept({ expression: words }))).toBe(true);
    });

    it('an expression percept is recognised by its mint alone, before `kind` existed', () => {
        // Parity with the backend classifier's positive-evidence-first rule.
        expect(isExpressionPercept({ id: 'pctx_legacy', expression: 'x' })).toBe(true);
    });
});
