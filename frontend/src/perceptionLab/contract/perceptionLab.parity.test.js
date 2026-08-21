// PERCEPTUAL-ORGANS-002 Lane A — the frontend half of the cross-language parity gate.
//
// The Perception Lab contract is DATA read by three runtimes. Data read by three runtimes drifts
// unless something fails when it does. These are the things that fail.
//
// FIVE CHECKS, and each one is here because of a specific way this could go quietly wrong:
//
//  1. THE MIRROR IS THE CANONICAL FILE. `frontend/src/contracts/perception-lab.v1.json` exists
//     only because the Vercel project uploads `frontend/` as its deployment source, so the bundle
//     cannot import from the repo root. A copy that nothing pins is a second contract with a
//     head start.
//
//  2. THE JS READS THE CLOSED SETS FROM THE CONTRACT. Asserted against the file rather than
//     against literals here, so a set edited in one place and not the other fails.
//
//  3. EVERY COMMITTED FIXTURE VALIDATES IN THE JS VALIDATORS, and every field the contract says
//     the Lab UI reads actually resolves on it. This is the check with no substitute: the claim
//     of the lane is that three runtimes enforce ONE contract, and this is where Python-authored
//     records meet the JavaScript law.
//
//  4. THE JS RESOLVER'S OWN OUTPUT IS COMMITTED FOR PYTHON TO RECOMPUTE. Written here because
//     only vitest can import the extensionless ESM. The backend suite reads the same file and
//     re-runs every case through `definitions.resolve_parameters`.
//
//  5. THE PYTHON GATES' OUTPUT IS RECOMPUTED HERE. The mirror image of (4): refusals Python
//     built, reproduced by `checkOrganLock` / `checkInputs` / `checkCapability`.
//
// Nothing in this file is a mock. The validators, the resolver and the fixtures are the real ones.
//
// Regenerate the JS-authored fixture with:
//     UPDATE_PARITY_FIXTURES=1 npx vitest run src/perceptionLab/contract

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import CONTRACT from '../../contracts/perception-lab.v1.json';
import {
    SCHEMA_VERSION, ORGAN_FAMILIES, ENABLED_ORGAN_FAMILIES, RUN_OUTCOMES, EXECUTION_IDENTITIES,
    LIFECYCLE_STATES, REVIEW_VERDICTS, EPISTEMIC_STATUSES, REFUSAL_CODES, PROJECTION_HINT_KEYS,
    ARTIFACT_KINDS, BASIS_CEILINGS, ENFORCED_LAWS, VALIDATORS,
    organ, operation, isOrganEnabled, enabledOrgans, producibleArtifactKinds,
    resolveParameters, checkOrganLock, checkInputs, checkCapability,
    consumedFields, missingConsumedFields, readPath,
    validateArtifact, validateRun, validatePlan, validateReview, validateSession,
    validateInputRef, referenceOf, sessionKnows, declaredReferences,
    PERCEPTUAL_FORMS, PARTITION_CEILINGS, RELATION_KINDS, form, formsFor, formHasProducer,
    effectiveForm, derivedCeiling, checkInputForms, checkFormProducible, validateFormPayload,
    optionalConsumedFields,
} from './perceptionLabContract';
import { PROJECTION_FOR_KIND } from '../topologyView';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '../../../..');
const CANONICAL = path.join(REPO_ROOT, 'contracts');
const MIRROR = path.resolve(HERE, '../../contracts');
const FIXTURES = path.join(CANONICAL, 'fixtures', 'perception-lab');

const read = (p) => fs.readFileSync(p, 'utf8');
const fixture = (name) => JSON.parse(read(path.join(FIXTURES, name)));
const MANIFEST = fixture('manifest.json');

// Written by this file, read by `test_perception_lab_contracts.py`.
const JS_RESOLVER_FIXTURE = path.join(FIXTURES, 'js-resolver.parameters.json');
// Written by this file, read by `test_perception_lab_instance_refs.py`.
const JS_REFS_FIXTURE = path.join(FIXTURES, 'js-instance-refs.json');
// Written by that file, recomputed here.
const PY_GATES_FIXTURE = path.join(FIXTURES, 'py-gates.refusals.json');

