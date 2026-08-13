// PERCEPTUAL-ORGANS-002 Lane E — the one piece of state the laboratory has.
//
// Every component below the shell is a view. This hook holds the session, the ledger and the
// selection, and it is the only place that calls the client. Two reasons, and the second is the
// one that matters:
//
//   1. a component that fetches is a component that cannot be mounted in a test;
//   2. every mutation of the ledger passes through one function, so "there is no hidden save
//      path" is a statement about ~200 lines rather than about a subtree. `setLifecycle` is here,
//      `review` is here, and there is nothing else that writes.
//
// WHAT IT WILL NOT DO:
//
//   - it does not derive a lifecycle from a verdict, or a verdict from a lifecycle;
//   - it does not mark anything `kept` because a run succeeded;
//   - it does not resolve a follow-up prompt against anything but `selected_artifact_ids`,
//     `selected_instance_refs` and `active_artifact_id`, which is why `references` is derived
//     from those on every render and passed explicitly to `plan()`. Derived, never remembered —
//     a deselected mask has nowhere in this hook to survive;
//   - it does not swallow an error. A rejected client call lands in `error`, with the outcome
//     `failed` on the surface, and never silently leaves the previous run on screen as if it
//     were the answer to the new question.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { assertClientShape } from './clients/labClient';
import { instanceRef } from './records';

const EMPTY = Object.freeze({
    session: null,
    plan: null,
    run: null,
    artifacts: [],
    plans: [],
    runs: [],
    reviews: [],
    ledger: [],
});

