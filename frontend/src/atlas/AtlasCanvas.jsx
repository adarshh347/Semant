import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    ReactFlow, Background, Controls, MiniMap, applyNodeChanges,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import AtlasImageNode from './AtlasImageNode.jsx';
import AtlasClaimNode from './AtlasClaimNode.jsx';
import AtlasPlanPanel from './AtlasPlanPanel.jsx';
import { atlasService } from './atlasService.js';
import {
    ATLAS_NODE_TYPE, arrangementFrom, flowNodesFromView, positionsOf, refusalLines,
} from './atlasDocument.js';
import {
    CLAIM_NODE_TYPE, acceptPayload, bindingEdges, claimFlowNodes, isClaimNodeId,
} from './atlasPlan.js';
import {
    refusalLine, refusedEdge, relationEdges, connectionRefusal, relationSummary,
} from './atlasRelation.js';
import {
    droppedLines, ghostEdges, scoutRefusalLine, scoutSummary, withoutCandidate,
} from './atlasScout.js';

/**
 * ATLAS C1 — the canvas: a corpus, coexisting, with its committed percepts on it.
 *
 * WHAT THE SURFACE IS FOR. Everything above Layer 3 has looked at one picture at a time. The
 * reading that matters across a corpus — a dispersed civic ground against a centralized rotunda —
 * is not IN any one photograph, and you cannot see it in a surface that shows one. This is the
 * place where the images sit together and a writer can move them around while thinking.
 *
 * SPATIAL POSITION ASSERTS NOTHING. Dragging two nodes together is a writer's thinking aid, not a
 * relation claimed, and nothing in this component reads the distance between nodes. The moment
 * proximity meant something, every accidental arrangement would become an assertion nobody made.
 * A relation is a drawn edge, an edge is a real `compare_views` percept, and that is C3.
 *
 * THE DOCUMENT STORES ARRANGEMENT ONLY. `data` on each node — the image, the overlays — comes from
 * `/view`, hydrated from the ledger on every load, and is never sent back. What this component
 * saves is `{node_id, x, y}`, debounced, for the nodes that actually moved.
 *
 * SAVING IS VISIBLE, INCLUDING WHEN IT REFUSES. A save that dropped a stale node quietly would
 * leave a curator believing the canvas holds something it does not, so refusals render as text on
 * the surface rather than as a console warning.
 */

const SAVE_DEBOUNCE_MS = 600;

const nodeTypes = { [ATLAS_NODE_TYPE]: AtlasImageNode, [CLAIM_NODE_TYPE]: AtlasClaimNode };

