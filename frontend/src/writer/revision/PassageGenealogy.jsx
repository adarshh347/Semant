import React, { useState } from 'react';
import DeclarationDiff from './DeclarationDiff';
import './Revision.css';

/**
 * Semant Writer · W8 — how this paragraph became what it is. READ-ONLY.
 *
 * THERE IS NO RESTORE BUTTON, AND ITS ABSENCE IS DELIBERATE RATHER THAN UNFINISHED. A
 * "revert to v1" affordance looks like the natural companion to a history view, and it is
 * the one thing this view must not offer: restoring would either mutate the current version
 * or silently append a copy the author never re-declared, and both make the pointer move
 * without an authoring act behind it. If the author wants v1's prose back, the honest route
 * is the one the whole system is built on — declare what they want again and render it,
 * which produces a new version with an honest diff explaining itself.
 *
 * EVERY ENTRY LEADS WITH ITS DECLARATION DIFF, not with the prose. The prose is what
 * changed; the declarations are why, and a history that showed only the paragraphs would be
 * a diff viewer rather than a genealogy.
 *
 * A REVISION THAT ANSWERED A W7 FLAG SHOWS WHETHER IT WORKED — including when it did not.
 * `still present` is displayed as plainly as `cleared`, because a loop that only showed its
 * successes would quietly teach the author that revision always works.
 */
export default function PassageGenealogy({ versions = [], currentVersion = null }) {
  const [openVersion, setOpenVersion] = useState(null);

  if (!versions.length) return null;

  const current = currentVersion ?? versions[versions.length - 1]?.version;

  return (
    <section className="writer-genealogy" data-testid="genealogy">
      <header className="writer-genealogy__head">
        <h4>How this passage became what it is</h4>
        <p className="writer-genealogy__note">
          Every version you committed is kept. Nothing here can be edited or restored —
          to go back, declare it again and render.
        </p>
      </header>

      <ol className="writer-genealogy__list">
        {versions.map((version) => {
          const isCurrent = version.version === current;
          const open = openVersion === version.version;
          const loop = version.loop_outcome;
          return (
            <li
              key={version.id || version.version}
              className={`writer-version${isCurrent ? ' writer-version--current' : ''}`}
              data-testid="genealogy-version"
            >
              <div className="writer-version__head">
                <span className="writer-version__number" data-testid="version-number">
                  v{version.version}
                </span>
                {isCurrent && (
                  <span className="writer-version__badge" data-testid="version-current">
                    current
                  </span>
                )}
                {!isCurrent && (
                  <span className="writer-version__badge writer-version__badge--past">
                    superseded — kept
                  </span>
                )}
                {version.revised_from && (
                  <span className="writer-version__parent" data-testid="version-parent">
                    revised from {version.revised_from}
                  </span>
                )}
              </div>

              {version.version === 1 ? (
                <p className="writer-version__origin">First committed version.</p>
              ) : (
                <DeclarationDiff diff={version.declaration_diff} compact />
              )}

              {version.in_response_to?.flag_id && (
                <p className="writer-version__flag" data-testid="version-flag-link">
                  You revised this against{' '}
                  <code>{version.in_response_to.element || 'an alignment flag'}</code>
                  {loop && (
                    <span
                      className={`writer-version__loop writer-version__loop--${loop.outcome}`}
                      data-testid="version-loop-outcome"
                    >
                      {loop.outcome === 'cleared'
                        ? '— the divergence cleared'
                        : '— the divergence was still there afterwards'}
                    </span>
                  )}
                </p>
              )}

              <button
                type="button"
                className="writer-version__peek"
                data-testid="version-peek"
                aria-expanded={open}
                onClick={() => setOpenVersion(open ? null : version.version)}
              >
                {open ? 'hide this version' : 'read this version'}
              </button>
              {open && (
                <blockquote className="writer-version__text" data-testid="version-text">
                  {version.text}
                </blockquote>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
