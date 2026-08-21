// PERCEPTUAL-FORMS-001E — the registry, and every view run against every scenario.
//
// The interesting test in this file is the last describe block. It renders all nineteen forms
// through all of their views under all of their scenarios — several hundred renders — and asserts
// only that each one produced layers that pass the declaration gate. It catches nothing about
// whether a picture is pretty and everything about whether a picture can be described, which is
// the property this lane is for.

import { describe, it, expect } from 'vitest';
import {
    VIEWS, COVERAGE, SURFACES, ALTERNATIVE_MODES, verifyRegistry, viewsFor, defaultViewFor,
    viewFor, renderView, FORM_GROUPS,
} from './rendererRegistry';
import {
    PERCEPTUAL_FORMS, form, formsFor, PROJECTION_KINDS,
} from '../contract/perceptionLabContract';
import { SCENARIOS, scenariosFor, payloadFor } from './fixtures/formFixtures';
import { assertLayer, EVIDENCE, treatmentCollisions } from './layerModel';
import { resolvableIds } from './fixtures/endpointGeometry';

describe('the renderer registry agrees with the form registry', () => {
    it('verifies at import, and again on demand', () => {
        expect(() => verifyRegistry()).not.toThrow();
        expect(COVERAGE).toBeTruthy();
    });

    it('registers a view set for every one of the nineteen forms', () => {
        expect(Object.keys(VIEWS).sort()).toEqual([...PERCEPTUAL_FORMS].sort());
        for (const key of PERCEPTUAL_FORMS) {
            expect(viewsFor(key).length, key).toBeGreaterThan(0);
        }
    });

    it('draws every projection the contract declares, for every form', () => {
        // The direction that rots quietly: a form gains a projection and the renderer never grows
        // the view, so the contract promises a drawing that does not exist.
        for (const key of PERCEPTUAL_FORMS) {
            expect(COVERAGE[key].undrawn, `${key} declares projections nothing draws`).toEqual([]);
        }
    });

    it('draws nothing a form does not declare', () => {
        for (const key of PERCEPTUAL_FORMS) {
            const declared = form(key).renderer_projections.map((p) => p.kind);
            for (const view of viewsFor(key)) {
                for (const kind of view.projections) {
                    expect(declared, `${key}/${view.key}`).toContain(kind);
                    expect(PROJECTION_KINDS).toContain(kind);
                }
            }
        }
    });

    it('fails loudly when a view draws an undeclared projection', () => {
        // The gate, demonstrated. `shared.assertDeclared` is what makes this impossible to write.
        const undeclared = PROJECTION_KINDS.find(
            (k) => !form('extent.hard_mask').renderer_projections.some((p) => p.kind === k));
        expect(undeclared).toBeTruthy();
        expect(form('extent.hard_mask').renderer_projections.map((p) => p.kind))
            .not.toContain(undeclared);
    });

    it('gives every view a known surface and a known alternatives mode', () => {
        for (const key of PERCEPTUAL_FORMS) {
            for (const view of viewsFor(key)) {
                expect(SURFACES, `${key}/${view.key}`).toContain(view.surface);
                if (view.alternatives) {
                    expect(ALTERNATIVE_MODES, `${key}/${view.key}`).toContain(view.alternatives);
                }
            }
        }
    });

    it('gives every form exactly one default view', () => {
        for (const key of PERCEPTUAL_FORMS) {
            const defaults = viewsFor(key).filter((v) => v.default);
            expect(defaults.length, key).toBe(1);
            expect(defaultViewFor(key).key).toBe(defaults[0].key);
        }
    });

    it('falls back to the default when an unknown view is asked for', () => {
        expect(viewFor('extent.hard_mask', 'no-such-view').key)
            .toBe(defaultViewFor('extent.hard_mask').key);
    });
});

