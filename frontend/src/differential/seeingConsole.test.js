import { describe, it, expect } from 'vitest';
import {
    FIND_PARTS_OPERATION, FIND_PARTS_LABEL, CONSOLE_COPY,
    EMPTY_TITLE, EMPTY_BODY, LOOKING_CAPTION, FIND_PARTS_FAILED,
    WAYS_OF_LOOKING, SPECIALIST_WAYS, BASE_WAY, WAY_KEYS,
    chosenWays, toggleWay, isAutoWay, wayReason, wayLabel,
    GRAINS, GRAIN_KEYS, grainLabel,
    sourceStrip, scheduledSources, hasBlockedSource, CAPABILITY_ROLE,
    memoryEntries, memorySummary, latestEntry, entryTime,
    MEMORY_SCOPE, MEMORY_PROVENANCE,
} from './seeingConsole';
import { OPERATIONS, OPERATION_LABEL, EPISTEMIC, AFFECTS, hasCausalWording } from './visionActivity';

/**
 * CIRCUIT-001 P2 — the Seeing Console's pure layer.
 *
 * The tests that matter here are not copy tests. Copy is what this gate is UNFREEZING, and a
 * suite that asserts display strings would have to be rewritten by the next label change.
 * What is pinned instead:
 *
 *   - wire identity survives the rename (keys, operation id, profile values, mode values);
 *   - the humane label maps to the RIGHT pass, so attention vocabulary cannot mis-select;
 *   - the console never invents readiness it was not told about;
 *   - unreadable stays distinct from absent, at every level.
 */

// ── the rename: labels move, wire identity does not ──────────────────────────

describe('the operation is renamed for the curator and unchanged on the wire', () => {
    it('still speaks to the `dissect` operation', () => {
        // If this ever changes, every stored run, every `dissect.*` stage id and the route
        // itself have to change with it. The label above it is free; this is not.
        expect(FIND_PARTS_OPERATION).toBe('dissect');
        expect(OPERATIONS).toContain('dissect');
    });

    it('no curator-facing string the console owns says "dissect"', () => {
        for (const s of CONSOLE_COPY) {
            expect(String(s).toLowerCase()).not.toContain('dissect');
        }
        expect(OPERATION_LABEL.dissect.toLowerCase()).not.toContain('dissect');
    });

    it('the primary action is labelled, non-empty, and not the operation id', () => {
        expect(FIND_PARTS_LABEL).toBeTruthy();
        expect(FIND_PARTS_LABEL).not.toBe(FIND_PARTS_OPERATION);
    });

    it('key integrity: renaming a label did not drop or add an operation', () => {
        // A key-integrity check, not a copy check (P1 spec Part E.3). A wrong KEY degrades
        // every stage to the humanStage fallback; a wrong LABEL is just words.
        expect(Object.keys(OPERATION_LABEL).sort()).toEqual([...OPERATIONS].sort());
        expect(Object.keys(EPISTEMIC).sort()).toEqual([...OPERATIONS].sort());
        expect(Object.keys(AFFECTS).sort()).toEqual([...OPERATIONS].sort());
    });

    it('the empty state invites perceptual work rather than naming the machine', () => {
        // The one copy assertion in the file, and it earns its place: the OLD copy is the
        // defect this gate was opened to fix, so a regression to it must fail loudly.
        expect(`${EMPTY_TITLE} ${EMPTY_BODY}`).not.toContain('anatomy');
        expect(EMPTY_BODY.toLowerCase()).toContain('grounds');
        expect(EMPTY_BODY.toLowerCase()).toContain('percepts');
    });

    it('no console copy asserts a cause', () => {
        // The Rail's own guard (visionActivity.CAUSAL_FORBIDDEN), extended to the console.
        for (const s of [...CONSOLE_COPY, MEMORY_SCOPE, MEMORY_PROVENANCE, LOOKING_CAPTION, FIND_PARTS_FAILED]) {
            expect(hasCausalWording(s)).toBe(false);
        }
    });
});

// ── ways of looking → domain-profile specialists ─────────────────────────────

