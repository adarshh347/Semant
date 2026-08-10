// PERCEPTUAL-ORGANS-002 Lane E — the client, the planners and the resolver.
//
// Everything the laboratory renders comes through here, so these tests are the ones that decide
// whether the DOM suites are testing anything. They are written against Lane A's validators: a
// record this client produces that the contract would refuse is a failure here, not a surprise
// in Lane F.

import { describe, it, expect } from 'vitest';
import {
    VALIDATORS, missingConsumedFields, isOrganEnabled, ENABLED_ORGAN_FAMILIES, ORGAN_FAMILIES,
} from '../contract/perceptionLabContract';
import {
    assertClientShape, assertNoPromotionSurface, assertUploadedSource, FORBIDDEN_CLIENT_METHODS,
} from './labClient';
import { createFixtureClient, decideOutcome, defaultCapabilityStates } from './fixtureClient';
import { availableOperations, conceptFrom, planFromPrompt } from '../planning';

const valid = (kind, record) => {
    const problems = VALIDATORS[kind](record);
    expect(problems, `${kind} problems: ${problems.join(' | ')}`).toEqual([]);
    expect(missingConsumedFields(kind, record)).toEqual([]);
};

async function openSession(client, {
    source_id = 'scene_controls', selected_organ = 'extent', mode = 'isolation' } = {}) {
    const session = await client.createSession({ source_id, selected_organ, mode });
    return session;
}

async function directRun(client, session, operation, parameters = {}, input_refs = [], opts = {}) {
    const plan = await client.plan({
        session_id: session.session_id, planner: 'direct', operation, parameters, input_refs,
        for_execution: true,
    });
    const out = await client.run({ session_id: session.session_id, plan_id: plan.plan_id,
        execution_identity: opts.execution_identity || 'FIXTURE' });
    return { plan, ...out };
}

describe('the client interface', () => {
    it('has every method the lab shell calls', () => {
        expect(() => assertClientShape(createFixtureClient())).not.toThrow();
    });

    it('exposes no promotion path — and the check catches one that is added', () => {
        expect(() => assertNoPromotionSurface(createFixtureClient())).not.toThrow();
        for (const forbidden of FORBIDDEN_CLIENT_METHODS) {
            const smuggled = { ...createFixtureClient(), [forbidden]: () => {} };
            expect(() => assertNoPromotionSurface(smuggled)).toThrow(/separate explicit human act/);
        }
    });

    it('says what it is, and that is not the badge on a run', async () => {
        const client = createFixtureClient();
        expect(client.identity()).toBe('FIXTURE');
        const session = await openSession(client);
        const { run } = await directRun(client, session, 'extent.find_all');
        expect(run.execution_identity).toBe('FIXTURE');
        const live = await directRun(client, session, 'extent.find_all', {}, [],
            { execution_identity: 'LIVE' });
        expect(live.run.execution_identity).toBe('LIVE');
    });
});

describe('the upload handoff', () => {
    it('an upload failure rejects — it never resolves as a success', async () => {
        const client = createFixtureClient({ uploadFails: true });
        await expect(client.uploadSource(new Blob())).rejects.toThrow(/did not complete/);
    });

    it('a source without a digest or dimensions is not an uploaded source', () => {
        expect(() => assertUploadedSource({ source: { id: 'x', photo_url: 'y' } }))
            .toThrow(/image_digest/);
        expect(() => assertUploadedSource({
            source: { id: 'x', photo_url: 'y', image_digest: 'd', natural_width: 0,
                natural_height: 0 },
        })).toThrow();
        expect(() => assertUploadedSource({ source: null })).toThrow();
    });

    it('a successful upload yields a source a session can be opened on', async () => {
        const client = createFixtureClient();
        const { source } = await client.uploadSource({ name: 'finial.jpg', size: 4096 });
        expect(source.image_digest).toMatch(/^sha256:/);
        const session = await client.createSession({
            source_id: source.id, selected_organ: 'extent', mode: 'isolation' });
        valid('LabSession', session);
        expect(session.source.image_digest).toBe(source.image_digest);
    });
});

