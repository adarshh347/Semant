// PERCEPTUAL-ORGANS-002 Lane F2 — the real wire.
//
// The same object `fixtureClient.js` is: `labClient.js` describes the interface, `useLabSession`
// is the only caller, and nothing below the shell knows a URL exists. What changes is where the
// answers come from — F1's `/api/v1/perception-lab` rather than a scene in memory.
//
// ── FOUR THINGS THIS FILE REFUSES TO DO ─────────────────────────────────────
//
//   1. FALL BACK. `identity()` is `'LIVE'` and there is no branch that can make it anything else.
//      A backend that is down produces an ERROR, never a quiet switch to fixtures: a laboratory
//      that answered from a scene while the badge said LIVE would be the single worst thing this
//      surface could do, and it would look like everything working.
//
//   2. RUN A FIXTURE. `run({ execution_identity: 'FIXTURE' })` REJECTS. This wire has no fixtures
//      to run, and executing live because the caller asked for something else is the same lie
//      pointing the other way. The shell disables that button for a LIVE client; this is the
//      check underneath it, because a disabled button is a suggestion.
//
//   3. TAKE A RECORD ON TRUST. Every session, plan, run, artifact and review is put through Lane
//      A's own validators on the way in. The backend and this browser hold one contract in two
//      languages, and the whole value of that is lost if drift shows up as a blank panel three
//      screens later instead of as a named failure at the boundary.
//
//   4. INVENT AN IDENTITY. There is no id minted here, no shadow source record, and no local
//      digest. A lab source IS a post: `source.id` is the `post_id`, and the digest is the one the
//      backend computed from the bytes it actually read.
//
// ── WHAT IS DELIBERATELY NOT SENT ───────────────────────────────────────────
//
// `plan()` drops the caller's `references` list. The backend derives what a follow-up may mean
// from the session it holds, and a browser that posted its own list could widen what the session
// declared — which is precisely the invented identity the reference law exists to prevent. The
// hook calls `select()` and AWAITS it before planning, so the session is already current; this is
// not the browser's opinion being ignored, it is the browser's opinion having already been
// recorded in the one place that is authoritative.
//
// `for_execution` is dropped for the same kind of reason: plan time is plan time, the backend's
// resolver knows it, and a flag that could turn it into execution time would be a second answer to
// a question the contract settles.

import { API_URL } from '../../config/api';
import { assertNoPromotionSurface, assertUploadedSource } from './labClient';
import { VALIDATORS } from '../contract/perceptionLabContract';

export const LAB_BASE = `${API_URL}/api/v1/perception-lab`;

/** The route the rest of the shell already uploads through. One post contract, not two. */
export const POSTS_BASE = `${API_URL}/api/v1/posts`;

/**
 * A request the laboratory made and the backend turned down, carrying the status and the body.
 *
 * The status is kept rather than folded into a string because the codes mean different things to
 * a person: 409 is a plan that wants confirming and the client should ask, 404 is a session that
 * is gone, 503 is the lab store being unreachable and nothing was written. `AtlasRequestError`
 * makes the same argument in `atlasService.js`, and this follows it deliberately.
 */
export class LabRequestError extends Error {
    constructor(message, status, detail = null) {
        super(message);
        this.name = 'LabRequestError';
        this.status = status;
        this.detail = detail;
    }
}

/** A plan that asked to be confirmed, executed without confirmation. Its own type, so a caller
 *  can ask the person rather than showing them a 409. */
export class ConfirmationRequired extends LabRequestError {
    constructor(message, detail) {
        super(message, 409, detail);
        this.name = 'ConfirmationRequired';
    }
}

function messageFor(status, detail, action) {
    if (status === 401 || status === 403) {
        return `The backend did not accept this browser’s API key (${status}). `
            + 'Set VITE_API_KEY to match the backend’s API_KEY and reload.';
    }
    if (detail && typeof detail === 'object' && detail.why) return String(detail.why);
    if (typeof detail === 'string' && detail) return detail;
    return `Could not ${action} (${status}).`;
}

/**
 * Validate a record against the contract, or say exactly which law it broke.
 *
 * Throwing rather than warning. A run whose `outcome` is a word this browser does not know is not
 * a run this browser can draw honestly, and rendering it anyway would put an unlabelled state on
 * screen — which is the one failure the whole absence vocabulary exists to prevent.
 */
