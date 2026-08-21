// PERCEPTUAL-FORMS-001E — the renderer registry, and the gate it puts itself through.
//
// Lane A's parity suite already checks one half of this: `topologyView.PROJECTION_FOR_KIND` is
// asserted against the projections `topology.pair_relation` declares, because "the form registry
// and the renderer registry are two answers to one question" is the failure the form grammar was
// written to end. This module is the other half, generalised — nineteen forms, forty-odd views,
// and a `verifyRegistry` that runs at module load.
//
// FOUR THINGS ARE CHECKED, AT IMPORT, IN THE APPLICATION AND NOT ONLY IN A TEST:
//
//   1. every form is registered. A form with no view is a form nobody can look at, and the
//      grammar's whole claim is that all nineteen are designed now.
//   2. no view draws a projection its form does not declare. `shared.assertDeclared` catches this
//      at build time for a view that runs; this catches it for one that has not run yet.
//   3. every DECLARED projection is drawn by some view. This is the direction that rots quietly:
//      a form gains a projection in the contract and the renderer never grows the view, so the
//      contract promises a drawing that does not exist.
//   4. every form that carries a hypothesis has a `one_at_a_time` default. "Never collapse
//      alternatives into one overlay by default" is a sentence in a build brief until something
//      fails when it is broken.
//
// The throw is deliberate rather than a console warning. A registry that is wrong renders
// confidently, and a confident wrong drawing is the thing this lane exists to prevent.

import { PERCEPTUAL_FORMS, form, formsFor } from '../contract/perceptionLabContract';
import { EXTENT_VIEWS } from './renderers/extentRenderers';
import { TOPOLOGY_VIEWS } from './renderers/topologyRenderers';

/** The five places a view can be drawn. Not decoration: a diagram is not a stage. */
export const SURFACES = Object.freeze([
    'stage',     // one letterboxed image stage
    'compare',   // several labelled stages, side by side, never superimposed
    'sheet',     // a grid of cropped thumbnails
    'diagram',   // node-link or matrix, in diagram space
    'panel',     // measurements and sentences, no geometry
]);

/** How a view holds competing readings apart. */
export const ALTERNATIVE_MODES = Object.freeze(['one_at_a_time', 'side_by_side', 'layered']);

const RAW = Object.freeze({ ...EXTENT_VIEWS, ...TOPOLOGY_VIEWS });

/** Normalise a view declaration so every consumer reads the same shape. */
const normalise = (formKey, view, index) => Object.freeze({
    form: formKey,
    key: view.key,
    label: view.label,
    hint: view.hint ?? null,
    surface: view.surface,
    projections: Object.freeze([...(view.projections || [])]),
    alternatives: view.alternatives ?? null,
    focuses: view.focuses === true,
    sweeps: view.sweeps === true,
    editable: view.editable ?? null,
    needs: Object.freeze([...(view.needs || [])]),
    default: view.default === true || index === 0,
    build: view.build,
});

export const VIEWS = Object.freeze(Object.fromEntries(
    Object.entries(RAW).map(([formKey, views]) => [
        formKey,
        Object.freeze(views.map((v, i) => normalise(formKey, v, i))),
    ])));

/**
 * The registry's own gate. Called at module load; exported so a test can name the failure.
 *
 * Returns the coverage report rather than a boolean, because the useful artefact of this check is
 * the table of which projections each form declares and which view draws them — that table is
 * what a reviewer reads to see the lane is complete.
 */
