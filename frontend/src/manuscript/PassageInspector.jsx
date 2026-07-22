import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  describeSelection, buildChipInspection, selectionQuestions,
  actionsForSelection, inspectorSummary,
} from './manuscriptField';
import { resolveGround } from '../differential/grounds';
import './PassageInspector.css';

/**
 * Passage Inspector — what the selected writing rests on.
 *
 * CIRCUIT-001 P2C-MS, first slice. **Read-only. It renders derivations and
 * nothing else.** It does not persist, does not call a model, does not create a
 * Mention, does not alter the editor schema, and does not touch the `/percept`
 * slash flow or the P1B handoff.
 *
 * It listens rather than couples: a percept chip already emits
 * `semant:region-focus` (regionRefInline), and a text selection is read from the
 * live DOM range scoped to `.manuscript`. Nothing in the editor had to change to
 * make the writing answerable.
 *
 * Discipline it renders:
 *   - records and judgements are labelled and styled apart (P1D)
 *   - the evidence line appears ONLY when degraded or unknown (P1)
 *   - unanswerable questions say `not assessed`, never a clean answer (P1C)
 *   - every act is preview-only with NO button, and says so (P2B)
 */
export default function PassageInspector({ store, blocks = [] }) {
  const [selection, setSelection] = useState(() => describeSelection());

  // A percept chip announces itself through the event the chip already emits.
  useEffect(() => {
    const onFocus = (e) => {
      const perceptId = e.detail?.perceptId || null;
      if (!perceptId) return;
      setSelection(describeSelection({
        kind: 'percept_chip',
        chips: [{ perceptId, regionIds: (e.detail?.regionIds || []).join(',') }],
      }));
    };
    window.addEventListener('semant:region-focus', onFocus);
    return () => window.removeEventListener('semant:region-focus', onFocus);
  }, []);

  // A prose selection is read from the live range. Transient by design: a
  // selection is never persisted and never becomes a Mention — the corpus has no
  // evidence yet of how curators cite, so inventing a second citation model
  // beside Mentions would be premature (P0 open decisions §4).
  const readSelection = useCallback(() => {
    if (typeof window === 'undefined' || !window.getSelection) return;
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    const root = range.commonAncestorContainer;
    const el = root.nodeType === 1 ? root : root.parentElement;
    if (!el || !el.closest?.('.manuscript')) return;

    const text = sel.toString();
    if (!text.trim()) return;

    // Chips inside the range — the markup is the record.
    const frag = range.cloneContents();
    const chips = [...frag.querySelectorAll('[data-region-ref]')].map((c) => ({
      perceptId: c.getAttribute('data-percept-id') || null,
      regionIds: c.getAttribute('data-region-ids') || '',
      label: c.getAttribute('data-label') || '',
    }));
    const block = el.closest?.('[data-id]');
    setSelection(describeSelection({
      kind: 'text', text, blockId: block?.getAttribute('data-id') || null, chips,
    }));
  }, []);

  useEffect(() => {
    document.addEventListener('selectionchange', readSelection);
    return () => document.removeEventListener('selectionchange', readSelection);
  }, [readSelection]);

  const percepts = store?.percepts || [];
  const grounds = store?.grounds || [];
  const regions = store?.regions || [];
  const mentions = store?.mentions || [];

  const inspection = useMemo(() => {
    if (selection.kind !== 'percept_chip') return null;
    const id = selection.cited_percept_ids[0];
    const percept = percepts.find((p) => p.id === id) || null;
    return buildChipInspection(percept, {
      grounds,
      // Supplying the resolver is what lets evidence be assessed at all. Without
      // it the state is `unknown` — never `intact`.
      resolve: (g) => resolveGround(g, { regions, grounds }),
      mentions,
      recallCount: store?.recallCount?.(id) ?? 0,
      label: selection.text,
    });
  }, [selection, percepts, grounds, regions, mentions, store]);

  const questions = useMemo(
    () => (selection.kind === 'text' ? selectionQuestions(selection) : []),
    [selection],
  );
  const actions = useMemo(() => actionsForSelection(selection), [selection]);
  const summary = inspectorSummary(selection, inspection);

  if (selection.kind === 'none') {
    return (
      <aside className="passage-inspector is-resting" aria-label="Passage inspector">
        <p className="pi-resting">Select a sentence, or a percept chip, to see what it rests on.</p>
      </aside>
    );
  }

  return (
    <aside className="passage-inspector" aria-label="Passage inspector">
      <header className="pi-head">
        <span className="pi-eyebrow">What this rests on</span>
        <span className="pi-summary">{summary}</span>
      </header>

      {selection.kind === 'text' && (
        <>
          <blockquote className="pi-quote">{selection.text}</blockquote>
          {selection.citation_state === 'cites_nothing' && (
            // A RECORD. Not "unsupported" — the system knows what the markup
            // shows, not what the sentence rests on.
            <p className="pi-record pi-none">No percept citation yet</p>
          )}
          <ul className="pi-questions">
            {questions.map((q) => (
              <li key={q.key} className={`pi-q pi-voice-${q.voice}${q.answerable ? '' : ' is-unassessed'}`}>
                <span className="pi-q-label">{q.question}</span>
                <span className="pi-q-answer">{q.answer}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      {selection.kind === 'percept_chip' && inspection && (
        inspection.resolved ? (
          <dl className="pi-sections">
            {inspection.sections.map((s) => (
              <div key={s.key} className={`pi-section pi-voice-${s.voice}${s.hasCounterforce ? ' has-counterforce' : ''}`}>
                <dt>{s.label}</dt>
                <dd>{s.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="pi-judgement">{inspection.note}</p>
        )
      )}

      {actions.length > 0 && (
        <div className="pi-actions">
          <span className="pi-actions-head">Preview only — execution path not wired yet</span>
          <ul>
            {actions.map((a) => (
              // No button. An Apply that quietly does nothing teaches the
              // curator that the whole panel is theatre.
              <li key={a.type} className="pi-action" data-action-type={a.type} data-wired="false">
                {a.label}
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
