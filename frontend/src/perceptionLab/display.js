// PERCEPTUAL-ORGANS-002 Lane E — the words, decided once.
//
// Six axes have to stay apart on one screen, and they are apart in the contract:
//
//     execution identity   LIVE · REPLAY · FIXTURE          — where the answer came from
//     run outcome          ready · empty · unavailable …    — how the run ended
//     epistemic status     measured · visible · interpretive · uncertain
//     epistemic basis      mask · box · depth_artifact · manual · declared
//     lifecycle            proposed · edited · kept · rejected · promoted
//     review verdict       correct · partial · wrong · unclear
//
// They collapse when they are given the same visual treatment or, worse, overlapping words. If
// `kept` and `correct` both render as a green tick, then a person has been told that a curation
// state and a human judgement are the same fact, and no amount of tooltip repairs it.
//
// So: every axis has its OWN vocabulary here, its own `data-` attribute in the markup, and its
// own block of CSS. A value with no entry throws rather than falling through to a shrug — an
// unlabelled status is a status a person will read as whatever the surrounding pixels suggest.
//
// PURE MODULE. Data in, words out. `axisLabels` is asserted against the contract's closed sets by
// the suite, so a set that grows fails here until this file grows with it.

import {
    CAPABILITY_STATES, EPISTEMIC_BASES, EXECUTION_IDENTITIES, LIFECYCLE_STATES, PLANNER_IDENTITIES,
    RUN_OUTCOMES, REVIEW_VERDICTS, STAGE_STATES, IDENTITY_SCOPES, BASIS_CEILINGS,
} from './contract/perceptionLabContract';

const table = (name, entries) => Object.freeze({ name, entries: Object.freeze(entries) });

export const EXECUTION = table('execution_identity', {
    LIVE: { label: 'LIVE', hint: 'an adapter was called, just now, on this image' },
    REPLAY: { label: 'REPLAY', hint: 'the lab ledger, re-shown. Nothing was called and nothing could be' },
    FIXTURE: { label: 'FIXTURE', hint: 'committed data. Nothing was called' },
});

export const OUTCOME = table('run_outcome', {
    ready: { label: 'Ready', hint: 'the organ ran and produced a measurement' },
    empty: { label: 'Empty', hint: 'the organ ran, looked, and there was nothing of that kind. This is a measurement' },
    unavailable: { label: 'Unavailable', hint: 'the adapter is in the catalogue and is not running here. Nothing looked at the image' },
    refused: { label: 'Refused', hint: 'the request was well formed and this laboratory will not do it' },
    partial: { label: 'Partial', hint: 'some stages produced a measurement and some did not' },
    failed: { label: 'Failed', hint: 'something raised. No claim is made about the image at all' },
});

export const STAGE = table('stage_state', {
    queued: { label: 'queued', hint: 'waiting' },
    started: { label: 'running', hint: 'in flight' },
    completed: { label: 'completed', hint: 'produced a measurement' },
    empty: { label: 'empty', hint: 'looked, and found nothing of that kind' },
    refused: { label: 'refused', hint: 'a law said no; the organ was never asked' },
    unavailable: { label: 'unavailable', hint: 'the adapter is not running here' },
    skipped: { label: 'skipped', hint: 'not reached' },
    failed: { label: 'failed', hint: 'raised' },
});

export const EPISTEMIC = table('epistemic_status', {
    measured: { label: 'measured', hint: 'computed from the pixels of this image' },
    visible: { label: 'visible', hint: 'present in the picture and someone can point at it. Nothing computed it' },
    interpretive: { label: 'interpretive', hint: 'a reading of the image, not a quantity taken from it' },
    uncertain: { label: 'uncertain', hint: 'no claim is being made' },
    sourced: { label: 'sourced', hint: 'from outside the image — walled out of this laboratory' },
});

export const BASIS = table('epistemic_basis', {
    mask: { label: 'mask', hint: 'per-pixel, on a shared raster' },
    box: { label: 'box', hint: 'bounding boxes, which systematically over-estimate. Interpretive however confident the number' },
    depth_artifact: { label: 'depth field', hint: 'an ordering over a SUPPLIED depth field' },
    manual: { label: 'drawn', hint: 'a person drew it' },
    declared: { label: 'declared', hint: 'an imported region asserting its own geometry. The lab carries the claim and may not raise it' },
});

export const LIFECYCLE = table('lifecycle_status', {
    proposed: { label: 'Proposed', hint: 'produced, and nothing has been decided about it' },
    edited: { label: 'Edited', hint: 'a person changed it in this laboratory' },
    kept: { label: 'Kept', hint: 'kept in the lab ledger. NOT promoted into Semant, and not judged correct' },
    rejected: { label: 'Rejected', hint: 'set aside in the lab ledger. The record stays' },
    promoted: { label: 'Promoted', hint: 'written into Semant by an explicit act. Not reachable from this laboratory' },
});