describe('the Perception Lab contract — one law, three runtimes', () => {
    it('the frontend mirror is byte-identical to the canonical contract', () => {
        expect(read(path.join(MIRROR, 'perception-lab.v1.json')),
               'perception-lab.v1.json has drifted from contracts/perception-lab.v1.json — run '
               + 'python scripts/contracts_sync.py')
            .toBe(read(path.join(CANONICAL, 'perception-lab.v1.json')));
    });

    it('reads its version and closed sets from the contract, not from literals here', () => {
        expect(SCHEMA_VERSION).toBe('perception-lab.v1');
        expect(ORGAN_FAMILIES).toEqual(CONTRACT.closed_sets.organ_families);
        expect(RUN_OUTCOMES).toEqual(CONTRACT.closed_sets.run_outcomes);
        expect(EXECUTION_IDENTITIES).toEqual(CONTRACT.closed_sets.execution_identities);
        expect(LIFECYCLE_STATES).toEqual(CONTRACT.closed_sets.lifecycle_states);
        expect(REVIEW_VERDICTS).toEqual(CONTRACT.closed_sets.review_verdicts);
        expect(REFUSAL_CODES).toEqual(CONTRACT.closed_sets.refusal_codes);
        expect(ARTIFACT_KINDS).toEqual(CONTRACT.closed_sets.artifact_kinds);
    });

    it('claims every law the contract declares', () => {
        expect([...ENFORCED_LAWS].sort())
            .toEqual(CONTRACT.laws.map((l) => l.id).sort());
    });
});

describe('eight organs, two of them enabled', () => {
    it('registers all eight families', () => {
        expect(ORGAN_FAMILIES).toHaveLength(8);
        expect(Object.keys(CONTRACT.organs.reduce((a, o) => ({ ...a, [o.family]: 1 }), {})))
            .toHaveLength(8);
    });

    it('enables exactly extent and topology', () => {
        expect(enabledOrgans().map((o) => o.family)).toEqual(['extent', 'topology']);
        expect(ENABLED_ORGAN_FAMILIES).toEqual(['extent', 'topology']);
        expect(isOrganEnabled('extent')).toBe(true);
        expect(isOrganEnabled('depth')).toBe(false);
    });

    it('gives a deferred organ no operations, adapters, tools or epistemic ceiling', () => {
        for (const family of ORGAN_FAMILIES.filter((f) => !isOrganEnabled(f))) {
            const o = organ(family);
            expect(o.operations, `${family} declares operations`).toEqual([]);
            expect(o.adapters, `${family} declares adapters`).toEqual([]);
            expect(o.manual_tools).toEqual([]);
            expect(o.render_projections).toEqual([]);
            expect(o.produces_artifact_kinds).toEqual([]);
            expect(o.epistemic_ceiling, `${family} claims a quality of evidence it cannot produce`)
                .toBeNull();
        }
    });

    it('throws rather than returning a stub for an unknown organ or operation', () => {
        expect(() => organ('echolocation')).toThrow(/not a registered organ family/);
        expect(() => operation('extent.imagine')).toThrow(/not a declared operation/);
    });

    it('declares depth_field without letting anything mint one', () => {
        expect(ARTIFACT_KINDS).toContain('depth_field');
        expect(producibleArtifactKinds()).not.toContain('depth_field');
        expect(organ('depth').declares_artifact_kinds).toEqual(['depth_field']);
    });
});

describe('topology declares its inputs; occlusion declares its dependency', () => {
    it('every topology operation requires an extent input and may not invoke extent', () => {
        for (const op of organ('topology').operations) {
            const required = (op.inputs || []).filter(
                (i) => i.required && (i.artifact_kinds || []).includes('extent_set'));
            expect(required.length, `${op.key} does not say where its extents come from`)
                .toBeGreaterThan(0);
            expect(op.must_not_invoke).toContain('extent');
            expect(op.must_not_invoke).toContain('depth');
        }
    });

    it('occlusion plans without depth and refuses to run without it', () => {
        const endpoints = [
            { role: 'source', scope: 'session', artifact_id: 'art_a' },
            { role: 'target', scope: 'session', artifact_id: 'art_b' },
        ];
        expect(checkInputs('topology.occlusion', endpoints, { forExecution: false })).toBeNull();
        const refused = checkInputs('topology.occlusion', endpoints, { forExecution: true });
        expect(refused.code).toBe('missing_depth_artifact');
        expect(operation('topology.occlusion').dependency_declaration.may_invoke).toBe(false);
    });

    it('topology with no extents refuses rather than measuring nothing', () => {
        expect(checkInputs('topology.containment', [], { forExecution: true }).code)
            .toBe('missing_extent_inputs');
    });
});

