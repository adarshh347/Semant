// PERCEPTUAL-ORGANS-002 Lane E — planners propose, the resolver authorizes.
//
// Lane D owns the real conductor. This is the frontend's own copy of the same TWO-STAGE SHAPE,
// built so the laboratory works against fixtures before any backend exists, and so the UI is
// exercised by the thing it will actually receive. It is not a second contract: every gate below
// is one of Lane A's exported functions (`checkOrganLock`, `resolveParameters`, `checkInputs`,
// `checkCapability`) and every refusal is a Lane A refusal code with a Lane A message.
//
// THE ONE STRUCTURAL CLAIM, and it is the claim the whole Direct/Prompt arm rests on:
//
//     Direct and Prompt differ ONLY in who writes `proposed_steps`. `resolve()` is one function
//     and both arms enter it. There is no direct path that skips a gate, so a control cannot do
//     something a prompt is refused, and a prompt cannot do something a control cannot.
//
// A planner may therefore be wrong, and being wrong is survivable — it proposes into a resolver
// that answers to the contract. What a planner may never do is dispatch, author geometry, or
// change the organ, and the resolver is where each of those dies.
//
// PURE MODULE. No fetch, no clock (timestamps are arguments), no DOM.

import {
    checkCapability, checkInputs, checkOrganLock, message, operation, operationsFor,
    referenceOf, resolveParameters, sessionKnows, validateInputRef,
} from './contract/perceptionLabContract';
import { inputRef, labPlan, proposedStep, resolvedStep } from './records';

// ── the resolver ────────────────────────────────────────────────────────────

/**
 * Take proposals to a plan.
 *
 * Every step runs the four gates in this order, and the order is not cosmetic: an unknown
 * operation cannot have its parameters checked, and parameters that refuse make an input check
 * meaningless. The first gate that refuses ends that step, and the step does NOT reach
 * `resolved_steps` — a plan preview that showed a refused step as resolved would be showing a
 * person something they are about to be told they cannot run.
 *
 * `forExecution` distinguishes composing from running. Occlusion without a depth field is a
 * legitimate thing to have on screen while you look for one; it is not a legitimate thing to run.
 */
