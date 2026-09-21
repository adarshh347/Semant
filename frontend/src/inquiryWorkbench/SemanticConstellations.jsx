import React, { useState } from 'react';
import { PRESERVATION_VALUES, selectedAnchor } from './semanticConstellationContract';
import './semanticConstellations.css';

export default function SemanticConstellations({ session, onWrite, onRefresh }) {
    const extension = session.semantic_constellations;
    const [editing, setEditing] = useState(null);
    const [creating, setCreating] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    if (!extension?.known) return null;
    const write = async (action, body, cid) => {
        setBusy(true); setError('');
        try {
            await onWrite(action, { ...body, expected_checkpoint: session.checkpoint }, cid);
            setCreating(false); setEditing(null);
        } catch (e) {
            setError(e.message || 'Could not save. Your input is still here.');
        } finally { setBusy(false); }
    };
    return <section className="iw-panel iw-thought" aria-label="Keep this thought together">
        <h2 className="iw-h2">Keep this thought together</h2>
        <p className="iw-quiet">Preserve the question, then inspect what the claims retain.
            This record does not change the compiler or strengthen evidence.</p>
        {extension.paused && <p role="status">Preparation paused — {extension.preparation === 'prompt'
            ? 'no model has run. Save and confirm your source and question.'
            : extension.sources.some((s) => s.origin === 'model_reading')
                ? 'the image reading is stored. Compilation has not started; you can anchor a reading block now.'
                : 'the reading stage has settled without a reading block. Inspect its outcome below; compilation has not started.'}</p>}
        {!extension.current.length && <div className="iw-empty">
            <span aria-hidden="true">◇</span><h3 className="iw-h3">No thought recorded yet</h3>
            <p>Nothing here says whether the original source held a coherent thought. Select a passage to preserve.</p>
        </div>}
        {!creating && !editing && <button className="iw-expand" type="button"
            onClick={() => setCreating(true)}>Select a passage</button>}
        {(creating || editing) && <ThoughtForm key={editing?.constellation_id || 'new'}
            sources={extension.sources} row={editing} busy={busy}
            onCancel={() => { setCreating(false); setEditing(null); }}
            onSave={(thought) => write('save', { thought,
                expected_constellation_revision: editing?.revision || 0 }, editing?.constellation_id)} />}
        {error && <div role="alert" className="iw-error">{error}
            <button type="button" className="iw-expand" onClick={onRefresh}>Refresh session; keep my input</button>
        </div>}
        {extension.current.map((row) => <ThoughtRecord key={`${row.constellation_id}:${row.revision}`}
            row={row} session={session} busy={busy} onEdit={() => { setEditing(row); setCreating(false); }}
            onReview={(body) => write('review', body, row.constellation_id)} />)}
        {extension.paused && <button className="iw-start" type="button" disabled={busy ||
            !extension.current.some((r) => r.status === 'reviewed' && r.timing === 'before_compilation')}
            onClick={() => write('continue', {})}>
            {extension.preparation === 'prompt' ? 'Continue to image reading' : 'Continue to compilation'}
        </button>}
        <details><summary>Revision history ({extension.history.length})</summary>
            <p className="iw-quiet">Earlier captures and judgments are preserved. An edit after compilation is retrospective.</p>
            {extension.history.map((row) => <article key={`${row.constellation_id}:${row.revision}`}>
                <p><code>{row.constellation_id}</code> · revision {row.revision} · {row.revision_reason}
                    {' · '}{row.timing} · {row.revision_actor}</p>
                <p>{row.organising_question}</p>
                {row.anchors.map((a, i) => <blockquote key={i}>{a.exact_text}</blockquote>)}
                <p>{row.judgment.value}: {row.judgment.note}</p>
            </article>)}
        </details>
    </section>;
}

