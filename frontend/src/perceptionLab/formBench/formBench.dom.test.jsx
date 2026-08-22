/**
 * PERCEPTUAL-FORMS-001H — the two lower levels, driven the way a person drives them.
 *
 * THE THREE LEVELS ARE VISIBLY DISTINCT, and this file is where that stops being a claim. Direct
 * form, deterministic recipe and prompt proposal are three arms with three consequences printed
 * beside the switch, and a person can tell which one they are in without reading a plan.
 *
 * WHAT EACH TEST IS ABOUT:
 *
 *   the producer      model / code / human, the checkpoint, the revision — and for one that is
 *                     not running, WHY and what would change it
 *   the absence       a form nothing can write says which of the three absences it is
 *   two drawings      the panes are side by side and never superimposed
 *   the threshold     every scalar that decides what is drawn is printed beside the drawing
 *   the hypothesis    no control on either panel accepts one
 *   the study         every step stays on screen, and readiness is shown before anything is spent
 *
 * The client here is a stub, not the fixture client: these panels read routes the fixture wire
 * does not serve, and a stub is the honest way to drive them without inventing a second backend.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import FormBench from './FormBench';
import { thresholdsOf } from './thresholds';
import RecipeTray from './RecipeTray';
import ModeControls from '../components/ModeControls';
import { ARM_CONSEQUENCE } from '../components/armConsequence';
import { FORM_CLIENT_METHODS, missingFormMethods, supportsForms } from './formClient';

// `FormStage` measures its own container through `useStageGeometry`, which observes it. jsdom
// has no ResizeObserver, and the existing lab suites stub it the same way for the same reason.
if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => { await act(async () => { await Promise.resolve(); }); };

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
});

const text = () => container.textContent;
const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const byText = (sel, needle) => all(sel).find((el) => el.textContent.includes(needle));
const click = async (el) => {
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};
const choose = async (el, value) => {
    await act(async () => {
        Object.getOwnPropertyDescriptor(window.HTMLSelectElement.prototype, 'value')
            .set.call(el, value);
        el.dispatchEvent(new Event('change', { bubbles: true }));
    });
    await settle();
};

const RINGS = {
    form: 'extent.boundary_rings',
    label: 'Boundary rings',
    question: 'Where exactly does its edge run, as curves rather than pixels?',
    organ: 'extent',
    state: 'experimental',
    producible: true,
    writable_as_artifact: false,
    can_be_produced_here: true,
    blocked_by: ['no_operation'],
    note: 'no operation declares this form, so no artifact of it can exist.',
    producers: [{
        key: 'perception_lab.extent_forms.boundary_rings', kind: 'code',
        label: 'exact derivation — boundary_rings', state: 'available',
        model: null, revision: 'extent-exact-forms.v1', reason: null, remedy: null,
        admission: null,
    }],
    renderer_projections: [{ kind: 'ring_outline', mode: 'direct', note: '' }],
    accepted_input_forms: ['extent.hard_mask'],
    absence: { examined_field: 'rings_traced', empty_means: 'the mask was traced' },
    epistemic_ceiling: 'measured',
    carries_hypothesis: false,
};

const SOFT = {
    ...RINGS,
    form: 'extent.soft_field',
    label: 'Soft field',
    question: 'How much of it is here, where the edge is not a line?',
    state: 'deferred',
    producible: false,
    can_be_produced_here: false,
    blocked_by: ['deferred_form', 'no_operation', 'capability_unavailable'],
    note: 'registered and deferred.',
    producers: [{
        key: 'vitmatte_small', kind: 'model', label: 'ViTMatte small', state: 'unavailable',
        model: 'hustvl/vitmatte-small-composition-1k', revision: null,
        reason: 'the runtime does not import: ModuleNotFoundError',
        remedy: 'install the ML stack here', admission: 'adopt_as_experimental',
    }, {
        key: 'sam3_concept', kind: 'model', label: 'SAM 3', state: 'unavailable',
        model: 'facebook/sam3', revision: 'sam3-pcs-v1',
        reason: 'SAM3_WEIGHTS is unset. The checkpoint is never discovered from a hub cache.',
        remedy: 'export SAM3_WEIGHTS=/absolute/path/to/sam3.pt', admission: null,
    }],
    accepted_input_forms: ['extent.hard_mask'],
};

const RINGS_PAYLOAD = {
    variant: 'extent_boundary', rings_traced: 1,
    boundaries: [{
        of: { artifact_id: 'art_1', instance_id: 'inst_1' },
        raster_shape: [8, 8],
        rings: [{ ring_id: 'ring_a', winding: 'outer', closed: true, length: null,
            points: [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]] }],
    }],
};

const DERIVATION = {
    derivation_id: 'der_1', session_id: 'labs_1', form: 'extent.boundary_rings',
    organ: 'extent', payload_variant: 'extent_boundary', payload: RINGS_PAYLOAD,
    producible: true, writable_as_artifact: false, ceiling: 'measured', basis: 'mask',
    partition: 'exact_derivation', producer: 'perception_lab.extent_forms.boundary_rings',
    producer_kind: 'code', producer_revision: 'extent-exact-forms.v1',
    source_image_digest: 'sha256:00112233', input_artifact_ids: ['art_1'],
    parameters: {}, dropped_parameters: [], refusals: [],
    omitted: [{ what: 'art_1#inst_2', reason: 'part_not_supplied',
        detail: 'a box-only instance has no mask to derive from' }],
    measurements: {}, created_at: '2026-08-22T09:00:00Z',
};

const LEDGER = [{
    identity: { artifact_id: 'art_1', artifact_kind: 'extent_set' },
}];

function bench(overrides = {}) {
    return {
        available: true,
        unavailable: null,
        forms: [RINGS, SOFT],
        derivable: ['extent.boundary_rings'],
        counts: { registered: 19, writable_as_artifact: 3, producible_here: 9 },
        recipes: null,
        readiness: {},
        derivations: [],
        busy: false,
        error: null,
        checkRecipe: vi.fn(),
        derive: vi.fn(),
        planRecipe: vi.fn(),
        inputsFor: () => LEDGER,
        ...overrides,
    };
}

// ── the direct form level ───────────────────────────────────────────────────

describe('the direct form level', () => {
    it('names the producer, its kind, its checkpoint and its revision', async () => {
        await mount(<FormBench bench={bench()} onDerive={vi.fn()} />);
        const producer = q('.fb-producer');
        expect(producer.getAttribute('data-kind')).toBe('code');
        expect(producer.getAttribute('data-state')).toBe('available');
        expect(producer.textContent).toContain('perception_lab.extent_forms.boundary_rings');
        expect(producer.textContent).toContain('no checkpoint');
        expect(producer.textContent).toContain('extent-exact-forms.v1');
    });

    it('says why a producer is not running and what would change it', async () => {
        await mount(<FormBench bench={bench()} onDerive={vi.fn()} />);
        await choose(q('#fb-form'), 'extent.soft_field');
        const sam3 = byText('.fb-producer', 'sam3_concept');
        expect(sam3.textContent).toContain('SAM3_WEIGHTS is unset');
        expect(sam3.textContent).toContain('export SAM3_WEIGHTS=');
        expect(sam3.textContent).toContain('facebook/sam3');
    });

    it('says which absence a form that cannot be written is in', async () => {
        await mount(<FormBench bench={bench()} onDerive={vi.fn()} />);
        expect(q('.fb-blocked').textContent).toContain('no_operation');

        await choose(q('#fb-form'), 'extent.soft_field');
        const blocked = q('.fb-blocked').textContent;
        expect(blocked).toContain('deferred_form');
        expect(blocked).toContain('capability_unavailable');
    });

    it('marks an experimental form as unable to become an artifact', async () => {
        await mount(<FormBench bench={bench()} onDerive={vi.fn()} />);
        expect(text()).toContain('cannot become an artifact');
        expect(q('.fb-state').textContent).toContain('experimental');
    });

    it('will not offer to produce a form no producer here computes', async () => {
        await mount(<FormBench bench={bench()} onDerive={vi.fn()} />);
        await choose(q('#fb-form'), 'extent.soft_field');
        expect(q('[data-action="derive"]').disabled).toBe(true);
        expect(text()).toContain('Nothing is substituted');
    });

    it('sends the artifacts a person chose and nothing else', async () => {
        const onDerive = vi.fn();
        await mount(<FormBench bench={bench()} onDerive={onDerive} />);
        await click(q('.fb-inputs input[type="checkbox"]'));
        await click(q('[data-action="derive"]'));
        expect(onDerive).toHaveBeenCalledWith('extent.boundary_rings', ['art_1']);
    });

    it('draws two views at once and never superimposes them', async () => {
        await mount(<FormBench bench={bench({ derivations: [DERIVATION] })}
            onDerive={vi.fn()} />);
        const panes = all('.fb-pane');
        expect(panes).toHaveLength(2);
        expect(panes.map((p) => p.getAttribute('data-side'))).toEqual(['left', 'right']);
        expect(panes[0].getAttribute('data-view'))
            .not.toBe(panes[1].getAttribute('data-view'));
    });

    it('prints the receipt: producer, revision, ceiling, basis and the verdict', async () => {
        await mount(<FormBench bench={bench({ derivations: [DERIVATION] })}
            onDerive={vi.fn()} />);
        const receipt = q('.fb-receipt').textContent;
        expect(receipt).toContain('@ extent-exact-forms.v1');
        expect(receipt).toContain('ceiling measured');
        expect(receipt).toContain('basis mask');
        expect(receipt).toContain('producible');
    });

    it('shows what the producer left out rather than only what it kept', async () => {
        await mount(<FormBench bench={bench({ derivations: [DERIVATION] })}
            onDerive={vi.fn()} />);
        const omitted = q('.fb-omitted').textContent;
        expect(omitted).toContain('part_not_supplied');
        expect(omitted).toContain('art_1#inst_2');
    });

    it('prints every scalar that decides what is drawn', async () => {
        const withField = {
            ...DERIVATION,
            form: 'extent.density_field',
            payload: {
                variant: 'extent_density_field', members_counted: 3, samples_taken: 3,
                counts_are_exact: true, members: [],
                smoothing: { applied: true, method: 'gaussian', bandwidth: 1.5 },
                field: { field_shape: [4, 4], value_range: [0, 2],
                    calibration: { state: 'nominal' } },
            },
        };
        expect(thresholdsOf(withField)).toEqual([
            ['smoothing', 'gaussian @ 1.5'],
            ['value_range', '0 – 2'],
            ['calibration', 'nominal'],
        ]);
        await mount(<FormBench bench={bench({ derivations: [withField],
            forms: [RINGS, { ...RINGS, form: 'extent.density_field', label: 'Density field' }],
            derivable: ['extent.density_field'] })} onDerive={vi.fn()} />);
        await choose(q('#fb-form'), 'extent.density_field');
        const dl = q('.fb-thresholds').textContent;
        expect(dl).toContain('gaussian @ 1.5');
        expect(dl).toContain('nominal');
    });

    it('has no control that accepts a hypothesis', async () => {
        await mount(<FormBench bench={bench({ derivations: [DERIVATION] })}
            onDerive={vi.fn()} />);
        const labels = all('button').map((b) => b.textContent).join(' ');
        for (const forbidden of ['Accept', 'Promote', 'Keep', 'Confirm', 'Resolve', 'Choose']) {
            expect(labels).not.toContain(forbidden);
        }
    });

    it('says which levels a wire without the form routes cannot serve', async () => {
        await mount(<FormBench bench={bench({ available: false, forms: null,
            unavailable: 'This wire does not serve forms, recipes.' })}
        onDerive={vi.fn()} />);
        expect(text()).toContain('does not serve forms, recipes');
    });

    it('does not draw an empty catalogue while the catalogue is still being read', async () => {
        await mount(<FormBench bench={bench({ forms: [] })}
            onDerive={vi.fn()} />);
        expect(text()).toContain('Nineteen forms and zero forms look the same');
    });
});

// ── the recipe level ────────────────────────────────────────────────────────

const RECIPE = {
    key: 'boundary-and-void',
    label: 'Boundary and void study',
    question: 'Where exactly does its edge run, and what does it enclose?',
    organ: 'extent', mode: 'isolation',
    required_forms: ['extent.hard_mask', 'extent.boundary_rings'],
    prerequisites: ['a source image is loaded'],
    bounds: { max_operations: 1, max_model_calls: 1 },
    expected_renderers: ['mask_fill'],
    fixtures: ['donut'],
    asks_for: {},
    steps: [
        { id: 'propose', kind: 'operation', why: 'the masks are the substrate',
            operation: 'extent.find_all', parameters: { max_instances: 8 }, produces: null,
            reads: [], asks_for: [] },
        { id: 'trace', kind: 'derivation', why: 'the edge as closed curves', operation: null,
            parameters: {}, produces: 'extent.boundary_rings', reads: ['propose'],
            asks_for: [] },
    ],
    stop_conditions: [{ when: 'the proposal returns no instance', outcome: 'empty',
        reason: 'something looked and found nothing separable' }],
    decision_points: [{ at: 'trace', asks: 'Is that a void inside this extent?',
        why_a_person: 'the producer answers a different question, exactly',
        options: ['a hole', 'a gap'] }],
};

const BLOCKED = {
    ...RECIPE, key: 'fragment-continuity', label: 'Fragment continuity study',
    required_forms: ['extent.fused_hypothesis'],
};

function recipeBench(overrides = {}) {
    return bench({
        recipes: [RECIPE, BLOCKED],
        readiness: {
            'boundary-and-void': { ready: true, reasons: [], unproducible_forms: [] },
            'fragment-continuity': {
                ready: false,
                reasons: ['extent.fused_hypothesis: not producible in this deployment'],
                unproducible_forms: ['extent.fused_hypothesis'],
            },
        },
        ...overrides,
    });
}

describe('the deterministic recipe level', () => {
    it('shows readiness before anything is spent, with the reason', async () => {
        await mount(<RecipeTray bench={recipeBench()} onPlan={vi.fn()} />);
        const blocked = q('[data-recipe="fragment-continuity"]');
        expect(blocked.getAttribute('data-ready')).toBe('false');
        expect(blocked.textContent).toContain('not producible in this deployment');
        expect(q('[data-recipe="boundary-and-void"]').getAttribute('data-ready')).toBe('true');
    });

    it('prints the bound on model calls beside the study', async () => {
        await mount(<RecipeTray bench={recipeBench()} onPlan={vi.fn()} />);
        expect(all('[data-bound="model"]').map((c) => c.textContent))
            .toEqual(['\u22641 model calls', '\u22641 model calls']);
    });

    it('keeps every step on screen, and draws an operation differently from a derivation',
        async () => {
            await mount(<RecipeTray bench={recipeBench()} onPlan={vi.fn()} />);
            await click(byText('.fb-recipe-head', 'Boundary and void study'));
            const steps = all('.fb-step');
            expect(steps.map((s) => s.getAttribute('data-kind')))
                .toEqual(['operation', 'derivation']);
            expect(steps[0].textContent).toContain('extent.find_all');
            expect(steps[1].textContent).toContain('extent.boundary_rings');
        });

    it('prints why a person is needed at every decision point', async () => {
        await mount(<RecipeTray bench={recipeBench()} onPlan={vi.fn()} />);
        await click(byText('.fb-recipe-head', 'Boundary and void study'));
        expect(q('.fb-decisions').textContent)
            .toContain('the producer answers a different question');
    });

    it('says that proposing is not running', async () => {
        const onPlan = vi.fn();
        await mount(<RecipeTray bench={recipeBench()} onPlan={onPlan} />);
        await click(byText('.fb-recipe-head', 'Boundary and void study'));
        expect(text()).toContain('Nothing runs when you press this');
        await click(q('[data-action="plan"]'));
        expect(onPlan).toHaveBeenCalledWith('boundary-and-void', {});
    });

    it('asks readiness for every study exactly once when the catalogue arrives', async () => {
        const check = vi.fn();
        await mount(<RecipeTray bench={bench({ recipes: [RECIPE], readiness: {},
            checkRecipe: check })} onPlan={vi.fn()} />);
        expect(check).toHaveBeenCalledTimes(1);
        expect(check).toHaveBeenCalledWith('boundary-and-void');
    });
});

// ── the three levels are visibly distinct ───────────────────────────────────

describe('the arms', () => {
    it('offers four levels and says what each one does', async () => {
        await mount(<ModeControls mode="isolation" arm="form" organ="extent"
            onMode={vi.fn()} onArm={vi.fn()} />);
        expect(all('[data-arm]').map((b) => b.getAttribute('data-arm')))
            .toEqual(['direct', 'form', 'recipe', 'prompt']);
        expect(q('[data-arm-consequence="form"]').textContent)
            .toContain('cannot become an artifact');
    });

    it('gives each arm a different consequence', () => {
        const said = Object.values(ARM_CONSEQUENCE);
        expect(new Set(said).size).toBe(said.length);
    });

    it('marks the arm a person is in', async () => {
        await mount(<ModeControls mode="isolation" arm="recipe" organ="extent"
            onMode={vi.fn()} onArm={vi.fn()} />);
        expect(q('[data-arm="recipe"]').getAttribute('aria-pressed')).toBe('true');
        expect(q('[data-arm="direct"]').getAttribute('aria-pressed')).toBe('false');
    });
});

describe('the client seam', () => {
    it('names the six methods a wire needs for the two lower levels', () => {
        expect(FORM_CLIENT_METHODS).toEqual([
            'forms', 'recipes', 'recipeReadiness', 'planRecipe', 'derive', 'derivations']);
    });

    it('reports which methods a stale wire is missing rather than refusing to mount', () => {
        expect(supportsForms({})).toBe(false);
        expect(missingFormMethods({ forms: () => {}, recipes: () => {} }))
            .toEqual(['recipeReadiness', 'planRecipe', 'derive', 'derivations']);
    });

    it('none of the six can promote anything', () => {
        for (const method of FORM_CLIENT_METHODS) {
            expect(method).not.toMatch(/promote|commit|publish|accept|approve/i);
        }
    });
});
