/**
 * INQUIRY WORKBENCH — the partition, and the pairs nobody compared. HARNESS-003E.
 *
 * 003D made the council visible: which pass, what it cost, how long it waited. This lane cuts two
 * of those passes into several requests each, because one request over every atom could not be sent
 * — 9,827 tokens against an 8,000 allowance. Batching on its own makes a relation crossing a
 * boundary structurally invisible, so the passes also compare every PAIR of batches.
 *
 * The pixel guarantee is therefore about the MATRIX rather than about the batches:
 *
 *   · how many batches, over how many items, is on the pass row;
 *   · `n of m batch pairs compared` is printed, and short coverage is MARKED rather than left to
 *     be read off two numerals side by side;
 *   · every unexamined pair prints IN FULL, with its reason, because "the budget stopped the run"
 *     and "nothing was found between these two" are opposite reports;
 *   · a pass that was never partitioned shows no plan at all — the ledger and the audit make no
 *     request, and `1 batch` on them would report a partition that never happened;
 *   · one batch prints "nothing across to compare" rather than `0 of 0`, which reads as a
 *     comparison that found nothing.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import ArtifactLedger from './ArtifactLedger.jsx';
import { normalizeSession, normalizeBatchPlan } from './inquiryContract.js';
import { batchedCouncilFixture, councilFixture } from './inquiryFixtures.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => { await act(async () => { el.click(); }); };

async function mount(fixture) {
    const session = normalizeSession(fixture);
    await act(async () => { root.render(<ArtifactLedger session={session} />); });
    return session;
}

const row = (id) => $(`[data-artifact="${id}"]`);
const openPasses = async () => { await click(row('passes').querySelector('.iw-expand')); };
const pass = (name) => $(`[data-pass="${name}"]`);

// ── the partition, on the pass row ──────────────────────────────────────────

describe('TestThePartitionIsOnThePassRow', () => {
    it('says how many batches carried how many items', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        expect(pass('relation_architect').querySelector('[data-fact="batches"]').textContent)
            .toMatch(/4 batches over\s*74 semantic_atoms/);
    });

    it('says how large the largest request was against what the account allows', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        expect(pass('relation_architect').querySelector('[data-fact="request-size"]').textContent)
            .toMatch(/largest request ~7104 of\s*8000 allowed/);
    });

    it('shows no plan at all on a pass that was never partitioned', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        expect(pass('source_ledger').querySelector('[data-batch-plan]')).toBeNull();
        expect(pass('semantic_dissector').querySelector('[data-batch-plan]')).toBeNull();
    });
});

// ── the coverage matrix ─────────────────────────────────────────────────────

describe('TestEveryPairOfBatchesIsAccountedFor', () => {
    it('prints how many pairs were compared, across how many rounds', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        expect(pass('relation_architect').querySelector('[data-fact="pairs"]').textContent)
            .toMatch(/6 of 6\s*batch pairs\s*compared across 4 rounds/);
    });

    it('marks short coverage rather than leaving it to be read off two numerals', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        const whole = pass('relation_architect').querySelector('[data-fact="pairs"]');
        const short = pass('epistemic_operationalizer').querySelector('[data-fact="pairs"]');
        expect(short.textContent).toMatch(/1 of 3/);
        expect(short.className).toContain('iw-pass-pairs--short');
        expect(whole.className).not.toContain('iw-pass-pairs--short');
    });

    it('prints every unexamined pair with the reason it was not examined', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        const named = $$('[data-unexamined-pair="true"]');
        expect(named).toHaveLength(2);
        expect(named[0].textContent).toContain('never compared');
        expect(named[0].textContent).toContain('bat_o1');
        expect(named[0].textContent).toContain('bat_o3');
        expect(named[0].textContent).toMatch(/declared\s*wall-clock budget/);
    });

    it('prints no unexamined list when every pair was compared', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        expect(pass('relation_architect').querySelector('[data-unexamined-pair]')).toBeNull();
    });

    it('says one batch had nothing across rather than printing 0 of 0', async () => {
        const fixture = batchedCouncilFixture();
        const passes = fixture.graph.passes.map((p) => (p.pass_name === 'relation_architect'
            ? { ...p,
                batch_plan: { ...p.batch_plan, batches: 1, pairs_total: 0, pairs_examined: 0,
                    rounds: [], unexamined_pairs: [] } }
            : p));
        await mount({ ...fixture, graph: { ...fixture.graph, passes } });
        await openPasses();
        const architect = pass('relation_architect');
        expect(architect.querySelector('[data-fact="pairs"]')).toBeNull();
        expect(architect.querySelector('[data-fact="pairs-none"]').textContent)
            .toContain('nothing across to compare');
    });
});

// ── the honesty the plan adds ───────────────────────────────────────────────

describe('TestThePlanReportsWhatItCouldNotSend', () => {
    it('says when a batch was too large to send at all', async () => {
        const fixture = batchedCouncilFixture();
        const passes = fixture.graph.passes.map((p) => (p.pass_name === 'relation_architect'
            ? { ...p, batch_plan: { ...p.batch_plan, unsendable_batches: 1 } } : p));
        await mount({ ...fixture, graph: { ...fixture.graph, passes } });
        await openPasses();
        expect(pass('relation_architect').querySelector('[data-fact="unsendable"]').textContent)
            .toMatch(/1 batch too large to\s*send — refused before transport/);
    });

    it('says how many duplicate claims were merged, and nothing when none were', async () => {
        await mount(batchedCouncilFixture());
        await openPasses();
        expect(pass('relation_architect').querySelector('[data-fact="duplicates"]').textContent)
            .toMatch(/1 duplicate claim\s*merged/);
        expect(pass('epistemic_operationalizer').querySelector('[data-fact="duplicates"]'))
            .toBeNull();
    });
});

// ── the contract underneath ─────────────────────────────────────────────────

describe('TestTheBatchPlanIsReadAsSent', () => {
    it('is null where the backend sent nothing, and null is not an empty plan', () => {
        expect(normalizeBatchPlan(undefined)).toBeNull();
        expect(normalizeBatchPlan(null)).toBeNull();
        expect(normalizeBatchPlan('4 batches')).toBeNull();
    });

    it('reports complete pair coverage as tri-state, with null for nothing across', () => {
        expect(normalizeBatchPlan({ pairs_total: 6, pairs_examined: 6 }).pairs_complete).toBe(true);
        expect(normalizeBatchPlan({ pairs_total: 6, pairs_examined: 4 }).pairs_complete).toBe(false);
        // One batch: there was nothing across, which is not a comparison that came up short.
        expect(normalizeBatchPlan({ pairs_total: 0, pairs_examined: 0 }).pairs_complete).toBeNull();
        expect(normalizeBatchPlan({}).pairs_complete).toBeNull();
    });

    it('keeps an unrecognised round outcome as unknown rather than guessing at it', () => {
        const plan = normalizeBatchPlan({ rounds: [{ outcome: 'a_word_nobody_declared' }] });
        expect(plan.rounds[0].outcome.known).toBe(false);
        expect(plan.rounds[0].outcome.value).toBe('a_word_nobody_declared');
    });

    it('reaches the pass through normalizeSession', async () => {
        const session = normalizeSession(batchedCouncilFixture());
        const architect = session.graph.passes.find(
            (p) => p.pass_name.value === 'relation_architect');
        expect(architect.batch_plan.pairs_examined).toBe(6);
        expect(architect.batch_plan.dispositions.orphan).toBe(13);
        const ledger = session.graph.passes.find((p) => p.pass_name.value === 'source_ledger');
        expect(ledger.batch_plan).toBeNull();
    });
});

describe('the stylesheet carries the distinction the markup makes', () => {
    it('gives short pair coverage and an unexamined pair their own treatment', () => {
        const css = fs.readFileSync(path.join(HERE, 'inquiryWorkbench.css'), 'utf8');
        expect(css).toContain('.iw-pass-pairs--short');
        expect(css).toContain('.iw-pass-unexamined');
    });
});
