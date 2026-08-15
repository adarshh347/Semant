// PERCEPTUAL-ORGANS-002 Lane F2 — the live client, against the records the backend actually sends.
//
// THE RESPONSES HERE ARE NOT INVENTED. Every session, plan, run, artifact and review this fake
// backend answers with is a file out of `contracts/fixtures/perception-lab/`, which
// `backend/tests/test_perception_lab_contracts.py` loads through the Pydantic models and
// `perceptionLab.parity.test.js` loads through the JavaScript validators. So "the client reads
// what the backend sends" is checked against the one set of records both runtimes are held to,
// rather than against a shape somebody typed into a test file to make it pass.
//
// The manifest's own coverage line is what makes this worth doing: all six run outcomes, all three
// execution identities, all four payload variants. Every one of them goes through this client.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import sessionRecord from '../../../../contracts/fixtures/perception-lab/session.extent-isolation.json';
import chainSession from '../../../../contracts/fixtures/perception-lab/session.topology-chain.json';
import planRecord from '../../../../contracts/fixtures/perception-lab/plan.direct-extent-find-all.json';
import runReady from '../../../../contracts/fixtures/perception-lab/run.live-ready.json';
import runEmpty from '../../../../contracts/fixtures/perception-lab/run.live-empty.json';
import runUnavailable from '../../../../contracts/fixtures/perception-lab/run.live-unavailable.json';
import runRefused from '../../../../contracts/fixtures/perception-lab/run.live-refused-missing-depth.json';
import runPartial from '../../../../contracts/fixtures/perception-lab/run.live-partial.json';
import runFailed from '../../../../contracts/fixtures/perception-lab/run.live-failed.json';
import runReplay from '../../../../contracts/fixtures/perception-lab/run.replay-extent.json';
import runFixture from '../../../../contracts/fixtures/perception-lab/run.fixture-topology.json';
import extentSet from '../../../../contracts/fixtures/perception-lab/artifact.extent-set.json';
import relationSet from '../../../../contracts/fixtures/perception-lab/artifact.topology-relation-set.json';
import negativeSpace from '../../../../contracts/fixtures/perception-lab/artifact.negative-space-field.json';
import refusalArtifact from '../../../../contracts/fixtures/perception-lab/artifact.refusal-missing-depth.json';
import reviewRecord from '../../../../contracts/fixtures/perception-lab/review.correct.json';
import { createHttpLabClient, LabRequestError, ConfirmationRequired } from './httpClient';
import { assertClientShape, REQUIRED_CLIENT_METHODS } from './labClient';

const BASE = 'http://backend.test/api/v1/perception-lab';
const POSTS = 'http://backend.test/api/v1/posts';

const SOURCE = {
    id: '64b7f1a2c3d4e5f60718293a',
    post_id: '64b7f1a2c3d4e5f60718293a',
    origin: 'post',
    title: 'a fixture picture',
    photo_url: 'https://example.invalid/fixture.png',
    image_digest: 'sha256:5a3d47eb1e2e61fb017decccc9d3349067ea72902584a9f4eda850a66cb442ab',
    natural_width: 64,
    natural_height: 48,
    region_count: 2,
};

/**
 * A fake backend that answers URLs, records what it was sent, and can be told to fail.
 *
 * Deliberately a fetch stub rather than a mocked client: what is under test is the wire — the
 * paths, the bodies, the status codes and the unwrapping — and a mocked client would test nothing
 * but the mock.
 */
function backend(routes = {}) {
    const calls = [];
    const impl = async (url, init = {}) => {
        const method = init.method || 'GET';
        const path = String(url).replace(BASE, '').replace(POSTS, 'POSTS');
        const body = init.body && typeof init.body === 'string' ? JSON.parse(init.body) : init.body;
        calls.push({ method, path, body, url: String(url) });
        const key = `${method} ${path}`;
        const route = routes[key] ?? routes[path];
        if (route === undefined) {
            return response(404, { detail: { error: 'no_route', why: `${key} is not stubbed` } });
        }
        return typeof route === 'function' ? route({ method, path, body }) : response(200, route);
    };
    impl.calls = calls;
    impl.sent = (needle) => calls.find((c) => `${c.method} ${c.path}` === needle
        || c.path === needle);
    return impl;
}