export function resolve({ session_id, planner, planner_fell_back_from = null, selected_organ,
    mode, proposals, capabilityStates = {}, knownReferences = null, plan_id, created_at,
    forExecution = false }) {
    const resolved = [];
    const refusals = [];
    const dropped = [];
    const clamped = [];
    const prerequisites = [];

    for (const step of proposals) {
        // gate 1 — the organ lock.
        const locked = checkOrganLock(step.operation, { selectedOrgan: selected_organ, mode });
        if (locked) { refusals.push({ ...locked, step_id: step.step_id }); continue; }

        // gate 2 — parameters. Dropped and clamped are RECORDED even when the step then refuses:
        // what a planner tried to smuggle in is evidence whether or not the step survived.
        const params = resolveParameters(step.operation, step.parameters || {});
        for (const d of params.dropped) dropped.push({ step_id: step.step_id, ...d });
        for (const c of params.clamped) clamped.push({ step_id: step.step_id, ...c });
        if (params.refusal) { refusals.push({ ...params.refusal, step_id: step.step_id }); continue; }

        // gate 2b — references. Language may not mint an identity: an input naming an artifact
        // this session has never selected is `unknown_reference`, not a lookup. The same is true
        // one level down — selecting a SET does not license every mask inside it, or "deselect
        // that mask" would be a gesture with no effect while the containing set stayed selected.
        if (knownReferences) {
            const stray = (step.input_refs || [])
                .filter((r) => r.artifact_id && !sessionKnows(r, knownReferences));
            if (stray.length) {
                refusals.push({
                    code: 'unknown_reference',
                    organ: selected_organ,
                    operation: step.operation,
                    step_id: step.step_id,
                    message: message('unknown_reference', { reference: referenceOf(stray[0]) }),
                    missing: stray.map(referenceOf),
                    remedy: "select the artifact first — 'that mask' resolves through ids, never "
                        + 'through language',
                    detail: { references: stray.map(referenceOf) },
                });
                continue;
            }
        }

        // gate 2c — the shape of every ref. `instance_id` beside `region_id`, or with no
        // artifact at all, is not a reference this contract can read.
        const malformed = (step.input_refs || []).flatMap((r) => validateInputRef(r));
        if (malformed.length) {
            refusals.push({
                code: 'invalid_parameters',
                organ: selected_organ,
                operation: step.operation,
                step_id: step.step_id,
                message: message('invalid_parameters',
                    { operation: step.operation, detail: malformed.join('; ') }),
                missing: [],
                remedy: 'an instance is named with the artifact that holds it, and never beside '
                    + 'a canonical region',
                detail: { problems: malformed },
            });
            continue;
        }

        // gate 3 — inputs.
        const inputs = checkInputs(step.operation, step.input_refs || [], { forExecution });
        if (inputs) { refusals.push({ ...inputs, step_id: step.step_id }); continue; }

        // gate 4 — capability.
        const adapter = params.clean.adapter || null;
        const capability = checkCapability(step.operation, { adapter, states: capabilityStates });
        if (capability) { refusals.push({ ...capability, step_id: step.step_id }); continue; }

        const op = operation(step.operation);
        const chosen = adapter || (op.adapters || []).find(
            (a) => (capabilityStates[a] || 'unknown_until_runtime') !== 'unavailable') || null;

        const checked = ['organ_lock', 'parameters'];
        if ((op.inputs || []).length) checked.push('inputs');
        checked.push('capability');

        resolved.push(resolvedStep({
            step_id: step.step_id,
            organ: step.organ,
            operation: step.operation,
            parameters: params.clean,
            input_refs: step.input_refs || [],
            adapter: chosen,
            prerequisites_checked: checked,
        }));
        if (op.requires_confirmation) {
            prerequisites.push(`${op.key} is confirmed before it runs — ${op.summary}`);
        }
    }

    const organs = new Set(resolved.map((s) => s.organ));
    const crossing = mode === 'chain' && organs.size > 1;
    if (crossing) {
        prerequisites.push('this plan crosses the organ boundary; each stage keeps its own '
            + 'artifact, adapter and timing, and the person confirms between them');
    }
    const needsConfirmation = crossing
        || resolved.some((s) => operation(s.operation).requires_confirmation);

    return labPlan({
        plan_id,
        session_id,
        planner,
        planner_fell_back_from,
        selected_organ,
        mode,
        proposed_steps: proposals,
        resolved_steps: resolved,
        prerequisites,
        refusals,
        dropped_parameters: dropped,
        clamped_parameters: clamped,
        requires_confirmation: needsConfirmation,
        created_at,
    });
}

// ── the direct planner ──────────────────────────────────────────────────────

/** One control press → one typed command. The rationale says so, plainly. */
export function planDirect({ operation: opKey, parameters = {}, input_refs = [], step_id = 'step_1' }) {
    const op = operation(opKey);
    return [proposedStep({
        step_id,
        organ: op.organ,
        operation: opKey,
        parameters,
        input_refs,
        rationale: `the person chose ${op.label}`,
    })];
}

// ── the deterministic prompt planner ────────────────────────────────────────

/**
 * The phrase table. Deterministic, offline, and testable — the planner a person gets when no
 * model is reachable, and the one every prompt test in this lane runs against.
 *
 * Ordered: the first match wins, so the specific phrases sit above the general ones. `find the X`
 * must not be eaten by `find`, and `in front of` must not be eaten by `inside`.
 */