describe('ways of looking map onto the profile values the backend accepts', () => {
    it('every way key is a real specialist value, and general is the base', () => {
        expect(WAY_KEYS).toEqual(['general', 'fashion', 'architecture', 'painting']);
        expect(BASE_WAY.key).toBe('general');
        expect(SPECIALIST_WAYS.map((w) => w.key)).toEqual(['fashion', 'architecture', 'painting']);
    });

    it('the humane label selects the right pass, not a lookalike', () => {
        // The whole risk of this rename: "Built space" must patch `architecture`, never
        // `painting`, and no label may collide with another's key.
        expect(wayLabel('architecture')).toBe('Built space');
        expect(wayLabel('fashion')).toBe('Fashion & body');
        expect(wayLabel('painting')).toBe('Painting & surface');
        const labels = WAYS_OF_LOOKING.map((w) => w.label);
        expect(new Set(labels).size).toBe(labels.length);
    });

    it('every way carries a hint, so a mode of attention is explainable', () => {
        for (const w of WAYS_OF_LOOKING) expect(w.hint).toBeTruthy();
    });

    it('defaults to general when the post has no profile', () => {
        expect(chosenWays(null)).toEqual(['general']);
        expect(chosenWays({})).toEqual(['general']);
        expect(chosenWays({ chosen: [] })).toEqual(['general']);
        expect(chosenWays({ chosen: ['painting'] })).toEqual(['painting']);
    });

    it('toggling adds, removes, and never sends `general` back', () => {
        // The service re-adds the base pass first. Sending it would let a curator's toggle
        // decide the base pass, which is not theirs to decide — identical to the control
        // this replaced, and the reason that behaviour is pinned rather than reimplemented.
        expect(toggleWay(['general'], 'painting')).toEqual(['painting']);
        expect(toggleWay(['general', 'painting'], 'fashion')).toEqual(['painting', 'fashion']);
        expect(toggleWay(['general', 'painting'], 'painting')).toEqual([]);
        expect(toggleWay(['general'], 'general')).toEqual([]);
        expect(toggleWay(undefined, 'fashion')).toEqual(['fashion']);
    });

    it('auto is only true when the profile says it was not overridden', () => {
        expect(isAutoWay({ user_overridden: false })).toBe(true);
        expect(isAutoWay({ user_overridden: true })).toBe(false);
        expect(isAutoWay({})).toBe(false);       // absent ≠ auto
        expect(isAutoWay(null)).toBe(false);
    });
});

describe('the router reason is cleaned or withheld', () => {
    it('drops the live corpus stutter rather than showing it', () => {
        // Real stored value on post 695be8b0…: an empty seed appended to twice.
        expect(wayReason({ reason: ' · user override · user override' })).toBe('user override');
    });
    it('returns null for an empty or punctuation-only reason', () => {
        expect(wayReason({ reason: '' })).toBe(null);
        expect(wayReason({ reason: ' · · ' })).toBe(null);
        expect(wayReason(null)).toBe(null);
    });
    it('leaves a genuinely multi-part reason intact', () => {
        expect(wayReason({ reason: 'garments detected · high confidence' }))
            .toBe('garments detected · high confidence');
    });
});

// ── grain: the subdivision vocabulary ────────────────────────────────────────

describe('grain keys are the `mode` values the detect route already accepts', () => {
    it('keys are frozen', () => {
        expect(GRAIN_KEYS).toEqual(
            ['general', 'garment', 'body', 'texture', 'material', 'composition'],
        );
    });
    it('every grain has a distinct label and falls back to its key when unknown', () => {
        const labels = GRAINS.map((g) => g.label);
        expect(new Set(labels).size).toBe(labels.length);
        expect(grainLabel('not_a_grain')).toBe('not_a_grain');
    });
});

// ── sources ──────────────────────────────────────────────────────────────────

const CAPS = {
    yolo11n_seg: { name: 'yolo11n_seg', capability: 'segment', state: 'ready', reason: '' },
    sam21_hiera_tiny: { name: 'sam21_hiera_tiny', capability: 'mask_refine', state: 'ready', reason: '' },
    fashionpedia_r50fpn: {
        name: 'fashionpedia_r50fpn', capability: 'fashion_parse', state: 'deferred',
        reason: 'local unavailable — serverless',
    },
};

describe('the source strip reports what it was told and nothing else', () => {
    it('names the role from the capability the server itself reports', () => {
        const scheduled = scheduledSources(sourceStrip(['yolo11n_seg', 'sam21_hiera_tiny'], CAPS));
        expect(scheduled.map((s) => s.role)).toEqual([
            CAPABILITY_ROLE.segment, CAPABILITY_ROLE.mask_refine,
        ]);
        expect(scheduled.map((s) => s.state)).toEqual(['ready', 'ready']);
    });

    it('an unrecorded pass is `unknown`, NOT `ready`', () => {
        // The control this replaced defaulted to `ready`, asserting availability on the
        // strength of a missing record. A strip that invents readiness is worse than one
        // that admits it does not know — this is the assertion that keeps it honest.
        const [s] = sourceStrip(['mystery_model'], CAPS);
        expect(s.state).toBe('unknown');
        expect(s.stateLabel).toBe('not reported');
        expect(s.label).toBe('mystery_model');     // an unnameable source is still shown
    });

    it('capabilities this way of looking does not schedule are marked unused', () => {
        const strip = sourceStrip(['yolo11n_seg'], CAPS);
        const unused = strip.filter((s) => !s.used).map((s) => s.name);
        expect(unused).toEqual(['fashionpedia_r50fpn', 'sam21_hiera_tiny']);
        expect(strip.find((s) => s.name === 'fashionpedia_r50fpn').state).toBe('unused');
        expect(scheduledSources(strip).map((s) => s.name)).toEqual(['yolo11n_seg']);
    });

    it('deferred is carried through with its reason, and is not a blocker', () => {
        const strip = sourceStrip(['fashionpedia_r50fpn'], CAPS);
        expect(strip[0].state).toBe('deferred');
        expect(strip[0].detail).toContain('serverless');
        expect(hasBlockedSource(strip)).toBe(false);   // deferred ≠ unavailable
    });

    it('flags a scheduled source that is genuinely unavailable', () => {
        const caps = { x: { capability: 'segment', state: 'unavailable', reason: 'no gpu' } };
        expect(hasBlockedSource(sourceStrip(['x'], caps))).toBe(true);
        // …but never for an unscheduled one: it is not in the way of anything.
        expect(hasBlockedSource(sourceStrip([], caps))).toBe(false);
    });

    it('survives no passes and no capabilities at all', () => {
        expect(sourceStrip()).toEqual([]);
        expect(sourceStrip(['yolo11n_seg'], {})[0].state).toBe('unknown');
    });
});