const response = (status, payload) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => payload,
});

const envelope = (identity, body) => ({ execution_identity: identity, ...body });

const client = (routes) => createHttpLabClient({
    baseUrl: BASE, postsUrl: POSTS, fetchImpl: backend(routes),
});

const withFetch = (routes) => {
    const impl = backend(routes);
    return [createHttpLabClient({ baseUrl: BASE, postsUrl: POSTS, fetchImpl: impl }), impl];
};


// ── the interface ────────────────────────────────────────────────────────────

describe('the live client is the client the laboratory was written against', () => {
    it('satisfies the whole interface, including the negative half', () => {
        expect(() => assertClientShape(client({}))).not.toThrow();
        for (const method of REQUIRED_CLIENT_METHODS) {
            expect(typeof client({})[method]).toBe('function');
        }
    });

    it('is LIVE, and there is no argument that makes it anything else', () => {
        expect(client({}).identity()).toBe('LIVE');
        expect(createHttpLabClient({ baseUrl: BASE, fetchImpl: backend({}) }).identity()).toBe('LIVE');
    });

    it('has no promotion surface', () => {
        const c = client({});
        for (const forbidden of ['promote', 'commit', 'save', 'acceptAll', 'writeRegion']) {
            expect(forbidden in c).toBe(false);
        }
    });
});


// ── real response parity ─────────────────────────────────────────────────────

describe('every record the backend sends is read as the contract holds it', () => {
    it('reads a session out of its envelope', async () => {
        const [c, impl] = withFetch({
            'POST /sessions': envelope('LIVE', { session: sessionRecord, source: SOURCE }),
        });
        const session = await c.createSession({
            source_id: SOURCE.post_id, selected_organ: 'extent', mode: 'isolation' });

        expect(session).toEqual(sessionRecord);
        // A `source_id` IS a `post_id`. No second image identity crosses this wire.
        expect(impl.sent('POST /sessions').body).toEqual({
            post_id: SOURCE.post_id, selected_organ: 'extent', mode: 'isolation' });
    });

    it('reads a whole history and validates all five record types on the way in', async () => {
        const c = client({
            'GET /sessions/labs_x/history': envelope('LIVE', {
                session: sessionRecord,
                plans: [planRecord],
                runs: [runReady, runPartial],
                artifacts: [extentSet, relationSet, negativeSpace, refusalArtifact],
                reviews: [reviewRecord],
            }),
        });
        const history = await c.history({ session_id: 'labs_x' });

        expect(history.session).toEqual(sessionRecord);
        expect(history.plans).toHaveLength(1);
        expect(history.runs.map((r) => r.outcome)).toEqual(['ready', 'partial']);
        // All four payload variants, straight from the committed records.
        expect(history.artifacts.map((a) => a.measurement.payload_variant)).toEqual([
            'extent_set', 'topology_relation_set', 'negative_space_field', 'refusal']);
        expect(history.reviews[0].verdict).toBe('correct');
    });

    it.each([
        ['ready', runReady], ['empty', runEmpty], ['unavailable', runUnavailable],
        ['refused', runRefused], ['partial', runPartial], ['failed', runFailed],
    ])('carries the %s outcome through untouched', async (outcome, record) => {
        const c = client({
            'POST /sessions/labs_x/runs': envelope('LIVE', {
                run: record, artifacts: [], response: { lines: [], text: '' },
                source_unchanged: true }),
        });
        const out = await c.run({ session_id: 'labs_x', plan_id: 'plan_1' });

        expect(out.run.outcome).toBe(outcome);
        expect(out.run).toEqual(record);
        expect(out.source_unchanged).toBe(true);
    });

    it.each([
        ['LIVE', runReady], ['REPLAY', runReplay], ['FIXTURE', runFixture],
    ])('carries the %s identity through untouched, whatever the client is', async (id, record) => {
        const c = client({
            'POST /sessions/labs_x/runs': envelope('LIVE', { run: record, artifacts: [] }),
        });
        const out = await c.run({ session_id: 'labs_x', plan_id: 'plan_1' });

        // The client is LIVE and the RUN may be anything. Two questions, and this client answers
        // only the first — the badge on a run is the run's own field.
        expect(c.identity()).toBe('LIVE');
        expect(out.run.execution_identity).toBe(id);
    });

    it('refuses a record whose vocabulary this browser does not know, at the boundary', async () => {
        const c = client({
            'POST /sessions/labs_x/runs': envelope('LIVE', {
                run: { ...runReady, outcome: 'mostly_fine' }, artifacts: [] }),
        });
        await expect(c.run({ session_id: 'labs_x', plan_id: 'plan_1' }))
            .rejects.toThrow(/does not hold the contract/);
    });

    it('names the law that was broken rather than saying the shape was wrong', async () => {
        const c = client({
            'POST /sessions/labs_x/runs': envelope('LIVE', {
                run: { ...runReady, execution_identity: 'SORT_OF_LIVE' }, artifacts: [] }),
        });
        await expect(c.run({ session_id: 'labs_x', plan_id: 'plan_1' }))
            .rejects.toThrow(/unknown execution identity "SORT_OF_LIVE"/);
    });
});


