// PERCEPTUAL-ORGANS-002 Lane E — the session, out of the laboratory and onto disk.
//
// WHAT AN EXPORT IS FOR, and it decides every choice below: somebody reads this file months from
// now, without the laboratory, and has to be able to tell what was measured, what was drawn, what
// was refused and what a person thought. An export that "cleaned up" the record would destroy
// exactly the evidence it exists to carry.
//
// SO THE RULES ARE:
//
//   1. THE RECORDS GO OUT AS THEY CAME IN. No renaming, no flattening, no dropping of nulls, no
//      merging of the review into the artifact. Byte-for-byte the contract's five record types.
//      `verifyExport` runs Lane A's own validators over every record on the way out, so a bundle
//      that would not survive re-import cannot be produced in the first place.
//
//   2. WHAT THIS BROWSER DERIVED IS SEGREGATED. Every contact band, every wash, every duplicate
//      re-derivation lives under `derived_in_browser`, never merged into `artifacts`. A reader who
//      takes the top-level records gets the measurement and nothing else; a reader who wants the
//      pictures has to go and get them from a block that says where they came from.
//
//   3. NOTHING IS PROMOTED BY EXPORTING. An export is a copy. It carries lifecycle states as they
//      are, it mints no canonical ids, and it says so in the envelope — because "export to Semant"
//      is precisely the hidden promotion path this laboratory must not have.
//
// PURE MODULE. The timestamp is an argument.

import { SCHEMA_VERSION, VALIDATORS } from './contract/perceptionLabContract';

export const EXPORT_KIND = 'perception-lab.session-export';
export const EXPORT_VERSION = 1;

/**
 * Build the bundle.
 *
 * `derived` is optional and, when given, is kept in its own block. Callers pass what the surface
 * actually drew, so the export answers "what did the person see" as well as "what was measured" —
 * two questions an export that carried only one of them would silently conflate.
 */
export function buildExport({ session, plans = [], runs = [], artifacts = [], reviews = [],
    derived = null, exported_at, client_identity = 'unknown', note = null }) {
    if (!session) throw new Error('there is no session to export');
    return {
        export_kind: EXPORT_KIND,
        export_version: EXPORT_VERSION,
        schema_version: SCHEMA_VERSION,
        exported_at,
        exported_by: 'perception_lab_frontend',
        client_identity,
        what_this_is:
            'A copy of one Perception Lab session, in the records of `perception-lab.v1`. Every '
            + 'artifact here is SESSION-LOCAL: none of it is in Semant, and importing this file '
            + 'does not put it there. Lifecycle states are carried as they were; `kept` means '
            + 'kept in the lab ledger and nothing more.',
        not_this: [
            'Not a promotion. No canonical id is minted here and none can be.',
            'Not a judgement. Reviews are separate records keyed by artifact_id, exactly as the '
                + 'contract holds them, because a verdict folded into an artifact becomes a '
                + 'property of the measurement.',
            'Not a rendering. What this browser drew is under `derived_in_browser` and is not a '
                + 'measurement, however exact its arithmetic.',
        ],
        note,
        session,
        plans,
        runs,
        artifacts,
        reviews,
        derived_in_browser: derived
            ? {
                what_this_is:
                    'Projections computed in the browser to show where the measurements live: '
                    + 'traced mask boundaries, contact bands, intersections, clearances and '
                    + 'distance washes. Each carries `computed_by: lab_browser`. None of it is a '
                    + 'measurement and none of it came from an adapter.',
                ...derived,
            }
            : null,
        counts: {
            plans: plans.length,
            runs: runs.length,
            artifacts: artifacts.length,
            reviews: reviews.length,
            refusals: artifacts.filter(
                (a) => a.identity.artifact_kind === 'refusal').length,
        },
    };
}

/**
 * Run the contract's own validators over the whole bundle.
 *
 * Returns a list of problems — empty means it holds. Deliberately not a boolean: an export that
 * fails needs to say WHICH record and WHY, because the alternative is a person discovering it on
 * re-import with nothing to go on.
 */
export function verifyExport(bundle) {
    const problems = [];
    const check = (kind, record, label) => {
        const found = VALIDATORS[kind](record);
        for (const p of found) problems.push(`${label}: ${p}`);
    };
    if (bundle.export_kind !== EXPORT_KIND) problems.push('this is not a session export');
    if (bundle.schema_version !== SCHEMA_VERSION) {
        problems.push(`schema_version ${bundle.schema_version} is not ${SCHEMA_VERSION}`);
    }
    check('LabSession', bundle.session, 'session');
    bundle.plans.forEach((p, i) => check('LabPlan', p, `plans[${i}] ${p.plan_id}`));
    bundle.runs.forEach((r, i) => check('LabRun', r, `runs[${i}] ${r.run_id}`));
    bundle.artifacts.forEach((a, i) => check('PerceptualArtifact', a,
        `artifacts[${i}] ${a.identity?.artifact_id}`));
    bundle.reviews.forEach((r, i) => check('LabReview', r, `reviews[${i}] ${r.review_id}`));

    // The separation the export exists to preserve, checked rather than assumed.
    for (const artifact of bundle.artifacts) {
        if ('review' in artifact || 'reviews' in artifact || 'verdict' in artifact) {
            problems.push(`${artifact.identity.artifact_id} carries a verdict. A review is a `
                + 'separate record; folding it in makes `correct` a property of the measurement.');
        }
        if (artifact.identity.identity_scope === 'canonical'
            && !artifact.identity.identity_refs.length) {
            problems.push(`${artifact.identity.artifact_id} claims a canonical scope and cites `
                + 'nothing. An export may not mint an identity Semant does not hold.');
        }
    }
    return problems;
}

/**
 * Serialize, and refuse to serialize a bundle that would not survive re-import.
 *
 * The throw is the point. An export is read once, later, by somebody who cannot ask what it meant;
 * writing a broken one silently is worse than not writing one.
 */
export function exportJson(input) {
    const bundle = buildExport(input);
    const problems = verifyExport(bundle);
    if (problems.length) {
        throw new Error('this session does not hold the contract and will not be exported:\n  - '
            + problems.join('\n  - '));
    }
    return JSON.stringify(bundle, null, 2);
}

/** A stable filename: the session, and the moment it left. */
export function exportFilename(session, exported_at) {
    const stamp = String(exported_at).replace(/[:.]/g, '-');
    return `perception-lab-${session.session_id}-${stamp}.json`;
}
