import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import AtlasCanvas from './AtlasCanvas.jsx';
import AtlasLightTable from './AtlasLightTable.jsx';
import AtlasDifferential from './AtlasDifferential.jsx';
import AtlasPlanPanel from './AtlasPlanPanel.jsx';
import { atlasService } from './atlasService.js';
import {
    ATLAS_MODES, MACHINE_READ_INTENTION, MODE_CANVAS, MODE_LIGHT_TABLE, MODE_PLAN,
    arrangementFrom, flowNodesFromView, isClaimNodeId, isMode, notePatchesFrom, notesOf,
    positionsOf, refusalLines,
} from './atlasDocument.js';
import { acceptPayload, bindingEdges, claimFlowNodes } from './atlasPlan.js';
import {
    connectionRefusal, refusalLine, refusedEdge, relationEdges, relationSummary,
} from './atlasRelation.js';
import {
    droppedLines, ghostEdges, scoutRefusalLine, scoutSummary, withoutCandidate,
} from './atlasScout.js';

/**
 * ATLAS T1 — the workspace: one Atlas document, seen through whichever mode is on.
 *
 * WHAT MAKES MODES REAL. Everything that IS the Atlas lives here — the hydrated view, the nodes,
 * the arrangement, the author notes, the way into the Differential, both debounced saves. A mode
 * receives that state and renders it. So switching mode cannot switch documents (there is only
 * one), cannot lose an unsaved note (the note is held here, and its save timer keeps running
 * across the switch), and cannot strand a drag (the arrangement is here too).
 *
 * The alternative — each mode owning a fetch and its own copy of the state — would have been less
 * code today and a bug generator forever: two renderers with two ideas of the same document,
 * diverging the moment a save landed in one and not the other. "A mode only swaps the renderer"
 * has to be true in the component tree, not just in the prose.
 *
 * THE DIFFERENTIAL PATH IS C2'S, UNCHANGED AND SHARED. Both modes hand a post id up to `openImage`;
 * the workspace unmounts itself, gives the instrument the viewport, and on return re-reads the
 * ledger. Neither mode learns what was made — the `/view` re-read is the only channel, which is
 * what keeps the Atlas from ever holding percept truth.
 *
 * TWO SAVES, TWO ROUTES, ON PURPOSE. Positions go to `/arrangement`, notes to `/notes`. They are
 * debounced identically and refuse identically, and neither request can perform the other's
 * gesture — a drag cannot write a note, and typing a note cannot move a picture.
 */

const SAVE_DEBOUNCE_MS = 600;