export default function useLabSession(client, { initialOrgan = 'extent',
    initialMode = 'isolation' } = {}) {
    const [sources, setSources] = useState(null);          // null = not asked yet
    const [sourceId, setSourceId] = useState(null);
    const [capabilities, setCapabilities] = useState({});
    const [state, setState] = useState(EMPTY);
    const [busy, setBusy] = useState(null);                // what is in flight, in words
    const [error, setError] = useState(null);
    const [uploadError, setUploadError] = useState(null);
    const [organ, setOrganState] = useState(initialOrgan);
    const [mode, setModeState] = useState(initialMode);
    const [selectedIds, setSelectedIds] = useState([]);
    const [selectedInstances, setSelectedInstances] = useState([]);
    const [activeId, setActiveId] = useState(null);
    const [focus, setFocus] = useState({ instanceId: null, relationId: null });

    const alive = useRef(true);
    /**
     * Is this hook still mounted? Set on the way IN as well as on the way out.
     *
     * THE `alive.current = true` IS THE WHOLE OF A BUG THIS LANE FOUND BY MOUNTING THE
     * LABORATORY FOR REAL. Under `React.StrictMode` — which the app root uses — React mounts,
     * runs the effect, runs its cleanup, and runs the effect again. With only a cleanup here, the
     * second pass left `alive.current` false forever: `guard`'s `finally` then skipped
     * `setBusy(null)`, `busy` stayed truthy, and every control in the laboratory was disabled from
     * the first action onwards. The surface looked completely finished and did nothing.
     *
     * It was invisible to this lane's own suite because those tests mount without StrictMode, and
     * invisible in production because the double-invoke is a development behaviour. Which is
     * exactly why it took mounting it at a route to find, and why the fix belongs here rather than
     * in the route.
     */
    useEffect(() => {
        alive.current = true;
        return () => { alive.current = false; };
    }, []);

    useMemo(() => assertClientShape(client), [client]);

    const guard = useCallback(async (what, fn) => {
        setBusy(what);
        setError(null);
        try {
            const out = await fn();
            return out;
        } catch (err) {
            if (alive.current) setError({ what, message: String(err?.message || err) });
            return null;
        } finally {
            if (alive.current) setBusy(null);
        }
    }, []);

    useEffect(() => {
        let live = true;
        Promise.all([client.listSources(), client.capabilities()])
            .then(([s, c]) => {
                if (!live) return;
                setSources(s.sources);
                setCapabilities(c.states || {});
            })
            .catch((err) => { if (live) setError({ what: 'opening the laboratory', message: String(err.message || err) }); });
        return () => { live = false; };
    }, [client]);

    const refresh = useCallback(async (session_id) => {
        const history = await client.history({ session_id });
        if (!alive.current) return null;
        setState((prev) => ({
            ...prev,
            session: history.session,
            plans: history.plans,
            runs: history.runs,
            ledger: history.artifacts,
            reviews: history.reviews,
        }));
        return history;
    }, [client]);

    // ── source and organ ────────────────────────────────────────────────────

    const openSession = useCallback(async (source_id) => guard('opening a session', async () => {
        const session = await client.createSession({
            source_id, selected_organ: organ, mode });
        setSourceId(source_id);
        setState({ ...EMPTY, session, ledger: [], plans: [], runs: [], reviews: [] });
        setSelectedIds([]);
        setSelectedInstances([]);
        setActiveId(null);
        setFocus({ instanceId: null, relationId: null });
        await refresh(session.session_id);
        return session;
    }), [client, guard, organ, mode, refresh]);

    /**
     * The upload handoff.
     *
     * An upload that rejects sets `uploadError` and NOTHING else: no session, no source in the
     * list, no optimistic row that would let a person believe the image is there. This is the
     * whole of "upload failures do not report success".
     */
    const uploadSource = useCallback(async (file) => {
        setUploadError(null);
        setBusy('uploading');
        try {
            const { source } = await client.uploadSource(file);
            if (!alive.current) return null;
            setSources((prev) => [...(prev || []), source]);
            return source;
        } catch (err) {
            if (alive.current) setUploadError(String(err?.message || err));
            return null;
        } finally {
            if (alive.current) setBusy(null);
        }
    }, [client]);

    const setOrgan = useCallback(async (nextOrgan) => {
        setOrganState(nextOrgan);
        if (!state.session) return;
        await guard('switching organ', async () => {
            const session = await client.setOrgan({
                session_id: state.session.session_id, selected_organ: nextOrgan, mode });
            setState((prev) => ({ ...prev, session }));
            return session;
        });
    }, [client, guard, mode, state.session]);

    const setMode = useCallback(async (nextMode) => {
        setModeState(nextMode);
        if (!state.session) return;
        await guard('switching mode', async () => {
            const session = await client.setOrgan({
                session_id: state.session.session_id, selected_organ: organ, mode: nextMode });
            setState((prev) => ({ ...prev, session }));
            return session;
        });
    }, [client, guard, organ, state.session]);

    // ── selection ───────────────────────────────────────────────────────────

    const select = useCallback(async (ids, nextActive, nextInstances) => {
        setSelectedIds(ids);
        if (nextActive !== undefined) setActiveId(nextActive);
        // An instance whose artifact just left the selection leaves with it. Otherwise "deselect
        // that set" would be recorded and then disobeyed by the next follow-up, which would still
        // find the mask through the other field.
        const kept = (nextInstances ?? selectedInstances).filter(
            (r) => ids.includes(r.artifact_id));
        setSelectedInstances(kept);
        if (!state.session) return;
        const session = await client.select({
            session_id: state.session.session_id,
            artifact_ids: ids,
            active_artifact_id: nextActive,
            selected_instance_refs: kept,
        });
        setState((prev) => ({ ...prev, session }));
    }, [client, state.session, selectedInstances]);

    const toggleSelected = useCallback((id) => {
        const next = selectedIds.includes(id)
            ? selectedIds.filter((x) => x !== id) : [...selectedIds, id];
        select(next, next.includes(id) ? id : activeId);
    }, [selectedIds, activeId, select]);

    /**
     * Narrow the selection to one mask, or widen it back.
     *
     * SELECTING AN INSTANCE SELECTS ITS ARTIFACT — the contract refuses a session that holds an
     * instance ref for an artifact it has not selected, because a reference reachable from one
     * field and invisible in the other is how a deselection stops taking effect.
     *
     * Deselecting the instance leaves the ARTIFACT selected: un-narrowing returns the reference
     * to the whole set, which is where it was. Making it also un-select would leave a person no
     * way to say "actually, all of them".
     */
    const toggleSelectedInstance = useCallback((artifact_id, instance_id) => {
        const has = selectedInstances.some(
            (r) => r.artifact_id === artifact_id && r.instance_id === instance_id);
        const nextInstances = has
            ? selectedInstances.filter(
                (r) => !(r.artifact_id === artifact_id && r.instance_id === instance_id))
            : [...selectedInstances, instanceRef(artifact_id, instance_id)];
        const nextIds = selectedIds.includes(artifact_id)
            ? selectedIds : [...selectedIds, artifact_id];
        select(nextIds, has ? activeId : artifact_id, nextInstances);
    }, [selectedInstances, selectedIds, activeId, select]);

    /**
     * What a follow-up prompt is allowed to mean, in session order.
     *
     * An artifact with a selected instance contributes that instance; one without contributes
     * itself, meaning the whole set. Derived on every render from the two selection fields rather
     * than remembered, so there is nowhere for a deselected mask to survive.
     */
    const references = useMemo(() => selectedIds.flatMap((id) => {
        const chosen = selectedInstances.filter((r) => r.artifact_id === id);
        return chosen.length ? chosen : [{ artifact_id: id, instance_id: null }];
    }), [selectedIds, selectedInstances]);

    // ── planning and running ────────────────────────────────────────────────

    /**
     * COMPOSING IS NOT RUNNING, and the contract says so in one flag.
     *
     * `for_execution: false` is not laxity. `topology.occlusion` declares its depth input optional
     * to plan and required to run, precisely so a person may assemble the question before they
     * have a depth field — and this laboratory has no organ that can make one. Planning with
     * `for_execution: true` would collapse that into "you may not even ask", which is the shape of
     * a hidden capability rather than a declared one.
     *
     * The gate is not skipped, it is MOVED: `PlanPreview` runs the execution-time input check over
     * every resolved step and says, before the button is pressed, which of them will refuse when
     * run. The run then refuses for real, with a refusal artifact in the ledger.
     */
    const planDirectly = useCallback((operation, parameters, input_refs) => guard(
        'proposing a plan', async () => {
            // A CONTROL THAT NAMED A MASK HAS SELECTED THAT MASK, and the session is told so
            // before the plan is proposed.
            //
            // The reference gate is one gate for both arms — that is the whole claim the Direct
            // and Prompt arms rest on — and it refuses an instance the session never declared.
            // So rather than exempting the Direct arm, clicking a mask on the stage RECORDS the
            // selection, which is what clicking a mask means. The consequence is the one that
            // matters: the follow-up prompt afterwards reads the same list, and deselecting the
            // mask takes it away from both arms at once.
            //
            // Only instances the LEDGER holds are recorded. A control cannot declare a mask into
            // existence: a ref naming one that is not in the artifact stays undeclared and the
            // resolver refuses it `unknown_reference`, which is the same answer a prompt gets.
            const holds = (artifact_id, instance_id) => state.ledger
                .filter((a) => a.identity.artifact_id === artifact_id)
                .some((a) => (a.measurement?.payload?.instances || [])
                    .some((i) => i.instance_id === instance_id));
            const named = (input_refs || []).filter(
                (r) => r?.artifact_id && r?.instance_id && holds(r.artifact_id, r.instance_id));
            const fresh = named.filter((r) => !selectedInstances.some(
                (s) => s.artifact_id === r.artifact_id && s.instance_id === r.instance_id));
            if (fresh.length) {
                const nextInstances = [...selectedInstances,
                    ...fresh.map((r) => instanceRef(r.artifact_id, r.instance_id))];
                const nextIds = [...new Set([...selectedIds, ...named.map((r) => r.artifact_id)])];
                await select(nextIds, activeId ?? named[0].artifact_id, nextInstances);
            }
            const plan = await client.plan({
                session_id: state.session.session_id,
                planner: 'direct',
                operation,
                parameters,
                input_refs,
                references,
                for_execution: false,
            });
            setState((prev) => ({ ...prev, plan }));
            return plan;
        }), [client, guard, state.session, state.ledger, references, selectedInstances, selectedIds,
        activeId, select]);

    const planFromText = useCallback((text, planner = 'model') => guard(
        'proposing a plan', async () => {
            const plan = await client.plan({
                session_id: state.session.session_id,
                planner,
                prompt: text,
                // Follow-ups resolve ONLY through what this session has selected, at the depth
                // it was selected to. "those two" means these references, or it means nothing.
                references,
                for_execution: false,   // see `planDirectly` — composing is not running
            });
            setState((prev) => ({ ...prev, plan }));
            await refresh(state.session.session_id);
            return plan;
        }), [client, guard, state.session, references, refresh]);

    const runPlan = useCallback((plan_id, execution_identity = 'FIXTURE') => guard(
        'running', async () => {
            const out = await client.run({
                session_id: state.session.session_id, plan_id, execution_identity });
            setState((prev) => ({ ...prev, run: out.run, artifacts: out.artifacts }));
            const nextActive = out.artifacts.length
                ? out.artifacts[out.artifacts.length - 1].identity.artifact_id : activeId;
            setActiveId(nextActive);
            await refresh(state.session.session_id);
            return out;
        }), [client, guard, state.session, activeId, refresh]);

    const replayRun = useCallback((run_id) => guard('replaying', async () => {
        const out = await client.replay({ session_id: state.session.session_id, run_id });
        setState((prev) => ({ ...prev, run: out.run, artifacts: out.artifacts }));
        await refresh(state.session.session_id);
        return out;
    }), [client, guard, state.session, refresh]);

    // ── the two axes a person moves, one at a time ──────────────────────────

    const review = useCallback((artifact_id, verdict, notes, corrections = []) => guard(
        'recording a verdict', async () => {
            const record = await client.review({
                session_id: state.session.session_id, artifact_id, verdict, notes, corrections });
            await refresh(state.session.session_id);
            return record;
        }), [client, guard, state.session, refresh]);

    const setLifecycle = useCallback((artifact_id, status) => guard(
        'changing the lifecycle', async () => {
            const record = await client.setLifecycle({
                session_id: state.session.session_id, artifact_id, status });
            await refresh(state.session.session_id);
            return record;
        }), [client, guard, state.session, refresh]);

    // ── derived reading ─────────────────────────────────────────────────────

    const byId = useMemo(
        () => new Map(state.ledger.map((a) => [a.identity.artifact_id, a])), [state.ledger]);

    const active = activeId ? byId.get(activeId) || null : null;

    const reviewsFor = useCallback(
        (artifact_id) => state.reviews.filter((r) => r.artifact_id === artifact_id),
        [state.reviews]);

    return {
        // what the laboratory is talking to
        clientIdentity: client.identity(),
        capabilities,
        sources,
        sourceId,
        // where it is
        session: state.session,
        organ,
        mode,
        // what it holds
        plan: state.plan,
        run: state.run,
        artifacts: state.artifacts,
        ledger: state.ledger,
        plans: state.plans,
        runs: state.runs,
        reviews: state.reviews,
        byId,
        active,
        activeId,
        selectedIds,
        selectedInstances,
        references,
        focus,
        // what it is doing
        busy,
        error,
        uploadError,
        // what a person can do
        openSession,
        uploadSource,
        setOrgan,
        setMode,
        select,
        toggleSelected,
        toggleSelectedInstance,
        setActiveId,
        setFocus,
        planDirectly,
        planFromText,
        runPlan,
        replayRun,
        review,
        setLifecycle,
        reviewsFor,
        refresh,
    };
}