describe('the gates', () => {
    it('locks the organ in isolation and permits the crossing in chain', () => {
        expect(checkOrganLock('topology.adjacency',
                              { selectedOrgan: 'extent', mode: 'isolation' }).code)
            .toBe('organ_locked');
        expect(checkOrganLock('topology.adjacency',
                              { selectedOrgan: 'extent', mode: 'chain' })).toBeNull();
    });

    it('calls an undeclared operation unsupported, not locked', () => {
        expect(checkOrganLock('extent.divine', { selectedOrgan: 'extent', mode: 'isolation' }).code)
            .toBe('unsupported_operation');
    });

    it('drops an undeclared parameter and records it', () => {
        const r = resolveParameters('extent.find_all',
                                    { max_instances: 4, mask_rle: { size: [1, 1], counts: [] } });
        expect(r.refusal).toBeNull();
        expect(r.clean).toEqual({ max_instances: 4 });
        expect(r.dropped.map((d) => d.name)).toEqual(['mask_rle']);
    });

    it('clamps a bounded parameter and records the clamp', () => {
        const r = resolveParameters('extent.find_all', { max_instances: 9000 });
        expect(r.clean).toEqual({ max_instances: 64 });
        expect(r.clamped).toEqual([
            { name: 'max_instances', requested: 9000, applied: 64, bound: 'maximum=64' }]);
    });

    it('refuses a declared parameter of the wrong type, and a missing required one', () => {
        expect(resolveParameters('extent.find_all', { max_instances: 'lots' }).refusal.code)
            .toBe('invalid_parameters');
        expect(resolveParameters('extent.find_named', {}).refusal.code).toBe('invalid_parameters');
    });

    it('does not refuse an adapter nobody has looked at yet', () => {
        expect(checkCapability('extent.find_all', { states: {} })).toBeNull();
        expect(checkCapability('extent.find_named',
                               { adapter: 'sam3_concept', states: { sam3_concept: 'unavailable' } })
            .code).toBe('capability_unavailable');
    });

    it('declares no default on any parameter anywhere', () => {
        for (const op of Object.values(
            CONTRACT.organs.flatMap((o) => o.operations || []))) {
            for (const p of op.parameters || []) {
                expect(p.default, `${op.key}.${p.name} declares a default`).toBeNull();
            }
        }
    });
});

describe('the separations, in JavaScript', () => {
    const artifact = () => fixture('artifact.extent-set.json');

    it('accepts the honest fixture', () => {
        expect(validateArtifact(artifact())).toEqual([]);
    });

    it('refuses geometry in a projection hint', () => {
        const a = artifact();
        a.projection.hints = { opacity: 0.4, mask_rle: { size: [1, 1], counts: [] } };
        expect(validateArtifact(a).join(' ')).toMatch(/mask_rle/);
    });

    it('keeps the projection hint keys free of anything that could stand in for evidence', () => {
        for (const key of PROJECTION_HINT_KEYS) {
            expect(key).not.toMatch(/mask|polygon|rle|geometry|points|box|path/);
        }
    });

    it('refuses a verdict carried on the artifact', () => {
        const a = artifact();
        a.review = { verdict: 'correct' };
        expect(validateArtifact(a).join(' ')).toMatch(/separate record/);
    });

    it('refuses a sourced measurement and a measured interpretation', () => {
        const a = artifact();
        a.measurement.epistemic_status = 'sourced';
        expect(validateArtifact(a).length).toBeGreaterThan(0);
        const b = artifact();
        b.interpretation.epistemic_status = 'measured';
        expect(validateArtifact(b).length).toBeGreaterThan(0);
    });

    it('keeps a box basis interpretive no matter how confident the number looks', () => {
        const a = fixture('artifact.topology-relation-set-box-basis.json');
        expect(validateArtifact(a)).toEqual([]);
        expect(a.measurement.payload.relations[0].measurements.containment).toBeCloseTo(0.999);
        a.measurement.epistemic_status = 'measured';
        expect(validateArtifact(a).join(' ')).toMatch(/box-basis measurement may claim at most/);
    });

    it('refuses a cross-organ payload', () => {
        const a = fixture('artifact.topology-relation-set.json');
        a.identity.organ_family = 'extent';
        expect(validateArtifact(a).length).toBeGreaterThan(0);
    });

    it('refuses an artifact from a disabled organ', () => {
        const a = artifact();
        a.identity.organ_family = 'colour';
        expect(validateArtifact(a).join(' ')).toMatch(/disabled/);
    });

    it('keeps lifecycle, verdict and epistemic status as three sets with no shared member', () => {
        const lifecycle = new Set(LIFECYCLE_STATES);
        const verdicts = new Set(REVIEW_VERDICTS);
        for (const s of EPISTEMIC_STATUSES) {
            expect(lifecycle.has(s)).toBe(false);
            expect(verdicts.has(s)).toBe(false);
        }
        for (const s of LIFECYCLE_STATES) expect(verdicts.has(s)).toBe(false);
    });

    it('refuses a review that tries to carry an epistemic or lifecycle status', () => {
        const r = fixture('review.correct.json');
        expect(validateReview(r)).toEqual([]);
        expect(validateReview({ ...r, epistemic_status: 'measured' }).join(' '))
            .toMatch(/does not make/);
    });

    it('agrees with the contract about every basis ceiling', () => {
        expect(BASIS_CEILINGS).toEqual(CONTRACT.epistemics.basis_ceilings);
    });
});

