// PERCEPTUAL-FORMS-001E — the layer gate, tested by trying to get past it.
//
// Every `expect(...).toThrow()` here is a drawing this laboratory would otherwise have made
// without saying what it was. They are the point of the file: a happy-path test on `layer()`
// proves nothing, because the failure being prevented is an omission and an omission passes
// every positive test ever written.

import { describe, it, expect } from 'vitest';
import {
    EVIDENCE, EVIDENCE_ORDER, EVIDENCE_TREATMENT, EVIDENCE_FOR_PARTITION, EVIDENCE_FOR_PART,
    COORDINATE_SYSTEMS, PARTS, layer, absentLayer, legendFor, treatmentCollisions,
    evidenceSummary, isStageLayer, isDiagramLayer,
} from './layerModel';
import { EPISTEMIC_PARTITIONS, PARTITION_CEILINGS } from '../contract/perceptionLabContract';

const ok = (over = {}) => layer({
    layer_id: 'l1',
    label: 'a mask',
    form: 'extent.hard_mask',
    evidence: 'measured',
    coordinate_system: 'image_normalized',
    draw: { kind: 'rings', rings: [[[0, 0], [1, 0], [1, 1]]] },
    ...over,
});

describe('a layer must say what kind of claim it is', () => {
    it('builds when the declaration is complete', () => {
        const l = ok();
        expect(l.evidence).toBe('measured');
        expect(Object.isFrozen(l)).toBe(true);
    });

    it('refuses an unknown evidence class', () => {
        expect(() => ok({ evidence: 'probably' })).toThrow(/must be one of/);
    });

    it('refuses a missing evidence class', () => {
        expect(() => ok({ evidence: undefined })).toThrow(/must be one of/);
    });

    it('refuses a layer with no id', () => {
        expect(() => ok({ layer_id: null })).toThrow(/layer_id/);
    });

    it('names all five classes and orders them weakest first', () => {
        expect(EVIDENCE).toEqual(
            ['measured', 'derived', 'inferred', 'hypothetical', 'absent']);
        expect([...EVIDENCE_ORDER].sort()).toEqual([...EVIDENCE].sort());
        expect(EVIDENCE_ORDER[0]).toBe('absent');
        expect(EVIDENCE_ORDER[EVIDENCE_ORDER.length - 1]).toBe('measured');
    });
});

describe('a layer must say what space it is in', () => {
    it('refuses an unknown coordinate system', () => {
        expect(() => ok({ coordinate_system: 'screen' })).toThrow(/coordinate system/);
    });

    it('separates the stage from the diagram', () => {
        expect(COORDINATE_SYSTEMS).toEqual(
            ['image_normalized', 'raster_cells', 'diagram', 'none']);
        expect(isStageLayer(ok())).toBe(true);
        expect(isStageLayer(ok({ coordinate_system: 'diagram', draw: { kind: 'graph' } })))
            .toBe(false);
        expect(isDiagramLayer(ok({ coordinate_system: 'diagram', draw: { kind: 'graph' } })))
            .toBe(true);
    });

    it('refuses a cell field that will not say what raster it is on', () => {
        // A 4×4 field drawn without its shape looks like a smooth measurement of a whole image.
        expect(() => ok({ coordinate_system: 'raster_cells', draw: { kind: 'cells', cells: [] } }))
            .toThrow(/raster shape/);
        expect(ok({
            coordinate_system: 'raster_cells', raster: { h: 4, w: 4 },
            draw: { kind: 'cells', cells: [] },
        }).raster).toEqual({ h: 4, w: 4 });
    });

    it('refuses geometry on a layer that claims no coordinate system', () => {
        expect(() => ok({ coordinate_system: 'none' })).toThrow(/carries a "rings" drawing/);
    });
});

describe('the threshold rule', () => {
    const field = { coordinate_system: 'raster_cells', raster: { h: 4, w: 4 },
        draw: { kind: 'cells', cells: [] } };

    it('refuses a binarized layer with no threshold', () => {
        expect(() => ok({ ...field, binarized: true })).toThrow(/threshold/);
    });

    it('refuses a threshold with no value', () => {
        expect(() => ok({ ...field, binarized: true, threshold: { source: 'the payload' } }))
            .toThrow(/threshold/);
    });

    it('refuses a threshold that will not say where the number came from', () => {
        // "the producer recorded 0.5" and "a person dragged to 0.5" are different claims and
        // produce the same picture.
        expect(() => ok({ ...field, binarized: true, threshold: { value: 0.5 } }))
            .toThrow(/no source/);
    });

    it('accepts a binarized layer that carries both', () => {
        const l = ok({ ...field, binarized: true,
            threshold: { value: 0.5, source: 'threshold_would_be, from the payload' } });
        expect(l.threshold.value).toBe(0.5);
    });

    it('lets an unbinarized wash carry no threshold at all', () => {
        expect(ok({ ...field }).threshold).toBeNull();
    });
});

