// PERCEPTUAL-ORGANS-002 Lane F2 — F1's routes, answered by the fixture laboratory.
//
// A TEST DOUBLE, and it is worth being exact about what it does and does not prove.
//
//   IT PROVES   that `createHttpLabClient` speaks F1's routes correctly, that the shell works
//               end to end over HTTP rather than over an object handed to it, and that a whole
//               sitting — session, direct run, prompt run, one mask selected, refine, chain,
//               topology, review, reload, replay, export — survives the wire.
//
//   IT DOES NOT PROVE   anything about Python. F1's own suite drives the real conductor, the real
//               Extent façade and the real Topology organs through the real routes; nothing here
//               can stand in for that and nothing here should be read as if it did.
//
// WHY THE FIXTURE CLIENT UNDERNEATH rather than canned JSON. Because a canned response cannot be
// re-selected, re-planned and re-run: the eleven flows this exists for are STATEFUL, and a
// stateless stub would let the client pass tests against a laboratory that has no memory. The
// fixture client is a real, contract-valid, stateful lab; this file is a route table over it, and
// the route table is the thing being tested.
//
// The runs it reports carry `LIVE`, because that is what this stands in for. A test that wants the
// FIXTURE wire uses `createFixtureClient` directly — as every Lane E suite does — rather than
// asking this shim to lie in the other direction.

import { createFixtureClient } from './fixtureClient';

const ok = (payload) => ({
    ok: true, status: 200, json: async () => payload,
});
const fail = (status, detail) => ({
    ok: false, status, json: async () => ({ detail }),
});

const envelope = (identity, body) => ({ execution_identity: identity, ...body });

/**
 * @param {object} [options]
 * @param {string} [options.labBase] the lab API root this shim answers on
 * @param {string} [options.postsBase] the posts API root
 * @param {object} [options.lab] an existing fixture client to serve, so a test can reach in
 * @param {object} [options.fixtureOptions] passed to `createFixtureClient`
 */
