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
    const flowEdges = useMemo(() => (planView ? bindingEdges(planView) : []), [planView]);

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
                    {status && <span className="atlas-status">{status}</span>}
                </div>
            </header>

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
                    // Nobody draws a binding by hand. C4's edges are minted from a plan the gate
                    // judged, and C3's will be minted from a real `compare_views` percept —
                    // neither is a line anyone gets to assert with a drag.
                    nodesConnectable={false}
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