describe('the organ lock', () => {
    it('only extent and topology are enabled, and the other six are still registered', () => {
        expect(ORGAN_FAMILIES).toHaveLength(8);
        expect(ENABLED_ORGAN_FAMILIES).toEqual(['extent', 'topology']);
        expect(ORGAN_FAMILIES.filter(isOrganEnabled)).toEqual(['extent', 'topology']);
    });

    it('a prompt cannot change the organ in isolation mode — it is refused, not dropped', async () => {
        const client = createFixtureClient();
        const session = await openSession(client, { selected_organ: 'extent' });
        const plan = await client.plan({
            session_id: session.session_id, planner: 'rules', prompt: 'do those two touch?' });
        valid('LabPlan', plan);
        expect(plan.resolved_steps).toEqual([]);
        expect(plan.refusals.map((r) => r.code)).toContain('organ_locked');
        expect(plan.refusals[0].remedy).toMatch(/chain mode/);
        // and the crossing proposal is still visible — a refusal shows what was refused
        expect(plan.proposed_steps[0].operation).toBe('topology.adjacency');
    });

    it('chain mode permits the crossing and demands confirmation', async () => {
        const client = createFixtureClient();
        const session = await openSession(client, { selected_organ: 'topology', mode: 'chain' });
        const findAll = await directRun(client, session, 'extent.find_all');
        expect(findAll.run.outcome).toBe('ready');
        const artifactId = findAll.artifacts[0].identity.artifact_id;
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct',
            operation: 'topology.adjacency',
            input_refs: [
                { role: 'source', scope: 'session', artifact_id: artifactId, region_id: null, geometry_rev: null },
                { role: 'target', scope: 'session', artifact_id: artifactId, region_id: null, geometry_rev: null },
            ],
            for_execution: true,
        });
        valid('LabPlan', plan);
        expect(plan.resolved_steps).toHaveLength(1);
    });
});

describe('the resolver — one gate for both arms', () => {
    it('drops an undeclared parameter and records it; clamps one that is out of bounds', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'extent.find_all',
            parameters: { max_instances: 900, mask_rle: { size: [2, 2], counts: [0, 4] } },
        });
        valid('LabPlan', plan);
        expect(plan.dropped_parameters).toEqual([{
            step_id: plan.proposed_steps[0].step_id,
            name: 'mask_rle',
            reason: "extent.find_all declares no parameter 'mask_rle'",
        }]);
        expect(plan.clamped_parameters[0]).toMatchObject({
            name: 'max_instances', requested: 900, applied: 64, bound: 'maximum=64' });
        expect(plan.resolved_steps[0].parameters).toEqual({ max_instances: 64 });
    });

    it('refuses a declared parameter of the wrong type rather than coercing it', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'extent.find_named',
            parameters: { concept: 42 } });
        expect(plan.resolved_steps).toEqual([]);
        expect(plan.refusals[0].code).toBe('invalid_parameters');
    });

    it('refuses an id the session never selected — language cannot mint an identity', async () => {
        const client = createFixtureClient();
        const session = await openSession(client, { selected_organ: 'topology' });
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'topology.adjacency',
            input_refs: [
                { role: 'source', scope: 'session', artifact_id: 'art_invented', region_id: null, geometry_rev: null },
                { role: 'target', scope: 'session', artifact_id: 'art_invented_2', region_id: null, geometry_rev: null },
            ],
        });
        expect(plan.refusals[0].code).toBe('unknown_reference');
        expect(plan.refusals[0].remedy).toMatch(/resolves through ids/);
    });

    it('refuses topology with no extents at all, as missing inputs and not as empty', async () => {
        const client = createFixtureClient();
        const session = await openSession(client, { selected_organ: 'topology' });
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'topology.adjacency',
            for_execution: true });
        expect(plan.refusals[0].code).toBe('missing_extent_inputs');
        const { run } = await client.run({ session_id: session.session_id, plan_id: plan.plan_id });
        valid('LabRun', run);
        expect(run.outcome).toBe('refused');
        expect(run.outcome).not.toBe('empty');
    });

    it('refuses an unavailable adapter as unavailable, not as empty', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'extent.find_named',
            parameters: { concept: 'drapery', adapter: 'sam3_concept' } });
        expect(plan.refusals[0].code).toBe('capability_unavailable');
        const { run } = await client.run({ session_id: session.session_id, plan_id: plan.plan_id });
        valid('LabRun', run);
        expect(run.outcome).toBe('unavailable');
        expect(run.refusals.some((r) => r.code === 'capability_unavailable')).toBe(true);
    });

    it('direct and prompt reach the same resolved step', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const direct = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'extent.find_named',
            parameters: { concept: 'drapery', adapter: 'grounded_sam' } });
        const prompted = await client.plan({
            session_id: session.session_id, planner: 'rules', prompt: 'find the drapery',
            parameters: { adapter: 'grounded_sam' } });
        expect(prompted.resolved_steps[0].operation).toBe(direct.resolved_steps[0].operation);
        expect(prompted.resolved_steps[0].parameters).toEqual(direct.resolved_steps[0].parameters);
        expect(prompted.resolved_steps[0].authorized_by).toBe('resolver');
        expect(direct.resolved_steps[0].authorized_by).toBe('resolver');
    });

    it('a model planner that is not reachable comes back as rules, saying what it fell back from', async () => {
        const client = createFixtureClient({ modelPlannerReachable: false });
        const session = await openSession(client);
        const plan = await client.plan({
            session_id: session.session_id, planner: 'model', prompt: 'mask every instance' });
        expect(plan.planner).toBe('rules');
        expect(plan.planner_fell_back_from).toBe('model');
        valid('LabPlan', plan);
    });

    it('a phrase outside the closed vocabulary proposes nothing and says why', () => {
        const out = planFromPrompt({ text: 'tell me about the artist', selectedOrgan: 'extent' });
        expect(out.proposals).toEqual([]);
        expect(out.note).toMatch(/does not guess/);
    });

    it('pulls a concept out of a phrase, and refuses to invent one', () => {
        expect(conceptFrom('find the drapery')).toBe('drapery');
        expect(conceptFrom('mask every face')).toBe('face');
        expect(conceptFrom('where is the left bar?')).toBe('left bar');
        expect(conceptFrom('find')).toBe(null);
    });
});

