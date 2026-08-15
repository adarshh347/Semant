// PERCEPTUAL-ORGANS-002 Lane E — the client the laboratory develops and is tested against.
//
// It answers the whole interface in `labClient.js` from the synthetic scenes and the fixture
// runner, and it holds the lab ledger in memory. It is the frontend's stand-in for Lanes B, C, D
// and the store F will build — and its value is that it is DELIBERATELY UNKIND: adapters can be
// declared unavailable, an upload can be made to fail, a run can be made to break, and each of
// those is a state the surface must render rather than an edge case it may skip.
//
// THREE THINGS IT ENFORCES, and they are the three that matter:
//
//   1. A REPLAY RUN CANNOT RECOMPUTE. `replay()` re-serves the recorded artifacts and never
//      touches the runner. `mutateReplayToRecompute()` exists so the suite can prove the guard is
//      real: flip it on and `validateRun` fails, which is the whole point of the guard.
//
//   2. THE SOURCE IS NOT TOUCHED. `source_digest_before` and `source_digest_after` are read from
//      the scene either side of the run, and the scene is frozen.
//
//   3. NO PROMOTION EXISTS. `assertNoPromotionSurface` runs over this object at construction, so
//      adding a `promote` here fails at import time rather than in review.
//
// Determinism: ids come from a counter and time from a fake clock seeded at construction, so two
// identical sessions export byte-identical JSON and the export test can compare them.

import {
    assertNoPromotionSurface, assertUploadedSource,
} from './labClient';
import { CONTRACT } from '../contract/perceptionLabContract';
import {
    assertValid, createIds, labReview, labRun, labSession, replayProvenance,
} from '../records';
import { resolve, planDirect, planFromPrompt } from '../planning';
import { SCENES, sceneAsSource, sceneById, sceneRasters, sceneSource } from '../fixtures/scenes';
import { executeStep } from '../fixtures/fixtureRunner';

const BASE_TIME = Date.UTC(2026, 7, 10, 9, 0, 0);

/** A fake clock. Every call advances it by a fixed step, so durations are real and repeatable. */
function createClock(stepMs = 37) {
    let t = BASE_TIME;
    return {
        now: () => { t += stepMs; return new Date(t).toISOString(); },
        elapsed: (a, b) => (a && b ? Date.parse(b) - Date.parse(a) : null),
        peek: () => new Date(t).toISOString(),
    };
}

/** Every adapter the contract declares, and what this deployment claims about it. */
export function defaultCapabilityStates(overrides = {}) {
    const states = {};
    for (const organ of CONTRACT.organs) {
        for (const adapter of organ.adapters || []) {
            states[adapter.key] = adapter.key === 'human' ? 'available' : 'available';
        }
    }
    // SAM 3 is the adapter this phase most often does not have, so the default deployment says
    // so. A laboratory whose every adapter is available has never shown anybody `unavailable`.
    states.sam3_concept = 'unavailable';
    return { ...states, ...overrides };
}

const ADAPTER_MODELS = {
    yolo_sam2_auto: 'sam2_hiera_large',
    sam3_concept: 'sam3',
    grounded_sam: 'grounding_dino + sam',
    sam2_refine: 'sam2_hiera_large',
};

const ADAPTER_REVISIONS = {
    yolo_sam2_auto: '2024-07-29',
    sam3_concept: '2026-02-11',
    grounded_sam: '2024-03-02',
    sam2_refine: '2024-07-29',
    nestedness_organ: 'wave2.5',
    adjacency_organ: 'wave3',
    mask_arithmetic: 'wave3',
    distance_transform: 'wave3',
    occlusion_organ: 'wave3',
};

/**
 * What a follow-up prompt may mean, in session order.
 *
 * An artifact with a selected instance contributes that instance; one without contributes itself,
 * meaning the whole set. Derived from the session's two selection fields rather than stored, so
 * there is no third place a deselected mask could linger — which is the same rule `SessionView`
 * applies in Python, and the reason both runtimes answer "which one did it mean" identically.
 */