export const VERDICT = table('review_verdict', {
    correct: { label: 'Correct', hint: 'the person judged it right. This changes no status and no lifecycle' },
    partial: { label: 'Partly right', hint: 'some of it is what they meant' },
    wrong: { label: 'Wrong', hint: 'the person judged it wrong. The measurement is unchanged and stays in the ledger' },
    unclear: { label: 'Unclear', hint: 'the person could not tell' },
});

export const PLANNER = table('planner', {
    direct: { label: 'Direct', hint: 'the person chose the operation with controls' },
    rules: { label: 'Rules planner', hint: 'a deterministic phrase match over a closed vocabulary' },
    model: { label: 'Model planner', hint: 'a language model proposed, into the same resolver' },
});

export const CAPABILITY = table('capability_state', {
    available: { label: 'available', hint: 'loadable here' },
    deferred: { label: 'deferred', hint: 'declared, not yet wired' },
    unavailable: { label: 'not running here', hint: 'in the catalogue and not loadable in this deployment' },
    unknown_until_runtime: { label: 'unknown until run', hint: 'nobody has asked yet' },
});

export const SCOPE = table('identity_scope', {
    session: { label: 'session only', hint: 'this identity exists inside this laboratory session' },
    canonical: { label: 'canonical', hint: 'an identity Semant holds, cited with its revision' },
});

const TABLES = { EXECUTION, OUTCOME, STAGE, EPISTEMIC, BASIS, LIFECYCLE, VERDICT, PLANNER,
    CAPABILITY, SCOPE };

/** Look a value up, or throw. There is no fallback: an unlabelled state is an unreadable one. */
export function describe(table, value) {
    const entry = table.entries[value];
    if (!entry) {
        throw new Error(`no ${table.name} vocabulary for "${value}". A state with no words is a `
            + 'state a person reads off the surrounding pixels.');
    }
    return entry;
}

/** The vocabularies against the closed sets they claim to cover. Asserted by the suite. */
export const AXIS_COVERAGE = Object.freeze({
    EXECUTION: EXECUTION_IDENTITIES,
    OUTCOME: RUN_OUTCOMES,
    STAGE: STAGE_STATES,
    BASIS: EPISTEMIC_BASES,
    LIFECYCLE: LIFECYCLE_STATES,
    VERDICT: REVIEW_VERDICTS,
    PLANNER: PLANNER_IDENTITIES,
    CAPABILITY: CAPABILITY_STATES,
    SCOPE: IDENTITY_SCOPES,
});

export const TABLES_BY_NAME = Object.freeze(TABLES);

/** The ceiling sentence for a basis — why a number cannot be promoted past its substrate. */
export function ceilingNote(basis) {
    const ceiling = BASIS_CEILINGS[basis];
    if (!ceiling) return null;
    return `a ${describe(BASIS, basis).label} basis may claim at most ${ceiling}`;
}

/** `1840` → `1.84s`; `null` → `unmeasured`, which is not `0ms`. Zero is a real measurement. */
export function duration(ms) {
    if (ms === null || ms === undefined) return 'unmeasured';
    if (ms === 0) return '0ms';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
}

/** A number for a person: enough digits to compare, not so many it reads as precision. */
export function num(v, digits = 3) {
    if (v === null || v === undefined) return '—';
    if (!Number.isFinite(v)) return '—';
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(digits);
}

/** The measurement keys, in a stable order, so two relations can be read side by side. */
export function orderedMeasurements(measurements = {}) {
    return Object.keys(measurements).sort().map((k) => ({ key: k, value: measurements[k] }));
}

/** A short, honest sentence for an artifact's kind — used where a heading needs one line. */
export function artifactSummary(artifact) {
    const payload = artifact?.measurement?.payload;
    if (!payload) return 'no payload';
    switch (payload.variant) {
        case 'extent_set':
            return payload.instances.length
                ? `${payload.instances.length} extent${payload.instances.length > 1 ? 's' : ''}`
                : `nothing found for “${payload.searched}”`;
        case 'topology_relation_set':
            return payload.relations.length
                ? `${payload.relations.length} relation${payload.relations.length > 1 ? 's' : ''} `
                    + `over ${payload.pairs_examined} pairs`
                : `${payload.pairs_examined} pairs examined, no relation of that kind`;
        case 'negative_space_field':
            return `a ${payload.field_shape.join('×')} distance field`;
        case 'refusal':
            return payload.refusal.code;
        default:
            return payload.variant;
    }
}