describe('extent operations', () => {
    it('find_all produces a measured extent_set with real masks', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const { run, artifacts } = await directRun(client, session, 'extent.find_all');
        valid('LabRun', run);
        expect(run.outcome).toBe('ready');
        const art = artifacts[0];
        valid('PerceptualArtifact', art);
        expect(art.measurement.epistemic_status).toBe('measured');
        expect(art.measurement.epistemic_basis).toBe('mask');
        expect(art.measurement.payload.instances.length).toBe(7);
        expect(art.measurement.payload.instances[0].mask_rle.counts.length).toBeGreaterThan(1);
        expect(art.measurement.payload.searched).toBe('every separable instance');
    });

    it('an absent concept comes back EMPTY, with what was searched for', async () => {
        const client = createFixtureClient();
        const session = await openSession(client, { source_id: 'scene_absent' });
        const { run, artifacts } = await directRun(client, session, 'extent.find_named',
            { concept: 'face', adapter: 'grounded_sam' });
        valid('LabRun', run);
        expect(run.outcome).toBe('empty');
        expect(artifacts[0].measurement.payload.searched).toBe('face');
        expect(artifacts[0].measurement.payload.instances).toEqual([]);
        expect(artifacts[0].projection.projection_kind).toBe('none');
        expect(artifacts[0].interpretation.notes).toMatch(/is not in this picture/);
    });

    it('a drawn extent is VISIBLE on a manual basis — never measured', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const { artifacts } = await directRun(client, session, 'extent.draw', {
            tool: 'polygon',
            polygon: [[0.2, 0.2], [0.5, 0.2], [0.5, 0.6], [0.2, 0.6]],
        });
        const art = artifacts[0];
        valid('PerceptualArtifact', art);
        expect(art.measurement.epistemic_status).toBe('visible');
        expect(art.measurement.epistemic_basis).toBe('manual');
        expect(art.provenance.producer_kind).toBe('human');
        expect(art.provenance.adapter).toBe(null);
    });

    it('a refinement keeps the identity and moves the revision', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const first = await directRun(client, session, 'extent.find_all');
        const baseId = first.artifacts[0].identity.artifact_id;
        const baseInstance = first.artifacts[0].measurement.payload.instances[0];
        await client.select({ session_id: session.session_id, artifact_ids: [baseId] });
        const refined = await directRun(client, session, 'extent.refine',
            { mode: 'add', box: { x: 0.05, y: 0.62, w: 0.2, h: 0.1 } },
            [{ role: 'base', scope: 'session', artifact_id: baseId, region_id: null, geometry_rev: null }]);
        const out = refined.artifacts[0];
        valid('PerceptualArtifact', out);
        expect(out.measurement.payload.instances[0].instance_id).toBe(baseInstance.instance_id);
        expect(out.identity.derived_from).toEqual([baseId]);
        expect(out.projection.projection_kind).toBe('before_after');
    });

    it('a low-confidence name is withheld while the geometry survives', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const { artifacts } = await directRun(client, session, 'extent.find_all');
        const instances = artifacts[0].measurement.payload.instances;
        const unnamed = instances.filter((i) => i.naming === null);
        expect(unnamed.length).toBeGreaterThan(0);
        for (const i of unnamed) expect(i.mask_rle).toBeTruthy();
        for (const i of instances) {
            if (i.naming) expect(i.naming.epistemic_status).toBe('interpretive');
        }
    });

    it('duplicates are reported and both instances are kept', async () => {
        const client = createFixtureClient();
        const session = await openSession(client, { source_id: 'scene_instances' });
        const { artifacts } = await directRun(client, session, 'extent.find_all');
        const payload = artifacts[0].measurement.payload;
        expect(payload.duplicates.length).toBeGreaterThan(0);
        const flagged = payload.duplicates[0].instance_ids;
        for (const id of flagged) {
            expect(payload.instances.some((i) => i.instance_id === id)).toBe(true);
        }
    });

    it('compare corresponds two sets and says what only one of them saw', async () => {
        const client = createFixtureClient();
        const session = await openSession(client, { source_id: 'scene_instances' });
        const left = await directRun(client, session, 'extent.find_all');
        const right = await directRun(client, session, 'extent.find_named',
            { concept: 'drapery', adapter: 'grounded_sam' });
        const ids = [left.artifacts[0].identity.artifact_id, right.artifacts[0].identity.artifact_id];
        await client.select({ session_id: session.session_id, artifact_ids: ids });
        const { artifacts } = await directRun(client, session, 'extent.compare', {}, [
            { role: 'left', scope: 'session', artifact_id: ids[0], region_id: null, geometry_rev: null },
            { role: 'right', scope: 'session', artifact_id: ids[1], region_id: null, geometry_rev: null },
        ]);
        const comparison = artifacts[0].measurement.payload.comparison;
        expect(comparison.left_artifact_id).toBe(ids[0]);
        expect(comparison.correspondences.length).toBeGreaterThan(0);
        expect(comparison.only_in_left.length).toBeGreaterThan(0);
        expect(artifacts[0].projection.projection_kind).toBe('ab_overlay');
    });
});

