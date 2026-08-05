import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import AtlasCanvas from './AtlasCanvas.jsx';
import AtlasLightTable from './AtlasLightTable.jsx';
import AtlasDifferential from './AtlasDifferential.jsx';
import { atlasService } from './atlasService.js';
import {
    ATLAS_MODES, MACHINE_READ_INTENTION, MODE_CANVAS, MODE_LIGHT_TABLE,
    arrangementFrom, flowNodesFromView, isMode, notePatchesFrom, notesOf, positionsOf,
    refusalLines,
} from './atlasDocument.js';

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

    // ── what the header says ─────────────────────────────────────────────────

    const unreadable = view?.unreadable || [];
    const counts = useMemo(() => ({
        images: nodes.length,
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

            {mode === MODE_LIGHT_TABLE ? (
                <AtlasLightTable
                    nodes={nodes}
                    onNotesChange={changeNotes}
                    onMachineRead={machineRead}
                    notesStatus={notesStatus}
                />
            ) : (
                <AtlasCanvas nodes={nodes} onNodesChange={onNodesChange} />
            )}
        </div>
    );
}