describe('replay cannot recompute', () => {
    it('accepts the replay fixture and its uncallable adapter', () => {
        const run = fixture('run.replay-extent.json');
        expect(validateRun(run)).toEqual([]);
        expect(run.replay.adapter_callable).toBe(false);
    });

    it('refuses a replay or fixture run that invoked an adapter', () => {
        for (const name of ['run.replay-extent.json', 'run.fixture-topology.json']) {
            const run = fixture(name);
            run.stage_attempts[0].invoked = true;
            expect(validateRun(run).join(' '), name).toMatch(/Only LIVE may call an adapter/);
        }
    });

    it('refuses a replay with no source run, and a live run carrying replay provenance', () => {
        const replay = fixture('run.replay-extent.json');
        expect(validateRun({ ...replay, replay: null }).length).toBeGreaterThan(0);
        const live = fixture('run.live-ready.json');
        expect(validateRun({ ...live, replay: replay.replay }).length).toBeGreaterThan(0);
    });

    it('lets an honest record NAME an adapter it did not call', () => {
        for (const name of ['run.live-unavailable.json', 'run.fixture-topology.json',
            'run.replay-extent.json']) {
            const run = fixture(name);
            expect(validateRun(run), name).toEqual([]);
            expect(run.stage_attempts[0].adapter).toBeTruthy();
            expect(run.stage_attempts[0].invoked).toBe(false);
        }
    });
});

describe('the five nothings stay apart', () => {
    it('refuses an unavailable run that does not name what is not running', () => {
        const run = fixture('run.live-unavailable.json');
        expect(validateRun(run)).toEqual([]);
        run.refusals[0].code = 'invalid_parameters';
        expect(validateRun(run).join(' ')).toMatch(/indistinguishable from having found nothing/);
    });

    it('refuses a refused run with no refusal, and an empty run with one', () => {
        const refused = fixture('run.live-refused-missing-depth.json');
        expect(validateRun({ ...refused, refusals: [] }).length).toBeGreaterThan(0);
        const empty = fixture('run.live-empty.json');
        expect(validateRun({ ...empty, refusals: refused.refusals }).length).toBeGreaterThan(0);
    });

    it('reads a disjoint relation as a finding and an empty set as a measurement', () => {
        const relationKinds = CONTRACT.closed_sets.relation_kinds;
        expect(relationKinds).toContain('disjoint');
        const cases = CONTRACT.absence_semantics.distinctions.map((d) => d.case);
        expect(cases).toContain('measured emptiness');
        expect(cases).toContain('a positive no-relation');
    });
});

describe('the isolation lock, in a plan', () => {
    it('accepts a crossing proposal only alongside its refusal', () => {
        const plan = fixture('plan.model-organ-locked.json');
        expect(validatePlan(plan)).toEqual([]);
        expect(validatePlan({ ...plan, refusals: [] }).join(' ')).toMatch(/organ_locked/);
    });

    it('refuses a resolved step that left the locked organ', () => {
        const plan = fixture('plan.direct-extent-find-all.json');
        plan.resolved_steps[0].organ = 'topology';
        expect(validatePlan(plan).join(' ')).toMatch(/A prompt may not change organs/);
    });

    it('refuses a proposal that claims authority, and an authority that is not the resolver', () => {
        const plan = fixture('plan.direct-extent-find-all.json');
        const withClaim = JSON.parse(JSON.stringify(plan));
        withClaim.proposed_steps[0].authorized_by = 'resolver';
        expect(validatePlan(withClaim).join(' ')).toMatch(/no authority to claim/);
        const withOther = JSON.parse(JSON.stringify(plan));
        withOther.resolved_steps[0].authorized_by = 'planner';
        expect(validatePlan(withOther).join(' ')).toMatch(/Only the resolver authorizes/);
    });

    it('makes a crossing chain ask first', () => {
        const plan = fixture('plan.chain-extent-to-topology.json');
        expect(validatePlan(plan)).toEqual([]);
        expect(validatePlan({ ...plan, requires_confirmation: false }).join(' '))
            .toMatch(/requires confirmation/);
    });

    it('will not let a rules fallback wear the model\'s name', () => {
        const plan = fixture('plan.rules-fallback.json');
        expect(plan.planner).toBe('rules');
        expect(plan.planner_fell_back_from).toBe('model');
        expect(validatePlan({ ...plan, planner_fell_back_from: 'rules' }).length)
            .toBeGreaterThan(0);
    });

    it('refuses a session on a deferred organ', () => {
        const s = fixture('session.extent-isolation.json');
        expect(validateSession(s)).toEqual([]);
        expect(validateSession({ ...s, selected_organ: 'depth' }).join(' '))
            .toMatch(/nothing behind the glass/);
    });
});

