import React, { useCallback, useEffect, useState } from 'react';
import RevisionCard from './RevisionCard';
import PassageGenealogy from './PassageGenealogy';
import './Revision.css';

const ORCHESTRATION_KEYS = ['goal', 'arc', 'priority', 'avoid', 'voice'];

/**
 * Semant Writer · W8 — revising one committed passage.
 *
 * THE RE-RENDER GOES THROUGH THE ORDINARY RUN PATH, and that is the load-bearing decision
 * on this side. The panel composes the author's (possibly changed) declarations back into a
 * plain block — `// avoid: …` lines and a `/ operator(…)` line — and sends it to the same
 * endpoint the editor's Render button uses. There is no revise-and-render call anywhere in
 * the service.
 *
 * A second render path is exactly where a "the author wants this improved" instruction
 * eventually gets added: it would have no first-render caller to break, so nothing would
 * object. Sharing the one path means the no-silent-improvement guard cannot be routed
 * around, because there is nowhere else to route.
 *
 * WHAT THE AUTHOR EDITS HERE IS THEIR DECLARATIONS, NOT THE PROSE. There is no textarea for
 * the passage. If they want different words they change what they declared and render, or
 * they type the sentence themselves in the editor — which is authoring, and needs no model.
 */
export default function RevisionPanel({
  lineageId,
  sceneId,
  blockId,
  answering = null,
  onPrepare,
  onRender,
  onAcceptRevision,
  onDismiss,
  onClose = null,
}) {
  const [prepared, setPrepared] = useState(null);
  const [orchestration, setOrchestration] = useState({});
  const [operators, setOperators] = useState('');
  const [proposal, setProposal] = useState(null);
  const [diff, setDiff] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  useEffect(() => {
    let live = true;
    (async () => {
      setError('');
      try {
        const data = await onPrepare(sceneId, blockId);
        if (!live) return;
        setPrepared(data);
        setOrchestration({ ...(data.declared?.intents || {}) });
        setOperators(Object.keys(data.declared?.operators || {}).join(' + '));
      } catch (err) {
        if (live) setError(err.message || 'could not load this passage');
      }
    })();
    return () => { live = false; };
  }, [sceneId, blockId, onPrepare]);

  /** The author's declarations, back into the block notation the loop already speaks. */
  const composeBlock = useCallback(() => {
    const lines = [];
    ORCHESTRATION_KEYS.forEach((key) => {
      const value = (orchestration[key] || '').trim();
      if (value) lines.push(`// ${key}: ${value}`);
    });
    const invocation = operators.trim();
    if (invocation) lines.push(`/ ${invocation}`);
    return lines.join('\n');
  }, [orchestration, operators]);

  const render = async () => {
    setError('');
    setStatus('');
    setBusy(true);
    try {
      const block = composeBlock();
      if (!block.includes('/')) {
        setError('A revision needs at least one operator to render from.');
        return;
      }
      const result = await onRender(block);
      const rendered = (result.results || []).find((r) => r.status === 'ok');
      if (!rendered) {
        const refusal = (result.results || []).find((r) => r.refusal);
        setError(refusal?.refusal || 'Nothing rendered — nothing has changed.');
        return;
      }
      setProposal({ id: rendered.passage_id, text: rendered.text });
      setDiff(diffAgainst(prepared?.declared, {
        operators: parseOperators(operators, prepared?.declared?.operators || {}),
        intents: cleaned(orchestration),
      }));
    } catch (err) {
      setError(err.message || 'the re-render did not go through');
    } finally {
      setBusy(false);
    }
  };

  const accept = async ({ passageId, inResponseTo }) => {
    const result = await onAcceptRevision({
      passageId, lineageId, sceneId, blockId, inResponseTo,
    });
    setProposal(null);
    setDiff(null);
    setPrepared((p) => (p ? {
      ...p,
      current_version: result.version.version,
      current_text: result.version.text,
      history: [...(p.history || []), result.version],
    } : p));
    setStatus(`Committed as v${result.version.version}. v${result.version.version - 1} is kept.`);
    return result;
  };

  const dismiss = async (passageId) => {
    await onDismiss(passageId);
    setProposal(null);
    setDiff(null);
    setStatus('Kept the version you had. Nothing was written.');
  };

  if (error && !prepared) {
    return <section className="writer-revision" data-testid="revision-panel-error">
      <p className="writer-revision__error">{error}</p>
    </section>;
  }
  if (!prepared) return null;

  return (
    <section className="writer-revision-panel" data-testid="revision-panel">
      <header className="writer-revision__head">
        <span className="writer-revision__label">
          Revising v{prepared.current_version}
        </span>
        <span className="writer-revision__note">
          Change what you declared, then render. Your current version stays until you
          accept a new one.
        </span>
        {onClose && (
          <button type="button" data-testid="revision-close" onClick={onClose}>close</button>
        )}
      </header>

      <div className="writer-revision__declarations">
        <label htmlFor="rev-operators">
          <span>Operators</span>
          <input
            id="rev-operators"
            data-testid="revise-operators"
            value={operators}
            onChange={(e) => setOperators(e.target.value)}
            placeholder="restraint + threshold"
          />
        </label>
        {ORCHESTRATION_KEYS.map((key) => (
          <label key={key} htmlFor={`rev-${key}`}>
            <span>// {key}</span>
            <input
              id={`rev-${key}`}
              data-testid={`revise-${key}`}
              value={orchestration[key] || ''}
              onChange={(e) => setOrchestration((o) => ({ ...o, [key]: e.target.value }))}
            />
          </label>
        ))}
      </div>

      <div className="writer-revision__actions">
        <button type="button" data-testid="revise-render" disabled={busy} onClick={render}>
          Render a new version
        </button>
        {status && <span className="writer-revision__note" data-testid="revision-status">
          {status}
        </span>}
      </div>
      {error && <p className="writer-revision__error">{error}</p>}

      {proposal && (
        <RevisionCard
          lineageId={lineageId}
          currentVersion={prepared.current_version}
          currentText={prepared.current_text}
          proposal={proposal}
          diff={diff}
          answering={answering}
          busy={busy}
          onAccept={accept}
          onDismiss={dismiss}
        />
      )}

      <PassageGenealogy
        versions={prepared.history || []}
        currentVersion={prepared.current_version}
      />
    </section>
  );
}