function ThoughtForm({ sources, row, busy, onSave, onCancel }) {
    const initial = row?.anchors[0];
    const [sourceIndex, setSourceIndex] = useState(Math.max(0, sources.findIndex((s) =>
        s.source_id === initial?.source_id && s.origin === initial?.origin)));
    const source = sources[sourceIndex];
    const [anchors, setAnchors] = useState(row?.anchors.map(({ origin, source_id, span, exact_text }) =>
        ({ origin, source_id, span, exact_text })) || []);
    const [question, setQuestion] = useState(row?.organising_question || '');
    const [tension, setTension] = useState(row?.central_tension || '');
    const [alternatives, setAlternatives] = useState(row?.alternatives.map((a) => a.text).join('\n') || '');
    const [relevance, setRelevance] = useState(row?.perceptual_relevance || '');
    const [questions, setQuestions] = useState(row?.perceptual_questions.join('\n') || '');
    const [actor, setActor] = useState('');
    const lines = (text) => text.split('\n').map((s) => s.trim()).filter(Boolean);
    const submit = (confirmed) => onSave({
        organising_question: question, central_tension: tension, anchors,
        alternatives: lines(alternatives).map((text) => {
            const previous = row?.alternatives.find((a) => a.text === text);
            return previous || { text, authorship: { kind: 'human', actor } };
        }), perceptual_relevance: relevance, perceptual_questions: lines(questions),
        authorship: { kind: 'human', actor }, confirmed_by: confirmed ? actor : null,
    });
    const ready = actor.trim() && question.trim() && anchors.length &&
        anchors.reduce((n, a) => n + Array.from(a.exact_text).length, 0) <= 4000;
    return <div className="iw-thought-form">
        <label>Stored source<select aria-label="Stored source" value={sourceIndex}
            onChange={(e) => setSourceIndex(Number(e.target.value))}>
            {sources.map((s, i) => <option key={`${s.origin}:${s.source_id}`} value={i}>
                {s.author} · {s.source_id}</option>)}
        </select></label>
        {source && <><p className="iw-quiet">Select an intact passage below (up to 4,000 characters).
            Selection replaces the source anchors for this revision.</p>
            <textarea aria-label="Select source passage" className="iw-prompt" readOnly rows={5}
                value={source.text} onSelect={(e) => {
                    if (e.target.selectionEnd > e.target.selectionStart)
                        setAnchors([selectedAnchor(source, e.target.selectionStart, e.target.selectionEnd)]);
                }} />
            <button type="button" className="iw-expand" disabled={Array.from(source.text).length > 4000}
                onClick={() => setAnchors([selectedAnchor(source, 0, source.text.length)])}>Use whole passage</button>
        </>}
        {anchors.map((a, i) => <blockquote key={i}>{a.exact_text}</blockquote>)}
        <label>Organising question<textarea aria-label="Organising question" value={question}
            onChange={(e) => setQuestion(e.target.value)} maxLength={2000} /></label>
        <label>Central tension (optional)<textarea value={tension}
            onChange={(e) => setTension(e.target.value)} maxLength={2000} /></label>
        <label>Alternative interpretations (one per line)<textarea value={alternatives}
            onChange={(e) => setAlternatives(e.target.value)} /></label>
        <p className="iw-quiet">Alternatives need not be exhaustive or mutually exclusive.</p>
        <label>Perceptual relevance (optional)<textarea value={relevance}
            onChange={(e) => setRelevance(e.target.value)} maxLength={2000} /></label>
        <label>Possible perceptual questions (one per line; nothing executes)<textarea value={questions}
            onChange={(e) => setQuestions(e.target.value)} /></label>
        <label>Your name or initials<input aria-label="Thought author" value={actor}
            onChange={(e) => setActor(e.target.value)} maxLength={200} /></label>
        <div className="iw-thought-actions">
            <button type="button" className="iw-expand" disabled={!ready || busy} onClick={() => submit(false)}>Save proposal</button>
            <button type="button" className="iw-start" disabled={!ready || busy} onClick={() => submit(true)}>Save and confirm thought</button>
            <button type="button" className="iw-expand" disabled={busy} onClick={onCancel}>Cancel edit</button>
        </div>
    </div>;
}

function Membership({ label, id, choices, onChange, disabled }) {
    return <label>{label}<select aria-label={`Membership ${id}`} disabled={disabled}
        value={choices[id] || 'unassessed'} onChange={(e) => onChange(id, e.target.value)}>
        <option value="unassessed">Not assessed</option><option value="confirmed">Confirm membership</option>
        <option value="rejected">Reject membership</option>
    </select></label>;
}