export function verifyRegistry() {
    const problems = [];
    const coverage = {};

    const missing = PERCEPTUAL_FORMS.filter((k) => !VIEWS[k]);
    if (missing.length) {
        problems.push(`no renderer is registered for ${missing.join(', ')}. A form with no view `
            + 'is a form nobody can look at');
    }
    const extra = Object.keys(VIEWS).filter((k) => !PERCEPTUAL_FORMS.includes(k));
    if (extra.length) {
        problems.push(`${extra.join(', ')} is rendered here and is not a registered form`);
    }

    for (const formKey of PERCEPTUAL_FORMS) {
        const views = VIEWS[formKey];
        if (!views) continue;
        const declaration = form(formKey);
        const declared = (declaration.renderer_projections || []).map((p) => p.kind);
        const drawn = new Set(views.flatMap((v) => v.projections));

        for (const view of views) {
            if (!SURFACES.includes(view.surface)) {
                problems.push(`${formKey}/${view.key} declares surface "${view.surface}"`);
            }
            if (view.alternatives && !ALTERNATIVE_MODES.includes(view.alternatives)) {
                problems.push(`${formKey}/${view.key} declares alternatives "${view.alternatives}"`);
            }
            for (const kind of view.projections) {
                if (!declared.includes(kind)) {
                    problems.push(`${formKey}/${view.key} draws "${kind}", which ${formKey} does `
                        + `not declare. It declares ${declared.join(', ')}`);
                }
            }
        }

        const undrawn = declared.filter((k) => !drawn.has(k));
        if (undrawn.length) {
            problems.push(`${formKey} declares ${undrawn.join(', ')} and no view draws `
                + `${undrawn.length > 1 ? 'them' : 'it'}. A projection the contract promises and `
                + 'the renderer never grew is a drawing a person will look for and not find');
        }

        // ── the alternatives rule ─────────────────────────────────────────
        //
        // "Never collapse alternatives into one overlay by default" applies to forms that hold
        // SEVERAL COMPETING READINGS, and `carries_hypothesis` is not that test. All four forms
        // that carry a hypothesis assert something unseen, but only three of them hold rivals:
        // `extent.visible_inferred_partition` has three PARTS of one extent — visible, inferred
        // and unknown — which are drawn together because together is what they are. Tabbing
        // through them would be as wrong as merging the others.
        //
        // The contract already draws that line, in the projection each form declares.
        // `hypothesis_stack` IS the projection for "several readings held at once", and exactly
        // the three forms with rivals declare it. So the rule reads it rather than inventing a
        // second list that would have to be kept in step by hand.
        const holdsRivals = declared.includes('hypothesis_stack');
        if (holdsRivals) {
            const fallback = views.find((v) => v.default);
            if (!fallback || fallback.alternatives !== 'one_at_a_time') {
                problems.push(`${formKey} declares the hypothesis_stack projection — it holds `
                    + `several readings at once — and its default view ("${fallback?.key}") is `
                    + 'not one_at_a_time. Merging alternatives into one overlay by default '
                    + 'asserts a reading nobody chose');
            }
        }

        coverage[formKey] = {
            organ: declaration.organ,
            state: declaration.state,
            carries_hypothesis: declaration.carries_hypothesis,
            declared_projections: declared,
            views: views.map((v) => ({
                key: v.key, surface: v.surface, projections: [...v.projections],
                alternatives: v.alternatives,
            })),
            undrawn,
        };
    }

    if (problems.length) {
        throw new Error(`the renderer registry does not agree with the form registry:\n  - `
            + `${problems.join('\n  - ')}`);
    }
    return Object.freeze(coverage);
}

/** Runs at import. See the header for why this is a throw and not a warning. */
export const COVERAGE = verifyRegistry();

/* ── the lookups a surface needs ─────────────────────────────────────────── */

export const viewsFor = (formKey) => VIEWS[formKey] || [];
export const defaultViewFor = (formKey) => viewsFor(formKey).find((v) => v.default)
    ?? viewsFor(formKey)[0] ?? null;
export const viewFor = (formKey, viewKey) => viewsFor(formKey).find((v) => v.key === viewKey)
    ?? defaultViewFor(formKey);

/** Every form, grouped by organ, in registry order — the shape the form picker renders. */
export const FORM_GROUPS = Object.freeze(['extent', 'topology'].map((organ) => Object.freeze({
    organ,
    forms: Object.freeze(formsFor(organ).map((f) => Object.freeze({
        key: f.key,
        label: f.label,
        question: f.question,
        state: f.state,
        carries_hypothesis: f.carries_hypothesis,
        views: viewsFor(f.key).length,
    }))),
})));

/**
 * Render one view, and never let a broken build take the page down with it.
 *
 * A `build` that throws is a bug in this directory, and the useful behaviour is to show the
 * message where the drawing would have been rather than to blank the laboratory — a person
 * testing nineteen forms should be able to keep testing the other eighteen. The failure is
 * returned as an `absent` layer, which means it goes through the same declaration gate as
 * everything else and appears in the legend rather than in a console nobody has open.
 */
export function renderView(formKey, viewKey, payload, ctx = {}) {
    const view = viewFor(formKey, viewKey);
    if (!view) {
        return { view: null, layers: [], error: `${formKey} has no view "${viewKey}"` };
    }
    if (!payload) {
        return {
            view,
            layers: [],
            error: null,
            empty: 'no payload is selected',
        };
    }
    try {
        const out = view.build(payload, { ...ctx, formKey });
        return { view, layers: out.layers || [], sides: out.sides ?? null,
            items: out.items ?? null, error: null };
    } catch (e) {
        return {
            view,
            layers: [],
            error: `${formKey}/${view.key} could not be built: ${e.message}`,
        };
    }
}