export function createFixtureHttpBackend({ labBase, postsBase, lab = null,
    fixtureOptions = {} } = {}) {
    const client = lab || createFixtureClient(fixtureOptions);
    const calls = [];
    const uploads = [];
    let uploadFails = false;
    let nextPostId = 0;

    async function route(method, path, body) {
        // ── the catalogue and the corpus ────────────────────────────────────
        if (method === 'GET' && path.startsWith('/capabilities')) {
            const { states } = await client.capabilities();
            return ok(envelope('LIVE', { states, organs: [] }));
        }
        if (method === 'GET' && path.startsWith('/sources/')) {
            const id = decodeURIComponent(path.slice('/sources/'.length));
            const { sources } = await client.listSources();
            const source = sources.find((s) => s.id === id);
            if (!source) return fail(404, { error: 'unknown_post', post_id: id });
            return ok(envelope('LIVE', { source: { ...source, post_id: source.id } }));
        }
        if (method === 'GET' && path.startsWith('/sources')) {
            const { sources } = await client.listSources();
            return ok(envelope('LIVE', {
                // A LISTING HAS NOT HASHED ANYTHING, exactly as F1's does not. The digest arrives
                // with `GET /sources/{id}`, when a person has actually chosen one.
                sources: sources.map((s) => ({ ...s, post_id: s.id, image_digest: null })),
            }));
        }

        // ── sessions ────────────────────────────────────────────────────────
        if (method === 'POST' && path === '/sessions') {
            const session = await client.createSession({
                source_id: body.post_id, selected_organ: body.selected_organ, mode: body.mode });
            const { sources } = await client.listSources();
            const source = sources.find((s) => s.id === body.post_id);
            return ok(envelope('LIVE', {
                session, source: { ...source, post_id: source.id } }));
        }

        const session_id = (path.match(/^\/sessions\/([^/]+)/) || [])[1];
        if (!session_id) return fail(404, { error: 'no_route', why: `${method} ${path}` });
        const rest = path.slice(`/sessions/${session_id}`.length);

        try {
            if (method === 'GET' && rest === '') {
                return ok(envelope('LIVE', { session: await client.getSession({ session_id }) }));
            }
            if (method === 'GET' && rest === '/history') {
                return ok(envelope('LIVE', await client.history({ session_id })));
            }
            if (method === 'GET' && rest === '/export') {
                const bundle = await client.history({ session_id });
                return ok({
                    export_kind: 'perception-lab.session-export',
                    export_version: 1,
                    execution_identity: 'LIVE',
                    ...bundle,
                    counts: {
                        plans: bundle.plans.length, runs: bundle.runs.length,
                        artifacts: bundle.artifacts.length, reviews: bundle.reviews.length,
                    },
                });
            }
            if (method === 'PATCH' && rest === '') {
                // ONE DOOR FOR ORGAN, MODE AND SELECTION, as F1 has it. `clear_active` is its own
                // flag because `null` and "absent" are the same thing in JSON.
                let session = await client.getSession({ session_id });
                if (body.selected_organ !== undefined || body.mode !== undefined) {
                    session = await client.setOrgan({
                        session_id,
                        selected_organ: body.selected_organ ?? session.selected_organ,
                        mode: body.mode ?? session.mode });
                }
                if (body.selected_artifact_ids !== undefined
                    || body.selected_instance_refs !== undefined
                    || body.active_artifact_id !== undefined || body.clear_active) {
                    session = await client.select({
                        session_id,
                        artifact_ids: body.selected_artifact_ids,
                        active_artifact_id: body.clear_active
                            ? null : body.active_artifact_id,
                        selected_instance_refs: body.selected_instance_refs,
                    });
                }
                return ok(envelope('LIVE', { session }));
            }
            if (method === 'POST' && rest === '/plans') {
                const command = (body.commands || [])[0] || {};
                const plan = await client.plan({
                    session_id,
                    planner: body.planner,
                    prompt: body.prompt || '',
                    operation: command.operation,
                    parameters: command.parameters || {},
                    input_refs: command.input_refs || [],
                    // NOT from the request body. F1 derives the references from the session it
                    // holds, and this shim must not accept a list the browser posted — otherwise
                    // the test would pass against a client that widened what the session declared.
                    references: [],
                    for_execution: false,
                });
                return ok(envelope('LIVE', { plan, authorized: plan.resolved_steps.length > 0 }));
            }
            if (method === 'POST' && rest === '/runs') {
                const plan = (await client.history({ session_id })).plans
                    .find((p) => p.plan_id === body.plan_id);
                if (!plan) return fail(404, { error: 'unknown_plan', plan_id: body.plan_id });
                if (plan.requires_confirmation && !body.confirmed) {
                    return fail(409, { error: 'confirmation_required', plan_id: plan.plan_id,
                        prerequisites: plan.prerequisites,
                        why: 'this plan asked to be confirmed and was not' });
                }
                const out = await client.run({
                    session_id, plan_id: body.plan_id, execution_identity: 'LIVE' });
                return ok(envelope('LIVE', {
                    run: out.run, artifacts: out.artifacts, plan,
                    outcome: out.run.outcome,
                    source_unchanged:
                        out.run.source_digest_after === out.run.source_digest_before,
                }));
            }
            if (method === 'POST' && rest === '/runs/cancel') {
                return ok(envelope('LIVE',
                    await client.cancel({ session_id, run_ticket: body.run_ticket })));
            }
            if (method === 'POST' && rest === '/replays') {
                const out = await client.replay({ session_id, run_id: body.run_id });
                return ok(envelope('REPLAY', { run: out.run, artifacts: out.artifacts }));
            }
            if (method === 'POST' && rest === '/reviews') {
                return ok(envelope('LIVE', { review: await client.review({
                    session_id, artifact_id: body.artifact_id, reviewer: body.reviewer,
                    verdict: body.verdict, notes: body.notes,
                    corrections: body.corrections }) }));
            }
            const lifecycle = rest.match(/^\/artifacts\/([^/]+)\/lifecycle$/);
            if (method === 'PATCH' && lifecycle) {
                if (body.status === 'promoted') {
                    return fail(422, { error: 'promotion_is_not_a_lifecycle_edit',
                        why: 'promotion is a separate confirmed act, and it is not here' });
                }
                return ok(envelope('LIVE', { artifact: await client.setLifecycle({
                    session_id, artifact_id: lifecycle[1], status: body.status }) }));
            }
        } catch (err) {
            const message = String(err?.message || err);
            if (/^no (session|plan|run|artifact)/.test(message)) {
                return fail(404, { error: 'unknown_record', why: message });
            }
            return fail(422, { error: 'refused', why: message });
        }
        return fail(404, { error: 'no_route', why: `${method} ${path}` });
    }

    /** The `fetch` a test installs. */
    const fetchImpl = async (url, init = {}) => {
        const method = init.method || 'GET';
        const href = String(url);
        const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body;
        calls.push({ method, url: href });

        if (postsBase && href.startsWith(postsBase)) {
            if (uploadFails) return fail(500, 'the archive refused the upload');
            // The archive returns a POST, and the source that post becomes is then read back
            // through `GET /sources/{id}` — which is the two-call shape the live client uses and
            // the reason it uses it: the archive has not decoded the image and has no digest.
            // Creating it in the fixture lab is what makes the second call able to answer.
            nextPostId += 1;
            const { source } = await client.uploadSource({
                name: `uploaded_${nextPostId}.png`, size: 1024 + nextPostId });
            const post = { id: source.id, photo_url: source.photo_url };
            uploads.push(post);
            return ok(post);
        }
        if (!href.startsWith(labBase)) {
            return fail(404, { error: 'not_this_backend', why: href });
        }
        return route(method, href.slice(labBase.length), body);
    };

    return {
        fetchImpl,
        lab: client,
        calls,
        uploads,
        failUploads: (on = true) => { uploadFails = on; },
    };
}

export default createFixtureHttpBackend;