export default function AtlasCanvas({ atlasId, service = atlasService }) {
    const [view, setView] = useState(null);
    const [nodes, setNodes] = useState([]);
    const [error, setError] = useState('');
    const [status, setStatus] = useState('');
    const [refusals, setRefusals] = useState([]);

    // ── C4: plan mode ──
    // `plan` is what the server last said. `claims` is what the writer has done to it since, and
    // the two are kept apart on purpose: `isEdited` compares them, and a single merged copy would
    // leave nothing able to say the verdicts on screen predate the edit.
    const [thesis, setThesis] = useState('');
    const [plan, setPlan] = useState(null);
    const [claims, setClaims] = useState([]);
    const [planning, setPlanning] = useState(false);
    const [accepting, setAccepting] = useState(false);
    const [accepted, setAccepted] = useState(false);
    const [planError, setPlanError] = useState('');

    // ── C3: relation edges ──
    // The last refusal, held only so it can be DRAWN on the line it refers to. It is never sent,
    // never stored, and is cleared by the next gesture — a refusal about one pair of photographs
    // must not linger over a canvas the writer has moved on from.
    const [relationRefusal, setRelationRefusal] = useState(null);
    const [drawing, setDrawing] = useState(false);

    // ── T2: the Scout ──
    // Candidates live HERE and nowhere else — session state, never sent back, gone on reload.
    // That is not an implementation shortcut: a candidate that survived a reload would be a
    // model's hunch persisting alongside committed evidence, and the difference between the two
    // is the only thing this canvas is really about.
    const [candidates, setCandidates] = useState([]);
    const [scoutDropped, setScoutDropped] = useState([]);
    const [scoutRefusal, setScoutRefusal] = useState(null);
    const [scouting, setScouting] = useState(false);
    const [confirming, setConfirming] = useState('');
    // What the gate SAID about candidates already confirmed.
    //
    // C3 could leave a refusal on the attempted line alone, because the writer had just dragged
    // that exact line and was looking at it. A confirmed ghost DISAPPEARS — so if the reason lived
    // only on an edge label, the honest "no" the Scout is supposed to deliver would vanish with
    // it, and confirming an ungroundable pair would look identical to nothing happening.
    const [scoutAnswers, setScoutAnswers] = useState([]);

    // The arrangement the SERVER is known to hold. A save diffs against this, not against the last
    // render, so a drag that ends where it started sends nothing.
    const saved = useRef({});
    const timer = useRef(null);
    // React Flow's own instance, for the one thing a plan needs the VIEW to do (see below).
    const flow = useRef(null);

    useEffect(() => {
        let live = true;
        setError('');
        (async () => {
            try {
                const data = await service.view(atlasId);
                if (!live) return;
                setView(data);
                const flow = flowNodesFromView(data);
                setNodes(flow);
                saved.current = positionsOf(flow);
                // An Atlas that already holds an accepted plan opens wearing it. The stored plan
                // is the record — it is shown as it was stored, not re-planned, because a fresh
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
        return () => { live = false; if (timer.current) clearTimeout(timer.current); };
    }, [atlasId, service]);

    const flush = useCallback(async (current) => {
        const patches = arrangementFrom(current, saved.current);
        if (!patches.length) return;
        setStatus('saving…');
        try {
            const res = await service.saveArrangement(atlasId, patches);
            // Trust what came BACK, not what was sent — the server is what a reload will read,
            // and a refused node must not be recorded here as though it had moved.
            const confirmed = {};
            (res?.atlas?.nodes || []).forEach((n) => {
                confirmed[String(n.node_id)] = { x: Number(n.x), y: Number(n.y) };
            });
            saved.current = confirmed;
            setRefusals(refusalLines(res?.refused));
            setStatus('arrangement saved');
        } catch (e) {
            // Never a silent failure: an arrangement the curator believes is saved and is not
            // is the one outcome worse than an error message.
            setStatus('');
            setError(e?.message || 'The arrangement did not save.');
        }
    }, [atlasId, service]);

    const onNodesChange = useCallback((changes) => {
        setNodes((prev) => {
            const next = applyNodeChanges(changes, prev);
            if (timer.current) clearTimeout(timer.current);
            timer.current = setTimeout(() => flush(next), SAVE_DEBOUNCE_MS);
            return next;
        });
    }, [flush]);

    // ── C3: draw a relation ──

    /**
     * Run the gate on one pair. THE ONLY WAY AN EDGE IS EVER MADE on this canvas.
     *
     * Both gestures land here: dragging a line by hand (C3) and confirming a Scout candidate (T2).
     * They are the same call because they must be — if confirming a ghost had its own path, that
     * path would be a way to draw a relation between two photographs without `compare_views`
     * having looked at either, and the Scout's hunch would become evidence by being clicked.
     * Returns the outcome so a caller can clean up its own affordance.
     */
    const groundRelation = useCallback(async (source, target) => {
        try {
            const res = await service.drawRelation(atlasId, {
                source_node: source, target_node: target,
            });
            if (res?.refused) {
                // Drawn on the attempted line, persisted nowhere.
                setRelationRefusal(res.refused);
                return { refused: res.refused };
            }
            // Re-read the view rather than splicing the returned edge in. The edge's words come
            // from the ledger, and a client that assembled them from its own request would be the
            // one place this surface could disagree with what was actually committed.
            setView(await service.view(atlasId));
            return { edge: res?.edge || null };
        } catch (e) {
            const refused = {
                reason: 'unavailable', source_node: source, target_node: target,
                detail: e?.message || 'the comparison could not be run',
            };
            setRelationRefusal(refused);
            return { refused };
        }
    }, [atlasId, service]);

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

    // ── T2: ask the Scout, and confirm what it proposes ──

    const onScout = useCallback(async () => {
        if (scouting) return;
        setScouting(true);
        setScoutRefusal(null);
        setRelationRefusal(null);
        try {
            const res = await service.scout(atlasId);
            if (res?.refused) {
                // The previous batch goes with it. Leaving stale ghosts under a fresh refusal
                // would let a writer read old hunches as this run's answer.
                setCandidates([]);
                setScoutDropped(res.dropped || []);
                setScoutRefusal(res.refused);
                return;
            }
            setCandidates(res?.candidates || []);
            setScoutDropped(res?.dropped || []);
            // A fresh batch is a fresh question; last round's verdicts would read as this one's.
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
     * Confirm a candidate: run the real gate on it.
     *
     * The ghost is removed EITHER WAY. On success the pair is now a real edge and a ghost beside it
     * would be a duplicate claim in a weaker style; on refusal the ghost has been answered, and the
     * refusal renders in its place on the same line (C3's `refusedEdge`). What must never happen is
     * the ghost quietly persisting as though it were still an open question after the gate has
     * spoken.
     */
    const onConfirmCandidate = useCallback(async (candidate) => {
        if (!candidate || confirming) return;
        const pair = `${candidate.from}~${candidate.to}`;
        setConfirming(pair);
        setRelationRefusal(null);
        try {
            const outcome = await groundRelation(candidate.from, candidate.to);
            if (outcome?.refused) {
                // The honest "no", kept where the writer is already reading. It also stays after
                // the ghost has gone, which the edge label cannot do.
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

    // ── C4: ask, edit, accept ──

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
            // the only ones that describe what was actually accepted — replacing the local claims
            // with the response is what makes a claim that lost its evidence go struck on screen.
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

    // What the canvas draws: the writer's current structure over the server's plan. Derived, never
    // stored — the claim column is laid out from the ORDER, so a reorder moves the cards.
    const planView = useMemo(() => (plan ? { ...plan, claims } : null), [claims, plan]);

    // CLAIM CARDS GO INTO THE SAME NODE ARRAY AS THE PICTURES, and that is the whole reason this
    // is a merge rather than a concatenation at render time. React Flow measures the nodes it is
    // given and reports each measurement back through `onNodesChange`; a node whose measurement
    // the app never applies stays unmeasured forever, and an unmeasured node has no handle bounds,
    // and a handle with no bounds anchors no edge. Claim cards kept outside this array rendered
    // perfectly and every single connector was silently dropped — no error, no warning, just no
    // lines. So they live here, are measured here, and are excluded at the SAVE boundary instead
    // (`positionsOf`), which is where they never belonged in the first place.
    // BOTH KINDS OF LINE, IN ONE ARRAY, AND THEY MUST NEVER READ AS ONE KIND.
    //   · C4 bindings  — claim→image, dashed, unarrowed, labelled with an argumentative function.
    //                    They assert a percept WOULD resolve.
    //   · C3 relations — image↔image, solid, arrowed, labelled with the relation's own role and
    //                    epistemic kind. They assert a comparison WAS produced and committed.
    //   · T2 ghosts    — image↔image, DOTTED, unarrowed, greyed, labelled "unconfirmed · <hunch>".
    //                    They assert NOTHING. A model thinks this pair might repay comparison.
    //   · a refusal    — the line a writer attempted that could not be grounded. Drawn, never
    //                    persisted, and impossible to mistake for any of the above.
    //
    // Ghosts are laid down FIRST so a real relation or a refusal on the same pair draws over them
    // rather than under: once the gate has spoken about a pair, the hunch is no longer the thing
    // to look at.
    const flowEdges = useMemo(() => {
        const refused = refusedEdge(relationRefusal);
        return [
            ...ghostEdges(candidates),
            ...(planView ? bindingEdges(planView) : []),
            ...relationEdges(view),
            ...(refused ? [refused] : []),
        ];
    }, [candidates, planView, relationRefusal, view]);

    // A claim card's content changes what it DRAWS (its status, which percepts bound); the set and
    // order change where the cards SIT. Both have to reach the node array, so the signature covers
    // both — while staying stable across a render that changed neither.
    const hasPlan = Boolean(planView);
    const claimSignature = JSON.stringify(
        claims.map((c) => [c.claim_id, c.text, c.status, c.dirty === true,
            (c.percepts || []).map((p) => `${p.step_id}:${p.bound}`)]));

    useEffect(() => {
        setNodes((prev) => {
            const images = prev.filter((n) => !isClaimNodeId(n.id));
            if (!hasPlan) return images.length === prev.length ? prev : images;
            const was = new Map(prev.filter((n) => isClaimNodeId(n.id)).map((n) => [n.id, n]));
            return [...images, ...claimFlowNodes(planView, images).map((n) => {
                // Carry the measurement forward for a card that survived the edit. Rebuilding it
                // unmeasured would hide it (React Flow hides what it has not measured) and drop
                // its connectors until the next measurement pass.
                const before = was.get(n.id);
                return before ? { ...n, measured: before.measured } : n;
            })];
        });
        // `planView` is deliberately absent: it is a fresh object every render, and `claimSignature`
        // already covers everything about it that this effect reads.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [claimSignature, hasPlan]);

    // WHEN AN ARGUMENT ARRIVES, SHOW IT. The claim column is laid out to the left of the corpus,
    // which on a canvas already fitted to the images is off-screen — so the first plan a writer
    // ever asks for appears to do nothing to the canvas. Refit when the SET of claims changes
    // (arrived, reordered, one removed), not on every keystroke of an edit, or the view would
    // lurch while somebody is rewording a sentence.
    const claimIds = claims.map((c) => c.claim_id).join(',');
    useEffect(() => {
        if (!claimIds || !flow.current) return undefined;
        // One frame late, on purpose: the cards have just been added to the node array and React
        // Flow has not measured them yet, so fitting now would frame a bounding box that does not
        // include them.
        const t = setTimeout(() => flow.current?.fitView({ padding: 0.12, duration: 350 }), 120);
        return () => clearTimeout(t);
    }, [claimIds]);

    const relations = relationSummary(view);
    const scout = scoutSummary(candidates, scoutDropped);
    const unreadable = view?.unreadable || [];
    // Images only. Since C4 the node array also holds claim cards, and a header that counted them
    // would report more photographs than the corpus has — which is exactly the drift this line is
    // there to prevent, so it filters rather than trusting the array's length.
    const counts = useMemo(() => {
        const images = nodes.filter((n) => !isClaimNodeId(n.id));
        return {
            images: images.length,
            percepts: images.reduce((n, node) => n
                + (node.data?.grounds?.length || 0)
                + (node.data?.marks?.length || 0)
                + (node.data?.regions?.length || 0), 0),
        };
    }, [nodes]);

    if (error && !view) {
        return <div className="atlas-error" role="alert">{error}</div>;
    }

    return (
        <div className="atlas-shell">
            <header className="atlas-head">
                <div className="atlas-head-what">
                    <h1 className="atlas-title">{view?.title || 'Atlas'}</h1>
                    <p className="atlas-sub">
                        {counts.images} image{counts.images === 1 ? '' : 's'} ·{' '}
                        {counts.percepts} committed percept{counts.percepts === 1 ? '' : 's'}
                        {' · '}
                        {/* Said out loud, on the surface, because it is the rule a canvas most
                            tempts a reader to forget. */}
                        <em className="atlas-note">position is a thinking aid — it asserts nothing</em>
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
                    </p>
                    {planView && (
                        // The second thing a plan-mode canvas most tempts a reader to forget: a
                        // line from a claim says the gate would grant that percept, not that two
                        // pictures are related. Relations between images are C3's, and they will
                        // be real comparative percepts rather than proposals.
                        <p className="atlas-sub">
                            <em className="atlas-note">
                                a line here binds a claim to the evidence that would carry it — it
                                is a proposal the gate allowed, not a relation between images
                            </em>
                        </p>
                    )}
                </div>
                <div className="atlas-head-status" aria-live="polite">
                    {/* T2. The word is "Suggest", never "Find": the Scout has not looked at a
                        photograph and cannot find anything in one. */}
                    <button type="button" className="atlas-scout-go" data-scout
                        onClick={onScout} disabled={scouting}
                        title="Ask a model which pairs might repay comparison. It proposes only — each one still has to be grounded by the comparison before it becomes a relation.">
                        {scouting ? 'asking…' : 'Suggest relations'}
                    </button>
                    {status && <span className="atlas-status">{status}</span>}
                </div>
            </header>

            {/* T2: what the Scout proposed, and what it was not allowed to propose. */}
            {scoutRefusal && (
                <div className="atlas-banner is-refused" role="alert">
                    {scoutRefusalLine(scoutRefusal)}
                </div>
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

            {scoutAnswers.length > 0 && (
                // A refusal is a RESULT, not a non-event. It outlives the ghost it answered,
                // because the writer needs to know their corpus cannot carry that comparison.
                <ul className="atlas-banner is-refused" role="alert">
                    {scoutAnswers.map((a) => (
                        <li key={a.pair}>{a.pair.replace('~', ' ↔ ')}: {a.line}</li>
                    ))}
                </ul>
            )}

            {scoutDropped.length > 0 && (
                // Shown, never swallowed. How often the model invents an image or tries to name a
                // relation is what tells a writer how far to trust the next batch.
                <ul className="atlas-banner is-dropped" role="note">
                    {droppedLines(scoutDropped).map((line, i) => <li key={i}>{line}</li>)}
                </ul>
            )}

            {unreadable.length > 0 && (
                <div className="atlas-banner is-unreadable" role="note">
                    {unreadable.length} image{unreadable.length === 1 ? '' : 's'} in this corpus
                    could not be read. {unreadable.length === 1 ? 'It stays' : 'They stay'} on the
                    canvas rather than disappearing from it.
                </div>
            )}

            {refusals.length > 0 && (
                <ul className="atlas-banner is-refused" role="alert">
                    {refusals.map((line, i) => <li key={i}>{line}</li>)}
                </ul>
            )}

            {error && view && <div className="atlas-banner is-error" role="alert">{error}</div>}

            <div className="atlas-with-plan">
                <div className="atlas-canvas">
                <ReactFlow
                    nodes={nodes}
                    edges={flowEdges}
                    nodeTypes={nodeTypes}
                    onNodesChange={onNodesChange}
                    onInit={(instance) => { flow.current = instance; }}
                    onConnect={onConnect}
                    // Nobody draws a binding by hand. C4's edges are minted from a plan the gate
                    // judged, and C3's will be minted from a real `compare_views` percept —
                    // neither is a line anyone gets to assert with a drag.
                    // C3 turns this on. What a drag produces is a REQUEST to `compare_views`,
                    // not a line: `onConnect` never adds an edge itself, so an ungroundable pair
                    // leaves the canvas exactly as it was, wearing the refusal.
                    nodesConnectable
                    connectOnClick={false}
                    elementsSelectable
                    fitView
                    minZoom={0.1}
                    maxZoom={2}
                    proOptions={{ hideAttribution: false }}
                >
                    <Background gap={48} size={1} />
                    <Controls showInteractive={false} />
                    <MiniMap pannable zoomable ariaLabel="Atlas overview" />
                </ReactFlow>
                </div>

                <AtlasPlanPanel
                    thesis={thesis} onThesis={setThesis} onPlan={onPlan} planning={planning}
                    plan={plan} claims={claims} onClaims={setClaims}
                    onAccept={onAccept} onDiscard={onDiscard}
                    accepting={accepting} accepted={accepted} error={planError} />
            </div>
        </div>
    );
}
