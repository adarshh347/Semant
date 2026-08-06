import React, { useState } from 'react';
import { writerService } from '../writerService';
import './AlignmentReading.css';

/**
 * Semant Writer · W7 — the alignment reading, on screen.
 *
 * THERE IS NO REWRITE BUTTON, AND THERE MUST NEVER BE ONE. The reading says where the prose
 * diverges from what the author declared. What to do about it is theirs, and the forward
 * action is going back through the render loop under adjusted orchestration — an authoring
 * act, not a patch this panel applies. A "fix it" affordance here would turn a diagnosis
 * into the model's taste editing the author's book, which is the thing W7 exists to refuse.
 *
 * EVERY FLAG SHOWS WHAT IT RESTS ON. Not as a footnote — as the first thing after the
 * quoted span. A flag whose declared element were hidden would read exactly like generic
 * craft advice, and the author would have no way to tell the two apart. The backend already
 * drops any flag that cannot cite one; this makes the citation visible so the discipline is
 * legible rather than merely true.
 *
 * SILENCE IS RENDERED AS A RESULT. `aligned` and `thin` get their own states, phrased so
 * they read as answers rather than as the panel having failed to find something.
 */
export default function AlignmentReading({ reading, onDecide = null, busy = false }) {
  const [deciding, setDeciding] = useState('');

  if (!reading) return null;

  const decide = async (flagId, state) => {
    if (!onDecide) return;
    setDeciding(flagId);
    try {
      await onDecide(flagId, state);
    } finally {
      setDeciding('');
    }
  };

  const { status, detail, flags = [], measured_against: measured = [], model } = reading;

  if (status === 'aligned') {
    return (
      <section className="writer-reading writer-reading--aligned" data-testid="reading">
        <p className="writer-reading__verdict" data-testid="reading-aligned">
          Aligned — nothing here diverges from what you declared.
        </p>
        <Measured elements={measured} model={model} />
      </section>
    );
  }

  if (status === 'thin') {
    return (
      <section className="writer-reading writer-reading--thin" data-testid="reading">
        <p className="writer-reading__verdict" data-testid="reading-thin">{detail}</p>
      </section>
    );
  }

  if (status === 'no_provenance') {
    return (
      <section className="writer-reading writer-reading--thin" data-testid="reading">
        <p className="writer-reading__verdict" data-testid="reading-no-provenance">{detail}</p>
      </section>
    );
  }

  if (status === 'unavailable' || status === 'error') {
    return (
      <section className="writer-reading writer-reading--unavailable" data-testid="reading">
        {/* Not "aligned". Could-not-look and looked-and-found-nothing are different answers. */}
        <p className="writer-reading__verdict" data-testid="reading-unavailable">{detail}</p>
      </section>
    );
  }

  return (
    <section className="writer-reading writer-reading--flagged" data-testid="reading">
      <p className="writer-reading__count" data-testid="reading-count">
        {flags.length} {flags.length === 1 ? 'divergence' : 'divergences'} from what you declared
      </p>

      {flags.map((flag) => (
        <article key={flag.id} className="writer-flag" data-testid="reading-flag">
          <blockquote className="writer-flag__span">{flag.span}</blockquote>

          {/* What this rests on — first, and in the author's own words. */}
          <p className="writer-flag__against" data-testid="flag-element">
            <span className="writer-flag__label">
              {flag.element_kind === 'intent'
                ? `against your // ${flag.element.replace('intent:', '')}`
                : flag.element_kind === 'operator_negative_example'
                  ? `against what you said /${flag.operator} is NOT`
                  : `against what you said /${flag.operator} should do`}
            </span>
            <span className="writer-flag__declared">“{flag.declared}”</span>
            {flag.operator_version && (
              <span className="writer-flag__version">/{flag.operator} v{flag.operator_version}</span>
            )}
          </p>

          <p className="writer-flag__divergence">{flag.divergence}</p>

          <footer className="writer-flag__actions">
            {flag.state === 'open' ? (
              <>
                <span className="writer-flag__note">
                  Nothing changes here — re-render it yourself if you agree.
                </span>
                <button
                  type="button"
                  data-testid="flag-acted"
                  disabled={busy || deciding === flag.id}
                  onClick={() => decide(flag.id, 'acted')}
                >
                  That's real
                </button>
                <button
                  type="button"
                  data-testid="flag-dismissed"
                  disabled={busy || deciding === flag.id}
                  onClick={() => decide(flag.id, 'dismissed')}
                >
                  Not a problem
                </button>
              </>
            ) : (
              <span className="writer-flag__decided" data-testid="flag-decided">
                {flag.state === 'acted' ? "marked real" : 'dismissed'}
              </span>
            )}
          </footer>
        </article>
      ))}

      <Measured elements={measured} model={model} />
    </section>
  );
}

/** The reading's own provenance — it is held to the standard it holds the prose to. */
function Measured({ elements, model }) {
  const [open, setOpen] = useState(false);
  if (!elements?.length) return null;
  return (
    <div className="writer-reading__measured">
      <button type="button" onClick={() => setOpen((o) => !o)} data-testid="show-measured">
        {open ? 'hide what this was measured against' : 'what was this measured against?'}
      </button>
      {open && (
        <ul data-testid="measured-elements">
          {elements.map((e) => (
            <li key={e.id}>
              <code>{e.id}</code>
              <span>“{e.declared}”</span>
            </li>
          ))}
          {model && <li className="writer-reading__model">read by {model}</li>}
        </ul>
      )}
    </div>
  );
}