describe('topology operations', () => {
    const prepare = async (client, source_id = 'scene_controls') => {
        const session = await openSession(client, { source_id, selected_organ: 'extent' });
        const { artifacts } = await directRun(client, session, 'extent.find_all');
        const artifactId = artifacts[0].identity.artifact_id;
        await client.select({ session_id: session.session_id, artifact_ids: [artifactId] });
        await client.setOrgan({ session_id: session.session_id, selected_organ: 'topology' });
        return { session, artifactId, extent: artifacts[0] };
    };
    const pair = (artifactId) => ([
        { role: 'source', scope: 'session', artifact_id: artifactId, region_id: null, geometry_rev: null },
        { role: 'target', scope: 'session', artifact_id: artifactId, region_id: null, geometry_rev: null },
    ]);

    it('containment finds the square inside the field, directed and mask-based', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const { run, artifacts } = await directRun(client, session, 'topology.containment', {},
            pair(artifactId));
        valid('LabRun', run);
        const payload = artifacts[0].measurement.payload;
        expect(payload.pairs_examined).toBeGreaterThan(0);
        const nested = payload.relations.find((r) => r.kind === 'nested_within');
        expect(nested).toBeTruthy();
        expect(nested.directed).toBe(true);
        expect(nested.basis).toBe('mask');
        expect(nested.epistemic_status).toBe('measured');
        expect(nested.measurements.containment).toBeGreaterThan(0.94);
    });

    it('a BOX basis containment stays interpretive however confident the number is', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const { artifacts } = await directRun(client, session, 'topology.containment',
            { basis: 'box' }, pair(artifactId));
        const art = artifacts[0];
        valid('PerceptualArtifact', art);
        expect(art.measurement.epistemic_basis).toBe('box');
        expect(art.measurement.epistemic_status).toBe('interpretive');
        for (const r of art.measurement.payload.relations) {
            expect(r.basis).toBe('box');
            expect(r.epistemic_status).toBe('interpretive');
        }
        expect(art.measurement.basis_detail).toMatch(/WAVE2\.5/);
    });

    it('adjacency reports the contact band, and an undirected relation is undirected', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const { artifacts } = await directRun(client, session, 'topology.adjacency',
            { contact_tolerance_px: 1 }, pair(artifactId));
        const relations = artifacts[0].measurement.payload.relations;
        const meets = relations.filter((r) => r.kind === 'meets');
        expect(meets.length).toBeGreaterThan(0);
        for (const r of relations) {
            expect(r.directed).toBe(false);
            expect(typeof r.measurements.contact_pixels).toBe('number');
            expect(r.measurements.contact_tolerance_px).toBe(1);
        }
    });

    it('a disjoint relation is a POSITIVE finding with a distance, not an empty result', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const { run, artifacts } = await directRun(client, session, 'topology.disjoint', {},
            pair(artifactId));
        expect(run.outcome).toBe('ready');
        const disjoint = artifacts[0].measurement.payload.relations.filter((r) => r.kind === 'disjoint');
        expect(disjoint.length).toBeGreaterThan(0);
        expect(disjoint[0].measurements.separation_px).toBeGreaterThan(0);
    });

    it('overlap is exact and never allows a box basis', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const { artifacts } = await directRun(client, session, 'topology.overlap', {},
            pair(artifactId));
        const overlaps = artifacts[0].measurement.payload.relations.filter((r) => r.kind === 'overlaps');
        expect(overlaps.length).toBeGreaterThan(0);
        for (const r of artifacts[0].measurement.payload.relations) expect(r.basis).toBe('mask');
        // `topology.overlap` declares NO parameters, so a basis cannot even be asked for: it is
        // dropped and recorded. An intersection of two boxes is an intersection of two boxes.
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'topology.overlap',
            parameters: { basis: 'box' }, input_refs: pair(artifactId) });
        expect(plan.dropped_parameters[0]).toMatchObject({
            name: 'basis', reason: "topology.overlap declares no parameter 'basis'" });
        expect(plan.resolved_steps[0].parameters).toEqual({});
    });

    it('negative space measures the complement and keeps the field behind a ref', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const { artifacts } = await directRun(client, session, 'topology.negative_space',
            { max_distance: 0.25 },
            [{ role: 'figure', scope: 'session', artifact_id: artifactId, region_id: null, geometry_rev: null }]);
        const art = artifacts[0];
        valid('PerceptualArtifact', art);
        expect(art.identity.artifact_kind).toBe('negative_space_field');
        expect(art.measurement.payload.field_ref.digest).toMatch(/^sha256:/);
        expect(art.measurement.payload.statistics.max).toBeLessThanOrEqual(0.25);
        expect(art.projection.projection_kind).toBe('scalar_wash');
    });

    it('all pairs needs at least two member sets, and refuses with one', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'topology.all_pairs',
            input_refs: [{ role: 'members', scope: 'session', artifact_id: artifactId,
                region_id: null, geometry_rev: null }] });
        expect(plan.refusals[0].code).toBe('missing_extent_inputs');
        expect(plan.refusals[0].message).toMatch(/at least 2 members/);
    });

    it('all pairs is bounded, and says what it was bounded to', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        await client.setOrgan({ session_id: session.session_id, selected_organ: 'extent' });
        const second = await directRun(client, session, 'extent.find_named',
            { concept: 'left bar', adapter: 'grounded_sam' });
        const secondId = second.artifacts[0].identity.artifact_id;
        await client.select({ session_id: session.session_id,
            artifact_ids: [artifactId, secondId] });
        await client.setOrgan({ session_id: session.session_id, selected_organ: 'topology' });
        const { artifacts } = await directRun(client, session, 'topology.all_pairs',
            { max_regions: 4 }, [
                { role: 'members', scope: 'session', artifact_id: artifactId, region_id: null, geometry_rev: null },
                { role: 'members', scope: 'session', artifact_id: secondId, region_id: null, geometry_rev: null },
            ]);
        const payload = artifacts[0].measurement.payload;
        expect(payload.bounded_to).toBe(4);
        expect(payload.pairs_examined).toBe(6);      // 4 choose 2, the bound doing its work
        expect(artifacts[0].projection.projection_kind).toBe('relation_graph');
    });

    it('occlusion refuses for want of a depth field, and the refusal is an artifact', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const plan = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'topology.occlusion',
            input_refs: pair(artifactId), for_execution: true });
        expect(plan.refusals[0].code).toBe('missing_depth_artifact');
        expect(plan.resolved_steps).toEqual([]);
        const { run } = await client.run({ session_id: session.session_id, plan_id: plan.plan_id });
        valid('LabRun', run);
        expect(run.outcome).toBe('refused');
    });

    it('occlusion is plannable without depth and unrunnable without it', async () => {
        const client = createFixtureClient();
        const { session, artifactId } = await prepare(client);
        const composing = await client.plan({
            session_id: session.session_id, planner: 'direct', operation: 'topology.occlusion',
            input_refs: pair(artifactId), for_execution: false });
        expect(composing.refusals).toEqual([]);
        expect(composing.resolved_steps).toHaveLength(1);
        expect(composing.requires_confirmation).toBe(true);
        // and running that plan still refuses, at the step
        const { run } = await client.run({ session_id: session.session_id,
            plan_id: composing.plan_id });
        expect(run.outcome).toBe('refused');
        expect(run.refusals[0].code).toBe('missing_depth_artifact');
        expect(run.stage_attempts[0].invoked).toBe(false);
    });
});

