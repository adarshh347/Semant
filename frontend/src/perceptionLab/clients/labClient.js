// PERCEPTUAL-ORGANS-002 Lane E — the seam Lane F connects, written down.
//
// The laboratory takes ONE prop: a client. Every component below it reads records and calls
// callbacks; not one of them knows what a URL is. That is what makes the whole surface testable
// against fixtures, and it is what makes the Lane F handoff a single object rather than a search
// for `fetch(` across a subtree.
//
// ── THE INTERFACE ───────────────────────────────────────────────────────────
//
//   identity()      → 'FIXTURE' | 'LIVE'
//       What this client IS, shown in the shell so a person always knows which wire they are on.
//       It is NOT the badge on a run: that comes from `run.execution_identity`, which the backend
//       decides. A LIVE client can return a REPLAY run and the badge must follow the run.
//
//   capabilities()  → Promise<{ states: { [adapter]: capability_state } }>
//       The adapter table. The frontend never guesses a capability state; `checkCapability`
//       takes this table as an argument precisely so it cannot.
//
//   listSources()   → Promise<{ sources: Source[] }>
//   uploadSource(file) → Promise<{ source: Source }>
//       Source: { id, title, photo_url, image_digest, natural_width, natural_height, origin }
//       An upload that fails REJECTS. It does not resolve with `{ source: null }`, and it does
//       not resolve with a source whose digest is absent — see `assertUploadedSource`.
//
//   createSession({ source, selected_organ, mode }) → Promise<LabSession>
//   setOrgan({ session_id, selected_organ, mode })  → Promise<LabSession>
//   plan({ session_id, planner, prompt?, operation?, parameters?, input_refs?, for_execution? })
//                                                   → Promise<LabPlan>
//   run({ session_id, plan_id, execution_identity }) → Promise<{ run, artifacts }>
//   replay({ session_id, run_id })                   → Promise<{ run, artifacts }>
//   review({ session_id, artifact_id, verdict, notes, corrections }) → Promise<LabReview>
//   setLifecycle({ session_id, artifact_id, status }) → Promise<PerceptualArtifact>
//
// ── WHAT THE INTERFACE DELIBERATELY DOES NOT HAVE ───────────────────────────
//
// There is no `promote`, no `save`, no `commit`, no `acceptAll`. Promotion into Semant's own
// ledger is Lane F's, is a separate explicit human act, and is not reachable from any control
// this lane builds. `assertNoPromotionSurface` is exported so the suite can assert that about
// whatever client is handed in — including Lane F's.
//
// `setLifecycle` is not promotion. `kept` is a curation state inside the laboratory and the
// contract says so in as many words; the review verdict and the epistemic status are two other
// axes and neither moves when it does.

/** Method names a Perception Lab client must have. Missing one is a wiring bug, not a 404. */
export const REQUIRED_CLIENT_METHODS = Object.freeze([
    'identity', 'capabilities', 'listSources', 'uploadSource', 'createSession', 'setOrgan',
    'plan', 'run', 'replay', 'review', 'setLifecycle',
]);

/**
 * Names that would make this laboratory able to change Semant. None of them may exist on a
 * client handed to the lab shell, whoever wrote it.
 */
export const FORBIDDEN_CLIENT_METHODS = Object.freeze([
    'promote', 'promoteAll', 'commit', 'save', 'acceptAll', 'approveAll', 'writeRegion',
    'writeGround', 'mutatePost', 'publish',
]);

export function assertClientShape(client) {
    const missing = REQUIRED_CLIENT_METHODS.filter((m) => typeof client?.[m] !== 'function');
    if (missing.length) {
        throw new Error(`this client is missing ${missing.join(', ')} — see labClient.js`);
    }
    return assertNoPromotionSurface(client);
}

/**
 * The negative half of the contract, checkable at runtime.
 *
 * A test can assert it about a fake; Lane F can assert it about the real one. "There is no hidden
 * promotion path" is otherwise a claim that lives only in a comment.
 */
export function assertNoPromotionSurface(client) {
    const found = FORBIDDEN_CLIENT_METHODS.filter((m) => client && m in client);
    if (found.length) {
        throw new Error(
            `a Perception Lab client may not expose ${found.join(', ')}. Promotion into Semant is `
            + 'a separate explicit human act and is not reachable from this laboratory.');
    }
    return client;
}

/**
 * An upload either produced a usable source or it did not.
 *
 * The existing `UploadForm` is not embedded in this lane for exactly this reason: its result
 * contract cannot tell a successful upload from a 200 with an error body, so a laboratory built
 * on it would open a session against an image the server never stored. This is the check that
 * makes "upload failures do not report success" a property rather than a hope.
 */
export function assertUploadedSource(result) {
    const source = result?.source;
    const missing = ['id', 'photo_url', 'image_digest', 'natural_width', 'natural_height']
        .filter((k) => source?.[k] === undefined || source?.[k] === null || source?.[k] === '');
    if (missing.length) {
        throw new Error(
            `the upload did not come back with ${missing.join(', ')}. A source without those is `
            + 'not something a run can cite, and reporting it as uploaded would put a session on '
            + 'an image that may not be there.');
    }
    if (!Number.isFinite(source.natural_width) || !Number.isFinite(source.natural_height)
        || source.natural_width <= 0 || source.natural_height <= 0) {
        throw new Error('the upload reported natural dimensions that cannot be a picture');
    }
    return source;
}
