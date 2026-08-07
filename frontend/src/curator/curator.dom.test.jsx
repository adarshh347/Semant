/**
 * WAVE4 — the curator UI: the four ways a face could betray the loop behind it.
 *
 * #172 made the API incapable of rendering `proposed` as `measured` — both fields required, no
 * defaults, derived on every read. **None of that reaches the screen.** A UI can take two honest
 * fields and print one word, and the curator would never know. So:
 *
 *   1. THE TWO STATUSES ARE TWO THINGS, visibly and in the DOM. Never one badge, never one word,
 *      and no two values share a treatment. §1.
 *   2. NOTHING COMMITS WITHOUT A DELIBERATE ACT — a name, a stated consequence, and a second
 *      confirm. One click cannot reach the ledger. §2.
 *   3. NO BULK PATH EXISTS. #172 left accept-all out of the API; a client loop would put it back
 *      out of clicks, and it would be invisible in any test that only checked one commit. §3.
 *   4. WHAT IS SHOWN IS WHAT WAS READ. After a commit the page re-fetches rather than patching the
 *      row — an optimistic update renders a status on the client's belief. §4.
 *
 * §5 covers the evidence: the producer's own numbers, shown and not summarised, absent shown absent.
 *
 * No testing-library — the project has none, and these are plain DOM queries against a real root,
 * the same shape as the other `.dom.test.jsx` suites.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import CuratorQueuePage from './CuratorQueuePage.jsx';
import EvidenceTable from './EvidenceTable.jsx';
import StatusPair from './StatusPair.jsx';

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

// ── fixtures: the shape the real route returns ──────────────────────────────

const OCCLUSION = {
    proposal_id: 'prop_aaa',
    kind: 'occlusion_supersedes_containment',
    producer: 'occlusion_organ',
    post_id: '6a6041b61ecd6db1c931eb79',
    mark_id: 'vm_occ_0309acd875e6',
    subject: {
        front_region_id: 'cseg_stone_texture_8',
        back_region_id: 'cseg_wall_surface_0',
        claim: 'cseg_stone_texture_8 is IN FRONT OF cseg_wall_surface_0, not inside it',
    },
    evidence: {
        ordering_dominance: 0.982201,
        ordering_separation: 0.982201,
        separation_floor: 0.95,
        ordering_ceiling: 0.986877,
        depth_grid: 192,
        basis: 'mask',
        front_cells: 1371,
        back_cells: 26633,
        contradicts: {
            relation: 'nested_within', containment: 0.979, nesting_index: 0.954, basis: 'mask',
        },
        detail: 'mask depth 0.3321 vs 0.0008 …',
    },
    filed_by: 'scripts/curator_file_occlusions.py',
    filed_at: '2026-08-07T16:00:00+00:00',
    committed_at: null,
    committed_by: null,
    epistemic: 'measured',
    ledger_status: 'proposed',
    live: false,
    detail_ledger: 'this mark is not in the ledger. The producer measured it, nobody has accepted it',
};

const SECOND = { ...OCCLUSION, proposal_id: 'prop_bbb', mark_id: 'vm_occ_second' };

function committedForm(row, curator = 'adarsh') {
    return {
        ...row,
        committed_at: '2026-08-07T17:00:00+00:00',
        committed_by: curator,
        ledger_status: 'committed',
        live: true,
        detail_ledger: 'a curator committed this mark; the ledger holds it',
    };
}

/** A fake backend recording every call, so "what the UI did" is checkable. */
function backend({ rows = [OCCLUSION, SECOND] } = {}) {
    const state = { rows: rows.map((r) => ({ ...r })), commits: [], gets: [] };
    const fetchMock = vi.fn(async (url, init) => {
        const target = String(url);
        state.gets.push(`${(init && init.method) || 'GET'} ${target}`);

        if (target.includes('/commit')) {
            const id = target.split('/queue/')[1].split('/commit')[0];
            const body = JSON.parse((init && init.body) || '{}');
            state.commits.push({ id, ...body });
            state.rows = state.rows.map((r) =>
                (r.proposal_id === id ? committedForm(r, body.curator) : r));
            return json({ proposal_id: id, committed_by: body.curator });
        }
        if (/\/queue\/[^/?]+$/.test(target)) {
            const id = target.split('/queue/')[1];
            const row = state.rows.find((r) => r.proposal_id === id);
            return row ? json(row) : json({ detail: 'no proposal' }, 404);
        }
        return json({ proposals: state.rows, total: state.rows.length, filter: {} });
    });
    vi.stubGlobal('fetch', fetchMock);
    return state;
}

function json(body, status = 200) {
    return { ok: status < 400, status, json: async () => body };
}

async function mount(element) {
    await act(async () => {
        root.render(<MemoryRouter>{element}</MemoryRouter>);
    });
    // let the queue + detail fetches settle
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await Promise.resolve(); });
}

const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => Array.from(container.querySelectorAll(sel));
const byText = (sel, text) => $$(sel).find((el) => el.textContent.includes(text));

// ── 1. two statuses, two things ────────────────────────────────────────────