// ── the selected instance, over the wire and back ────────────────────────────

describe('a selected instance survives the wire', () => {
    it('sends artifact/instance PAIRS and nothing else', async () => {
        const [c, impl] = withFetch({
            'PATCH /sessions/labs_x': envelope('LIVE', { session: sessionRecord }),
        });
        await c.select({
            session_id: 'labs_x',
            artifact_ids: ['art_a', 'art_b'],
            active_artifact_id: 'art_a',
            selected_instance_refs: [
                { artifact_id: 'art_a', instance_id: 'inst_2', stray: 'not sent' }],
        });

        expect(impl.sent('PATCH /sessions/labs_x').body).toEqual({
            selected_artifact_ids: ['art_a', 'art_b'],
            selected_instance_refs: [{ artifact_id: 'art_a', instance_id: 'inst_2' }],
            active_artifact_id: 'art_a',
        });
    });

    it('turns a cleared active artifact into its own flag, not into an absent key', async () => {
        const [c, impl] = withFetch({
            'PATCH /sessions/labs_x': envelope('LIVE', { session: sessionRecord }),
        });
        await c.select({ session_id: 'labs_x', artifact_ids: [], active_artifact_id: null });

        // `null` and "absent" are the same thing in JSON and two different acts to a person.
        const body = impl.sent('PATCH /sessions/labs_x').body;
        expect(body.clear_active).toBe(true);
        expect('active_artifact_id' in body).toBe(false);
    });

    it('leaves the active artifact alone when the caller said nothing about it', async () => {
        const [c, impl] = withFetch({
            'PATCH /sessions/labs_x': envelope('LIVE', { session: sessionRecord }),
        });
        await c.select({ session_id: 'labs_x', artifact_ids: ['art_a'] });

        const body = impl.sent('PATCH /sessions/labs_x').body;
        expect(body).toEqual({ selected_artifact_ids: ['art_a'] });
    });

    it('sends a Direct command as a command and a prompt as a sentence', async () => {
        const [c, impl] = withFetch({
            'POST /sessions/labs_x/plans': envelope('LIVE', { plan: planRecord }),
        });
        await c.plan({
            session_id: 'labs_x', planner: 'direct', operation: 'extent.refine',
            parameters: { mode: 'add' },
            input_refs: [{ role: 'base', scope: 'session', artifact_id: 'art_a',
                instance_id: 'inst_2' }],
            references: [{ artifact_id: 'art_a', instance_id: 'inst_2' }],
        });

        const body = impl.sent('POST /sessions/labs_x/plans').body;
        expect(body.commands[0].input_refs[0].instance_id).toBe('inst_2');
        // THE BROWSER'S `references` LIST IS NOT SENT. The backend derives what a follow-up may
        // mean from the session it holds; a list posted from here could widen it.
        expect('references' in body).toBe(false);
        expect('for_execution' in body).toBe(false);
    });
});


// ── refusals are answers; errors are errors ──────────────────────────────────