function checked(kind, record, where) {
    const validate = VALIDATORS[kind];
    if (!validate) throw new Error(`no validator for "${kind}"`);
    const problems = validate(record);
    if (problems.length) {
        throw new LabRequestError(
            `the backend's ${kind} from ${where} does not hold the contract this browser `
            + `enforces:\n  - ${problems.join('\n  - ')}`,
            0, { kind, problems });
    }
    return record;
}

const checkedAll = (kind, records, where) =>
    (records || []).map((r) => checked(kind, r, where));

/**
 * The live client.
 *
 * @param {object} [options]
 * @param {string} [options.baseUrl] the lab API root
 * @param {string} [options.postsUrl] the posts API root, for uploads
 * @param {typeof fetch} [options.fetchImpl] injected in tests; production uses the patched global
 *   `fetch`, which `config/api.js` has already taught to carry `X-API-Key`
 */
export function createHttpLabClient({ baseUrl = LAB_BASE, postsUrl = POSTS_BASE,
    fetchImpl = null } = {}) {
    const doFetch = (...args) => (fetchImpl || fetch)(...args);

    async function call(method, path, body, action) {
        let response;
        try {
            response = await doFetch(`${baseUrl}${path}`, {
                method,
                headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
                ...(body === undefined ? {} : { body: JSON.stringify(body) }),
            });
        } catch (err) {
            // The network, not the laboratory. Named as such: "could not reach the laboratory"
            // sends a person to their connection, and a 500 sends them to the logs.
            // No full stop: the shell's own error line appends one, and two in a row
            // ("…was recorded.. Nothing on this page…") is the kind of small wrongness that makes
            // a careful surface look careless. Found by reading the message on the page.
            throw new LabRequestError(
                `Could not reach the laboratory to ${action}: ${err?.message || err}. `
                + 'Nothing was run and nothing was recorded', 0);
        }
        let payload = null;
        try {
            payload = await response.json();
        } catch {
            payload = null;
        }
        if (!response.ok) {
            const detail = payload?.detail ?? payload;
            const message = messageFor(response.status, detail, action);
            if (response.status === 409 && detail?.error === 'confirmation_required') {
                throw new ConfirmationRequired(message, detail);
            }
            throw new LabRequestError(message, response.status, detail);
        }
        return payload || {};
    }

    const get = (path, action) => call('GET', path, undefined, action);
    const post = (path, body, action) => call('POST', path, body ?? {}, action);
    const patch = (path, body, action) => call('PATCH', path, body ?? {}, action);

    const client = {
        /**
         * LIVE, and there is no path to any other answer.
         *
         * The badge on a RUN comes from `run.execution_identity` and may well say REPLAY. This
         * says what the page is talking to, which is a different question, and the shell renders
         * them in two different places for exactly that reason.
         */
        identity: () => 'LIVE',

        capabilities: async () => {
            const body = await get('/capabilities', 'read the adapter catalogue');
            return { states: body.states || {}, organs: body.organs || [] };
        },

        // ── the corpus ──────────────────────────────────────────────────────

        /**
         * Posts a session could be opened on.
         *
         * `image_digest` comes back `null` here and that is the backend admitting it has not
         * hashed thirty images to draw a list. The digest arrives with `openSource`, when a person
         * has actually chosen one. A listing carrying a guessed digest would be worse than one
         * that says it has not looked.
         */
        listSources: async () => {
            const body = await get('/sources?limit=60', 'list the available images');
            return { sources: body.sources || [] };
        },

        /** One post, resolved to a source a run can cite. */
        openSource: async (post_id) => {
            const body = await get(`/sources/${encodeURIComponent(post_id)}`,
                'read that image');
            return { source: assertUploadedSource(body) };
        },

        /**
         * Upload, through the archive's own route, and then read the result back as a source.
         *
         * TWO CALLS, AND THE SECOND ONE IS THE POINT. `POST /api/v1/posts/` is the same route
         * `UploadForm` uses — one multipart contract for the whole shell, not a lab-private one —
         * and it returns a post. What it does not return is a digest or a raster, because those
         * are facts about bytes the API server has not decoded. So the lab asks the lab: the
         * source that comes back is the post, with the digest the backend computed from the image
         * it actually read.
         *
         * A FAILURE REJECTS. Not `{ source: null }`, not a 200 with an error body passed along:
         * `assertUploadedSource` runs over this client's own result, so a response that could not
         * open a session cannot be reported as an upload that worked.
         *
         * The `semant:posts-created` event goes out with the created post, so the rest of the
         * shell — the Archive, an open inquiry — learns about the image the same way it learns
         * about one uploaded through the dialog. The lab is a citizen of that contract rather than
         * a second island.
         */
        uploadSource: async (file, { description = '', tags = '' } = {}) => {
            if (!file) throw new Error('there is no file to upload');
            const form = new FormData();
            form.append('file', file);
            form.append('description', description);
            form.append('general_tags_str', tags);

            let response;
            try {
                response = await doFetch(`${postsUrl}/`, { method: 'POST', body: form });
            } catch (err) {
                throw new Error(`the upload did not reach the archive: ${err?.message || err}`);
            }
            let created = null;
            try {
                created = await response.json();
            } catch {
                created = null;
            }
            if (!response.ok) {
                const detail = created?.detail;
                throw new Error(typeof detail === 'string' && detail
                    ? detail
                    : `the archive refused the upload (${response.status}).`);
            }
            const post = Array.isArray(created) ? created[0] : created;
            if (!post?.id) {
                // A 2xx that carried no usable post is not a success. `UploadForm` reaches the
                // same conclusion about the same route, and for the same reason.
                throw new Error('the upload returned no post. Nothing was added to the archive.');
            }
            const { source } = await client.openSource(post.id);
            if (typeof window !== 'undefined' && window.dispatchEvent) {
                window.dispatchEvent(new CustomEvent('semant:posts-created', {
                    detail: { posts: [post], requestId: '' },
                }));
            }
            return { source };
        },

        // ── the sitting ─────────────────────────────────────────────────────

        /**
         * A post id in, a durable session out — with the real source in the first response.
         *
         * `source_id` IS a `post_id`. The lab creates no post and holds no second image identity,
         * which is what makes "the laboratory changed nothing" a statement about a document the
         * rest of Semant also has.
         */
        createSession: async ({ source_id, selected_organ, mode }) => {
            const body = await post('/sessions',
                { post_id: source_id, selected_organ, mode }, 'open a session');
            return checked('LabSession', body.session, 'POST /sessions');
        },

        getSession: async ({ session_id }) => {
            const body = await get(`/sessions/${session_id}`, 'read the session');
            return checked('LabSession', body.session, 'GET /sessions/{id}');
        },

        history: async ({ session_id }) => {
            const body = await get(`/sessions/${session_id}/history`, 'read the session history');
            return {
                session: checked('LabSession', body.session, 'the history'),
                plans: checkedAll('LabPlan', body.plans, 'the history'),
                runs: checkedAll('LabRun', body.runs, 'the history'),
                artifacts: checkedAll('PerceptualArtifact', body.artifacts, 'the history'),
                reviews: checkedAll('LabReview', body.reviews, 'the history'),
            };
        },

        setOrgan: async ({ session_id, selected_organ, mode }) => {
            const body = await patch(`/sessions/${session_id}`,
                { selected_organ, mode }, 'switch organ');
            return checked('LabSession', body.session, 'PATCH /sessions/{id}');
        },

        /**
         * What "that mask" is allowed to mean, recorded where it is authoritative.
         *
         * `active_artifact_id: null` and an absent key are the same thing in JSON and two
         * different acts to a person, so clearing the active artifact travels as its own flag.
         * Without it, "stop meaning that one" would be a request the backend could not tell from
         * "leave it alone".
         */
        select: async ({ session_id, artifact_ids, active_artifact_id,
            selected_instance_refs }) => {
            const update = {};
            if (artifact_ids !== undefined) update.selected_artifact_ids = artifact_ids;
            if (selected_instance_refs !== undefined) {
                update.selected_instance_refs = selected_instance_refs.map(
                    ({ artifact_id, instance_id }) => ({ artifact_id, instance_id }));
            }
            if (active_artifact_id === null) update.clear_active = true;
            else if (active_artifact_id !== undefined) update.active_artifact_id = active_artifact_id;
            const body = await patch(`/sessions/${session_id}`, update, 'record the selection');
            return checked('LabSession', body.session, 'PATCH /sessions/{id}');
        },

        // ── planning and running ────────────────────────────────────────────

        plan: async ({ session_id, planner, prompt = '', operation, parameters = {},
            input_refs = [] }) => {
            const request = planner === 'direct'
                ? { planner: 'direct', commands: [{ operation, parameters, input_refs }] }
                : { planner, prompt };
            const body = await post(`/sessions/${session_id}/plans`, request, 'propose a plan');
            return checked('LabPlan', body.plan, 'POST /plans');
        },

        /**
         * Execute an authorized plan. The only call in this file that reaches an adapter.
         *
         * `execution_identity` is accepted and CHECKED rather than ignored, because the shell
         * offers two run buttons and a client that quietly ran live when asked for fixtures would
         * be the fallback this file exists to refuse — pointing the other way.
         */
        run: async ({ session_id, plan_id, execution_identity = 'LIVE', confirmed = false,
            run_ticket = null }) => {
            if (execution_identity !== 'LIVE') {
                throw new Error(
                    `this laboratory is on the LIVE wire and cannot run ${execution_identity}. `
                    + 'There are no fixtures behind this client, and running live because the '
                    + 'request said otherwise would put the wrong badge on a real measurement.');
            }
            const body = await post(`/sessions/${session_id}/runs`,
                { plan_id, confirmed, run_ticket }, 'run the plan');
            return {
                run: checked('LabRun', body.run, 'POST /runs'),
                artifacts: checkedAll('PerceptualArtifact', body.artifacts, 'POST /runs'),
                response: body.response || null,
                source_unchanged: body.source_unchanged,
            };
        },

        /**
         * Pull a ticket.
         *
         * `cancelled: false` is a real answer and is passed through untouched: it means no run of
         * that ticket is in flight in the process that took this request, which is NOT the same
         * sentence as "the run has stopped". Cancellation is cooperative all the way down and the
         * backend says so; softening it here would make a stop button that sometimes does nothing
         * look like one that always works.
         */
        cancel: async ({ session_id, run_ticket, reason = 'cancelled by the person' }) => {
            const body = await post(`/sessions/${session_id}/runs/cancel`,
                { run_ticket, reason }, 'cancel the run');
            return { cancelled: !!body.cancelled, note: body.note || null };
        },

        replay: async ({ session_id, run_id }) => {
            const body = await post(`/sessions/${session_id}/replays`, { run_id },
                'replay the run');
            return {
                run: checked('LabRun', body.run, 'POST /replays'),
                artifacts: checkedAll('PerceptualArtifact', body.artifacts, 'POST /replays'),
            };
        },

        // ── a person's verdict, and the lab's own curation ───────────────────

        review: async ({ session_id, artifact_id, reviewer = 'curator', verdict, notes = '',
            corrections = [] }) => {
            const body = await post(`/sessions/${session_id}/reviews`,
                { artifact_id, reviewer, verdict, notes, corrections }, 'record the verdict');
            return checked('LabReview', body.review, 'POST /reviews');
        },

        /** A curation state inside the laboratory. `kept` is not promoted and not `measured`. */
        setLifecycle: async ({ session_id, artifact_id, status }) => {
            const body = await patch(
                `/sessions/${session_id}/artifacts/${artifact_id}/lifecycle`,
                { status }, 'change the lifecycle');
            return checked('PerceptualArtifact', body.artifact, 'PATCH /lifecycle');
        },

        /**
         * The backend's own bundle of this session.
         *
         * The browser builds one too, from the ledger it is holding, and `ExportBar` is what a
         * person downloads. This exists so the two can be COMPARED — if they disagree, one of them
         * is wrong about what happened, and a laboratory whose two accounts of a session differ
         * has a worse problem than either account.
         */
        exportSession: async ({ session_id }) =>
            get(`/sessions/${session_id}/export`, 'export the session'),
    };

    return assertNoPromotionSurface(client);
}

export default createHttpLabClient;
