import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  describeSelection, buildChipInspection, selectionQuestions,
  actionsForSelection, inspectorSummary, collapsedSummary,
  composePerceptFromSelection, draftFromSelection, challengeSupportAction, previewProposal,
} from './manuscriptField';
import { resolveGround } from '../differential/grounds';
import { buildPerceptPacket, packetSummary } from '../differential/perceptPacket';
import { buildCirculationThread, threadSummary } from '../differential/circulationThread';
import { marksForPercept, markDisplay } from '../differential/markStaging';
import './PassageInspector.css';

/**
 * Passage Inspector — what the selected writing rests on, and what it can do.
 *
 * CIRCUIT-001 P2C-MS shipped the read-only inspector. P2C-MS2 gives it
 * circulation energy: a collapse/expand control so it never dominates the page,
 * and real safe actions so the Manuscript can act back on the image and on
 * Differential — while never claiming to have acted where it has not.
 *
 * What is real here (nothing mutates the corpus, nothing dispatches a model):
 *   live      recall on the image · revise in Differential · start a passage ·
 *             send a selection back to Differential
 *   disclose  the percept's packet and circulation thread, from pure builders
 *   staged    a valid Perceptual-Action-Grammar proposal, built and shown, then
 *             STOPPED — "Ready, not sent"
 *   preview   a structured proposal for a grammar type that does not exist yet
 *
 * Coupling stays light: it listens to the `semant:region-focus` event the chip
 * already emits and to the live selection; the live actions are callbacks the
 * parent owns. Nothing in the editor had to change.
 */