describe('the two statuses are never one', () => {
    it('renders an epistemic badge and a ledger badge, separately', async () => {
        await mount(<StatusPair epistemic="measured" ledgerStatus="proposed" />);
        const epistemic = $('.cur-badge--epistemic');
        const ledger = $('.cur-badge--ledger');
        expect(epistemic.textContent.trim()).toBe('measured');
        expect(ledger.textContent.trim()).toBe('proposed');
        expect(epistemic).not.toBe(ledger);
    });

    it('says out loud that measured + proposed is not a contradiction', async () => {
        await mount(<StatusPair epistemic="measured" ledgerStatus="proposed" />);
        expect($('.cur-statusgloss').textContent).toMatch(/not in tension/i);
    });

    it('never prints a word that means both — no "settled", no "confirmed"', async () => {
        await mount(<StatusPair epistemic="measured" ledgerStatus="proposed" />);
        const text = container.textContent.toLowerCase();
        for (const forbidden of ['settled', 'confirmed', 'verified', 'true']) {
            expect(text).not.toContain(forbidden);
        }
    });

    it('shows a missing epistemic as missing rather than as uncertain', async () => {
        await mount(<StatusPair epistemic={null} ledgerStatus="proposed" />);
        expect($('.cur-badge--epistemic').textContent).toMatch(/no status on the mark/);
        expect(container.textContent).not.toMatch(/uncertain/);
    });

    it('gives every status value its own visual treatment', () => {
        // Read off the stylesheet, because this is a claim about pixels that no DOM query reaches:
        // a UI where `measured` and `committed` looked alike would be the collapse the read path
        // refuses, arriving one layer further out.
        const css = fs.readFileSync(path.join(HERE, 'curator.css'), 'utf8');
        const rule = (name) => {
            const m = css.match(new RegExp(`\\.cur-badge--${name}\\s*\\{([^}]*)\\}`));
            return m ? m[1].replace(/\s+/g, ' ').trim() : null;
        };
        const treatments = ['measured', 'interpretive', 'proposed', 'committed'].map(rule);
        expect(treatments.every(Boolean)).toBe(true);
        expect(new Set(treatments).size).toBe(4);
        // and the two families differ in KIND, not only in colour: outline vs filled
        expect(css).toMatch(/\.cur-badge--epistemic\s*\{[^}]*background:\s*transparent/);
        expect(rule('committed')).toMatch(/background:/);
    });
});

// ── 2. the commit is deliberate ────────────────────────────────────────────

describe('the commit is a deliberate act', () => {
    it('cannot be reached without a name', async () => {
        backend();
        await mount(<CuratorQueuePage />);
        const open = byText('button', 'Commit this to the ledger');
        expect(open.disabled).toBe(true);
    });

    it('states the consequence before it happens, and needs a second press', async () => {
        const state = backend();
        await mount(<CuratorQueuePage />);

        const input = $('input[aria-label="curator name"]');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, 'adarsh');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });

        await act(async () => {
            byText('button', 'Commit this to the ledger').click();
        });

        // the consequence, in the specific — and nothing committed yet
        const what = $('.cur-confirm-what').textContent;
        expect(what).toContain('vm_occ_0309acd875e6');
        expect(what).toContain('6a6041b61ecd6db1c931eb79');
        expect(state.commits).toHaveLength(0);

        await act(async () => { byText('button', 'Yes — commit as adarsh').click(); });
        await act(async () => { await Promise.resolve(); });
        expect(state.commits).toEqual([{ id: 'prop_aaa', curator: 'adarsh', note: '' }]);
    });

    it('says the kind of knowing will not change', async () => {
        backend();
        await mount(<CuratorQueuePage />);
        const input = $('input[aria-label="curator name"]');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, 'adarsh');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { byText('button', 'Commit this to the ledger').click(); });
        expect(container.textContent).toMatch(/cannot make an estimate into a measurement/);
    });

    it('offers no undo on a committed proposal, and says why', async () => {
        backend({ rows: [committedForm(OCCLUSION)] });
        await mount(<CuratorQueuePage />);
        expect(byText('button', 'Commit this to the ledger')).toBeUndefined();
        expect($('.cur-commit--done').textContent).toMatch(/no undo/i);
    });
});

// ── 3. no bulk path exists ─────────────────────────────────────────────────

describe('there is no bulk or automated commit', () => {
    it('exposes exactly one commit control, for the one open proposal', async () => {
        backend();
        await mount(<CuratorQueuePage />);
        // two proposals in the list, one commit affordance on screen
        expect($$('.cur-row')).toHaveLength(2);
        expect($$('.cur-btn--primary')).toHaveLength(1);
    });

    it('has no accept-all anywhere in the source', () => {
        // Scanned over the BODY, not the prose: the modules explain what they refuse, and a scan
        // that could not tell a mention from a call would force them to stop.
        const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
        for (const file of ['CuratorQueuePage.jsx', 'CommitAction.jsx', 'curatorService.js']) {
            const body = strip(fs.readFileSync(path.join(HERE, file), 'utf8'));
            for (const forbidden of ['commitAll', 'acceptAll', 'bulk', 'forEach(commit',
                                     'map(commit', 'threshold']) {
                expect(body).not.toContain(forbidden);
            }
        }
    });

    it('makes exactly one commit request per confirmed act', async () => {
        const state = backend();
        await mount(<CuratorQueuePage />);
        const input = $('input[aria-label="curator name"]');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, 'adarsh');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { byText('button', 'Commit this to the ledger').click(); });
        await act(async () => { byText('button', 'Yes — commit as adarsh').click(); });
        await act(async () => { await Promise.resolve(); });

        expect(state.gets.filter((g) => g.startsWith('POST'))).toHaveLength(1);
        // and the OTHER proposal is untouched
        expect(state.rows.find((r) => r.proposal_id === 'prop_bbb').ledger_status)
            .toBe('proposed');
    });
});