describe('replay', () => {
    it('re-serves the recorded artifacts and calls nothing', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const first = await directRun(client, session, 'extent.find_all');
        const again = await client.replay({ session_id: session.session_id,
            run_id: first.run.run_id });
        valid('LabRun', again.run);
        expect(again.run.execution_identity).toBe('REPLAY');
        expect(again.run.replay.adapter_callable).toBe(false);
        expect(again.run.replay.source_run_id).toBe(first.run.run_id);
        expect(again.run.stage_attempts.every((a) => a.invoked === false)).toBe(true);
        expect(again.artifacts).toEqual(first.artifacts);
        // the recorded duration and the reading of it are different numbers
        expect(again.run.duration_ms).not.toBe(first.run.duration_ms);
    });

    it('a replay that DID invoke fails the contract — the guard is real', async () => {
        const client = createFixtureClient({ mutateReplayToRecompute: true });
        const session = await openSession(client);
        const first = await directRun(client, session, 'extent.find_all');
        await expect(client.replay({ session_id: session.session_id, run_id: first.run.run_id }))
            .rejects.toThrow(/Only LIVE may call an adapter/);
    });
});

describe('outcomes', () => {
    it('a failing adapter is FAILED and makes no claim about the image', async () => {
        const client = createFixtureClient({ failOperations: ['extent.find_all'] });
        const session = await openSession(client);
        const { run, artifacts } = await directRun(client, session, 'extent.find_all');
        valid('LabRun', run);
        expect(run.outcome).toBe('failed');
        expect(artifacts).toEqual([]);
        expect(run.duration_ms).toBe(null);
        expect(run.completed_at).toBe(null);
    });

    it('decideOutcome keeps the five nothings apart', () => {
        const base = { resolved: 1, planRefusals: 0, refusals: [], anyEmpty: false,
            anyFailed: false, anyCompleted: true, artifacts: [{}] };
        expect(decideOutcome(base)).toBe('ready');
        expect(decideOutcome({ ...base, anyCompleted: false, anyEmpty: true, artifacts: [{}] }))
            .toBe('empty');
        expect(decideOutcome({ ...base, resolved: 0, planRefusals: 1,
            refusals: [{ code: 'organ_locked' }] })).toBe('refused');
        expect(decideOutcome({ ...base, resolved: 0, planRefusals: 1,
            refusals: [{ code: 'capability_unavailable' }] })).toBe('unavailable');
        expect(decideOutcome({ ...base, anyFailed: true, anyCompleted: false })).toBe('failed');
        expect(decideOutcome({ ...base, anyFailed: true, anyCompleted: true })).toBe('partial');
        expect(decideOutcome({ ...base, refusals: [{ code: 'missing_extent_inputs' }] }))
            .toBe('partial');
    });

    it('the source digest is identical either side of every run', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        for (const op of ['extent.find_all', 'extent.draw']) {
            const { run } = await directRun(client, session, op, op === 'extent.draw'
                ? { tool: 'mask_brush', polygon: [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]] } : {});
            expect(run.source_digest_after).toBe(run.source_digest_before);
            expect(run.source_digest_before).toBe(session.source.image_digest);
        }
    });
});

