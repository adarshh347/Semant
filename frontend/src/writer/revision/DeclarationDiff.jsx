import React from 'react';

/**
 * Semant Writer · W8 — what the author changed, on screen.
 *
 * THE DIFF SHOWN HERE IS THE DECLARATION DIFF, NOT A TEXT DIFF, and that is the point of
 * the component. A word-level diff of the prose answers "what moved"; it cannot answer
 * "why", and a genealogy that only shows successive paragraphs is a diff viewer wearing
 * provenance. What the author needs to see — and what the version record keeps — is which
 * of their own declarations changed to cause the re-render.
 *
 * It renders an explicit line when nothing changed. Silence there would read as a component
 * that failed to load; "you re-rendered under the same declarations" is a real and useful
 * thing to be told, because it means any difference in the prose came from the model's
 * sampling rather than from anything the author did.
 */
export default function DeclarationDiff({ diff, compact = false }) {
  if (!diff) return null;

  const rows = [
    ...(diff.operators_added || []).map((n) => ({
      key: `oa-${n}`, mark: '+', label: `/${n}`, note: 'operator added',
    })),
    ...(diff.operators_removed || []).map((n) => ({
      key: `or-${n}`, mark: '−', label: `/${n}`, note: 'operator removed',
    })),
    ...(diff.operators_reversioned || []).map((o) => ({
      key: `ov-${o.name}`,
      mark: '~',
      label: `/${o.name}`,
      note: `v${o.from} → v${o.to} — you edited the operator itself`,
    })),
    ...(diff.intents_added || []).map((k) => ({
      key: `ia-${k}`, mark: '+', label: `// ${k}`, note: 'staging added',
    })),
    ...(diff.intents_removed || []).map((k) => ({
      key: `ir-${k}`, mark: '−', label: `// ${k}`, note: 'staging removed',
    })),
    ...(diff.intents_changed || []).map((i) => ({
      key: `ic-${i.key}`,
      mark: '~',
      label: `// ${i.key}`,
      note: `“${i.from}” → “${i.to}”`,
    })),
  ];

  if (!rows.length) {
    return (
      <p className="writer-diff writer-diff--empty" data-testid="declaration-diff-empty">
        Nothing you declared changed — this was re-rendered under the same operators and
        staging.
      </p>
    );
  }

  return (
    <ul
      className={`writer-diff${compact ? ' writer-diff--compact' : ''}`}
      data-testid="declaration-diff"
    >
      {rows.map((row) => (
        <li key={row.key} className={`writer-diff__row writer-diff__row--${row.mark === '+' ? 'add' : row.mark === '−' ? 'remove' : 'change'}`}>
          <span className="writer-diff__mark" aria-hidden="true">{row.mark}</span>
          <code className="writer-diff__label">{row.label}</code>
          <span className="writer-diff__note">{row.note}</span>
        </li>
      ))}
    </ul>
  );
}