// ── 4. what is shown is what was read ──────────────────────────────────────

describe('the page renders the ledger, not its own belief', () => {
    it('re-reads after a commit instead of patching the row', async () => {
        const state = backend();
        await mount(<CuratorQueuePage />);
        const before = state.gets.filter((g) => g.startsWith('GET')).length;

        const input = $('input[aria-label="curator name"]');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value').set;
            setter.call(input, 'adarsh');
            input.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await act(async () => { byText('button', 'Commit this to the ledger').click(); });
        await act(async () => { byText('button', 'Yes — commit as adarsh').click(); });
        await act(async () => { await Promise.resolve(); });
        await act(async () => { await Promise.resolve(); });

        expect(state.gets.filter((g) => g.startsWith('GET')).length).toBeGreaterThan(before);
        expect($('.cur-badge--committed')).toBeTruthy();
    });

    it('shows proposed and committed as different things in the list', async () => {
        backend({ rows: [OCCLUSION, committedForm(SECOND)] });
        await mount(<CuratorQueuePage />);
        expect($$('.cur-dot--proposed')).toHaveLength(1);
        expect($$('.cur-dot--committed')).toHaveLength(1);
    });

    it('renders the queue in filed order and does not sort it', async () => {
        const strong = { ...OCCLUSION, proposal_id: 'prop_weak',
                         evidence: { ...OCCLUSION.evidence, ordering_separation: 0.9501 } };
        const weak = { ...SECOND, proposal_id: 'prop_strong',
                       evidence: { ...OCCLUSION.evidence, ordering_separation: 0.9999 } };
        backend({ rows: [strong, weak] });
        await mount(<CuratorQueuePage />);
        // Read off the source as well: an ordering that happened to match is not the same claim
        // as an ordering that cannot change.
        const body = fs.readFileSync(path.join(HERE, 'CuratorQueuePage.jsx'), 'utf8')
            .replace(/\/\*[\s\S]*?\*\//g, '');
        expect(body).not.toContain('.sort(');
    });
});

// ── 5. the evidence ────────────────────────────────────────────────────────

describe('the evidence is the producer’s, unsummarised', () => {
    it('shows the ordering statistic, its floor, its ceiling and the grid', async () => {
        await mount(<EvidenceTable evidence={OCCLUSION.evidence} subject={OCCLUSION.subject} />);
        const text = container.textContent;
        expect(text).toContain('0.9822');
        expect(text).toContain('0.9500');
        expect(text).toContain('0.9869');
        expect(text).toContain('192');
    });

    it('shows an absent field as absent, never as zero', async () => {
        const thin = { ordering_separation: 0.97 };
        await mount(<EvidenceTable evidence={thin} />);
        expect($$('.cur-ev-missing').length).toBeGreaterThan(0);
        expect(container.textContent).not.toMatch(/\b0\.0000\b/);
    });

    it('states what the occlusion contradicts, with both readings measured', async () => {
        await mount(<EvidenceTable evidence={OCCLUSION.evidence} subject={OCCLUSION.subject} />);
        const text = $('.cur-ev-contradicts').textContent;
        expect(text).toContain('nested_within');
        expect(text).toMatch(/Both readings are\s+measured/);
    });

    it('keeps a ratio at four places even when it lands on a round number', async () => {
        // CAUGHT ON THE LIVE QUEUE: a containment of exactly 1.0 rendered as `1` beside a nesting
        // index of `0.9958`, and the pair read as though one were a count and the other a
        // measurement. `Number.isInteger` is right for a cell count and wrong for a quantity that
        // has hit its ceiling.
        const round = { ...OCCLUSION.evidence,
                        contradicts: { relation: 'nested_within', containment: 1,
                                       nesting_index: 0.9958, basis: 'mask' } };
        await mount(<EvidenceTable evidence={round} />);
        const text = $('.cur-ev-contradicts').textContent;
        expect(text).toContain('1.0000');
        expect(text).toContain('0.9958');
    });

    it('computes no score, bar or confidence of its own', () => {
        const body = fs.readFileSync(path.join(HERE, 'EvidenceTable.jsx'), 'utf8')
            .replace(/\/\*[\s\S]*?\*\//g, '');
        for (const forbidden of ['confidence', 'score', 'progress', 'width:', 'strong /']) {
            expect(body).not.toContain(forbidden);
        }
    });
});