describe('the perceptual form grammar, in JavaScript', () => {
    const forms = CONTRACT.perceptual_forms;

    it('registers exactly the forms the closed set names, and fails closed on anything else', () => {
        expect(forms.map((f) => f.key)).toEqual([...PERCEPTUAL_FORMS]);
        expect(() => form('extent.fog')).toThrow(/not a registered perceptual form/);
        expect(formsFor('extent').length + formsFor('topology').length).toBe(forms.length);
    });

    it.each(forms.map((f) => [f.key]))(
        '%s declares a producer, a renderer, a receipt and a test obligation', (key) => {
            const f = form(key);
            expect(f.producer_classes.length, 'a form nothing could write is a word').toBeGreaterThan(0);
            expect(f.renderer_projections.length,
                   'a measurement nobody can look at cannot be reviewed').toBeGreaterThan(0);
            expect(f.required_provenance.length).toBeGreaterThan(0);
            expect(f.test_obligations.length, 'a law nothing fails on is a comment').toBeGreaterThan(0);
            expect(f.absence.examined_field, 'every form can say it looked').toBeTruthy();
            for (const p of f.renderer_projections) {
                expect(['direct', 'derived']).toContain(p.mode);
            }
        });

    it('only the forms an operation declares are enabled, and only they reach an artifact', () => {
        for (const f of forms) {
            const declared = f.produced_by_operations.length > 0;
            expect(declared, `${f.key} state/operation disagreement`)
                .toBe(f.state === 'enabled');
            expect(formHasProducer(f.key)).toBe(declared);
        }
        expect(forms.filter((f) => f.state === 'enabled').length).toBe(3);
    });

    it('every operation draws only what its form declares it can', () => {
        for (const organRecord of CONTRACT.organs) {
            for (const op of organRecord.operations || []) {
                for (const kind of op.produces) {
                    const f = forms.find((x) => x.artifact_kind === kind);
                    if (!f) continue;
                    const drawable = f.renderer_projections.map((p) => p.kind);
                    for (const projection of op.render_projections || []) {
                        expect(drawable, `${op.key} draws ${projection}, ${f.key} does not declare it`)
                            .toContain(projection);
                    }
                }
            }
        }
    });

    it('the partition caps the claim, and no confidence lifts it', () => {
        expect(PARTITION_CEILINGS.inferred_completion).toBe('uncertain');
        expect(PARTITION_CEILINGS.unresolved_alternative).toBe('uncertain');
        // A perfect mask basis, and still an assertion about pixels nobody saw.
        expect(derivedCeiling('extent.visible_inferred_partition', {
            basis: 'mask', partition: 'inferred_completion',
        })).toBe('uncertain');
        // A derivation is never stronger than the weakest thing it derived from.
        expect(derivedCeiling('topology.containment_tree', {
            basis: 'mask', partition: 'exact_derivation', inputStatuses: ['interpretive'],
        })).toBe('interpretive');
    });

    it('refuses the wrong input form, and refuses to write a deferred one', () => {
        expect(checkInputForms('extent.boundary_rings', ['extent.hard_mask'])).toBeNull();
        const wrong = checkInputForms('extent.boundary_rings', ['extent.soft_field'],
                                      { operation: 'extent.refine' });
        expect(wrong.code).toBe('unsupported_form');
        expect(wrong.message).toMatch(/does not accept extent\.soft_field/);
        expect(checkFormProducible('topology.pair_relation')).toBeNull();
        expect(checkFormProducible('extent.soft_field').code).toBe('form_not_producible');
    });

    it('reconciles with the renderer registry Lane E already ships', () => {
        // Lane E maps each relation kind to the drawing it asks for, and every one of those
        // drawings has to be something `topology.pair_relation` declares — otherwise the form
        // registry and the renderer registry are two answers to one question, which is the exact
        // failure the grammar was written to end.
        const declared = new Map(
            form('topology.pair_relation').renderer_projections.map((p) => [p.kind, p.mode]));
        for (const [relationKind, projection] of Object.entries(PROJECTION_FOR_KIND)) {
            expect(RELATION_KINDS, `${relationKind} is not a relation kind`)
                .toContain(relationKind);
            expect([...declared.keys()],
                   `Lane E draws ${projection} for ${relationKind}; the form does not declare it`)
                .toContain(projection);
            // and every one of them is DERIVED today, which is why the browser stamps them
            expect(declared.get(projection),
                   `${projection} is drawn from a payload that does not carry it`).toBe('derived');
        }
        // the forms that would make those same drawings direct, once something writes them
        expect(form('topology.contact_locus').renderer_projections
            .find((p) => p.kind === 'contact_band').mode).toBe('direct');
        expect(form('topology.intersection_area').renderer_projections
            .find((p) => p.kind === 'intersection_area').mode).toBe('direct');
    });

    it('reads a record written before the grammar existed', () => {
        const legacy = fixture('artifact.extent-set.json');
        expect(legacy.identity.form, 'the witness must actually predate the field')
            .toBeUndefined();
        expect(effectiveForm(legacy)).toBe('extent.hard_mask');
        expect(validateArtifact(legacy)).toEqual([]);
        expect(effectiveForm(fixture('artifact.refusal-missing-depth.json')))
            .toBeNull();
        expect(optionalConsumedFields('PerceptualArtifact'))
            .toEqual(['identity.form', 'measurement.partition']);
    });
});