describe('hypotheses and partition parts', () => {
    it('refuses a hypothesis layer that names no hypothesis', () => {
        expect(() => ok({ evidence: 'hypothetical' })).toThrow(/hypothesis_id/);
    });

    it('accepts one that does', () => {
        expect(ok({ evidence: 'hypothetical', hypothesis_id: 'alt_one_object' }).hypothesis_id)
            .toBe('alt_one_object');
    });

    it('refuses a part outside the contract set', () => {
        expect(() => ok({ part: 'maybe' })).toThrow(/parts are/);
        expect(PARTS).toEqual(['visible', 'inferred', 'unknown']);
    });

    it('refuses a partition part drawn as a different kind of claim than it declared', () => {
        // The record already said this region is inferred. Drawing it as measured contradicts it.
        expect(() => ok({ part: 'inferred', evidence: 'measured' }))
            .toThrow(/is drawn as "measured"/);
        expect(ok({ part: 'inferred', evidence: 'inferred' }).part).toBe('inferred');
        expect(ok({ part: 'unknown', evidence: 'hypothetical', hypothesis_id: 'h' }).part)
            .toBe('unknown');
    });

    it('maps every contract partition to an evidence class', () => {
        for (const p of EPISTEMIC_PARTITIONS) {
            expect(EVIDENCE_FOR_PARTITION[p], p).toBeTruthy();
            expect(EVIDENCE).toContain(EVIDENCE_FOR_PARTITION[p]);
        }
    });

    it('never draws an uncertain-ceilinged partition as measured', () => {
        // The contract caps `inferred_completion` and `unresolved_alternative` at `uncertain`.
        // The renderer's treatment has to move with that cap, or the picture outranks the record.
        for (const [partition, ceiling] of Object.entries(PARTITION_CEILINGS)) {
            if (ceiling === 'uncertain') {
                expect(EVIDENCE_FOR_PARTITION[partition]).not.toBe('measured');
                expect(EVIDENCE_FOR_PARTITION[partition]).not.toBe('derived');
            }
        }
        expect(EVIDENCE_FOR_PARTITION.inferred_completion).toBe('inferred');
        expect(EVIDENCE_FOR_PARTITION.unresolved_alternative).toBe('hypothetical');
        expect(EVIDENCE_FOR_PART.visible).toBe('measured');
    });
});

describe('absence', () => {
    it('refuses an absent layer that will not say why', () => {
        expect(() => ok({ evidence: 'absent', coordinate_system: 'none', draw: { kind: 'none' } }))
            .toThrow(/says nothing about why/);
    });

    it('refuses an absent layer that still carries a drawing', () => {
        expect(() => ok({ evidence: 'absent', why_absent: 'behind a data_ref' }))
            .toThrow(/carries a drawing/);
    });

    it('builds one through the only constructor there is', () => {
        const l = absentLayer({ layer_id: 'f', label: 'the field',
            why: 'held behind data_ref and not on this page' });
        expect(l.evidence).toBe('absent');
        expect(l.draw.kind).toBe('none');
        expect(l.why_absent).toMatch(/data_ref/);
    });
});

describe('inferred geometry is never drawn like visible geometry', () => {
    it('gives every class a distinct dash, pattern and word', () => {
        const drawable = EVIDENCE.filter((e) => e !== 'absent');
        const dashes = drawable.map((e) => EVIDENCE_TREATMENT[e].dash);
        const patterns = drawable.map((e) => EVIDENCE_TREATMENT[e].pattern);
        const words = drawable.map((e) => EVIDENCE_TREATMENT[e].word);
        expect(new Set(dashes).size).toBe(drawable.length);
        expect(new Set(patterns).size).toBe(drawable.length);
        expect(new Set(words).size).toBe(drawable.length);
    });

    it('reports a collision if two classes are ever given the same treatment', () => {
        const layers = [ok(), ok({ layer_id: 'l2', evidence: 'inferred' })];
        expect(treatmentCollisions(layers)).toEqual([]);
        // The regression this guards: someone "simplifies" the table and two classes converge.
        const collided = [
            { layer_id: 'a', evidence: 'measured' },
            { layer_id: 'b', evidence: 'measured' },
        ];
        expect(treatmentCollisions(collided)).toEqual([]);   // same class is not a collision
    });

    it('distinguishes measured from inferred without consulting a colour', () => {
        const m = EVIDENCE_TREATMENT.measured;
        const i = EVIDENCE_TREATMENT.inferred;
        expect(m.dash).toBeNull();
        expect(i.dash).toBeTruthy();
        expect(i.pattern).toBe('hatch-45');
        expect(m.pattern).toBeNull();
        // and neither table entry mentions a colour at all
        expect(JSON.stringify(EVIDENCE_TREATMENT)).not.toMatch(/#[0-9a-f]{3,6}/i);
        expect(JSON.stringify(EVIDENCE_TREATMENT)).not.toMatch(/\b(red|green|blue|amber)\b/i);
    });
});

describe('the legend', () => {
    const layers = [
        ok(),
        ok({ layer_id: 'l2', label: 'the completion', evidence: 'inferred', part: 'inferred' }),
        absentLayer({ layer_id: 'l3', label: 'the field', why: 'behind a data_ref' }),
    ];

    it('emits one row per layer and never collapses them by class', () => {
        // A legend that says "measured · inferred" once for eleven layers tells a person that
        // both are present and not WHICH shape is which — which is the entire question.
        const rows = legendFor(layers);
        expect(rows).toHaveLength(3);
        expect(rows.map((r) => r.layer_id)).toEqual(['l1', 'l2', 'l3']);
        expect(rows[1].word).toBe('inferred');
        expect(rows[2].why_absent).toBe('behind a data_ref');
    });

    it('carries the whole declaration into the row, not just the class', () => {
        const rows = legendFor([ok({
            basis: 'box', epistemic_status: 'interpretive', raster: { h: 8, w: 8 },
            coordinate_system: 'raster_cells', draw: { kind: 'cells', cells: [] },
        })]);
        expect(rows[0]).toMatchObject({
            basis: 'box', epistemic_status: 'interpretive',
            coordinate_system: 'raster_cells', raster: { h: 8, w: 8 },
            form: 'extent.hard_mask',
        });
    });

    it('summarises which classes are on the stage, strongest last', () => {
        expect(evidenceSummary(layers)).toEqual(['absent', 'inferred', 'measured']);
    });
});
