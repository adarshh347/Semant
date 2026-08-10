import React from 'react';
import { EmptyState, LifecycleChip, EpistemicChip, VerdictChip } from './Chips';
import { artifactSummary } from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — everything this session has produced, including the refusals.
 *
 * A REFUSAL IS A ROW. It has an id, a run, a step and a provenance, and it can be reopened and
 * read months later. A laboratory whose ledger held only its successes would be telling you that
 * the things it would not do never happened.
 *
 * Selection and activation are two different acts, so they are two different controls:
 *
 *   SELECTED  the set a follow-up resolves against. "those two" means exactly this list.
 *   ACTIVE    the one the inspector and the stage are showing.
 *
 * Collapsing them would mean that looking at something changed what a prompt would do to it, and
 * a person composing a two-endpoint question would keep losing an endpoint by reading it.
 *
 * Every row shows lifecycle and, if one exists, the verdict — as two visibly different chips
 * side by side. That adjacency is deliberate: this is the exact place where `kept` would start
 * being read as `correct`, so it is the place where they must be seen not to match.
 */
export default function Ledger({ ledger = [], selectedIds = [], activeId = null, reviewsFor,
    onToggleSelect, onActivate }) {
    return (
        <section className="pl-panel" aria-label="Ledger">
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Ledger</h2>
                <span className="pl-chip" data-ledger-count={ledger.length}>
                    {ledger.length} artifact{ledger.length === 1 ? '' : 's'}
                </span>
            </div>
            <p className="pl-panel-sub">
                Session-local. Nothing in this list is in Semant, and nothing here can put it
                there.
            </p>

            {ledger.length === 0 ? (
                <EmptyState title="This session has produced nothing yet"
                    hint="Refusals appear here too, with their run and their reason. A ledger of
                        successes only would hide what the laboratory would not do." />
            ) : (
                <ul className="pl-list" data-ledger>
                    {ledger.map((a) => {
                        const id = a.identity.artifact_id;
                        const selected = selectedIds.includes(id);
                        const reviews = reviewsFor ? reviewsFor(id) : [];
                        const last = reviews[reviews.length - 1] || null;
                        return (
                            <li key={id} className="pl-turn" data-ledger-row={id}
                                data-kind={a.identity.artifact_kind}>
                                <button type="button" className="pl-row"
                                    data-activate={id}
                                    aria-selected={activeId === id}
                                    onClick={() => onActivate(id)}>
                                    <span className="pl-row-name">{id}</span>
                                    <span className="pl-row-meta">{artifactSummary(a)}</span>
                                </button>
                                <span className="pl-chiprow">
                                    <button type="button" className="pl-btn pl-btn--quiet"
                                        data-select={id} aria-pressed={selected}
                                        onClick={() => onToggleSelect(id)}>
                                        {selected ? 'selected for reference' : 'select'}
                                    </button>
                                    <LifecycleChip status={a.lifecycle.status} />
                                    <EpistemicChip status={a.measurement.epistemic_status} />
                                    {last ? <VerdictChip verdict={last.verdict} /> : (
                                        <span className="pl-chip" data-unreviewed
                                            title="nobody has judged this. Not a verdict.">
                                            unjudged
                                        </span>
                                    )}
                                </span>
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}
