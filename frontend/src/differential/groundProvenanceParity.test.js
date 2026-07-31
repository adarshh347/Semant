/**
 * CIRCUIT-002 PROV-001 Seam 2 — a ground SHOWS its mark's provenance, it never authors its own.
 *
 * The decision this pins. Provenance is authored on the produced object (the mark) and derived by
 * the ground. CIRCUIT-001 P3-A already states the rule — "visible provenance on a ground, WITHOUT
 * authoring it … one source of truth" (regionStore.js) — and PROV-001 keeps it rather than
 * denormalising `run_id`/`step_id` onto grounds as a second authored copy. Two authored copies is
 * the drift `test_producer_parity` exists to catch on the backend, and it would arrive here the
 * first time a mark was superseded and its ground was not.
 *
 * So a ground must have NO independent path to a run or a step. If it ever grows one, the two can
 * disagree, and the ground's row will confidently name a run that did not produce what is on
 * screen. That is what these tests prevent.
 *
 *   1. makeGround authors no provenance at all        → the no-authoring-path claim
 *   2. what a ground shows equals its source mark      → the parity claim
 *   3. the newest linked mark wins a supersession      → parity survives the case that breaks it
 */
import { describe, it, expect } from 'vitest';
import { makeGround, groundFromRegion } from './grounds';
import { bridgeFieldsFromMark, reconcileBridgeFields, bridgeFieldsAgree } from './suggestionQuarantine';
import { makeVisualMark } from './visualMarks';

/** A mark minted for a real producer, carrying the receipt Seam 1 stamps. */
function producerMark(fields = {}) {
    return makeVisualMark('brush_field', {
        role: 'pressure_zone',
        geometry: { kind: 'raster', strokes: [[0.1, 0.2]] },
        provenance: { run_id: 'run_7', step_id: 's3', producer: 'pressure_zone' },
        ...fields,
    });
}

// ── 1. a ground has no authoring path ───────────────────────────────────────

describe('a ground authors no provenance', () => {
    it('makeGround mints nothing that names a run, a step or a producer', () => {
        const g = makeGround('field', { label: 'the drape' });
        expect(g.run_id).toBeUndefined();
        expect(g.step_id).toBeUndefined();
        expect(g.producer).toBeUndefined();
        expect(g.provenance).toBeUndefined();
    });

    it('the region adapter mints nothing either', () => {
        const g = groundFromRegion('reg_1', { label: 'shoulder' });
        expect(g.run_id).toBeUndefined();
        expect(g.step_id).toBeUndefined();
        expect(g.provenance).toBeUndefined();
    });

    it('a ground carries only DERIVED bridge fields, and only once reconciled', () => {
        // Before reconciliation there is nothing to show: a ground with no linked mark has no
        // provenance to assert, and inventing one would be the fabrication this forbids.
        const g = makeGround('field');
        expect(reconcileBridgeFields(g, [])).toBe(g);
    });
});

// ── 2. parity: what the ground shows IS the mark's ──────────────────────────

describe('parity with the source mark', () => {
    it('the derived bridge fields equal the mark they came from', () => {
        const mark = producerMark();
        const ground = makeGround('field');
        mark.linked_ground_ids = [ground.id];

        const shown = reconcileBridgeFields(ground, [mark]);
        expect(shown.mark_id).toBe(mark.id);
        expect(shown.instrument_role).toBe(mark.role);
        expect(shown).toMatchObject(bridgeFieldsFromMark(mark));
    });

    it('the run and the step are reachable ONLY through the mark', () => {
        // The point of the whole decision: the ground names its mark, and the mark names the
        // run and the step. One hop, one source of truth, nothing to drift.
        const mark = producerMark();
        const ground = makeGround('field');
        mark.linked_ground_ids = [ground.id];

        const shown = reconcileBridgeFields(ground, [mark]);
        expect(shown.run_id).toBeUndefined();
        expect(shown.step_id).toBeUndefined();

        const source = [mark].find((m) => m.id === shown.mark_id);
        expect(source.provenance.run_id).toBe('run_7');
        expect(source.provenance.step_id).toBe('s3');
    });

    it('the mark declares step_id even when no producer set one', () => {
        // Seam 2's frontend half: declared, not merely inherited from the spread.
        const curator = makeVisualMark('trace_mark', { role: 'rhythm', geometry: { kind: 'polyline', points: [] } });
        expect('step_id' in curator.provenance).toBe(true);
        expect(curator.provenance.step_id).toBeNull();
    });

    it('bridgeFieldsAgree reports agreement for a reconciled ground', () => {
        const mark = producerMark();
        const ground = makeGround('field');
        mark.linked_ground_ids = [ground.id];
        expect(bridgeFieldsAgree(reconcileBridgeFields(ground, [mark]), [mark])).toBe(true);
    });

    it('and reports DISagreement when a ground carries a stale copy', () => {
        // Non-vacuous: this is the drift that denormalising provenance onto the ground would
        // make routine. It must be detectable, or parity is an untested slogan.
        const mark = producerMark();
        const ground = { ...makeGround('field'), mark_id: 'mk_stale' };
        mark.linked_ground_ids = [ground.id];
        expect(bridgeFieldsAgree(ground, [mark])).toBe(false);
    });
});

// ── 3. supersession — the case parity has to survive ────────────────────────

describe('supersession', () => {
    it('the most recently updated linked mark is the one shown', () => {
        const ground = makeGround('field');
        const older = producerMark({ updated_at: '2026-08-01T00:00:00Z' });
        const newer = producerMark({ updated_at: '2026-08-02T00:00:00Z' });
        older.linked_ground_ids = [ground.id];
        newer.linked_ground_ids = [ground.id];

        const shown = reconcileBridgeFields(ground, [older, newer]);
        expect(shown.mark_id).toBe(newer.id);
        // A ground that had authored its own run_id would still be pointing at `older` here —
        // which is exactly the failure the one-source-of-truth rule avoids.
    });
});
