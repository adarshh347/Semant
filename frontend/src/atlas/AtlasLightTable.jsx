import React, { useCallback } from 'react';

import AtlasPerceptStage from './AtlasPerceptStage.jsx';
import { perceptSummary, withNoteAdded, withNoteEdit } from './atlasDocument.js';

/**
 * ATLAS T1 — the Light Table: the corpus as a scannable grid.
 *
 * A MODE, NOT AN APP. This renders the SAME nodes the Canvas renders, from the same `/view`, with
 * the same overlay renderer (`AtlasPerceptStage`) and the same way into the Differential. Nothing
 * here fetches, and nothing here holds document state — the workspace above owns all of it, which
 * is what makes switching modes cost nothing and lose nothing. What a mode changes is the LAYOUT
 * and which affordances make sense in it.
 *
 * WHY A GRID AND NOT A SMALLER CANVAS. The Canvas is for arranging: position is a thinking aid and
 * the corpus is spread out. The Light Table is for INTAKE — going down a corpus image by image,
 * seeing what has been read so far, saying something about it, and asking for a first machine
 * pass. Reading order, uniform cells, no drag: the layout is the corpus's own sequence, which is
 * evidence (M1), and nothing here may reorder it.
 *
 * THE TWO LANES, VISIBLE IN THE LAYOUT. Each cell has an author-notes slot and a machine-read
 * button, and they are deliberately not neighbours in the data model:
 *
 *   - An AUTHOR NOTE is the writer's own line. It is not a percept, not evidence, not citable, and
 *     never enters the ledger. It carries no epistemic chip — the five-way vocabulary grades how
 *     well a claim is GROUNDED, and a note claims nothing, so giving it `uncertain` would sneak it
 *     into the epistemic system at the bottom rung instead of leaving it outside. It gets its own
 *     visual treatment and the words "not evidence", because a reader scanning a grid will
 *     otherwise read anything in a box under a picture as a finding.
 *
 *   - A MACHINE READ runs the existing Director on the image and can produce exactly one thing: a
 *     QUARANTINED percept proposal, reviewed and accepted in the Differential like every other
 *     suggestion. It may not write a note.
 *
 * There is no code path from either lane to the other, and there must never be. A model that could
 * write into the author's own voice would make the notes slot untrustworthy — the writer could no
 * longer tell which lines were theirs — and a note that could be promoted to a percept would put
 * ungrounded prose into the evidence base wearing a chip it never earned.
 */

/** Enough of a unique id without a dependency. Collisions here are cosmetic — the server mints
 *  the id it stores — but a stable key stops React from re-mounting a field mid-typing. */
let noteSeq = 0;
const nextNoteId = () => `local_${Date.now().toString(36)}_${(noteSeq += 1)}`;

function LightTableCell({ node, onNotesChange, onOpen, onMachineRead, machineReadBusy }) {
    const data = node.data || {};
    const summary = perceptSummary(data);
    const notes = data.notes || [];

    const edit = useCallback((noteId, text) => {
        onNotesChange(node.id, withNoteEdit(notes, noteId, text));
    }, [node.id, notes, onNotesChange]);

    const add = useCallback(() => {
        onNotesChange(node.id, withNoteAdded(notes, nextNoteId()));
    }, [node.id, notes, onNotesChange]);

    return (
        <li className="lt-cell" data-post-id={data.postId} data-node-id={node.id}
            data-readable={data.readable ? 'true' : 'false'}>
            <div className="lt-cell-stage">
                {data.readable ? (
                    <AtlasPerceptStage data={data} className="lt-stage" />
                ) : (
                    <div className="lt-missing" role="note">
                        <strong>image unavailable</strong>
                        <span className="lt-missing-why">{data.unreadableReason}</span>
                    </div>
                )}
            </div>

            <div className="lt-cell-head">
                <span className="lt-cell-title">{data.title || data.postId}</span>
                <span className="lt-cell-count" data-drawn={summary.drawn}>
                    {summary.drawn === 0 ? 'no committed percepts'
                        : `${summary.drawn} percept${summary.drawn === 1 ? '' : 's'}`}
                </span>
            </div>

            {/* Never a tooltip — a suggestion the surface declined to draw is exactly the kind of
                thing a hover hides, and the shorter list would read as complete. */}
            {summary.withheldNote && (
                <p className="lt-withheld" role="note">{summary.withheldNote}</p>
            )}

            {/* ── lane one: the author's own voice ─────────────────────────── */}
            <div className="lt-notes" data-node-id={node.id}>
                <p className="lt-notes-label">
                    Author notes
                    {/* Said in words, on the surface. The visual treatment carries it too, but a
                        reader who only reads the text must still get the distinction. */}
                    <span className="lt-notes-caveat"> — yours, not evidence; never cited</span>
                </p>

                <ul className="lt-note-list">
                    {notes.map((note) => (
                        <li key={note.note_id} className="lt-note">
                            <textarea
                                className="lt-note-text"
                                data-note-id={note.note_id}
                                rows={2}
                                value={note.text}
                                maxLength={280}
                                placeholder="a line of your own…"
                                aria-label={`Author note on ${data.title || data.postId}`}
                                onChange={(e) => edit(note.note_id, e.target.value)}
                            />
                        </li>
                    ))}
                </ul>

                <button type="button" className="lt-note-add" data-add-note={node.id}
                    onClick={add}>
                    + note
                </button>
            </div>

            {/* ── lane two: what the machine may propose ───────────────────── */}
            <div className="lt-acts">
                {data.onOpen && (
                    <button type="button" className="lt-open" data-open-post={data.postId}
                        onClick={() => data.onOpen(data.postId)}
                        title={`Open ${data.title || data.postId} in the Differential`}>
                        open →
                    </button>
                )}
                {data.onMachineRead && (
                    <button type="button" className="lt-read" data-read-post={data.postId}
                        disabled={machineReadBusy}
                        onClick={() => onMachineRead(data.postId)}
                        title="Runs the Director on this image and opens the Differential. Whatever it finds arrives as a proposal you accept or dismiss — it is never committed for you.">
                        {machineReadBusy ? 'reading…' : 'machine read'}
                    </button>
                )}
            </div>
        </li>
    );
}

export default function AtlasLightTable({
    nodes = [], onNotesChange, onMachineRead, machineReadBusy = false, notesStatus = '',
}) {
    if (nodes.length === 0) {
        return <p className="lt-empty">This Atlas has no images on it.</p>;
    }

    return (
        <div className="lt">
            <p className="lt-legend">
                The corpus in its own order. Notes are yours; a machine read only ever proposes —
                you accept it in the Differential.
                {notesStatus && <span className="lt-status" aria-live="polite"> · {notesStatus}</span>}
            </p>
            <ul className="lt-grid">
                {nodes.map((node) => (
                    <LightTableCell
                        key={node.id}
                        node={node}
                        onNotesChange={onNotesChange}
                        onMachineRead={onMachineRead}
                        machineReadBusy={machineReadBusy}
                    />
                ))}
            </ul>
        </div>
    );
}