function ThoughtRecord({ row, session, busy, onEdit, onReview }) {
    const initial = {};
    for (const id of [...row.confirmed_claim_refs, ...row.confirmed_edge_refs]) initial[id] = 'confirmed';
    for (const id of [...row.rejected_claim_refs, ...row.rejected_edge_refs]) initial[id] = 'rejected';
    const [choices, setChoices] = useState(initial);
    const [judgment, setJudgment] = useState(row.judgment.value);
    const [note, setNote] = useState(row.judgment.note);
    const [recovered, setRecovered] = useState(row.judgment.recovered_thought);
    const [next, setNext] = useState(row.judgment.next_investigation);
    const [actor, setActor] = useState('');
    const [reference, setReference] = useState(null);
    const inspection = row.inspection;
    const refs = (ids, value) => ids.filter((id) => choices[id] === value);
    const claimIds = inspection?.candidates.map((c) => c.claim_ref) || [];
    const edgeIds = inspection?.candidate_edge_refs || [];
    const changed = (id, value) => setChoices((old) => ({ ...old, [id]: value }));
    const selected = refs(claimIds, 'confirmed');
    return <article className="iw-thought-record" id={row.constellation_id}>
        <p className="iw-quiet"><code>{row.constellation_id}</code> · revision {row.revision}
            {' · '}{row.timing === 'before_compilation' ? 'Captured before compilation' : 'Retrospective capture'}
            {' · '}{row.authorship.kind}: {row.authorship.actor} · {row.status}</p>
        <h3 className="iw-h3">Read these together</h3>
        <div className="iw-thought-columns">
            <div><h4>Intended thought</h4><p>{row.organising_question}</p>
                {row.central_tension && <p>{row.central_tension}</p>}
                {row.anchors.map((a, i) => <figure key={i}><blockquote>{a.exact_text}</blockquote>
                    <figcaption>{a.author} · {a.source_id} · characters {a.span.join('–')}</figcaption></figure>)}
                <h4>Alternative interpretations</h4>
                {row.alternatives.length ? <ul>{row.alternatives.map((a) => <li key={a.alternative_id}>
                    {a.text} <span className="iw-quiet">({a.authorship.kind}: {a.authorship.actor})</span>
                </li>)}</ul> : <p className="iw-quiet">No alternatives recorded.</p>}
                <p className="iw-quiet">Neither exhaustive nor necessarily mutually exclusive.</p>
                {row.perceptual_relevance && <p>{row.perceptual_relevance}</p>}
                {row.perceptual_questions.map((q, i) => <p key={i}>Possible question (non-executable): {q}</p>)}
                <button type="button" className="iw-expand" disabled={busy} onClick={onEdit}>Revise thought</button>
            </div>
            <div><h4>Resulting claims and relations</h4>
                {!inspection && <p role="status">No graph inspection yet. The intact source is saved.</p>}
                {row.graph_stale && <p role="alert">This inspection is stale. References remain pinned to
                    {' '}{inspection.graph.graph_hash}; no memberships can be changed against the new graph.</p>}
                {inspection && <>
                    <p className="iw-quiet">{inspection.candidate_count} structural candidates · graph
                        {' '}<code>{inspection.graph.graph_id}</code> · {inspection.graph.graph_hash}</p>
                    <p>Shared ancestry does not demonstrate semantic coherence.</p>
                    {inspection.narrowing_required && <p role="status">Narrow this selection to at most
                        {' '}{inspection.pilot_limit} claims, or revise the source passage. All
                        {' '}{inspection.candidate_count} candidates are shown.</p>}
                    {!claimIds.length && <p role="status">Zero matching claims. Inspect the missing links below.</p>}
                    {inspection.candidates.map((c) => {
                        const claim = row.graph_stale ? null : session.graph.claims.find((x) => x.claim_id === c.claim_ref);
                        return <div className="iw-thought-candidate" key={c.claim_ref}>
                            <p>{claim?.text || c.claim_ref}</p>
                            <p className="iw-quiet">{c.reason === 'source_atom_lineage'
                                ? 'Source → atom → claim ancestry' : 'Immediate graph neighbour (separate suggestion)'}</p>
                            <Membership label="Claim membership" id={c.claim_ref} choices={choices}
                                onChange={changed} disabled={busy || row.graph_stale} />
                            <details><summary>Source / atom / inference references</summary>
                                {[c.claim_ref, ...c.source_unit_refs, ...c.atom_refs, ...c.inference_refs].map((ref) =>
                                    <button key={ref} type="button" className="iw-expand iw-thought-ref"
                                        disabled={row.graph_stale} onClick={() => setReference(ref)}>{ref}</button>)}
                            </details>
                        </div>;
                    })}
                    <h4>Internal relations (direction preserved)</h4>
                    {!edgeIds.length && <p className="iw-quiet">No internal relations recorded.</p>}
                    {edgeIds.map((id) => {
                        const edge = row.graph_stale ? null : session.graph.claim_edges.find((e) => e.edge_id === id);
                        return <div key={id}><p>{edge ? `${edge.from_claim} → ${edge.relation} → ${edge.to_claim}` : id}</p>
                            <Membership label="Relation membership" id={id} choices={choices}
                                onChange={changed} disabled={busy || row.graph_stale} /></div>;
                    })}
                    <details open={inspection.missing_links.length > 0}><summary>Missing links</summary>
                        {inspection.missing_links.length ? <ul>{inspection.missing_links.map((x) => <li key={x}>{x}</li>)}</ul>
                            : <p>No broken references reported. Semantic preservation is still unassessed until you judge it.</p>}
                    </details>
                </>}
            </div>
        </div>
        {reference && <aside className="iw-thought-reference" aria-label="Reference inspection">
            <h4>Reference: {reference}</h4>
            <pre>{JSON.stringify([
                ...session.graph.claims, ...session.graph.source_units, ...session.graph.semantic_atoms,
            ].find((item) => [item.claim_id, item.source_unit_id, item.atom_id].includes(reference)) ||
                { missing_reference: reference }, null, 2)}</pre>
            <button type="button" className="iw-expand" onClick={() => setReference(null)}>Close reference</button>
        </aside>}
        <ul className="iw-quiet">{row.limits.map((limit) => <li key={limit}>{limit}</li>)}</ul>
        <p>Recorded preservation: <b>{row.judgment.value.replaceAll('_', ' ')}</b>
            {row.judgment.assessed_by && ` · ${row.judgment.assessed_by} · ${row.judgment.at}`}</p>
        {inspection && <div className="iw-thought-form">
            <label>Recover the original thought in your words<textarea aria-label="Recovered thought"
                value={recovered} onChange={(e) => setRecovered(e.target.value)} /></label>
            <label>Did the graph preserve it?<select aria-label="Preservation judgment" value={judgment}
                onChange={(e) => setJudgment(e.target.value)}>
                {PRESERVATION_VALUES.map((v) => <option key={v} value={v}>{v.replaceAll('_', ' ')}</option>)}
            </select></label>
            <label>What survived, or which connection is missing?<textarea aria-label="Preservation note"
                value={note} onChange={(e) => setNote(e.target.value)} /></label>
            <label>Choose a possible next investigation (nothing executes)<textarea aria-label="Next investigation"
                value={next} onChange={(e) => setNext(e.target.value)} /></label>
            <label>Your name or initials<input aria-label="Assessment author" value={actor}
                onChange={(e) => setActor(e.target.value)} /></label>
            <button type="button" className="iw-start" disabled={busy || row.graph_stale || !actor.trim() ||
                selected.length > 8 || (judgment !== 'not_assessed' && !note.trim())}
                onClick={() => onReview({ expected_constellation_revision: row.revision,
                    graph_hash: inspection.graph.graph_hash, actor,
                    confirmed_claim_refs: selected, rejected_claim_refs: refs(claimIds, 'rejected'),
                    confirmed_edge_refs: refs(edgeIds, 'confirmed'), rejected_edge_refs: refs(edgeIds, 'rejected'),
                    judgment: { value: judgment, note, recovered_thought: recovered, next_investigation: next } })}>
                Save memberships and human judgment
            </button>
        </div>}
    </article>;
}