const PHRASES = [
    { re: /\b(?:in front of|occlu\w*|behind)\b/i, operation: 'topology.occlusion', roles: ['source', 'target'] },
    { re: /\b(?:all[- ]pairs|how do these relate|relate to each other)\b/i, operation: 'topology.all_pairs', roles: ['members'] },
    { re: /\b(?:negative space|what surrounds|surrounds|around)\b/i, operation: 'topology.negative_space', roles: ['figure'] },
    { re: /\b(?:inside|within|contained?|contains)\b/i, operation: 'topology.containment', roles: ['source', 'target'] },
    { re: /\b(?:touch\w*|meets?|adjacen\w*|next to)\b/i, operation: 'topology.adjacency', roles: ['source', 'target'] },
    { re: /\b(?:overlap\w*|intersect\w*)\b/i, operation: 'topology.overlap', roles: ['source', 'target'] },
    { re: /\b(?:disjoint|apart|separate\w*|clearance|how far)\b/i, operation: 'topology.disjoint', roles: ['source', 'target'] },
    { re: /\b(?:compare|repeat|the other adapter|same thing)\b/i, operation: 'extent.compare', roles: ['left', 'right'] },
    { re: /\brefine\b/i, operation: 'extent.refine', roles: ['base'] },
    { re: /\b(?:mask every|find all|every instance|all instances|everything)\b/i, operation: 'extent.find_all', roles: [] },
    { re: /\b(?:mask|find|show|where(?:'s| is))\b/i, operation: 'extent.find_named', roles: [], concept: true },
];

/** Pull the concept out of "find the drapery" / "mask every face". Never invents one. */
export function conceptFrom(text) {
    const m = String(text || '').match(
        /\b(?:mask|find|show|segment|where(?:'s| is))\s+(?:me\s+)?(?:every|all|the|a|an)?\s*([\w\s-]{1,120}?)\s*[?.!]*$/i);
    const raw = (m?.[1] || '').trim();
    return raw && raw.length > 1 ? raw : null;
}

/**
 * A reference as this planner reads one: `"art_3"` or `{ artifact_id, instance_id }`.
 *
 * Both spellings, because a caller that has only artifact ids is still saying something true.
 * Normalising here rather than at four call sites is what stops "that mask" from meaning one
 * thing in the prompt arm and another in the direct arm.
 */
const asReference = (entry) => (typeof entry === 'string'
    ? { artifact_id: entry, instance_id: null }
    : { artifact_id: entry?.artifact_id, instance_id: entry?.instance_id ?? null });

/**
 * Text → proposals, using ONLY the references the session says are active or selected.
 *
 * `references` is the session's own list, at whatever depth the person selected: whole artifacts,
 * or artifact/instance pairs. "Do those two touch?" about two masks inside ONE extent set is the
 * ordinary case and it binds two instance refs of one artifact — before A2 that question could
 * not be asked at all.
 *
 * When the phrase needs two endpoints and the session declared fewer, the proposal is emitted
 * WITH the roles it could fill and the resolver refuses it as `missing_extent_inputs` — the
 * honest sequence. Quietly picking two artifacts from the ledger would be language minting an
 * identity.
 */
export function planFromPrompt({ text, selectedOrgan, references = [], step_id = 'step_1',
    parameters = {} }) {
    const said = String(text || '');
    const hit = PHRASES.find((p) => p.re.test(said));
    if (!hit) {
        return {
            proposals: [],
            unmatched: true,
            note: 'No declared operation matches that phrase. The rules planner reads a closed '
                + 'vocabulary; it does not guess.',
        };
    }
    const op = operation(hit.operation);
    const params = { ...parameters };
    if (hit.concept && !params.concept) {
        const concept = conceptFrom(said);
        if (concept) params.concept = concept;
    }
    const declared = references.map(asReference).filter((r) => r.artifact_id);
    const input_refs = [];
    const roles = hit.roles;
    if (roles.length === 1 && roles[0] === 'members') {
        for (const r of declared.slice(0, 12)) {
            input_refs.push(inputRef('members', r.artifact_id, { instance_id: r.instance_id }));
        }
    } else {
        roles.forEach((role, i) => {
            const r = declared[i];
            if (r) input_refs.push(inputRef(role, r.artifact_id, { instance_id: r.instance_id }));
        });
    }
    return {
        proposals: [proposedStep({
            step_id,
            organ: op.organ,
            operation: hit.operation,
            parameters: params,
            input_refs,
            rationale: `deterministic phrase match on ${hit.re.source} → ${op.label}`,
        })],
        unmatched: false,
        crossesOrgan: op.organ !== selectedOrgan,
    };
}

/**
 * The operations a person can reach from here, with the reason any of them is closed.
 *
 * Used to build the Direct controls, so a disabled button always carries a sentence. A control
 * that is simply absent teaches nothing; one that says "sam3_concept is in the catalogue and is
 * not running here" teaches the deployment.
 */
export function availableOperations({ selectedOrgan, mode, capabilityStates = {} }) {
    const families = mode === 'chain'
        ? [...new Set(['extent', 'topology'])]
        : [selectedOrgan];
    return families.flatMap((family) => operationsFor(family).map((op) => {
        const locked = checkOrganLock(op.key, { selectedOrgan, mode });
        const capability = checkCapability(op.key, { states: capabilityStates });
        return {
            ...op,
            organ: family,
            enabled: !locked && !capability,
            refusal: locked || capability || null,
        };
    }));
}