describe('what comes back when the laboratory says no', () => {
    it('a plan carrying only refusals is a plan, not a thrown error', async () => {
        const refusedPlan = {
            ...planRecord,
            resolved_steps: [],
            refusals: [{
                code: 'unknown_reference', organ: 'topology', operation: 'topology.containment',
                message: 'art_9#inst_3 is not a selected or active reference in this session.',
                missing: ['art_9#inst_3'], remedy: 'select the artifact first', detail: {},
            }],
        };
        const c = client({ 'POST /sessions/labs_x/plans': envelope('LIVE', { plan: refusedPlan }) });
        const plan = await c.plan({ session_id: 'labs_x', planner: 'rules', prompt: 'that mask' });

        expect(plan.resolved_steps).toEqual([]);
        expect(plan.refusals[0].missing).toEqual(['art_9#inst_3']);
    });

    it('a dangling reference is a refusal in the record and never a 4xx', async () => {
        const c = client({
            'POST /sessions/labs_x/runs': envelope('LIVE', { run: runRefused, artifacts: [] }),
        });
        const out = await c.run({ session_id: 'labs_x', plan_id: 'plan_1' });
        expect(out.run.outcome).toBe('refused');
        expect(out.run.refusals[0].code).toBe('missing_depth_artifact');
    });

    it('a plan that wants confirming throws its own type, so a caller can ask the person', async () => {
        const c = client({
            'POST /sessions/labs_x/runs': () => response(409, {
                detail: { error: 'confirmation_required', plan_id: 'plan_1',
                    prerequisites: ['this chain crosses the organ boundary'],
                    why: 'plan requires confirmation' },
            }),
        });
        await expect(c.run({ session_id: 'labs_x', plan_id: 'plan_1' }))
            .rejects.toBeInstanceOf(ConfirmationRequired);
    });

    it('passes the confirmation through when the person gave it', async () => {
        const [c, impl] = withFetch({
            'POST /sessions/labs_x/runs': envelope('LIVE', { run: runReady, artifacts: [] }),
        });
        await c.run({ session_id: 'labs_x', plan_id: 'plan_1', confirmed: true,
            run_ticket: 'tkt_1' });
        expect(impl.sent('POST /sessions/labs_x/runs').body).toEqual({
            plan_id: 'plan_1', confirmed: true, run_ticket: 'tkt_1' });
    });

    it('a session that is gone is a 404 with its status kept', async () => {
        const c = client({
            'GET /sessions/labs_gone': () => response(404, {
                detail: { error: 'unknown_session', session_id: 'labs_gone' } }),
        });
        await expect(c.getSession({ session_id: 'labs_gone' }))
            .rejects.toMatchObject({ status: 404, name: 'LabRequestError' });
    });

    it('an unreachable backend says so, and says nothing was run', async () => {
        const c = createHttpLabClient({
            baseUrl: BASE,
            fetchImpl: async () => { throw new TypeError('Failed to fetch'); },
        });
        await expect(c.capabilities()).rejects.toThrow(/Could not reach the laboratory/);
        await expect(c.capabilities()).rejects.toThrow(/Nothing was run/);
    });

    it('a refused API key names the setting that fixes it', async () => {
        const c = client({ 'GET /capabilities': () => response(401, { detail: 'nope' }) });
        await expect(c.capabilities()).rejects.toThrow(/VITE_API_KEY/);
    });
});


// ── no fallback, in either direction ─────────────────────────────────────────

describe('there is no silent fallback between the wires', () => {
    it('refuses to run FIXTURE rather than running LIVE and calling it fixtures', async () => {
        const [c, impl] = withFetch({
            'POST /sessions/labs_x/runs': envelope('LIVE', { run: runReady, artifacts: [] }),
        });
        await expect(c.run({
            session_id: 'labs_x', plan_id: 'plan_1', execution_identity: 'FIXTURE' }))
            .rejects.toThrow(/cannot run FIXTURE/);
        // And nothing was sent. A refusal that had already called the adapters would be worse
        // than the confusion it was refusing.
        expect(impl.calls).toHaveLength(0);
    });

    it('refuses to run REPLAY through the run door', async () => {
        const c = client({});
        await expect(c.run({
            session_id: 'labs_x', plan_id: 'plan_1', execution_identity: 'REPLAY' }))
            .rejects.toThrow(/cannot run REPLAY/);
    });

    it('replays through the replay door, which never carries a plan id', async () => {
        const [c, impl] = withFetch({
            'POST /sessions/labs_x/replays': envelope('REPLAY', {
                run: runReplay, artifacts: [extentSet] }),
        });
        const out = await c.replay({ session_id: 'labs_x', run_id: 'run_1' });

        expect(impl.sent('POST /sessions/labs_x/replays').body).toEqual({ run_id: 'run_1' });
        expect(out.run.execution_identity).toBe('REPLAY');
        expect(out.run.replay.adapter_callable).toBe(false);
        expect(out.run.stage_attempts.every((a) => a.invoked === false)).toBe(true);
    });
});


