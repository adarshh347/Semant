/**
 * INQUIRY WORKBENCH — the artifact ledger.
 *
 * The 002R rehearsal's `disconnected_artifact` failure: the backend had accumulated frame, posts,
 * reading blocks, verdicts, gaps and provenance, and the client read none of them. These tests are
 * about the chain being visible AND about absence being printed rather than implied.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import ArtifactLedger, { AbsenceLedger } from './ArtifactLedger.jsx';
import { normalizeSession, uncoveredSourceUnits } from './inquiryContract.js';
import {
    completedFixture, dissolvedFixture, barrenFixture, runningStagesFixture,
    consultFixture, FIXTURE_PROMPT,
} from './inquiryFixtures.js';

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
const openRow = async (id) => { await click(row(id).querySelector('.iw-expand')); };

// ── the chain, end to end ───────────────────────────────────────────────────

describe('the progressive chain', () => {
    it('renders every stage of it with a count', async () => {
        await mount(dissolvedFixture());
        const expected = {
            prompt: 1, posts: 2, frame: 1, reading_blocks: 3, source_units: 5, coverage: 4,
            atoms: 3, claims: 4, claim_edges: 3, observables: 3, decisions: 1, receipts: 1,
            verdicts: 2, synthesis: 3,
        };
        for (const [id, count] of Object.entries(expected)) {
            expect([id, row(id)?.dataset.count]).toEqual([id, String(count)]);
        }
    });

    it('shows the prompt byte-identically', async () => {
        await mount(completedFixture());
        await openRow('prompt');
        expect($('.iw-led-prompt').textContent).toBe(FIXTURE_PROMPT);
    });

    it('shows the fingerprint of each post read, not a checkmark', async () => {
        // Phase 1's claim is that no source post changed. A comparison is evidence; a tick is an
        // assurance.
        await mount(completedFixture());
        await openRow('posts');
        const post = $('[data-post-ref="post_altes_front"]');
        expect(post.textContent).toMatch(/fingerprint a1b2c3d4e5f60718…/);
        expect(post.textContent).toMatch(/re-checked at every write/);
    });

    it('marks a post that could not be read', async () => {
        const raw = completedFixture();
        raw.posts[1] = { ...raw.posts[1], readable: false, note: 'The image URL did not resolve.' };
        await mount(raw);
        await openRow('posts');
        expect($('[data-unreadable="true"]').textContent).toBe('could not be read');
        expect($('[data-post-ref="post_altes_rotunda"]').textContent)
            .toContain('The image URL did not resolve.');
    });

    it('renders the reading blocks the theorist emitted', async () => {
        // `graph_view` has sent these since HARNESS-002D and nothing read them. They are what the
        // dissector consumes, so a ledger showing claims without them starts the chain mid-way.
        await mount(completedFixture());
        await openRow('reading_blocks');
        expect($$('[data-block-id]')).toHaveLength(3);
        expect($('[data-block-id="rdb_1"]').textContent).toContain('a screen of columns');
        expect($('[data-block-id="rdb_3"] .iw-kind').textContent).toBe('association');
    });
});

// ── dissolution, and the unit nobody accounted for ──────────────────────────

describe('the dissolution ledger', () => {
    it('renders source units with their exact quotes', async () => {
        await mount(dissolvedFixture());
        await openRow('source_units');
        expect($$('[data-source-unit]')).toHaveLength(5);
        expect($('[data-source-unit="su_2"]').textContent)
            .toContain('what does the threshold between them actually do');
        expect($('[data-source-unit="su_1"] .iw-kind').textContent).toBe('prompt clause');
    });

    it('gives each disposition its own words', async () => {
        await mount(dissolvedFixture());
        await openRow('coverage');
        expect($('[data-coverage-for="su_1"] [data-disposition="represented_by"]').textContent)
            .toBe('became one or more atoms');
        expect($('[data-coverage-for="su_4"] [data-disposition="semantic_remainder"]').textContent)
            .toBe('was not dissolved, and the reason is recorded');
        expect($('[data-coverage-for="su_4"]').textContent)
            .toContain('No measurement of these pixels can settle it.');
    });

    it('names a source unit that received NO disposition, as lost rather than as remainder', async () => {
        // The dissolution contract says every source unit gets exactly one. A unit with none is
        // not a remainder — a remainder is a decision — it is a unit the compiler lost.
        const session = await mount(dissolvedFixture());
        expect(uncoveredSourceUnits(session.graph).map((u) => u.source_unit_id)).toEqual(['su_5']);

        expect(row('coverage').className).toContain('iw-led-row--warn');
        expect(row('coverage').textContent)
            .toMatch(/1 source unit received no disposition at all/);
        expect(row('coverage').textContent).toMatch(/it is a unit the compiler lost/);

        await openRow('coverage');
        const lost = $('[data-uncovered="su_5"]');
        expect(lost.textContent).toContain('no disposition — lost');
        expect(lost.textContent).toContain('the rotunda is a centre');
    });

    it('attributes a user-authored atom to the person', async () => {
        await mount(dissolvedFixture());
        await openRow('atoms');
        expect($('[data-atom-id="atm_2"] .iw-author--user').textContent).toBe('your direction');
        expect($('[data-atom-id="atm_1"] .iw-author--user')).toBeNull();
    });

    it('is silent about dissolution when the backend sends none of it', async () => {
        // Lane A is building these in parallel. A surface that showed "0 atoms" as a defect would
        // be reporting a lane that has not merged as a failure of the run.
        await mount(completedFixture());
        expect(row('source_units').dataset.count).toBe('0');
        expect(row('atoms').dataset.count).toBe('0');
        expect(row('coverage').className).not.toContain('iw-led-row--warn');
        expect(text()).not.toMatch(/no disposition at all/);
    });
});

// ── why is this here ────────────────────────────────────────────────────────

describe('why is this here', () => {
    it('opens on any object and names its source, producer and status', async () => {
        await mount(dissolvedFixture());
        await openRow('atoms');
        await click($('[data-why-for="atm_1"]'));
        const why = $('[data-why-open="atm_1"]');

        expect(why.textContent).toContain('atm_1');
        expect(why.textContent).toContain('su_3');                    // its source unit
        expect(why.textContent).toContain('semantic_dissector');      // producer
        expect(why.textContent).toContain('openai/gpt-oss-120b');     // model
        expect(why.textContent).toMatch(/interpretive — a reading about the images/);
    });

    it('shows the RAW record, so a field this client has not learned stays visible', async () => {
        const raw = dissolvedFixture();
        raw.graph.semantic_atoms[0].confidence_band = 'wide';   // a field no normaliser reads
        await mount(raw);
        await openRow('atoms');
        await click($('[data-why-for="atm_1"]'));

        const why = $('[data-why-open="atm_1"]');
        expect(why.textContent).toContain('confidence_band');
        expect(why.textContent).toContain('wide');
    });

    it('says "not recorded" rather than inventing a producer', async () => {
        const raw = dissolvedFixture();
        raw.graph.semantic_atoms[2].provenance = {};
        await mount(raw);
        await openRow('atoms');
        await click($('[data-why-for="atm_3"]'));
        expect($('[data-why-open="atm_3"]').textContent).toContain('semantic_dissector');

        await openRow('claim_edges');   // an object type with no provenance at all
        expect($('[data-ledger-edge="edg_1"]')).toBeTruthy();
    });

    it('is closed until asked', async () => {
        await mount(dissolvedFixture());
        await openRow('atoms');
        expect($('[data-why-open="atm_1"]')).toBeNull();
        expect($('[data-why-for="atm_1"]').getAttribute('aria-expanded')).toBe('false');
    });
});

// ── verdicts ────────────────────────────────────────────────────────────────

describe('verdicts', () => {
    it('keeps interpretive_only and not_investigated apart', async () => {
        // One says the claim was examined and nothing measured bears on it; the other says nobody
        // asked. A reader deciding how much to trust an answer needs both.
        await mount(completedFixture());
        await openRow('verdicts');
        expect($('[data-verdict="interpretive_only"]').textContent).toBe('interpretive only');
        expect($('[data-verdict="not_investigated"]').textContent).toBe('not investigated');
        expect($('[data-ledger-verdict="vd_colonnade"]').textContent)
            .toContain('It was looked at, and nothing measured bears on it.');
        expect($('[data-ledger-verdict="vd_temple"]').textContent).toContain('Nobody asked.');
    });

    it('shows no supported verdict in a session with no evidence', async () => {
        await mount(completedFixture());
        await openRow('verdicts');
        expect($('[data-verdict="supported_by_evidence"]')).toBeNull();
        expect($('[data-verdict="partially_supported"]')).toBeNull();
    });
});

// ── absence ─────────────────────────────────────────────────────────────────

describe('what it did not create', () => {
    it('prints the zeroes rather than leaving a gap', async () => {
        // A blank space where a count should be reads as "pending" to every reader.
        await mount(completedFixture());
        const absence = $('[data-absence-ledger="true"]');
        expect(absence.querySelector('[data-absent="grounds"]').textContent)
            .toBe('grounds created: 0');
        expect(absence.querySelector('[data-absent="percepts"]').textContent)
            .toBe('percepts created: 0');
        expect(absence.querySelector('[data-absent="evidence"]').textContent)
            .toBe('evidence created: 0');
        expect(absence.querySelector('[data-absent="atlas"]').textContent)
            .toBe('Atlas changes: 0');
        expect(absence.querySelector('[data-absent="marks"]').textContent)
            .toBe('marks committed: 0');
    });

    it('says a finished run DID not, rather than that it will not', async () => {
        // "will not" and "did not" are different promises, and a rehearsal that reads "will not"
        // on a session that already ended learns nothing about what happened.
        await mount(completedFixture());
        expect($('.iw-absence-note').textContent).toMatch(/This run is over and created none of these/);
        expect($('.iw-absence-note').textContent).not.toMatch(/will not once the run finishes/);
    });

    it('says a running one will not, and never implies they are pending', async () => {
        await mount(runningStagesFixture());
        const note = $('.iw-absence-note').textContent;
        expect(note).toMatch(/will not once the run finishes/);
        expect(note).toMatch(/not stages still to come/);
        expect(note).toMatch(/nothing here is pending/);
    });

    it('counts real evidence when a session has some', async () => {
        const session = normalizeSession({
            ...completedFixture(),
            evidence: [{ evidence_id: 'e1', usable_as_evidence: true, execution_mode: 'live' }],
        });
        await act(async () => { root.render(<AbsenceLedger session={session} />); });
        expect($('[data-absent="evidence"]').textContent).toBe('evidence created: 1');
    });
});

// ── a barren run still has a ledger ─────────────────────────────────────────

describe('a run that compiled nothing', () => {
    it('shows zero rows rather than an absent ledger', async () => {
        await mount(barrenFixture());
        expect(row('claims').dataset.count).toBe('0');
        expect(row('observables').dataset.count).toBe('0');
        expect(row('claims').className).toContain('is-empty');
        // but the things it DID produce are still there
        expect(row('reading_blocks').dataset.count).toBe('3');
        expect(row('posts').dataset.count).toBe('2');
    });

    it('offers no Open button for an empty row', async () => {
        await mount(barrenFixture());
        expect(row('claims').querySelector('.iw-expand')).toBeNull();
        expect(row('reading_blocks').querySelector('.iw-expand')).toBeTruthy();
    });
});

describe('a session before anything compiled', () => {
    it('renders without throwing on a graph with no dissolution objects', async () => {
        await mount(consultFixture());
        expect($('.iw-ledger')).toBeTruthy();
        expect(row('frame').dataset.count).toBe('1');
        expect(row('verdicts').dataset.count).toBe('0');
    });
});
