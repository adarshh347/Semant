import React, { useState } from 'react';
import DeclarationDiff from './DeclarationDiff';
import './Revision.css';

/**
 * Semant Writer · W8 — a proposed next version, on screen.
 *
 * THIS CARD OFFERS NO WAY TO IMPROVE ANYTHING, and that absence is the design. The buttons
 * are Accept and Dismiss: commit this as the next version, or keep the one you have. There
 * is no "try again but better", no "tighten", no slider between the two versions — every one
 * of those hands the model a standard the author never declared, which is the thing W8 spent
 * its whole guard budget refusing. If the author wants something different, they change
 * their declarations and render again, and the diff explains itself.
 *
 * THE DECLARATION DIFF IS SHOWN ABOVE THE PROSE. What changed in the author's own terms is
 * the thing that explains the new text, so it reads first; the prose is the consequence.
 *
 * THE CURRENT VERSION IS SHOWN BESIDE IT — to the AUTHOR. Note that the model never saw it:
 * a revision is a fresh render under the declared set, precisely so that "here is what you
 * wrote, now do better" is a sentence nobody can have said. Comparison is a person's job.
 */
export default function RevisionCard({
  lineageId,
  currentVersion,
  currentText,
  proposal,
  diff,
  answering = null,
  busy = false,
  onAccept,
  onDismiss,
}) {
  const [error, setError] = useState('');
  const [working, setWorking] = useState(false);

  if (!proposal) return null;

  const act = async (fn) => {
    setError('');
    setWorking(true);
    try {
      await fn();
    } catch (err) {
      setError(err.message || 'that did not go through');
    } finally {
      setWorking(false);
    }
  };

  const disabled = busy || working;

  return (
    <section className="writer-revision" data-testid="revision-card">
      <header className="writer-revision__head">
        <span className="writer-revision__label">
          A proposed v{(currentVersion || 1) + 1}
        </span>
        <span className="writer-revision__note" data-testid="revision-not-applied">
          Nothing has changed in your manuscript. v{currentVersion || 1} is still what the
          book says.
        </span>
      </header>

      <div className="writer-revision__why">
        <h5>What you changed</h5>
        <DeclarationDiff diff={diff} />
      </div>

      {answering?.element && (
        <p className="writer-revision__answering" data-testid="revision-answering">
          Revising against <code>{answering.element}</code>
        </p>
      )}

      <div className="writer-revision__texts">
        <article className="writer-revision__side">
          <h5>v{currentVersion || 1} — in the book now</h5>
          <blockquote data-testid="revision-current-text">{currentText}</blockquote>
        </article>
        <article className="writer-revision__side writer-revision__side--new">
          <h5>proposed</h5>
          <blockquote data-testid="revision-proposed-text">{proposal.text}</blockquote>
        </article>
      </div>

      <footer className="writer-revision__foot">
        <span className="writer-revision__note">
          Accepting keeps v{currentVersion || 1} — it moves the pointer, it does not
          overwrite.
        </span>
        <button
          type="button"
          data-testid="revision-accept"
          disabled={disabled}
          onClick={() => act(() => onAccept({
            passageId: proposal.id, lineageId, inResponseTo: answering,
          }))}
        >
          Make this v{(currentVersion || 1) + 1}
        </button>
        <button
          type="button"
          data-testid="revision-dismiss"
          disabled={disabled}
          onClick={() => act(() => onDismiss(proposal.id))}
        >
          Keep v{currentVersion || 1}
        </button>
      </footer>
      {error && <p className="writer-revision__error">{error}</p>}
    </section>
  );
}