// ── cancellation ─────────────────────────────────────────────────────────────

describe('cancellation says what it actually did', () => {
    it('passes a reached cancel through', async () => {
        const c = client({
            'POST /sessions/labs_x/runs/cancel': { cancelled: true, note: null },
        });
        expect(await c.cancel({ session_id: 'labs_x', run_ticket: 'tkt_1' }))
            .toEqual({ cancelled: true, note: null });
    });

    it('passes a cancel that reached nothing through UNSOFTENED', async () => {
        const c = client({
            'POST /sessions/labs_x/runs/cancel': {
                cancelled: false,
                note: 'no run with that ticket is in flight in this process.',
            },
        });
        const out = await c.cancel({ session_id: 'labs_x', run_ticket: 'tkt_9' });

        // `cancelled: false` is an answer. A client that returned `true` because the request
        // succeeded would make a stop button that sometimes does nothing look like one that works.
        expect(out.cancelled).toBe(false);
        expect(out.note).toMatch(/in flight/);
    });
});


// ── upload ───────────────────────────────────────────────────────────────────

describe('an upload yields a normal post, or it fails', () => {
    let dispatched;
    beforeEach(() => {
        dispatched = [];
        vi.stubGlobal('window', {
            dispatchEvent: (e) => { dispatched.push(e); return true; },
            CustomEvent: globalThis.CustomEvent,
        });
    });
    afterEach(() => vi.unstubAllGlobals());

    const file = { name: 'a.png', size: 11 };

    it('posts to the archive, then reads the source back with its digest', async () => {
        const [c, impl] = withFetch({
            'POST POSTS/': { id: SOURCE.post_id, photo_url: SOURCE.photo_url },
            [`GET /sources/${SOURCE.post_id}`]: envelope('LIVE', { source: SOURCE }),
        });
        const { source } = await c.uploadSource(file);

        expect(source.id).toBe(SOURCE.post_id);
        expect(source.image_digest).toMatch(/^sha256:/);
        // Two calls, in that order: the archive's own route, then the laboratory's.
        expect(impl.calls.map((x) => `${x.method} ${x.path}`)).toEqual([
            'POST POSTS/', `GET /sources/${SOURCE.post_id}`]);
    });

    it('tells the rest of the shell, through the shell’s own event', async () => {
        const [c] = withFetch({
            'POST POSTS/': { id: SOURCE.post_id },
            [`GET /sources/${SOURCE.post_id}`]: envelope('LIVE', { source: SOURCE }),
        });
        await c.uploadSource(file);

        expect(dispatched).toHaveLength(1);
        expect(dispatched[0].type).toBe('semant:posts-created');
        expect(dispatched[0].detail.posts[0].id).toBe(SOURCE.post_id);
    });

    it('rejects a failed upload rather than resolving with nothing', async () => {
        const [c, impl] = withFetch({
            'POST POSTS/': () => response(500, { detail: 'cloudinary said no' }),
        });
        await expect(c.uploadSource(file)).rejects.toThrow(/cloudinary said no/);
        // It never went on to open a source, so nothing downstream can believe the image is there.
        expect(impl.calls).toHaveLength(1);
    });

    it('rejects a 2xx that carried no post', async () => {
        const [c] = withFetch({ 'POST POSTS/': {} });
        await expect(c.uploadSource(file)).rejects.toThrow(/returned no post/);
    });

    it('rejects a source with no digest, however cheerful the response', async () => {
        const [c] = withFetch({
            'POST POSTS/': { id: SOURCE.post_id },
            [`GET /sources/${SOURCE.post_id}`]: envelope('LIVE', {
                source: { ...SOURCE, image_digest: null } }),
        });
        await expect(c.uploadSource(file)).rejects.toThrow(/image_digest/);
    });

    it('rejects a source whose dimensions cannot be a picture', async () => {
        const [c] = withFetch({
            'POST POSTS/': { id: SOURCE.post_id },
            [`GET /sources/${SOURCE.post_id}`]: envelope('LIVE', {
                source: { ...SOURCE, natural_width: 0 } }),
        });
        await expect(c.uploadSource(file)).rejects.toThrow();
    });
});