describe('every committed form payload, through the JavaScript law', () => {
    const cases = Object.entries(MANIFEST.form_payloads.by_form);

    it.each(cases.map(([key, entry]) => [key, entry]))('%s validates', (key, entry) => {
        const payload = fixture(entry.file);
        expect(payload.variant).toBe(entry.variant);
        expect(validateFormPayload(key, payload),
               `${entry.file} does not satisfy the JS form law`).toEqual([]);
    });

    it('covers every registered form, and nothing that is not one', () => {
        expect(Object.keys(MANIFEST.form_payloads.by_form)).toEqual([...PERCEPTUAL_FORMS]);
    });

    it('catches a dropped condition, an inferred pixel claiming to be visible, and a blur', () => {
        const conditional = fixture(MANIFEST.form_payloads.by_form[
            'topology.uncertain_relation_set'].file);
        const orphaned = structuredClone(conditional);
        orphaned.relations[0].conditioned_on = 'alt_nobody_declared';
        expect(validateFormPayload('topology.uncertain_relation_set', orphaned).join(' '))
            .toMatch(/dropped condition reads as a measurement/);

        const promoted = structuredClone(conditional);
        promoted.relations[0].epistemic_status = 'measured';
        expect(validateFormPayload('topology.uncertain_relation_set', promoted).join(' '))
            .toMatch(/may not be measured/);

        const partition = structuredClone(fixture(MANIFEST.form_payloads.by_form[
            'extent.visible_inferred_partition'].file));
        partition.regions[1].epistemic_status = 'measured';
        expect(validateFormPayload('extent.visible_inferred_partition', partition).join(' '))
            .toMatch(/pixels nobody saw/);

        const soft = structuredClone(fixture(MANIFEST.form_payloads.by_form[
            'extent.soft_field'].file));
        soft.field.derivation = 'blur_of_binary_mask';
        expect(validateFormPayload('extent.soft_field', soft).join(' '))
            .toMatch(/may not declare itself calibrated/);

        const fragments = structuredClone(fixture(MANIFEST.form_payloads.by_form[
            'extent.fragment_set'].file));
        fragments.unity_asserted = true;
        expect(validateFormPayload('extent.fragment_set', fragments).join(' '))
            .toMatch(/asserts no unity/);
    });

    it('an empty payload that counted nothing cannot pass for a measurement', () => {
        const graph = structuredClone(fixture(MANIFEST.form_payloads.by_form[
            'topology.adjacency_graph'].file));
        delete graph.pairs_examined;
        expect(validateFormPayload('topology.adjacency_graph', graph).join(' '))
            .toMatch(/proves something looked/);
    });
});

describe('every committed fixture, through the JavaScript law', () => {
    const cases = Object.entries(MANIFEST.records)
        .flatMap(([record, names]) => names.map((name) => [record, name]));

    it.each(cases)('%s / %s validates and keeps its consumed fields', (record, name) => {
        const doc = fixture(name);
        expect(VALIDATORS[record](doc), `${name} does not satisfy the JS validator`).toEqual([]);
        expect(missingConsumedFields(record, doc),
               `${name} is missing fields the Lab UI is declared to read`).toEqual([]);
    });

    it('covers every outcome and every execution identity', () => {
        const runs = MANIFEST.records.LabRun.map(fixture);
        expect(new Set(runs.map((r) => r.outcome))).toEqual(new Set(RUN_OUTCOMES));
        expect(new Set(runs.map((r) => r.execution_identity)))
            .toEqual(new Set(EXECUTION_IDENTITIES));
    });

    it('resolves every declared consumed path, and nothing more', () => {
        for (const record of Object.keys(MANIFEST.records)) {
            expect(consumedFields(record).length).toBeGreaterThan(0);
        }
        // The mutation: the reader that backs the check above must say "absent" for a path that is
        // not there, or the check above proves nothing.
        expect(readPath(fixture('artifact.extent-set.json'), 'provenance.adaptor')).toBeUndefined();
        expect(readPath(fixture('artifact.extent-set.json'), 'provenance.adapter')).toBeTruthy();
    });
});