// ── operation memory ─────────────────────────────────────────────────────────

const NOW = Date.parse('2026-07-23T12:00:00Z');
const at = (mins) => new Date(NOW - mins * 60000).toISOString();
const runOf = (operation, status, completed) => ({
    operation, status, completed_at: completed, events: [],
});

describe('operation memory is a projection, and says which four operations it covers', () => {
    it('derives one entry per instrumented operation, in a stable order', () => {
        const entries = memoryEntries({}, { now: NOW });
        expect(entries.map((e) => e.operation)).toEqual(OPERATIONS);
        expect(entries.every((e) => e.isEmpty)).toBe(true);
    });

    it('states its own scope and its own provenance', () => {
        // Gate 3G: if it does not stream, it must not read as though it does. These two
        // strings are the only thing standing between a projection and a fake live feed.
        expect(MEMORY_SCOPE).toContain(String(OPERATIONS.length));
        expect(MEMORY_SCOPE.toLowerCase()).toContain('not all vision activity');
        expect(MEMORY_PROVENANCE.toLowerCase()).toContain('latest recorded run');
    });
});

describe('the collapsed summary keeps absence and unreadability apart', () => {
    const entriesFor = (results) => memoryEntries(results, { now: NOW });

    it('nothing recorded', () => {
        expect(memorySummary(entriesFor({})).text).toBe('nothing recorded yet');
    });

    it('a failed read is never reported as an empty corpus', () => {
        // P2.2R-B1. "Nothing recorded" is a claim ABOUT THE DATA; a broken request is not
        // entitled to make it.
        const s = memorySummary(entriesFor({ dissect: { run: null, unreadable: true } }));
        expect(s.text).toBe('couldn’t read activity');
        expect(s.tone).toBe('unreadable');
    });

    it('counts what is recorded and flags partial unreadability alongside it', () => {
        const s = memorySummary(entriesFor({
            dissect: { run: runOf('dissect', 'succeeded', at(5)), unreadable: false },
            refine: { run: null, unreadable: true },
        }));
        expect(s.text).toBe('1 recorded · some unreadable');
        expect(s.tone).toBe('warn');
    });

    it('an active run outranks every other state', () => {
        const s = memorySummary(entriesFor({
            dissect: { run: runOf('dissect', 'running', null), unreadable: false },
            refine: { run: runOf('refine', 'succeeded', at(9)), unreadable: false },
        }));
        expect(s.text).toBe('observing…');
    });
});

describe('the latest operation is ordered by its own recorded time', () => {
    const results = {
        dissect: { run: runOf('dissect', 'succeeded', at(90)), unreadable: false },
        refine: { run: runOf('refine', 'succeeded', at(3)), unreadable: false },
        semantic_read: { run: null, unreadable: false },
        find_similar: { run: null, unreadable: true },
    };

    it('picks the most recently completed run', () => {
        const latest = latestEntry(memoryEntries(results, { now: NOW }), results);
        expect(latest.operation).toBe('refine');
    });

    it('never picks an empty or unreadable operation', () => {
        const only = { find_similar: { run: null, unreadable: true } };
        expect(latestEntry(memoryEntries(only, { now: NOW }), only)).toBe(null);
    });

    it('parses a timestamp, or returns null rather than guessing', () => {
        expect(entryTime(null)).toBe(null);
        expect(entryTime({ created_at: 'not a date' })).toBe(null);
        expect(entryTime({ created_at: at(0) })).toBe(NOW);
        // falls back through completed_at → updated_at → created_at
        expect(entryTime({ updated_at: at(1) })).toBe(NOW - 60000);
    });

    it('being latest says nothing about having produced anything', () => {
        // Ordering is not causality. Nothing derived from `latestEntry` may say otherwise,
        // and the entry copy it renders comes from the same guarded EPISTEMIC table.
        const latest = latestEntry(memoryEntries(results, { now: NOW }), results);
        expect(hasCausalWording(latest.epistemic)).toBe(false);
        expect(hasCausalWording(latest.present.label)).toBe(false);
    });
});