// ── the catalogue, the listing and the export ────────────────────────────────

describe('reading the corpus and the ledger', () => {
    it('reads the adapter table and never guesses a state', async () => {
        const c = client({
            'GET /capabilities?limit=60': undefined,
            'GET /capabilities': envelope('LIVE', {
                states: { yolo_sam2_auto: 'available', sam3_concept: 'unavailable' },
                organs: [{ family: 'extent', enabled: true, operations: [] }],
            }),
        });
        const out = await c.capabilities();

        expect(out.states).toEqual({ yolo_sam2_auto: 'available', sam3_concept: 'unavailable' });
        expect(out.organs[0].family).toBe('extent');
    });

    it('lists sources and reports the null digest as the honest absence it is', async () => {
        const c = client({
            'GET /sources?limit=60': envelope('LIVE', {
                sources: [{ ...SOURCE, image_digest: null, natural_width: null }] }),
        });
        const { sources } = await c.listSources();

        expect(sources[0].post_id).toBe(SOURCE.post_id);
        expect(sources[0].image_digest).toBeNull();
    });

    it('asks the backend for its own bundle so the two accounts can be compared', async () => {
        const bundle = {
            export_kind: 'perception-lab.session-export',
            execution_identity: 'LIVE',
            session: sessionRecord, plans: [planRecord], runs: [runReady],
            artifacts: [extentSet], reviews: [reviewRecord],
            counts: { plans: 1, runs: 1, artifacts: 1, reviews: 1 },
        };
        const c = client({ 'GET /sessions/labs_x/export': bundle });
        const out = await c.exportSession({ session_id: 'labs_x' });

        expect(out.export_kind).toBe('perception-lab.session-export');
        expect(out.session).toEqual(sessionRecord);
    });

    it('switches organ and mode through the one selection door', async () => {
        const [c, impl] = withFetch({
            'PATCH /sessions/labs_x': envelope('LIVE', { session: chainSession }),
        });
        const session = await c.setOrgan({
            session_id: 'labs_x', selected_organ: 'topology', mode: 'chain' });

        expect(impl.sent('PATCH /sessions/labs_x').body).toEqual({
            selected_organ: 'topology', mode: 'chain' });
        expect(session.mode).toBe('chain');
    });

    it('records a verdict without touching the artifact', async () => {
        const [c, impl] = withFetch({
            'POST /sessions/labs_x/reviews': envelope('LIVE', { review: reviewRecord }),
        });
        const review = await c.review({
            session_id: 'labs_x', artifact_id: extentSet.identity.artifact_id,
            verdict: 'correct', notes: 'yes' });

        expect(review).toEqual(reviewRecord);
        expect(impl.sent('POST /sessions/labs_x/reviews').body.verdict).toBe('correct');
    });

    it('sets a lifecycle at the lab-local path, which is not a promotion path', async () => {
        const [c, impl] = withFetch({
            [`PATCH /sessions/labs_x/artifacts/${extentSet.identity.artifact_id}/lifecycle`]:
                envelope('LIVE', { artifact: { ...extentSet,
                    lifecycle: { ...extentSet.lifecycle, status: 'kept' } } }),
        });
        const artifact = await c.setLifecycle({
            session_id: 'labs_x', artifact_id: extentSet.identity.artifact_id, status: 'kept' });

        expect(artifact.lifecycle.status).toBe('kept');
        // The artifact stays session-scoped. `kept` is a curation state in the lab's own ledger.
        expect(artifact.identity.identity_scope).toBe('session');
        expect(impl.calls[0].path).toContain('/lifecycle');
    });
});
