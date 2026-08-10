// PERCEPTUAL-ORGANS-002 Lane E — what leaves the laboratory is what was in it.
//
// The bundle is built from a REAL fixture-client session rather than from hand-written records,
// because the thing being checked is that a session this surface can actually produce survives
// the contract's own validators. A bundle assembled by hand would only prove that the builder can
// write valid JSON.

import { describe, it, expect } from 'vitest';
import { createFixtureClient } from './clients/fixtureClient';
import { buildExport, exportFilename, exportJson, verifyExport, EXPORT_KIND } from './exportSession';
import { SCHEMA_VERSION } from './contract/perceptionLabContract';

const AT = '2026-08-11T09:00:00.000Z';

/** Find, refine, review and file — a session with something of every kind in it. */
async function busySession(client = createFixtureClient()) {
    const session = await client.createSession({
        source_id: 'scene_instances', selected_organ: 'extent', mode: 'isolation' });
    const sid = session.session_id;

    const findPlan = await client.plan({ session_id: sid, planner: 'direct',
        operation: 'extent.find_all', parameters: {}, input_refs: [] });
    const found = await client.run({ session_id: sid, plan_id: findPlan.plan_id });
    const extentId = found.artifacts[0].identity.artifact_id;
    const instanceId = found.artifacts[0].measurement.payload.instances[0].instance_id;

    // The INSTANCE is selected too, not merely its set. Selecting an artifact means the whole
    // artifact; a step naming one mask inside it cites a reference the session has to have
    // declared, or "deselect that mask" would be a gesture with no effect.
    await client.select({ session_id: sid, artifact_ids: [extentId],
        active_artifact_id: extentId,
        selected_instance_refs: [{ artifact_id: extentId, instance_id: instanceId }] });

    const refinePlan = await client.plan({ session_id: sid, planner: 'direct',
        operation: 'extent.refine',
        parameters: { mode: 'add', points: [[0.3, 0.3]] },
        input_refs: [{ role: 'base', scope: 'session', artifact_id: extentId,
            instance_id: instanceId, region_id: null, geometry_rev: null }] });
    await client.run({ session_id: sid, plan_id: refinePlan.plan_id });

    // A refusal, so the bundle carries one. The organ moves FIRST — planning occlusion under the
    // Extent lock refuses at gate 1 and produces no artifact at all, which is a different (and
    // also correct) refusal from the one this bundle needs.
    await client.setOrgan({ session_id: sid, selected_organ: 'topology', mode: 'isolation' });
    const occlusionPlan = await client.plan({ session_id: sid, planner: 'direct',
        operation: 'topology.occlusion', parameters: {},
        input_refs: [
            { role: 'source', scope: 'session', artifact_id: extentId, instance_id: instanceId,
                region_id: null, geometry_rev: null },
            { role: 'target', scope: 'session', artifact_id: extentId, instance_id: instanceId,
                region_id: null, geometry_rev: null }],
        for_execution: false });
    await client.run({ session_id: sid, plan_id: occlusionPlan.plan_id });

    await client.review({ session_id: sid, artifact_id: extentId, verdict: 'partial',
        notes: 'two of these are the same thing',
        corrections: [{ field: 'instances[1]', was: 'separate', now: 'a duplicate of [0]',
            note: 'the adapter did not separate them' }] });
    await client.setLifecycle({ session_id: sid, artifact_id: extentId, status: 'kept' });

    const history = await client.history({ session_id: sid });
    return { client, sid, history, extentId };
}

const bundleOf = async () => {
    const { history } = await busySession();
    return buildExport({
        session: history.session,
        plans: history.plans,
        runs: history.runs,
        artifacts: history.artifacts,
        reviews: history.reviews,
        exported_at: AT,
        client_identity: 'FIXTURE',
    });
};

describe('a session this laboratory can produce survives the contract', () => {
    it('validates every record against Lane A’s own validators', async () => {
        expect(verifyExport(await bundleOf())).toEqual([]);
    });

    it('carries the refusals as artifacts rather than dropping them', async () => {
        const bundle = await bundleOf();
        expect(bundle.counts.refusals).toBeGreaterThan(0);
        expect(bundle.artifacts.some((a) => a.identity.artifact_kind === 'refusal')).toBe(true);
    });

    it('is byte-identical for two identical sessions, so two exports can be diffed', async () => {
        const a = await exportJson({ ...(await bundleOf()), exported_at: AT });
        const b = await exportJson({ ...(await bundleOf()), exported_at: AT });
        expect(a).toBe(b);
    });

    it('names the schema it speaks and the client it was taken from', async () => {
        const bundle = await bundleOf();
        expect(bundle.export_kind).toBe(EXPORT_KIND);
        expect(bundle.schema_version).toBe(SCHEMA_VERSION);
        expect(bundle.client_identity).toBe('FIXTURE');
    });
});