/** Intent values the author actually filled in. */
function cleaned(intents) {
  const out = {};
  Object.entries(intents || {}).forEach(([k, v]) => {
    if ((v || '').trim()) out[k] = v.trim();
  });
  return out;
}

/**
 * Operator names → their CURRENT versions, for the preview diff only.
 *
 * The authoritative diff is computed on the server against the parent version's frozen
 * provenance; this is a preview so the author can see what they are about to change before
 * they commit to it. Names not in the current declaration set have no known version yet,
 * which is honest: the server fills it in from what actually fired.
 */
function parseOperators(text, known) {
  const out = {};
  String(text || '').split('+').forEach((part) => {
    const name = part.trim().replace(/\(.*\)$/, '').trim();
    if (name) out[name] = known[name] ?? null;
  });
  return out;
}

/** The same shape the server produces, computed locally for the preview. */
function diffAgainst(before, after) {
  const ops0 = before?.operators || {};
  const ops1 = after?.operators || {};
  const int0 = before?.intents || {};
  const int1 = after?.intents || {};
  const keys = (a, b) => Object.keys(a).filter((k) => !(k in b));
  return {
    operators_added: keys(ops1, ops0).sort(),
    operators_removed: keys(ops0, ops1).sort(),
    operators_reversioned: Object.keys(ops1)
      .filter((n) => n in ops0 && ops1[n] != null && ops0[n] !== ops1[n])
      .map((n) => ({ name: n, from: ops0[n], to: ops1[n] })),
    intents_added: keys(int1, int0).sort(),
    intents_removed: keys(int0, int1).sort(),
    intents_changed: Object.keys(int1)
      .filter((k) => k in int0 && int0[k] !== int1[k])
      .map((k) => ({ key: k, from: int0[k], to: int1[k] })),
  };
}