export default function PassageInspector({
  store, blocks = [], postId = null,
  onRecall, onReviseInDifferential, onStartPassage, onSendToDifferential,
}) {
  const [selection, setSelection] = useState(() => describeSelection());
  const [expanded, setExpanded] = useState(true);
  // Staged/preview proposals the curator has surfaced, keyed by action. Held for
  // inspection only — nothing here is dispatched, saved, or committed.
  const [proposals, setProposals] = useState({});
  const [disclosure, setDisclosure] = useState(null); // 'packet' | 'thread' | null

  const resetTransient = () => { setProposals({}); setDisclosure(null); };

  // A percept chip announces itself through the event the chip already emits.
  useEffect(() => {
    const onFocus = (e) => {
      const perceptId = e.detail?.perceptId || null;
      if (!perceptId) return;
      resetTransient();
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
  // evidence yet of how curators cite, so a second citation model beside Mentions
  // would be premature (P0 open decisions §4).
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

    const frag = range.cloneContents();
    const chips = [...frag.querySelectorAll('[data-region-ref]')].map((c) => ({
      perceptId: c.getAttribute('data-percept-id') || null,
      regionIds: c.getAttribute('data-region-ids') || '',
      label: c.getAttribute('data-label') || '',
    }));
    const block = el.closest?.('[data-id]');
    resetTransient();
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

  const percept = useMemo(
    () => (selection.kind === 'percept_chip'
      ? percepts.find((p) => p.id === selection.cited_percept_ids[0]) || null
      : null),
    [selection, percepts],
  );

  const resolve = useCallback((g) => resolveGround(g, { regions, grounds }), [regions, grounds]);

  const inspection = useMemo(() => {
    if (selection.kind !== 'percept_chip') return null;
    return buildChipInspection(percept, {
      grounds,
      resolve, // supplying the resolver is what lets evidence be assessed at all
      mentions,
      recallCount: 0,
      label: selection.text,
    });
  }, [selection, percept, grounds, mentions, resolve]);

  const questions = useMemo(
    () => (selection.kind === 'text' ? selectionQuestions(selection) : []),
    [selection],
  );
  const actions = useMemo(() => actionsForSelection(selection), [selection]);

  // CIRCUIT-001 P2E — the visual marks (P2D-A) standing behind this percept's
  // evidence: an instrument mark rides on a ground, the percept cites the ground,
  // so the writing can reach the mark. Read-only from the store; SESSION-ONLY, so
  // the panel says "not saved" and does not pretend a mark survives reload.
  const markRefs = useMemo(() => {
    if (selection.kind !== 'percept_chip' || !percept) return [];
    return marksForPercept(percept, store?.visualMarks || []).map(markDisplay);
  }, [selection, percept, store]);

  // ── acting ──────────────────────────────────────────────────────────────
  const runLive = (key) => {
    switch (key) {
      case 'recall': onRecall?.(selection.cited_percept_ids[0]); break;
      case 'revise': onReviseInDifferential?.(selection.cited_percept_ids[0]); break;
      case 'start_passage': onStartPassage?.(selection.block_id); break;
      case 'send_first_attention': onSendToDifferential?.(selection.text); break;
      default: break;
    }
  };

  const toggleDisclosure = (which) => setDisclosure((d) => (d === which ? null : which));

  const stageProposal = (descriptor) => {
    setProposals((prev) => {
      if (prev[descriptor.key]) { const { [descriptor.key]: _drop, ...rest } = prev; return rest; }
      let value = null;
      if (descriptor.kind === 'staged') {
        if (descriptor.key === 'create_percept') value = composePerceptFromSelection(selection);
        else if (descriptor.key.startsWith('draft_')) value = draftFromSelection(descriptor.key, selection);
        else if (descriptor.key === 'challenge_support') value = challengeSupportAction(selection.cited_percept_ids[0]);
      } else {
        value = previewProposal(descriptor, selection);
      }
      return value ? { ...prev, [descriptor.key]: { descriptor, value } } : prev;
    });
  };

  const onActionClick = (a) => {
    if (a.kind === 'live') runLive(a.key);
    else if (a.kind === 'disclose') toggleDisclosure(a.key);
    else stageProposal(a); // staged | preview
  };

  // ── disclosures (pure builders — nothing is fetched or sent) ──────────────
  const packet = useMemo(
    () => (disclosure === 'packet' && percept
      ? buildPerceptPacket(percept, { postId, grounds, resolve, mentions, blocks, intent: 'read' })
      : null),
    [disclosure, percept, postId, grounds, resolve, mentions, blocks],
  );
  const thread = useMemo(
    () => (disclosure === 'thread' && percept
      ? buildCirculationThread(percept, { grounds, regions, mentions, visionRuns: null, recallCount: 0 })
      : null),
    [disclosure, percept, grounds, regions, mentions],
  );

  const summary = expanded ? inspectorSummary(selection, inspection) : collapsedSummary(selection, inspection);

  return (
    <aside
      className={`passage-inspector${selection.kind === 'none' ? ' is-resting' : ''}${expanded ? '' : ' is-collapsed'}`}
      aria-label="Passage inspector"
    >
      <header className="pi-head">
        <button
          type="button"
          className="pi-toggle"
          aria-expanded={expanded}
          aria-controls="pi-body"
          onClick={() => setExpanded((v) => !v)}
          title={expanded ? 'Collapse' : 'Expand'}
        >
          <span className="pi-chevron" aria-hidden>{expanded ? '▾' : '▸'}</span>
          <span className="pi-eyebrow">What this rests on</span>
        </button>
        <span className="pi-summary">{summary}</span>
      </header>

      {expanded && (
        <div id="pi-body" className="pi-body">
          {selection.kind === 'none' && (
            <p className="pi-resting">Select a sentence, or a percept chip, to see what it rests on — and what it can do.</p>
          )}

          {selection.kind === 'text' && (
            <>
              <blockquote className="pi-quote">{selection.text}</blockquote>
              {selection.citation_state === 'cites_nothing' && (
                <p className="pi-record pi-none">This sentence has not cited an image yet</p>
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

          {/* CIRCUIT-001 P2E — the visual marks behind the evidence. Session-only,
              and it says so. A suggestion reads as uncitable; a user/confirmed mark
              reads differently, with its provenance and any lineage. */}
          {selection.kind === 'percept_chip' && markRefs.length > 0 && (
            <div className="pi-marks" role="group" aria-label="Visual marks">
              <div className="pi-marks-head">Visual marks · Session — not saved</div>
              <ul>
                {markRefs.map((m) => (
                  <li key={m.id} className={`pi-mark${m.is_suggestion ? ' is-suggestion' : ''}`} data-citable={m.citable}>
                    <span className="pi-mark-role">{m.type.replace(/_/g, ' ')} · {m.role_label}</span>
                    <span className="pi-mark-prov">{m.provenance}</span>
                    <span className="pi-mark-cite">{m.citable ? 'citable' : 'not citable'}</span>
                    {m.derived_from && <span className="pi-mark-derived">accepted from {m.derived_from}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* disclosures */}
          {packet && (
            <div className="pi-disclosure" role="group" aria-label="Percept packet">
              <div className="pi-disclosure-head">Packet · {packetSummary(packet)}</div>
              <div className="pi-disclosure-line">{packet.dispatch.note}</div>
            </div>
          )}
          {thread && (
            <div className="pi-disclosure" role="group" aria-label="Circulation thread">
              <div className="pi-disclosure-head">Circulation · {threadSummary(thread)}</div>
              <ul className="pi-thread">
                {thread.map((row, i) => (
                  <li key={i} className={`pi-thread-row pi-voice-${row.voice === 'judgement' ? 'judgement' : 'record'}`}>
                    <span className="pi-thread-voice">{row.voice}</span>
                    <span className="pi-thread-text">{row.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* actions */}
          {actions.length > 0 && (
            <div className="pi-actions">
              <ul>
                {actions.map((a) => {
                  const staged = proposals[a.key];
                  const active = a.kind === 'disclose' ? disclosure === a.key : !!staged;
                  return (
                    <li key={a.key} className={`pi-action pi-kind-${a.kind}${active ? ' is-active' : ''}`}>
                      <button
                        type="button"
                        className="pi-action-btn"
                        data-action-key={a.key}
                        data-kind={a.kind}
                        aria-pressed={a.kind === 'live' ? undefined : active}
                        onClick={() => onActionClick(a)}
                      >
                        <span className="pi-action-label">{a.label}</span>
                        <span className="pi-action-tone">{a.tone}</span>
                      </button>
                      {staged && (
                        <div className="pi-proposal" data-grammar={staged.value?.type && staged.descriptor.kind === 'staged' ? 'true' : 'false'}>
                          <span className="pi-proposal-badge">
                            {staged.descriptor.kind === 'staged' ? 'Ready, not sent' : 'Structured preview'}
                          </span>
                          {staged.descriptor.kind === 'staged' && staged.value?.warnings?.length > 0 && (
                            <ul className="pi-proposal-warnings">
                              {staged.value.warnings.map((w, i) => <li key={i}>{w}</li>)}
                            </ul>
                          )}
                          {staged.descriptor.kind === 'preview' && (
                            <span className="pi-proposal-note">{staged.value.note}</span>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