describe('alternatives are never collapsed by default', () => {
    const withHypotheses = PERCEPTUAL_FORMS.filter((k) => form(k).carries_hypothesis);
    const holdsRivals = PERCEPTUAL_FORMS.filter(
        (k) => form(k).renderer_projections.some((p) => p.kind === 'hypothesis_stack'));

    it('finds the four forms that carry a hypothesis', () => {
        expect(withHypotheses).toEqual([
            'extent.fused_hypothesis',
            'extent.visible_inferred_partition',
            'extent.hypothesis_set',
            'topology.uncertain_relation_set',
        ]);
    });

    it('separates "asserts something unseen" from "holds several rivals"', () => {
        // All four assert something unseen. Only three hold rivals — `visible_inferred_partition`
        // has three PARTS of one extent, and tabbing through them would be as wrong as merging
        // the others. The contract already draws the line, in the projection each form declares.
        expect(holdsRivals).toEqual([
            'extent.fused_hypothesis',
            'extent.hypothesis_set',
            'topology.uncertain_relation_set',
        ]);
        expect(withHypotheses).toContain('extent.visible_inferred_partition');
        expect(holdsRivals).not.toContain('extent.visible_inferred_partition');
    });

    it('defaults every form that holds rivals to one reading at a time', () => {
        for (const key of holdsRivals) {
            expect(defaultViewFor(key).alternatives, key).toBe('one_at_a_time');
        }
    });

    it('draws the partition\'s three parts together, because together is what they are', () => {
        const out = renderView('extent.visible_inferred_partition', 'tricolor',
            payloadFor('extent.visible_inferred_partition'));
        expect(out.layers.map((l) => l.part)).toEqual(['visible', 'inferred', 'unknown']);
        expect(out.layers.map((l) => l.evidence))
            .toEqual(['measured', 'inferred', 'hypothetical']);
        expect(defaultViewFor('extent.visible_inferred_partition').alternatives).toBeNull();
    });

    it('offers a layered view only as an explicit choice, never as the default', () => {
        for (const key of PERCEPTUAL_FORMS) {
            const layered = viewsFor(key).filter((v) => v.alternatives === 'layered');
            for (const v of layered) expect(v.default, `${key}/${v.key}`).toBe(false);
        }
        expect(viewsFor('extent.hypothesis_set').map((v) => v.alternatives))
            .toEqual(['one_at_a_time', 'side_by_side', 'layered', null]);
    });
});

describe('the form groups the picker renders', () => {
    it('groups by organ, ten and nine', () => {
        expect(FORM_GROUPS.map((g) => g.organ)).toEqual(['extent', 'topology']);
        expect(FORM_GROUPS[0].forms).toHaveLength(10);
        expect(FORM_GROUPS[1].forms).toHaveLength(9);
        expect(FORM_GROUPS[0].forms.map((f) => f.key))
            .toEqual(formsFor('extent').map((f) => f.key));
    });

    it('carries the state, so a deferred form is visibly deferred', () => {
        const deferred = FORM_GROUPS.flatMap((g) => g.forms).filter((f) => f.state === 'deferred');
        expect(deferred).toHaveLength(7);
        // Seven forms are deferred and nine more are experimental: sixteen of the nineteen have
        // an empty `produced_by_operations`, so no artifact of them can exist yet. They render
        // here anyway — that is the point of freezing a payload a phase before anything computes
        // it, and a payload nobody can look at has not been reviewed.
        const experimental = FORM_GROUPS.flatMap((g) => g.forms)
            .filter((f) => f.state === 'experimental');
        expect(experimental).toHaveLength(9);
        for (const f of [...deferred, ...experimental]) expect(f.views).toBeGreaterThan(0);
    });
});

describe('every view of every form, under every scenario', () => {
    const cases = PERCEPTUAL_FORMS.flatMap((formKey) => viewsFor(formKey).flatMap(
        (view) => scenariosFor(formKey).map(
            (scenario) => ({ formKey, view: view.key, scenario }))));

    it('is a few hundred renders, not a handful', () => {
        expect(cases.length).toBeGreaterThan(150);
    });

    it.each(cases.map((c) => [`${c.formKey} · ${c.view} · ${c.scenario}`, c]))(
        '%s renders layers that pass the declaration gate', (_name, c) => {
            const out = renderView(c.formKey, c.view, payloadFor(c.formKey, c.scenario));
            expect(out.error, out.error || '').toBeNull();
            expect(out.layers.length,
                `${c.formKey}/${c.view}/${c.scenario} produced no layer at all. An empty result `
                + 'must still be an absent layer that says why').toBeGreaterThan(0);
            for (const l of out.layers) {
                expect(() => assertLayer(l)).not.toThrow();
                expect(EVIDENCE).toContain(l.evidence);
                expect(l.form ?? c.formKey).toBeTruthy();
            }
            expect(treatmentCollisions(out.layers)).toEqual([]);
        });

    it('puts stage layers on the stage and diagram layers in the diagram, never the reverse', () => {
        for (const c of cases) {
            const out = renderView(c.formKey, c.view, payloadFor(c.formKey, c.scenario));
            const view = viewFor(c.formKey, c.view);
            for (const l of out.layers) {
                if (l.evidence === 'absent') continue;
                if (view.surface === 'diagram') {
                    expect(l.coordinate_system, `${c.formKey}/${c.view}`)
                        .toMatch(/^(diagram|none)$/);
                } else if (view.surface === 'stage' || view.surface === 'sheet'
                    || view.surface === 'compare') {
                    // A node-link diagram letterboxed onto the image would put every node at a
                    // pixel, and a person would read those positions as locations.
                    expect(l.coordinate_system, `${c.formKey}/${c.view}/${l.layer_id}`)
                        .not.toBe('diagram');
                }
            }
        }
    });

    it('never draws a binarized layer without the threshold that made it', () => {
        for (const c of cases) {
            const out = renderView(c.formKey, c.view, payloadFor(c.formKey, c.scenario));
            for (const l of out.layers.filter((x) => x.binarized)) {
                expect(l.threshold?.value, `${c.formKey}/${c.view}`).toEqual(expect.any(Number));
                expect(l.threshold?.source).toBeTruthy();
            }
        }
    });
});