export default function AtlasWorkspace({
    atlasId, service = atlasService, initialMode = MODE_CANVAS,
}) {
    const [view, setView] = useState(null);
    const [nodes, setNodes] = useState([]);
    const [mode, setMode] = useState(isMode(initialMode) ? initialMode : MODE_CANVAS);
    const [error, setError] = useState('');
    const [status, setStatus] = useState('');
    const [notesStatus, setNotesStatus] = useState('');
    const [refusals, setRefusals] = useState([]);

    // C2: which image is open in the Differential — and, T1, what to ask of it on arrival.
    const [open, setOpen] = useState(null);    // { postId, intention }

    // ── C4: the argument ──
    // `plan` is what the server last said; `claims` is what the writer has done to it since. Kept
    // apart on purpose: `isEdited` compares them, and one merged copy would leave nothing able to
    // say that the verdicts on screen predate the edit.
    const [thesis, setThesis] = useState('');
    const [plan, setPlan] = useState(null);
    const [claims, setClaims] = useState([]);
    const [planning, setPlanning] = useState(false);
    const [accepting, setAccepting] = useState(false);
    const [accepted, setAccepted] = useState(false);
    const [planError, setPlanError] = useState('');

    // ── C3: relations ──
    // The last refusal, held only so it can be DRAWN on the line it refers to. Never sent, never
    // stored, cleared by the next gesture — a refusal about one pair of photographs must not
    // linger over a canvas the writer has moved on from.
    const [relationRefusal, setRelationRefusal] = useState(null);
    const [drawing, setDrawing] = useState(false);

    // ── T2: the Scout ──
    // Candidates are SESSION state and nothing else. A ghost is a model's hunch about which pair
    // might repay comparison; it is not a relation, it is not stored, and it is gone on reload.
    // Keeping it out of the document is what makes "nothing here is a relation yet" true rather
    // than merely printed.
    const [candidates, setCandidates] = useState([]);
    const [scoutDropped, setScoutDropped] = useState([]);
    const [scoutRefusal, setScoutRefusal] = useState(null);
    const [scouting, setScouting] = useState(false);
    const [confirming, setConfirming] = useState('');
    // A refusal that OUTLIVES the ghost it came from. Confirming removes the candidate either
    // way; if the answer was "no", the reason has to stay on screen, or the writer sees a
    // suggestion vanish and learns nothing about why the comparison would not ground.
    const [scoutAnswers, setScoutAnswers] = useState([]);

    // What the SERVER is known to hold. Saves diff against these, not against the last render, so
    // a drag that ends where it started and a note re-typed to its own text both send nothing.
    const savedPositions = useRef({});
    const savedNotes = useRef({});
    const posTimer = useRef(null);
    const noteTimer = useRef(null);

    const openImage = useCallback((postId) => setOpen({ postId, intention: null }), []);
    const machineRead = useCallback(
        (postId) => setOpen({ postId, intention: MACHINE_READ_INTENTION }), []);

    const callbacks = useMemo(
        () => ({ onOpen: openImage, onMachineRead: machineRead }), [openImage, machineRead]);

    /**
     * Re-read the ledger's current answer and redraw the overlays (C2).
     *
     * Only `data` is replaced; each node's `position` and its NOTES are carried over from what is
     * on screen. Positions, because taking them from the refetch would snap a node back over a
     * drag still inside its debounce. Notes, for the identical reason — a note typed two hundred
     * milliseconds ago is not on the server yet, and letting the server's older answer win would
     * delete a sentence the writer is still looking at.
     */
    const refreshOverlays = useCallback(async () => {
        try {
            const data = await service.view(atlasId);
            setView(data);
            const fresh = flowNodesFromView(data, callbacks);
            setNodes((prev) => {
                const at = Object.fromEntries(prev.map((n) => [n.id, n.position]));
                const said = Object.fromEntries(prev.map((n) => [n.id, n.data?.notes]));
                return fresh.map((n) => ({
                    ...n,
                    position: at[n.id] || n.position,
                    data: { ...n.data, notes: said[n.id] || n.data.notes },
                }));
            });
        } catch (e) {
            setError(e?.message || 'Could not refresh what is on this Atlas.');
        }
    }, [atlasId, callbacks, service]);

    useEffect(() => {
        let live = true;
        setError('');
        (async () => {
            try {
                const data = await service.view(atlasId);
                if (!live) return;
                setView(data);
                const flow = flowNodesFromView(data, callbacks);
                setNodes(flow);
                savedPositions.current = positionsOf(flow);
                savedNotes.current = notesOf(flow);
                // C4: an Atlas that already holds an accepted plan opens wearing it. The stored
                // plan is the record — shown as it was stored, never re-planned, because a fresh
                // model call on every page load would quietly replace what the writer accepted.
                if (data?.plan) {
                    setPlan(data.plan);
                    setClaims(data.plan.claims || []);
                    setThesis(data.plan.thesis || '');
                    setAccepted(true);
                }
            } catch (e) {
                if (live) setError(e?.message || 'Could not open this Atlas.');
            }
        })();
        return () => {
            live = false;
            if (posTimer.current) clearTimeout(posTimer.current);
            if (noteTimer.current) clearTimeout(noteTimer.current);
        };
    }, [atlasId, callbacks, service]);

    /** Coming back. The Atlas is told only that the curator is done — never what they made. */
    const closeDifferential = useCallback(async () => {
        setOpen(null);
        await refreshOverlays();
    }, [refreshOverlays]);

    // ── the arrangement save (C1) ────────────────────────────────────────────

    const flushPositions = useCallback(async (current) => {
        const patches = arrangementFrom(current, savedPositions.current);
        if (!patches.length) return;
        setStatus('saving…');
        try {
            const res = await service.saveArrangement(atlasId, patches);
            // Trust what came BACK — the server is what a reload will read, and a refused node
            // must not be recorded here as though it had moved.
            const confirmed = {};
            (res?.atlas?.nodes || []).forEach((n) => {
                confirmed[String(n.node_id)] = { x: Number(n.x), y: Number(n.y) };
            });
            savedPositions.current = confirmed;
            setRefusals(refusalLines(res?.refused));
            setStatus('arrangement saved');
        } catch (e) {
            setStatus('');
            setError(e?.message || 'The arrangement did not save.');
        }
    }, [atlasId, service]);

    const onNodesChange = useCallback((applied) => {
        setNodes(applied);
        if (posTimer.current) clearTimeout(posTimer.current);
        posTimer.current = setTimeout(() => flushPositions(applied), SAVE_DEBOUNCE_MS);
    }, [flushPositions]);

    // ── the notes save (T1) ──────────────────────────────────────────────────

    const flushNotes = useCallback(async (current) => {
        const patches = notePatchesFrom(current, savedNotes.current);
        if (!patches.length) return;
        setNotesStatus('saving…');
        try {
            const res = await service.saveNotes(atlasId, patches);
            const confirmed = {};
            (res?.atlas?.nodes || []).forEach((n) => {
                confirmed[String(n.node_id)] = (n.notes || []).map((note) => ({
                    note_id: String(note?.note_id || ''), text: String(note?.text || ''),
                }));
            });
            savedNotes.current = confirmed;
            setRefusals(refusalLines(res?.refused));
            setNotesStatus('notes saved');
        } catch (e) {
            // A note the writer believes is saved and is not is the failure that matters here —
            // they will close the tab on the strength of seeing their own sentence on screen.
            setNotesStatus('');
            setError(e?.message || 'Your notes did not save.');
        }
    }, [atlasId, service]);

    const changeNotes = useCallback((nodeId, notes) => {
        setNodes((prev) => {
            const next = prev.map((n) => (n.id === nodeId
                ? { ...n, data: { ...n.data, notes } }
                : n));
            if (noteTimer.current) clearTimeout(noteTimer.current);
            noteTimer.current = setTimeout(() => flushNotes(next), SAVE_DEBOUNCE_MS);
            return next;
        });
    }, [flushNotes]);

    // ── C4: ask, edit, accept ────────────────────────────────────────────────

    const onPlan = useCallback(async () => {
        if (!thesis.trim() || planning) return;
        setPlanning(true);
        setPlanError('');
        setAccepted(false);
        try {
            const data = await service.proposePlan(atlasId, { thesis: thesis.trim() });
            setPlan(data);
            setClaims(data.claims || []);
        } catch (e) {
            // A planner that failed says so. It never leaves the previous plan on screen looking
            // like the answer to the new thesis.
            setPlan(null);
            setClaims([]);
            setPlanError(e?.message || 'The planner could not be reached.');
        } finally {
            setPlanning(false);
        }
    }, [atlasId, planning, service, thesis]);

    const onAccept = useCallback(async () => {
        if (!claims.length || accepting) return;
        setAccepting(true);
        setPlanError('');
        try {
            const res = await service.acceptPlan(atlasId, acceptPayload(thesis, claims));
            // Trust what came BACK. The server re-bound the edited structure, so its verdicts are
            // the only ones describing what was actually accepted — replacing the local claims is
            // what makes a claim that lost its evidence go struck on screen.
            const stored = res?.plan || null;
            setPlan(stored);
            setClaims(stored?.claims || []);
            setAccepted(true);
        } catch (e) {
            setPlanError(e?.message || 'The plan was not accepted.');
        } finally {
            setAccepting(false);
        }
    }, [accepting, atlasId, claims, service, thesis]);

    const onDiscard = useCallback(async () => {
        setPlan(null);
        setClaims([]);
        setAccepted(false);
        setPlanError('');
        try {
            if (accepted) await service.clearPlan(atlasId);
        } catch (e) {
            setPlanError(e?.message || 'The stored plan was not cleared.');
        }
    }, [accepted, atlasId, service]);

    // ── C3: draw a relation ──────────────────────────────────────────────────

    /**
     * THE ONE PATH BY WHICH A RELATION IS EVER PERSISTED (T2).
     *
     * Drawing by hand and confirming a Scout candidate are the SAME call. That is structural, not
     * tidy: with two paths, one would eventually learn to trust the model's hunch and skip the
     * comparison, and a ghost would become a stored edge without `compare_views` ever having
     * looked at a mark. With one, there is no such path to write.
     *
     * It returns the outcome rather than swallowing it, because the two callers need different
     * things from a refusal — the drag leaves it on the attempted line, the Scout keeps it as text
     * that outlives the candidate.
     */
    const groundRelation = useCallback(async (source, target) => {
        try {
            const res = await service.drawRelation(atlasId, {
                source_node: source, target_node: target,
            });
            if (res?.refused) {
                setRelationRefusal(res.refused);
                return { refused: res.refused };
            }
            // Re-read rather than splicing the returned edge in. The edge's words come from the
            // ledger, and a client that assembled them from its own request would be the one place
            // this surface could disagree with what was actually committed.
            await refreshOverlays();
            return { edge: res?.edge || null };
        } catch (e) {
            const refused = {
                reason: 'unavailable', source_node: source, target_node: target,
                detail: e?.message || 'the comparison could not be run',
            };
            setRelationRefusal(refused);
            return { refused };
        }
    }, [atlasId, refreshOverlays, service]);

    const onConnect = useCallback(async (connection) => {
        if (drawing) return;
        setRelationRefusal(null);

        // The two checks a client can make honestly on its own. Everything else — whether the
        // marks exist, whether a relation can be named — belongs to the gate, and guessing at it
        // here would refuse comparisons the system would have allowed.
        const local = connectionRefusal(connection, { isClaimNode: isClaimNodeId });
        if (local) { setRelationRefusal(local); return; }

        setDrawing(true);
        try {
            await groundRelation(connection.source, connection.target);
        } finally {
            setDrawing(false);
        }
    }, [drawing, groundRelation]);

    // ── T2: the Scout ────────────────────────────────────────────────────────

    /** Ask a model which pairs might repay comparison. It proposes; it never asserts. */
    const onScout = useCallback(async () => {
        if (scouting) return;
        setScouting(true);
        setScoutRefusal(null);
        setRelationRefusal(null);
        try {
            const res = await service.scout(atlasId);
            if (res?.refused) {
                setCandidates([]);
                setScoutDropped(res.dropped || []);
                setScoutRefusal(res.refused);
                return;
            }
            setCandidates(res?.candidates || []);
            setScoutDropped(res?.dropped || []);
            setScoutAnswers([]);
        } catch (e) {
            setCandidates([]);
            setScoutRefusal({ reason: 'model_unavailable',
                detail: e?.message || 'the scout could not be reached' });
        } finally {
            setScouting(false);
        }
    }, [atlasId, scouting, service]);

    /**
     * Confirm a candidate — which RUNS the comparison, and may refuse.
     *
     * The candidate is removed either way, because it has been answered. When the answer was a
     * refusal the REASON is kept: a suggestion that simply vanished would teach the writer nothing
     * about why that pair cannot be compared.
     */
    const onConfirmCandidate = useCallback(async (candidate) => {
        if (!candidate || confirming) return;
        const pair = `${candidate.from}~${candidate.to}`;
        setConfirming(pair);
        setRelationRefusal(null);
        try {
            // Only the PAIR is sent. Nothing the model said about it travels to the gate — the
            // rationale is a hunch, and a hunch must not colour what the comparison finds by
            // looking at marks.
            const outcome = await groundRelation(candidate.from, candidate.to);
            if (outcome?.refused) {
                setScoutAnswers((prev) => [
                    ...prev.filter((a) => a.pair !== pair),
                    { pair, line: refusalLine(outcome.refused) },
                ]);
            }
        } finally {
            setCandidates((prev) => withoutCandidate(prev, candidate.from, candidate.to));
            setConfirming('');
        }
    }, [confirming, groundRelation]);

    /** Dismiss a candidate. Nothing was persisted, so nothing is undone — it simply goes. */
    const onDismissCandidate = useCallback((candidate) => {
        setCandidates((prev) => withoutCandidate(prev, candidate.from, candidate.to));
    }, []);

    // ── what the canvas draws ────────────────────────────────────────────────

    // The writer's current structure over the server's plan. Derived, never stored — the claim
    // column is laid out from the ORDER, so a reorder moves the cards.
    const planView = useMemo(() => (plan ? { ...plan, claims } : null), [claims, plan]);
    const showPlan = mode === MODE_PLAN;

    // CLAIM CARDS RIDE IN THE SAME NODE ARRAY AS THE PICTURES, and that is load-bearing rather
    // than convenient. React Flow measures the nodes it is given and reports each measurement back
    // through `onNodesChange`; a node whose measurement the app never applies stays unmeasured for
    // ever, has no handle bounds, and anchors no edge. Claim cards kept outside this array rendered
    // perfectly and every connector was silently dropped — no error, no warning, no lines. They are
    // excluded at the SAVE boundary instead (`positionsOf`), which is where they never belonged.
    const canvasNodes = useMemo(() => {
        const images = nodes.filter((n) => !isClaimNodeId(n.id));
        if (!showPlan || !planView) return images;
        const measured = new Map(nodes.filter((n) => isClaimNodeId(n.id)).map((n) => [n.id, n]));
        return [...images, ...claimFlowNodes(planView, images).map((n) => {
            // Keep what React Flow already measured for a card that survived the edit; one that
            // lost its measurement would vanish and take its connectors with it.
            const before = measured.get(n.id);
            return before ? { ...n, measured: before.measured } : n;
        })];
    }, [nodes, planView, showPlan]);

    const canvasEdges = useMemo(() => {
        const refused = refusedEdge(relationRefusal);
        return [
            ...(showPlan && planView ? bindingEdges(planView) : []),
            ...relationEdges(view),
            // T2's ghosts: dotted, unarrowed, greyed, and deliberately the weakest mark here.
            // They are session state — a hunch about which pair might repay comparison, not a
            // relation — and they carry an id prefix that cannot collide with a stored edge's.
            ...ghostEdges(candidates),
            ...(refused ? [refused] : []),
        ];
    }, [candidates, planView, relationRefusal, showPlan, view]);

    const scout = scoutSummary(candidates, scoutDropped);

    // ── what the header says ─────────────────────────────────────────────────

    const unreadable = view?.unreadable || [];
    const relations = relationSummary(view);
    // Images only. Since C4 the node array can also hold claim cards, and a header that counted
    // them would report more photographs than the corpus has — the one number here a reader takes
    // at face value.
    const counts = useMemo(() => ({
        images: nodes.filter((n) => !isClaimNodeId(n.id)).length,
        percepts: nodes.reduce((n, node) => n
            + (node.data?.grounds?.length || 0)
            + (node.data?.marks?.length || 0)
            + (node.data?.regions?.length || 0), 0),
        // Counted and named separately, never added to the percept total. A note is not a finding.
        notes: nodes.reduce((n, node) => n + (node.data?.notes?.length || 0), 0),
    }), [nodes]);

    if (error && !view) {
        return <div className="atlas-error" role="alert">{error}</div>;
    }

    // C2: the Differential takes the viewport, and the workspace UNMOUNTS rather than hiding behind
    // it — the instrument has its own model loading and pointer capture, and a live canvas
    // underneath would be two surfaces competing for the same gestures. State is on the server;
    // coming back re-reads it.
    if (open) {
        return (
            <AtlasDifferential
                postId={open.postId}
                intention={open.intention}
                title={nodes.find((n) => n.data?.postId === open.postId)?.data?.title || ''}
                onClose={closeDifferential}
            />
        );
    }

    return (
        <div className="atlas-shell" data-mode={mode}>
            <header className="atlas-head">
                <div className="atlas-head-what">
                    <h1 className="atlas-title">{view?.title || 'Atlas'}</h1>
                    <p className="atlas-sub">
                        {counts.images} image{counts.images === 1 ? '' : 's'} ·{' '}
                        {counts.percepts} committed percept{counts.percepts === 1 ? '' : 's'}
                        {counts.notes > 0 && (
                            <> · {counts.notes} author note{counts.notes === 1 ? '' : 's'}</>
                        )}
                        {relations.drawn > 0 && (
                            <>
                                {' · '}
                                <span className="atlas-rel-count">
                                    {relations.drawn} relation{relations.drawn === 1 ? '' : 's'} drawn
                                    {relations.stale > 0 && (
                                        // Never folded into the total. An edge whose relation left
                                        // the ledger is still on the canvas and is not evidence.
                                        <span className="atlas-rel-stale">
                                            {' '}({relations.stale} no longer in the ledger)
                                        </span>
                                    )}
                                </span>
                            </>
                        )}
                        {showPlan && (
                            <>
                                {' · '}
                                <em className="atlas-note">
                                    a line from a claim binds it to the evidence that would carry
                                    it — a proposal the gate allowed, not a relation between images
                                </em>
                            </>
                        )}
                        {mode === MODE_CANVAS && <>
                            {' · '}
                            {/* Said out loud, because it is the rule a canvas most tempts a
                                reader to forget. It is a fact about the CANVAS, so it goes when
                                the canvas does — the Light Table's grid is corpus order, and
                                claiming "position asserts nothing" there would be answering a
                                question nobody asked. */}
                            <em className="atlas-note">position is a thinking aid — it asserts nothing</em>
                        </>}
                    </p>
                </div>

                <div className="atlas-head-right">
                    {/* The mode switcher. Two buttons — this is the whole framework, and keeping
                        it this small is what stops a "mode" from growing into an app. */}
                    <div className="atlas-modes" role="group" aria-label="How to look at this Atlas">
                        {ATLAS_MODES.map((m) => (
                            <button
                                key={m.key} type="button"
                                className={`atlas-mode${mode === m.key ? ' is-on' : ''}`}
                                data-mode={m.key}
                                aria-pressed={mode === m.key}
                                title={m.hint}
                                onClick={() => setMode(m.key)}
                            >
                                {m.label}
                            </button>
                        ))}
                    </div>
                    {/* T2. The word is "Suggest", never "Find": the Scout has not looked at a
                        photograph and cannot find anything in one. */}
                    <button type="button" className="atlas-scout-go" data-scout
                        onClick={onScout} disabled={scouting}
                        title="Ask a model which pairs might repay comparison. It proposes only — each one still has to be grounded by the comparison before it becomes a relation.">
                        {scouting ? 'asking…' : 'Suggest relations'}
                    </button>
                    <div className="atlas-head-status" aria-live="polite">
                        {status && <span className="atlas-status">{status}</span>}
                    </div>
                </div>
            </header>

            {unreadable.length > 0 && (
                <div className="atlas-banner is-unreadable" role="note">
                    {unreadable.length} image{unreadable.length === 1 ? '' : 's'} in this corpus
                    could not be read. {unreadable.length === 1 ? 'It stays' : 'They stay'} on the
                    Atlas rather than disappearing from it.
                </div>
            )}

            {refusals.length > 0 && (
                <ul className="atlas-banner is-refused" role="alert">
                    {refusals.map((line, i) => <li key={i}>{line}</li>)}
                </ul>
            )}

            {error && view && <div className="atlas-banner is-error" role="alert">{error}</div>}

            {/* T2: what the Scout proposed, and what it was not allowed to propose. */}
            {scoutRefusal && (
                <div className="atlas-banner is-refused" role="alert">
                    {scoutRefusalLine(scoutRefusal)}
                </div>
            )}

            {droppedLines(scoutDropped).length > 0 && (
                // Drops are REPORTED, never silent: how often a model overreaches is the
                // observable that says whether to trust its suggestions at all.
                <ul className="atlas-banner is-dropped" role="note">
                    {droppedLines(scoutDropped).map((line) => <li key={line}>{line}</li>)}
                </ul>
            )}

            {scoutAnswers.length > 0 && (
                // A refusal that outlives the ghost that prompted it. The candidate is gone
                // because it was answered; the answer is what the writer needed.
                <ul className="atlas-banner is-refused" role="alert">
                    {scoutAnswers.map((a) => <li key={a.pair}>{a.pair}: {a.line}</li>)}
                </ul>
            )}

            {candidates.length > 0 && (
                <div className="atlas-scout" role="region" aria-label="Suggested comparisons">
                    <p className="atlas-scout-lede">
                        {scout.proposed} pair{scout.proposed === 1 ? '' : 's'} a model thinks might
                        repay comparison.{' '}
                        {/* The sentence that keeps the whole gate honest, on the surface where the
                            ghosts are, not buried in a tooltip. */}
                        <em className="atlas-note">
                            nothing here is a relation yet — confirming runs the comparison, which
                            can refuse
                        </em>
                    </p>
                    <ul className="atlas-scout-list">
                        {candidates.map((c) => {
                            const busy = confirming === `${c.from}~${c.to}`;
                            return (
                                <li key={`${c.from}~${c.to}`} className="atlas-scout-item"
                                    data-candidate={`${c.from}~${c.to}`}>
                                    <span className="atlas-scout-pair">{c.from} ↔ {c.to}</span>
                                    <span className="atlas-scout-why">{c.rationale}</span>
                                    <button type="button" className="atlas-scout-confirm"
                                        data-confirm={`${c.from}~${c.to}`}
                                        disabled={busy || drawing}
                                        onClick={() => onConfirmCandidate(c)}
                                        title="Run the comparison on this pair. It may refuse.">
                                        {busy ? 'comparing…' : 'confirm'}
                                    </button>
                                    <button type="button" className="atlas-scout-dismiss"
                                        data-dismiss={`${c.from}~${c.to}`}
                                        onClick={() => onDismissCandidate(c)}
                                        title="Take this suggestion off the canvas. Nothing was stored.">
                                        dismiss
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            )}

            {mode === MODE_LIGHT_TABLE ? (
                <AtlasLightTable
                    nodes={nodes}
                    onNotesChange={changeNotes}
                    onMachineRead={machineRead}
                    notesStatus={notesStatus}
                />
            ) : (
                // Canvas and Plan are the SAME renderer. Plan mode hands it claim cards and
                // binding connectors as well as images, and puts the panel beside it — which is
                // what "a mode only swaps the renderer" is supposed to mean.
                <div className={showPlan ? 'atlas-with-plan' : undefined}>
                    <AtlasCanvas
                        nodes={canvasNodes}
                        edges={canvasEdges}
                        onNodesChange={onNodesChange}
                        onConnect={onConnect}
                        connectable
                    />
                    {showPlan && (
                        <AtlasPlanPanel
                            thesis={thesis} onThesis={setThesis} onPlan={onPlan}
                            planning={planning} plan={plan} claims={claims} onClaims={setClaims}
                            onAccept={onAccept} onDiscard={onDiscard}
                            accepting={accepting} accepted={accepted} error={planError} />
                    )}
                </div>
            )}
        </div>
    );
}