describe('review and lifecycle are different axes', () => {
    it('a verdict changes no lifecycle and no epistemic status', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const { artifacts } = await directRun(client, session, 'extent.find_all');
        const id = artifacts[0].identity.artifact_id;
        const before = (await client.history({ session_id: session.session_id }))
            .artifacts.find((a) => a.identity.artifact_id === id);
        const review = await client.review({ session_id: session.session_id, artifact_id: id,
            verdict: 'correct', notes: 'both instances are what I meant' });
        valid('LabReview', review);
        const after = (await client.history({ session_id: session.session_id }))
            .artifacts.find((a) => a.identity.artifact_id === id);
        expect(after).toEqual(before);
        expect(after.lifecycle.status).toBe('proposed');
        expect(after.measurement.epistemic_status).toBe('measured');
        expect('verdict' in after).toBe(false);
        expect('review' in after).toBe(false);
    });

    it('a lifecycle change moves nothing else', async () => {
        const client = createFixtureClient();
        const session = await openSession(client);
        const { artifacts } = await directRun(client, session, 'extent.find_all');
        const id = artifacts[0].identity.artifact_id;
        const kept = await client.setLifecycle({ session_id: session.session_id, artifact_id: id,
            status: 'kept' });
        expect(kept.lifecycle.status).toBe('kept');
        expect(kept.measurement).toEqual(artifacts[0].measurement);
        expect(kept.identity.identity_scope).toBe('session');    // kept is not canonical
    });
});