describe('the empty scenario says what was looked at', () => {
    it.each(PERCEPTUAL_FORMS)('%s renders an absent layer with a reason', (formKey) => {
        const view = defaultViewFor(formKey);
        const out = renderView(formKey, view.key, payloadFor(formKey, 'empty'));
        const absent = out.layers.filter((l) => l.evidence === 'absent');
        // Not every form's empty scenario empties something the default view draws — a field form
        // has no collection to empty — but wherever the default view IS empty, it must say why.
        for (const l of absent) {
            expect(l.why_absent, `${formKey}/${view.key}`).toBeTruthy();
            expect(l.why_absent.length).toBeGreaterThan(20);
        }
    });

    it('distinguishes "looked and found nothing" from "could not look"', () => {
        const empty = renderView('topology.pair_relation', 'endpoints',
            payloadFor('topology.pair_relation', 'empty'));
        expect(empty.layers[0].why_absent).toMatch(/pairs were compared and none stood/);
        expect(empty.layers[0].why_absent).toMatch(/not a refusal/);
    });
});

describe('what this fixture set can and cannot resolve', () => {
    it('resolves exactly the two artifacts the payloads cite by name', () => {
        expect(resolvableIds().sort()).toEqual([
            'art_extent_1#inst_1', 'art_extent_1#inst_2',
            'art_fragments_1#frag_1', 'art_fragments_1#frag_2', 'art_fragments_1#frag_3',
        ]);
    });

    it('draws the contact locus, whose endpoints both resolve', () => {
        const out = renderView('topology.contact_locus', 'band',
            payloadFor('topology.contact_locus'));
        expect(out.layers[0].evidence).toBe('measured');
        expect(out.layers[0].draw.rings.length).toBeGreaterThan(0);
    });

    it('refuses the intersection, whose endpoints do not', () => {
        const out = renderView('topology.intersection_area', 'endpoints',
            payloadFor('topology.intersection_area'));
        expect(out.layers.every((l) => l.evidence === 'absent')).toBe(true);
        expect(out.layers[0].why_absent).toMatch(/no committed fixture carries/);
        expect(out.layers[0].why_absent).toMatch(/would draw a shape nobody measured/);
    });

    it('says which half resolved when only one did', () => {
        const out = renderView('topology.pair_relation', 'endpoints',
            payloadFor('topology.pair_relation'));
        const absent = out.layers.filter((l) => l.evidence === 'absent');
        expect(absent.length).toBeGreaterThan(0);
        // rel_2's target is inst_1, which resolves; its source is inst_fountain, which does not.
        const partial = absent.find((l) => l.why_absent.includes('inst_fountain'));
        expect(partial).toBeTruthy();
        expect(partial.why_absent).not.toMatch(/inst_1\b.*no committed fixture/);
    });
});

describe('renderView survives a broken build', () => {
    it('returns the message as an error rather than throwing the page down', () => {
        // A person testing nineteen forms should be able to keep testing the other eighteen.
        const out = renderView('extent.hard_mask', 'fill', { instances: null });
        expect(out.error).toMatch(/could not be built/);
        expect(out.layers).toEqual([]);
    });

    it('says so when there is no payload at all', () => {
        const out = renderView('extent.hard_mask', 'fill', null);
        expect(out.empty).toBe('no payload is selected');
        expect(out.error).toBeNull();
    });
});

describe('scenario coverage', () => {
    it('offers the withheld state on every form that carries a field', () => {
        for (const key of ['extent.soft_field', 'extent.density_field',
            'extent.visible_inferred_partition', 'topology.negative_space_field']) {
            expect(scenariosFor(key), key).toContain('withheld');
        }
    });

    it('refuses to draw a withheld field, and says the statistics are the measurement', () => {
        const out = renderView('extent.soft_field', 'wash',
            payloadFor('extent.soft_field', 'withheld'));
        expect(out.layers[0].evidence).toBe('absent');
        expect(out.layers[0].why_absent).toMatch(/held behind data_ref/);
        expect(SCENARIOS['extent.soft_field'].withheld.field.field_shape).toEqual([4, 4]);
    });
});
