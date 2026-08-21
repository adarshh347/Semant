import React from 'react';
import { toolsFor, VERDICTS, VERDICT_NOTE, groupProposals } from '../toolRegistry';
import { form } from '../../contract/perceptionLabContract';

/**
 * PERCEPTUAL-FORMS-001E — the human tools, and the panel that keeps saying they write nothing.
 *
 * THE TOOLS ARE THE FORM'S OWN. `manual_tools` is a declared field on every form, so the tray is
 * not a menu somebody designed — it is the set that form says it accepts. `extent.hard_mask` gets
 * a brush and a polygon; `topology.pair_relation` gets a pair picker and an endpoint correction;
 * `extent.hypothesis_set` gets accept/reject, and gets it because the contract says so.
 *
 * A PROPOSAL IS NOT A CORRECTION TO THE RECORD, and the panel says which one is on screen. The
 * record is a measurement. A person dragging a vertex here has not re-measured anything; they
 * have said "this looks wrong, and here is what I think it should be". Those are different
 * claims, and merging them is how a laboratory turns into an editor.
 *
 * THE VERDICTS ARE THE CONTRACT'S. `review_verdicts` is the authority on what correct / partial /
 * wrong / unclear are called, so a verdict marked here is one the record could hold. `unclear` is
 * given its own sentence because it is the one people skip, and it is the honest answer whenever
 * a field is behind a ref, an endpoint does not resolve, or a raster is too coarse to judge.
 */

export default function ToolTray({
    formKey, activeTool, onTool, focusLayer, verdict, onVerdict, note, onNote,
    proposals = [], onClear,
}) {
    const tools = toolsFor(formKey);
    const groups = groupProposals(proposals);
    const declaration = form(formKey);

    return (
        <section className="pl-fm-panel" aria-label="Tools" data-tools={formKey}>
            <h3>Tools</h3>
            <p className="pl-fm-note" data-writes="nothing">
                Fixture-only. Nothing here saves, promotes, or calls an API — this surface has no
                client at all. Everything below produces a proposal that lives on this page.
            </p>

            <ul className="pl-fm-tabs" data-tool-list={tools.length}>
                {tools.map((t) => (
                    <li key={t.kind}>
                        <button
                            type="button"
                            className="pl-fm-tab"
                            data-tool={t.kind}
                            aria-pressed={activeTool === t.kind}
                            title={t.hint}
                            onClick={() => onTool(activeTool === t.kind ? null : t.kind)}
                        >
                            {t.label}
                        </button>
                    </li>
                ))}
            </ul>
            {activeTool ? (
                <p className="pl-fm-note" data-tool-hint={activeTool}>
                    {tools.find((t) => t.kind === activeTool)?.hint}
                </p>
            ) : null}

            <h4>Mark this record</h4>
            <ul className="pl-fm-tabs" data-verdict-picker>
                {VERDICTS.map((v) => (
                    <li key={v.key}>
                        <button
                            type="button"
                            className="pl-fm-tab"
                            data-verdict={v.key}
                            aria-pressed={verdict === v.key}
                            title={VERDICT_NOTE[v.key]}
                            onClick={() => onVerdict(verdict === v.key ? null : v.key)}
                        >
                            {v.label}
                        </button>
                    </li>
                ))}
            </ul>
            {verdict ? (
                <p className="pl-fm-note" data-verdict-note={verdict}>{VERDICT_NOTE[verdict]}</p>
            ) : null}
            <label className="pl-fm-sweep">
                <span className="pl-fm-kicker">why</span>
                <input
                    type="text"
                    className="pl-fm-input"
                    data-verdict-why
                    value={note}
                    placeholder="a bare verdict is a feeling — say which part, and against what"
                    onChange={(e) => onNote(e.target.value)}
                />
            </label>
            {declaration.carries_hypothesis && verdict === 'correct' ? (
                <p className="pl-fm-why" data-hypothesis-verdict-note>
                    {declaration.key} carries a hypothesis. Marking it correct is a judgement about
                    the READING, not a resolution of it — resolving a hypothesis produces a new
                    artifact of a resolved form, and this laboratory writes none.
                </p>
            ) : null}

            <h4>
                Proposals
                <span className="pl-fm-legendcount" data-proposal-count={proposals.length}>
                    {proposals.length} unsaved
                </span>
            </h4>
            {proposals.length ? (
                <>
                    <ul className="pl-fm-proposals">
                        {groups.map((g) => (
                            <li key={g.target} className="pl-fm-proposal" data-proposal-target={g.target}>
                                <span className="pl-fm-proposalhead">{g.target}</span>
                                {g.proposals.map((p, i) => (
                                    <span key={i} className="pl-fm-proposalnote"
                                        data-proposal-kind={p.kind}>
                                        {p.kind.replace(/_/g, ' ')} via {p.tool}
                                        {p.note ? ` — ${p.note}` : ''}
                                        {typeof p.value === 'string' ? ` — ${p.value}` : ''}
                                    </span>
                                ))}
                                {/* A disagreement about ONE thing, gathered. Chronology would
                                    bury the fact that five of these are about one instance. */}
                                {g.proposals.length > 1 ? (
                                    <span className="pl-fm-proposalnote" data-proposal-cluster>
                                        {g.proposals.length} proposals about this one thing
                                    </span>
                                ) : null}
                            </li>
                        ))}
                    </ul>
                    <button type="button" className="pl-fm-btn" data-action="clear-proposals"
                        onClick={onClear}>
                        Discard all
                    </button>
                </>
            ) : (
                <p className="pl-fm-note" data-no-proposals>
                    None yet. {focusLayer
                        ? `Pick a tool above to propose something about ${focusLayer}.`
                        : 'Focus a layer in the legend, then pick a tool.'}
                </p>
            )}
        </section>
    );
}