export function sessionReferences(session) {
    const ids = [...new Set([
        ...(session?.active_artifact_id ? [session.active_artifact_id] : []),
        ...(session?.selected_artifact_ids || []),
    ])];
    return ids.flatMap((artifact_id) => {
        const chosen = (session?.selected_instance_refs || [])
            .filter((r) => r.artifact_id === artifact_id);
        return chosen.length
            ? chosen.map((r) => ({ artifact_id, instance_id: r.instance_id }))
            : [{ artifact_id, instance_id: null }];
    });
}

/**
 * @param {object} options
 * @param {Record<string,string>} [options.capabilityStates] adapter → capability_state
 * @param {boolean} [options.uploadFails] make `uploadSource` reject, to exercise the failure path
 * @param {string[]} [options.failOperations] operations whose runner throws, for the `failed` state
 * @param {boolean} [options.modelPlannerReachable] false ⇒ prompts fall back to rules, visibly
 */
export function createFixtureClient(options = {}) {
    const {
        capabilityStates = defaultCapabilityStates(),
        uploadFails = false,
        failOperations = [],
        modelPlannerReachable = false,
        scenes = SCENES,
    } = options;

    const ids = createIds(0);
    const clock = createClock();
    const uploaded = [];

    /** session_id → everything that session holds. The lab's whole store, in a Map. */
    const worlds = new Map();

    const sourceFor = (id) => sceneById(id) || uploaded.find((s) => s.id === id) || null;

    const worldOf = (session_id) => {
        const world = worlds.get(session_id);
        if (!world) throw new Error(`no session ${session_id}`);
        return world;
    };

    const client = {
        identity: () => 'FIXTURE',

        capabilities: async () => ({ states: { ...capabilityStates } }),

        listSources: async () => ({
            sources: [...scenes.map(sceneAsSource), ...uploaded],
        }),

        /**
         * The upload handoff. It either yields a source a run can cite, or it rejects.
         *
         * `assertUploadedSource` is applied to this client's OWN result, not only to a caller's,
         * so the fixture path cannot drift into returning something the real one would refuse.
         */
        uploadSource: async (file) => {
            if (uploadFails) {
                throw new Error('the upload did not complete — the store returned no digest');
            }
            const n = uploaded.length + 1;
            const scene = scenes[n % scenes.length] || scenes[0];
            const source = {
                ...sceneAsSource(scene),
                id: `upload_${n}`,
                scene_id: scene.id,
                title: file?.name || `Uploaded image ${n}`,
                origin: 'upload',
                image_digest: `sha256:upload_${n}_${(file?.size ?? 0)}`,
                note: 'uploaded in this session',
            };
            uploaded.push(source);
            return { source: assertUploadedSource({ source }) };
        },

        createSession: async ({ source_id, selected_organ, mode }) => {
            const source = sourceFor(source_id);
            if (!source) throw new Error(`no source ${source_id}`);
            const base = sceneById(source_id) || sceneById(source.scene_id) || scenes[0];
            const scene = { ...base, image_digest: source.image_digest };
            const session_id = ids.next('labs');
            const session = labSession({
                session_id,
                source: { ...sceneSource(scene), origin: source.origin,
                    post_id: source.post_id ?? null, image_digest: source.image_digest },
                selected_organ,
                mode,
                at: clock.now(),
            });
            worlds.set(session_id, {
                session,
                // Frozen: the runner is handed the scene and cannot change it, which is what
                // makes comparing the digest either side of a run worth doing.
                scene: Object.freeze(scene),
                source,
                rasters: sceneRasters(scene),
                artifactsById: new Map(),
                plansById: new Map(),
                runsById: new Map(),
                reviewsById: new Map(),
                canonicalRegions: new Map(),
            });
            return session;
        },

        // Selections survive an organ switch: the extents a person prepared are exactly what the
        // topology arm is for. What does not survive is any claim about them — switching organ
        // changes what may be asked, never what was found.
        setOrgan: async ({ session_id, selected_organ, mode }) => {
            const world = worldOf(session_id);
            world.session = assertValid('LabSession', {
                ...world.session,
                selected_organ: selected_organ ?? world.session.selected_organ,
                mode: mode ?? world.session.mode,
                updated_at: clock.now(),
            });
            return world.session;
        },

        /**
         * Both arms, one resolver.
         *
         * `planner: 'model'` with no model reachable comes back as `planner: 'rules'` with
         * `planner_fell_back_from: 'model'`. Never as a model plan. That single field is the
         * difference between a laboratory and a demo.
         */
        plan: async ({ session_id, planner, prompt = '', operation: opKey, parameters = {},
            input_refs = [], references = [], for_execution = false }) => {
            const world = worldOf(session_id);
            const { session } = world;
            let identity = planner;
            let fellBackFrom = null;
            let proposals = [];
            let note = null;

            if (planner === 'direct') {
                proposals = planDirect({ operation: opKey, parameters, input_refs,
                    step_id: `step_${ids.peek() + 1}` });
            } else {
                if (planner === 'model' && !modelPlannerReachable) {
                    identity = 'rules';
                    fellBackFrom = 'model';
                }
                const out = planFromPrompt({
                    text: prompt,
                    selectedOrgan: session.selected_organ,
                    // The session's own declared references, at the depth they were declared to.
                    // A caller may override with its own list; it may not widen what the session
                    // said, because `knownReferences` below is built from the session either way.
                    references: references.length ? references : sessionReferences(session),
                    step_id: `step_${ids.peek() + 1}`,
                    parameters,
                });
                proposals = out.proposals;
                note = out.note || null;
            }

            const plan = resolve({
                session_id,
                planner: identity,
                planner_fell_back_from: fellBackFrom,
                selected_organ: session.selected_organ,
                mode: session.mode,
                proposals,
                capabilityStates,
                // Artifacts the ledger holds OR the session selected; instances only where the
                // session named the pair. A set in the ledger does not license every mask inside
                // it — "deselect that mask" has to mean something.
                knownReferences: {
                    artifacts: new Set([
                        ...world.artifactsById.keys(),
                        ...session.selected_artifact_ids,
                    ]),
                    instances: new Set((session.selected_instance_refs || [])
                        .map((r) => `${r.artifact_id}#${r.instance_id}`)),
                },
                plan_id: ids.next('plan'),
                created_at: clock.now(),
                forExecution: for_execution,
            });
            world.plansById.set(plan.plan_id, plan);
            if (note) plan.prerequisites.push(note);
            if (prompt) {
                world.session = {
                    ...world.session,
                    prompt_turns: [...world.session.prompt_turns, {
                        turn_id: ids.next('turn'), text: prompt, at: clock.now(),
                        plan_id: plan.plan_id,
                    }],
                    updated_at: clock.now(),
                };
            }
            return plan;
        },

        run: async ({ session_id, plan_id, execution_identity = 'FIXTURE' }) => {
            const world = worldOf(session_id);
            const plan = world.plansById.get(plan_id);
            if (!plan) throw new Error(`no plan ${plan_id}`);
            const run_id = ids.next('run');
            const digestBefore = world.scene.image_digest;
            const startedAt = clock.now();

            const ctx = {
                scene: world.scene,
                rasters: world.rasters,
                session: world.session,
                artifactsById: world.artifactsById,
                canonicalRegions: world.canonicalRegions,
                ids,
                clock,
                run_id,
                execution_identity,
                adapterModels: ADAPTER_MODELS,
                adapterRevisions: ADAPTER_REVISIONS,
            };

            const attempts = [];
            const artifacts = [];
            const refusals = [...plan.refusals];
            let anyEmpty = false;
            let anyFailed = false;
            let anyCompleted = false;

            for (const step of plan.resolved_steps) {
                if (failOperations.includes(step.operation)) {
                    attempts.push({
                        attempt_id: `att_${step.step_id}`, step_id: step.step_id,
                        operation: step.operation, state: 'failed', adapter: step.adapter,
                        invoked: execution_identity === 'LIVE', started_at: startedAt,
                        completed_at: null, duration_ms: null,
                        detail: 'the adapter raised. No claim is made about the image.',
                    });
                    anyFailed = true;
                    continue;
                }
                const out = executeStep(step, ctx);
                attempts.push(out.attempt);
                if (out.refusal) refusals.push(out.refusal);
                if (out.artifact) {
                    artifacts.push(out.artifact);
                    world.artifactsById.set(out.artifact.identity.artifact_id, out.artifact);
                }
                if (out.attempt.state === 'failed') anyFailed = true;
                else if (out.empty) anyEmpty = true;
                else if (out.attempt.state === 'completed') anyCompleted = true;
            }

            const completedAt = clock.now();
            const outcome = decideOutcome({
                resolved: plan.resolved_steps.length,
                planRefusals: plan.refusals.length,
                refusals,
                anyEmpty,
                anyFailed,
                anyCompleted,
                artifacts,
            });

            const run = labRun({
                run_id,
                session_id,
                execution_identity,
                outcome,
                requested_plan_id: plan.plan_id,
                resolved_plan_id: plan.plan_id,
                artifact_ids: artifacts.map((a) => a.identity.artifact_id),
                stage_attempts: attempts,
                refusals,
                source_digest_before: digestBefore,
                source_digest_after: world.scene.image_digest,
                started_at: startedAt,
                completed_at: anyFailed && !anyCompleted ? null : completedAt,
                duration_ms: anyFailed && !anyCompleted
                    ? null : clock.elapsed(startedAt, completedAt),
                replay: null,
            });
            world.runsById.set(run_id, { run, artifacts });
            world.session = {
                ...world.session,
                run_ids: [...world.session.run_ids, run_id],
                active_artifact_id: artifacts.length
                    ? artifacts[artifacts.length - 1].identity.artifact_id
                    : world.session.active_artifact_id,
                updated_at: completedAt,
            };
            return { run, artifacts, session: world.session };
        },

        /**
         * A ticket, pulled. It never reaches anything, and it says so.
         *
         * A fixture run is a synchronous loop over resolved steps: by the moment a cancel could be
         * requested, there is nothing left to skip. So this answers `cancelled: false` — which is
         * the SAME answer the live client gives for a run on another worker, and the same shape,
         * which is the point of it being on the interface at all. A fixture that pretended to stop
         * something would teach the surface a promise the real wire cannot keep.
         */
        cancel: async ({ session_id, run_ticket }) => {
            worldOf(session_id);
            return {
                cancelled: false,
                note: `nothing of ticket ${run_ticket} is in flight — a fixture run completes `
                    + 'inside the call that started it, so there is no stage left to skip.',
            };
        },

        /**
         * Re-open a recorded run. Nothing is called; the artifacts are the ones already in the
         * ledger, and `adapter_callable: false` is on the record for `validateRun` to check.
         */
        replay: async ({ session_id, run_id }) => {
            const world = worldOf(session_id);
            const recorded = world.runsById.get(run_id);
            if (!recorded) throw new Error(`no run ${run_id}`);
            const startedAt = clock.now();
            const completedAt = clock.now();
            const run = labRun({
                run_id: ids.next('run'),
                session_id,
                execution_identity: 'REPLAY',
                outcome: recorded.run.outcome,
                requested_plan_id: recorded.run.requested_plan_id,
                resolved_plan_id: recorded.run.resolved_plan_id,
                artifact_ids: recorded.run.artifact_ids,
                stage_attempts: recorded.run.stage_attempts.map((a) => ({
                    ...a,
                    // Never `invoked`. The recorded duration was the measurement; this one is the
                    // reading of it, and they are deliberately different numbers.
                    invoked: options.mutateReplayToRecompute === true,
                    started_at: startedAt,
                    completed_at: completedAt,
                    duration_ms: clock.elapsed(startedAt, completedAt),
                    detail: 're-shown from the lab ledger',
                })),
                refusals: recorded.run.refusals,
                source_digest_before: world.scene.image_digest,
                source_digest_after: world.scene.image_digest,
                started_at: startedAt,
                completed_at: completedAt,
                duration_ms: clock.elapsed(startedAt, completedAt),
                replay: replayProvenance({
                    source_run_id: run_id,
                    recorded_at: recorded.run.completed_at || recorded.run.started_at,
                    reason: 're-opened from the lab ledger',
                }),
            });
            world.runsById.set(run.run_id, { run, artifacts: recorded.artifacts });
            world.session = {
                ...world.session,
                run_ids: [...world.session.run_ids, run.run_id],
                updated_at: completedAt,
            };
            return { run, artifacts: recorded.artifacts, session: world.session };
        },

        review: async ({ session_id, artifact_id, reviewer = 'curator', verdict, notes = '',
            corrections = [] }) => {
            const world = worldOf(session_id);
            if (!world.artifactsById.has(artifact_id)) throw new Error(`no artifact ${artifact_id}`);
            const review = labReview({
                review_id: ids.next('rev'),
                session_id,
                artifact_id,
                reviewer,
                verdict,
                notes,
                corrections,
                reviewed_at: clock.now(),
            });
            world.reviewsById.set(review.review_id, review);
            world.session = {
                ...world.session,
                review_ids: [...world.session.review_ids, review.review_id],
                updated_at: review.reviewed_at,
            };
            // The artifact is NOT touched. Not its lifecycle, not its epistemic status. A person
            // saying `correct` has not made a box-basis containment measured.
            return review;
        },

        /** A curation state, and nothing else. `kept` is not promoted and not `measured`. */
        setLifecycle: async ({ session_id, artifact_id, status, by = 'curator' }) => {
            const world = worldOf(session_id);
            const artifact = world.artifactsById.get(artifact_id);
            if (!artifact) throw new Error(`no artifact ${artifact_id}`);
            const next = {
                ...artifact,
                lifecycle: { status, changed_at: clock.now(), changed_by: by },
            };
            world.artifactsById.set(artifact_id, next);
            return next;
        },

        // ── reading the ledger back ─────────────────────────────────────────

        getSession: async ({ session_id }) => worldOf(session_id).session,

        history: async ({ session_id }) => {
            const world = worldOf(session_id);
            return {
                session: world.session,
                plans: [...world.plansById.values()],
                runs: [...world.runsById.values()].map((r) => r.run),
                artifacts: [...world.artifactsById.values()],
                reviews: [...world.reviewsById.values()],
            };
        },

        select: async ({ session_id, artifact_ids, active_artifact_id,
            selected_instance_refs }) => {
            const world = worldOf(session_id);
            const ids = artifact_ids ?? world.session.selected_artifact_ids;
            const active = active_artifact_id !== undefined
                ? active_artifact_id : world.session.active_artifact_id;
            // An instance ref whose artifact is no longer selected is dropped HERE as well as in
            // the hook, because this stands in for the backend and the backend is where the
            // invariant has to hold. `LabSession` refuses the other shape, so a client that let
            // one through would fail the validator rather than quietly disobey a deselection.
            const declared = new Set([...ids, ...(active ? [active] : [])]);
            const instances = (selected_instance_refs ?? world.session.selected_instance_refs)
                .filter((r) => declared.has(r.artifact_id));
            world.session = {
                ...world.session,
                selected_artifact_ids: ids,
                active_artifact_id: active,
                selected_instance_refs: instances,
                updated_at: clock.now(),
            };
            return world.session;
        },
    };

    return assertNoPromotionSurface(client);
}

/**
 * The outcome, decided once.
 *
 * The order matters and each branch is a distinction `absence_semantics` insists on:
 * `unavailable` is not `refused` is not `empty` is not `failed`, and `partial` is what you get
 * when some of those happened in one run.
 */
export function decideOutcome({ resolved, planRefusals, refusals, anyEmpty, anyFailed,
    anyCompleted, artifacts }) {
    const hasCapabilityRefusal = refusals.some((r) => r.code === 'capability_unavailable');
    if (!resolved) {
        // Nothing was authorized. Either a law said no, or an adapter is not here.
        if (hasCapabilityRefusal) return 'unavailable';
        if (planRefusals || refusals.length) return 'refused';
        return 'empty';
    }
    if (anyFailed && !anyCompleted && !anyEmpty) return 'failed';
    if (anyFailed || (refusals.length && (anyCompleted || anyEmpty))) return 'partial';
    if (refusals.length) return hasCapabilityRefusal ? 'unavailable' : 'refused';
    if (anyCompleted) return artifacts.length ? 'ready' : 'empty';
    if (anyEmpty) return 'empty';
    return 'empty';
}