describe('the two-runtime loop', () => {
    // The cases live here because this is the runtime that authors them. The backend suite reads
    // the committed file and recomputes every one through `definitions.resolve_parameters`.
    const RESOLVER_CASES = [
        { name: 'a clean direct command', operation: 'extent.find_all',
          params: { max_instances: 4 } },
        { name: 'a model smuggling geometry', operation: 'extent.find_all',
          params: { max_instances: 4, mask_rle: { size: [1, 1], counts: [] }, region_id: 'reg_7' } },
        { name: 'a number past its bound', operation: 'extent.find_all',
          params: { max_instances: 9000 } },
        { name: 'a number below its floor', operation: 'extent.find_all', params: { min_area: -1 } },
        { name: 'a wrong type', operation: 'extent.find_all', params: { max_instances: 'lots' } },
        { name: 'a missing required parameter', operation: 'extent.find_named', params: {} },
        { name: 'an undeclared enum member', operation: 'extent.find_named',
          params: { concept: 'drapery', adapter: 'clairvoyance' } },
        { name: 'a declared enum member', operation: 'extent.find_named',
          params: { concept: 'drapery', adapter: 'sam3_concept' } },
        { name: 'a null is absence, not a value', operation: 'extent.find_all',
          params: { max_instances: null } },
        { name: 'a clamped list', operation: 'topology.all_pairs',
          params: { max_regions: 40, relations: ['meets', 'overlaps', 'disjoint', 'contains',
                                                 'nested_within'] } },
        { name: 'a tolerance past its bound', operation: 'topology.adjacency',
          params: { contact_tolerance_px: 900 } },
        { name: 'an operation with no parameters at all', operation: 'topology.overlap',
          params: { basis: 'mask' } },
    ];

    it('commits its own resolver output for the backend to recompute', () => {
        const rendered = `${JSON.stringify({
            generated_by: 'frontend/src/perceptionLab/contract/perceptionLab.parity.test.js',
            how_to_regenerate:
                'UPDATE_PARITY_FIXTURES=1 npx vitest run src/perceptionLab/contract',
            cases: RESOLVER_CASES.map((c) => ({
                ...c,
                result: resolveParameters(c.operation, c.params),
            })),
        }, null, 2)}\n`;

        if (process.env.UPDATE_PARITY_FIXTURES) {
            fs.writeFileSync(JS_RESOLVER_FIXTURE, rendered, 'utf8');
        }
        expect(fs.existsSync(JS_RESOLVER_FIXTURE),
               `${path.basename(JS_RESOLVER_FIXTURE)} is missing — regenerate with `
               + 'UPDATE_PARITY_FIXTURES=1').toBe(true);
        expect(read(JS_RESOLVER_FIXTURE),
               'the JS resolver output has drifted from the committed fixture — regenerate with '
               + 'UPDATE_PARITY_FIXTURES=1 and check the backend suite still agrees')
            .toBe(rendered);
    });

    // ── the reference cases, at both depths ─────────────────────────────────
    //
    // PERCEPTUAL-ORGANS-002A2's own parity loop. The frontend emits what it thinks each of these
    // references IS — malformed or not, declared or not, and what it is called — and
    // `test_perception_lab_instance_refs.py` rebuilds all three answers from `InputRef`,
    // `SessionView.knows` and `InputRef.reference`. That is the exact check whose absence was the
    // A2 bug: the frontend wrote `instance_id` and the backend schema rejected it, and no test in
    // either language could see the disagreement.
    const REF_CASES = [
        { name: 'an artifact-level ref, exactly as it read before A2',
          ref: { role: 'base', scope: 'session', artifact_id: 'art_a', instance_id: null,
                 region_id: null, geometry_rev: null } },
        { name: 'a pre-A2 record with no instance_id key at all',
          ref: { role: 'base', scope: 'session', artifact_id: 'art_a', region_id: null,
                 geometry_rev: null } },
        { name: 'one instance inside a declared artifact',
          ref: { role: 'base', scope: 'session', artifact_id: 'art_a', instance_id: 'inst_2',
                 region_id: null, geometry_rev: null } },
        { name: 'an instance the session never declared',
          ref: { role: 'base', scope: 'session', artifact_id: 'art_a', instance_id: 'inst_9',
                 region_id: null, geometry_rev: null } },
        { name: 'an instance declared under a DIFFERENT artifact',
          ref: { role: 'base', scope: 'session', artifact_id: 'art_b', instance_id: 'inst_2',
                 region_id: null, geometry_rev: null } },
        { name: 'a bare instance identity', malformed: true,
          ref: { role: 'base', scope: 'session', artifact_id: null, instance_id: 'inst_2',
                 region_id: null, geometry_rev: null } },
        { name: 'an instance beside a canonical region', malformed: true,
          ref: { role: 'regions', scope: 'canonical', artifact_id: null, instance_id: 'inst_2',
                 region_id: 'reg_7', geometry_rev: 3 } },
        { name: 'a canonical region, which never carried an instance',
          ref: { role: 'regions', scope: 'canonical', artifact_id: null, instance_id: null,
                 region_id: 'reg_7', geometry_rev: 3 } },
        { name: 'a ref naming nothing at all', malformed: true,
          ref: { role: 'base', scope: 'session', artifact_id: null, instance_id: null,
                 region_id: null, geometry_rev: null } },
    ];

    // What the session declared, for `sessionKnows`. `art_a#inst_2` and nothing else at instance
    // depth — so `art_b#inst_2` is the wrong-artifact case and is refused on a matching bare id.
    const DECLARED_SESSION = {
        selected_artifact_ids: ['art_a', 'art_b'],
        active_artifact_id: 'art_a',
        active_region_ids: ['reg_7'],
        selected_instance_refs: [{ artifact_id: 'art_a', instance_id: 'inst_2' }],
    };

    it('commits what it thinks every reference is, for the backend to rebuild', () => {
        const declared = declaredReferences(DECLARED_SESSION);
        const rendered = `${JSON.stringify({
            generated_by: 'frontend/src/perceptionLab/contract/perceptionLab.parity.test.js',
            how_to_regenerate:
                'UPDATE_PARITY_FIXTURES=1 npx vitest run src/perceptionLab/contract',
            session: DECLARED_SESSION,
            cases: REF_CASES.map((c) => ({
                name: c.name,
                ref: c.ref,
                problems: validateInputRef(c.ref),
                reference: referenceOf(c.ref),
                known: sessionKnows(c.ref, declared),
            })),
        }, null, 2)}\n`;

        if (process.env.UPDATE_PARITY_FIXTURES) {
            fs.writeFileSync(JS_REFS_FIXTURE, rendered, 'utf8');
        }
        expect(fs.existsSync(JS_REFS_FIXTURE),
               `${path.basename(JS_REFS_FIXTURE)} is missing — regenerate with `
               + 'UPDATE_PARITY_FIXTURES=1').toBe(true);
        expect(read(JS_REFS_FIXTURE),
               'the JS reference rules have drifted from the committed fixture — regenerate with '
               + 'UPDATE_PARITY_FIXTURES=1 and check the backend suite still agrees')
            .toBe(rendered);
    });

    it('refuses exactly the three malformed shapes and admits the rest', () => {
        for (const c of REF_CASES) {
            const problems = validateInputRef(c.ref);
            expect(problems.length > 0, c.name).toBe(Boolean(c.malformed));
        }
    });

    it('reproduces every refusal the Python gates built', () => {
        expect(fs.existsSync(PY_GATES_FIXTURE),
               'py-gates.refusals.json is missing — run the backend suite with '
               + 'UPDATE_PARITY_FIXTURES=1').toBe(true);
        const { cases } = JSON.parse(read(PY_GATES_FIXTURE));
        expect(cases.length).toBeGreaterThan(0);

        for (const c of cases) {
            let got = null;
            if (c.gate === 'organ_lock') {
                got = checkOrganLock(c.operation,
                                     { selectedOrgan: c.selected_organ, mode: c.mode });
            } else if (c.gate === 'inputs') {
                got = checkInputs(c.operation, c.refs || [], { forExecution: c.for_execution });
            } else if (c.gate === 'capability') {
                got = checkCapability(c.operation, { adapter: c.adapter, states: c.states });
            } else {
                throw new Error(`unknown gate "${c.gate}" in the Python fixture`);
            }
            if (c.refusal === null) {
                expect(got, c.name).toBeNull();
            } else {
                expect(got, c.name).not.toBeNull();
                expect(got.code, c.name).toBe(c.refusal.code);
                expect(got.message, c.name).toBe(c.refusal.message);
                expect(got.missing, c.name).toEqual(c.refusal.missing);
                expect(got.detail, c.name).toEqual(c.refusal.detail);
            }
        }
    });
});
