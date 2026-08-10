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
//   - it does not resolve a follow-up prompt against anything but `selected_artifact_ids` and
//     `active_artifact_id`, which is why `references` is passed explicitly to `plan()`;
//   - it does not swallow an error. A rejected client call lands in `error`, with the outcome
//     `failed` on the surface, and never silently leaves the previous run on screen as if it
//     were the answer to the new question.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { assertClientShape } from './clients/labClient';

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
    const [activeId, setActiveId] = useState(null);
    const [focus, setFocus] = useState({ instanceId: null, relationId: null });

    const alive = useRef(true);
    useEffect(() => () => { alive.current = false; }, []);

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

    const select = useCallback(async (ids, nextActive) => {
        setSelectedIds(ids);
        if (nextActive !== undefined) setActiveId(nextActive);
        if (!state.session) return;
        const session = await client.select({
            session_id: state.session.session_id,
            artifact_ids: ids,
            active_artifact_id: nextActive,
        });
        setState((prev) => ({ ...prev, session }));
    }, [client, state.session]);

    const toggleSelected = useCallback((id) => {
        const next = selectedIds.includes(id)
            ? selectedIds.filter((x) => x !== id) : [...selectedIds, id];
        select(next, next.includes(id) ? id : activeId);
    }, [selectedIds, activeId, select]);

    // ── planning and running ────────────────────────────────────────────────

    const planDirectly = useCallback((operation, parameters, input_refs) => guard(
        'proposing a plan', async () => {
            const plan = await client.plan({
                session_id: state.session.session_id,
                planner: 'direct',
                operation,
                parameters,
                input_refs,
                references: selectedIds,
                for_execution: true,
            });
            setState((prev) => ({ ...prev, plan }));
            return plan;
        }), [client, guard, state.session, selectedIds]);

    const planFromText = useCallback((text, planner = 'model') => guard(
        'proposing a plan', async () => {
            const plan = await client.plan({
                session_id: state.session.session_id,
                planner,
                prompt: text,
                // Follow-ups resolve ONLY through what this session has selected. "those two"
                // means these ids, or it means nothing.
                references: selectedIds,
                for_execution: true,
            });
            setState((prev) => ({ ...prev, plan }));
            await refresh(state.session.session_id);
            return plan;
        }), [client, guard, state.session, selectedIds, refresh]);

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