describe('what a person can reach', () => {
    it('every operation of the selected organ is offered, with a reason for any that is closed', () => {
        const states = defaultCapabilityStates();
        const ops = availableOperations({ selectedOrgan: 'extent', mode: 'isolation',
            capabilityStates: states });
        expect(ops.map((o) => o.key)).toEqual([
            'extent.find_all', 'extent.find_named', 'extent.refine', 'extent.draw',
            'extent.reuse', 'extent.compare']);
        for (const op of ops) {
            if (!op.enabled) expect(op.refusal.message).toBeTruthy();
        }
        const topology = availableOperations({ selectedOrgan: 'extent', mode: 'chain',
            capabilityStates: states });
        expect(topology.some((o) => o.organ === 'topology')).toBe(true);
    });

    it('an adapter that is not running closes its operation with a sentence, not a silence', () => {
        const ops = availableOperations({
            selectedOrgan: 'extent', mode: 'isolation',
            capabilityStates: { ...defaultCapabilityStates(), grounded_sam: 'unavailable' } });
        const named = ops.find((o) => o.key === 'extent.find_named');
        expect(named.enabled).toBe(false);
        expect(named.refusal.code).toBe('capability_unavailable');
        expect(named.refusal.message).toMatch(/not running here/);
    });
});

describe('"that mask" reaches one instance, and deselection takes it away', () => {
    /** Find several extents, then narrow the selection to one of them. */
    async function narrowed(client = createFixtureClient()) {
        const session = await openSession(client, { source_id: 'scene_instances' });
        const sid = session.session_id;
        const plan = await client.plan({ session_id: sid, planner: 'direct',
            operation: 'extent.find_all', parameters: {}, input_refs: [] });
        const found = await client.run({ session_id: sid, plan_id: plan.plan_id });
        const artifact = found.artifacts[0];
        const [first, second] = artifact.measurement.payload.instances;
        const artifact_id = artifact.identity.artifact_id;
        await client.select({ session_id: sid, artifact_ids: [artifact_id],
            active_artifact_id: artifact_id,
            selected_instance_refs: [{ artifact_id, instance_id: second.instance_id }] });
        return { client, sid, artifact_id, first, second };
    }

    it('binds the selected instance, not its set, for a follow-up phrase', async () => {
        const { client, sid, artifact_id, second } = await narrowed();
        const plan = await client.plan({ session_id: sid, planner: 'rules',
            prompt: 'refine that', for_execution: false });
        expect(plan.proposed_steps[0].input_refs[0]).toMatchObject({
            artifact_id, instance_id: second.instance_id });
    });

    it('asks a pair question about two masks inside ONE set', async () => {
        const { client, sid, artifact_id, first, second } = await narrowed();
        await client.select({ session_id: sid, artifact_ids: [artifact_id],
            active_artifact_id: artifact_id,
            selected_instance_refs: [
                { artifact_id, instance_id: first.instance_id },
                { artifact_id, instance_id: second.instance_id }] });
        await client.setOrgan({ session_id: sid, selected_organ: 'topology', mode: 'isolation' });
        const plan = await client.plan({ session_id: sid, planner: 'rules',
            prompt: 'do those two touch?', for_execution: false });
        const refs = plan.proposed_steps[0].input_refs;
        // The question A2 made askable at all. Before it, both endpoints had to be whole sets and
        // the run measured every cross pair while the surface pretended one of them was asked.
        expect(refs.map((r) => r.instance_id))
            .toEqual([first.instance_id, second.instance_id]);
        expect(new Set(refs.map((r) => r.artifact_id))).toEqual(new Set([artifact_id]));
    });

    it('widens back to the whole set when the instance is deselected', async () => {
        const { client, sid, artifact_id } = await narrowed();
        await client.select({ session_id: sid, artifact_ids: [artifact_id],
            active_artifact_id: artifact_id, selected_instance_refs: [] });
        const plan = await client.plan({ session_id: sid, planner: 'rules',
            prompt: 'refine that', for_execution: false });
        expect(plan.proposed_steps[0].input_refs[0].instance_id).toBeNull();
    });

    it('drops the instance when its artifact leaves the selection', async () => {
        const { client, sid } = await narrowed();
        const session = await client.select({ session_id: sid, artifact_ids: [],
            active_artifact_id: null });
        expect(session.selected_instance_refs).toEqual([]);
        valid('LabSession', session);
    });

    it('refuses an instance the session never declared, naming artifact#instance', async () => {
        const { client, sid, artifact_id, first } = await narrowed();
        const plan = await client.plan({ session_id: sid, planner: 'direct',
            operation: 'extent.refine', parameters: { mode: 'add', points: [[0.4, 0.4]] },
            input_refs: [{ role: 'base', scope: 'session', artifact_id,
                instance_id: first.instance_id, region_id: null, geometry_rev: null }],
            for_execution: false });
        expect(plan.resolved_steps).toHaveLength(0);
        expect(plan.refusals[0].code).toBe('unknown_reference');
        expect(plan.refusals[0].missing)
            .toEqual([`${artifact_id}#${first.instance_id}`]);
    });

    it('refuses a malformed reference rather than reading past it', async () => {
        const { client, sid, artifact_id } = await narrowed();
        const plan = await client.plan({ session_id: sid, planner: 'direct',
            operation: 'extent.reuse', parameters: {},
            input_refs: [{ role: 'regions', scope: 'canonical', artifact_id: null,
                instance_id: 'inst_2', region_id: 'reg_7', geometry_rev: 3 }],
            for_execution: false });
        expect(plan.resolved_steps).toHaveLength(0);
        expect(plan.refusals[0].code).toBe('invalid_parameters');
        expect(plan.refusals[0].detail.problems.join(' '))
            .toMatch(/second geometry wearing one id/);
        expect(artifact_id).toBeTruthy();
    });
});