describe('the separations survive the round trip', () => {
    it('reviews stay separate records keyed by artifact_id', async () => {
        const bundle = await bundleOf();
        expect(bundle.reviews).toHaveLength(1);
        expect(bundle.reviews[0].artifact_id).toBeTruthy();
        for (const artifact of bundle.artifacts) {
            expect(artifact).not.toHaveProperty('review');
            expect(artifact).not.toHaveProperty('reviews');
            expect(artifact).not.toHaveProperty('verdict');
        }
    });

    it('a verdict recorded in the session did not move the lifecycle or the status', async () => {
        const { history, extentId } = await busySession();
        const artifact = history.artifacts.find((a) => a.identity.artifact_id === extentId);
        // `partial` was recorded and `kept` was set — separately, and neither is the other.
        expect(history.reviews[0].verdict).toBe('partial');
        expect(artifact.lifecycle.status).toBe('kept');
        expect(artifact.measurement.epistemic_status).toBe('measured');
        expect(artifact.lifecycle.changed_by).toBe('curator');
    });

    it('refuses to export an artifact that has acquired a verdict field', async () => {
        const bundle = await bundleOf();
        bundle.artifacts[0].verdict = 'correct';
        const problems = verifyExport(bundle);
        expect(problems.join(' ')).toMatch(/carries a verdict/);
        expect(problems.join(' ')).toMatch(/a property of the measurement/);
    });

    it('refuses to export a canonical claim that cites nothing', async () => {
        const bundle = await bundleOf();
        bundle.artifacts[0].identity.identity_scope = 'canonical';
        bundle.artifacts[0].identity.identity_refs = [];
        expect(verifyExport(bundle).join(' '))
            .toMatch(/may not mint an identity Semant does not hold/);
    });

    it('what the browser derived is segregated, never merged into the artifacts', async () => {
        const { history } = await busySession();
        const bundle = buildExport({
            session: history.session, plans: history.plans, runs: history.runs,
            artifacts: history.artifacts, reviews: history.reviews,
            derived: { projections: [{ relation_id: 'rel_1', derived: true,
                computed_by: 'lab_browser' }] },
            exported_at: AT,
        });
        expect(bundle.derived_in_browser.projections).toHaveLength(1);
        expect(bundle.derived_in_browser.what_this_is).toMatch(/None of it is a measurement/);
        // And the artifacts themselves are untouched by it.
        expect(JSON.stringify(bundle.artifacts)).not.toContain('lab_browser');
    });
});

describe('an export that would not survive re-import is not written', () => {
    it('throws with the sentences rather than writing a broken bundle', async () => {
        const { history } = await busySession();
        const broken = { ...history.artifacts[0] };
        delete broken.provenance;
        expect(() => exportJson({
            session: history.session, plans: history.plans, runs: history.runs,
            artifacts: [broken], reviews: [], exported_at: AT,
        })).toThrow(/does not hold the contract and will not be exported/);
    });

    it('will not export without a session', () => {
        expect(() => buildExport({ exported_at: AT })).toThrow(/no session to export/);
    });

    it('says so plainly: an export is a copy and promotes nothing', async () => {
        const bundle = await bundleOf();
        expect(bundle.what_this_is).toMatch(/none of it is in Semant/);
        expect(bundle.not_this.join(' ')).toMatch(/Not a promotion/);
        expect(bundle.not_this.join(' ')).toMatch(/No canonical id is minted here/);
    });
});

describe('the filename', () => {
    it('carries the session and the moment it left', async () => {
        const bundle = await bundleOf();
        const name = exportFilename(bundle.session, AT);
        expect(name).toContain(bundle.session.session_id);
        expect(name.endsWith('.json')).toBe(true);
        expect(name).not.toMatch(/[:]/);            // survives a filesystem
    });
});
