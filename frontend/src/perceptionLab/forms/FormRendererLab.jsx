import React, { useCallback, useMemo, useRef, useState } from 'react';
import useContainerWidth from '../useContainerWidth';
import { FORM_GROUPS, viewsFor, viewFor, renderView } from './rendererRegistry';
import { SCENARIO_NOTE, payloadFor, scenariosFor, FIXTURE_SOURCE } from './fixtures/formFixtures';
import { fieldCells, sweepStops } from './formGeometry';
import { proposal, toolsFor } from './toolRegistry';
import FormSurface from './components/FormSurface';
import FormInspector, { LayerLineage } from './components/FormInspector';
import ToolTray from './components/ToolTray';
import { form } from '../contract/perceptionLabContract';
import './forms.css';

/**
 * PERCEPTUAL-FORMS-001E — the laboratory.
 *
 * Nineteen forms, forty-four views, five surfaces, and a set of controls that produce proposals
 * and nothing else. Lane H mounts it; this component takes no client, because there is nothing
 * for a client to do here.
 *
 * WHAT THE CONTROLS ARE FOR, in the order the build asks for them:
 *
 *   focus / select        the legend rows, which are also the keyboard path.
 *   toggle form views     the view tabs. Every view a form declares, none it does not.
 *   threshold sweep       a range input, shown only on views that declare `sweeps`. The number
 *                         is on screen, always, and the layer is stamped `binarized` with it.
 *   accept / reject       the hypothesis picker plus the verdict tray.
 *   correct membership    the fragment tools — group and split, which the contract declares.
 *   inspect lineage       the lineage panel, which prints the cited revision separately from the
 *                         drawn one whenever they differ.
 *   compare revisions     the scenario compare control, which feeds a second payload to any view
 *                         whose `needs` includes a comparison.
 *   mark correct/…        the four verdicts, read off the contract's own closed set.
 *
 * IT RESPONDS TO ITS CONTAINER, NOT THE WINDOW. Lane H may mount this inside a pane, and a layout
 * keyed to the viewport would be correct exactly once — the technique is inherited from the
 * Perception Lab rather than rediscovered.
 *
 * `now` IS A PROP. Proposals carry a timestamp and this directory is deterministic: a screenshot
 * taken twice must be the same screenshot, so the clock is injected and defaults to null.
 */

const FIRST_FORM = 'extent.hard_mask';

export default function FormRendererLab({
    initialForm = FIRST_FORM, initialView = null, initialScenario = 'contract', now = null,
    onProposal = null,
}) {
    const rootRef = useRef(null);
    const { band } = useContainerWidth(rootRef);

    const [formKey, setFormKey] = useState(initialForm);
    const [scenario, setScenario] = useState(initialScenario);
    const [viewKey, setViewKey] = useState(initialView);
    const [focusId, setFocusId] = useState(null);
    const [hidden, setHidden] = useState(() => new Set());
    const [threshold, setThreshold] = useState(null);
    const [hypothesisId, setHypothesisId] = useState(null);
    const [comparison, setComparison] = useState(null);
    const [membership, setMembership] = useState({});
    const [activeTool, setActiveTool] = useState(null);
    const [verdict, setVerdict] = useState(null);
    const [note, setNote] = useState('');
    const [proposals, setProposals] = useState([]);

    const views = viewsFor(formKey);
    const view = viewFor(formKey, viewKey);
    const payload = payloadFor(formKey, scenario);
    const declaration = form(formKey);

    /** Everything a view's `build` is allowed to see. Nothing here reaches a network. */
    const ctx = useMemo(() => ({
        focusId: null,          // focus is a rendering state, not a filter — see below
        hypothesisId,
        threshold,
        membership,
        scenarioLabel: `${formKey} · ${scenario}`,
        comparison: comparison
            ? { label: `${formKey} · ${comparison}`, payload: payloadFor(formKey, comparison) }
            : null,
        hypothesisPayload: formKey === 'extent.fragment_set'
            ? payloadFor('extent.fused_hypothesis') : null,
    }), [formKey, scenario, hypothesisId, threshold, membership, comparison]);

    const out = useMemo(
        () => renderView(formKey, view?.key, payload, ctx), [formKey, view?.key, payload, ctx]);

    /** The hypotheses this payload holds, whatever the form calls them. */
    const alternatives = useMemo(() => {
        if (Array.isArray(payload?.alternatives)) {
            return payload.alternatives.map((a) => ({ id: a.alternative_id, weight: a.weight }));
        }
        if (Array.isArray(payload?.hypotheses)) {
            return payload.hypotheses.map((h) => ({ id: h.hypothesis_id, weight: h.weight }));
        }
        return [];
    }, [payload]);

    /** The sweep, where the view declares one. Stops come from the field's declared range. */
    const sweep = useMemo(() => {
        if (!view?.sweeps) return null;
        const f = fieldCells(payload?.field);
        if (!f.available) return { available: false, why: f.why };
        return {
            available: true,
            lo: f.range.lo,
            hi: f.range.hi,
            recorded: payload.threshold_would_be ?? null,
            stops: sweepStops(f, 5),
        };
    }, [view?.sweeps, payload]);

    const pick = useCallback((key) => {
        setFormKey(key);
        setScenario('contract');
        setViewKey(null);
        setFocusId(null);
        setHidden(new Set());
        setThreshold(null);
        setHypothesisId(null);
        setComparison(null);
        setMembership({});
        setActiveTool(null);
        // The verdict and the proposals are NOT cleared. A person who marked one form wrong and
        // moved to another has not withdrawn the mark, and silently dropping it would lose work
        // that this surface has no other way of keeping.
    }, []);

    const toggle = useCallback((id) => setHidden((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id); else next.add(id);
        return next;
    }), []);

    const propose = useCallback((spec) => {
        const p = proposal({ ...spec, formKey, at: now });
        setProposals((prev) => [...prev, p]);
        onProposal?.(p);
    }, [formKey, now, onProposal]);

    const tools = toolsFor(formKey);
    const canGroup = tools.some((t) => t.kind === 'fragment_group');

    return (
        <div className="pl-fm" ref={rootRef} data-w={band} data-form={formKey}
            data-view={view?.key} data-scenario={scenario}>
            <header className="pl-fm-bar">
                <span className="pl-fm-kicker">perceptual form renderers</span>
                <h1 className="pl-fm-title">{declaration.label}</h1>
                <p className="pl-fm-question" data-form-question>{declaration.question}</p>
                <span className="pl-fm-state" data-state={declaration.state}>
                    {declaration.state}
                </span>
            </header>

            <div className="pl-fm-body">
                <div className="pl-fm-rail">
                    <section className="pl-fm-panel" aria-label="Forms">
                        <h3>Forms</h3>
                        {FORM_GROUPS.map((group) => (
                            <div key={group.organ} data-organ-group={group.organ}>
                                <p className="pl-fm-kicker">{group.organ}</p>
                                <ul className="pl-fm-formlist">
                                    {group.forms.map((f) => (
                                        <li key={f.key}>
                                            <button
                                                type="button"
                                                className="pl-fm-formbtn"
                                                data-form-option={f.key}
                                                aria-pressed={f.key === formKey}
                                                onClick={() => pick(f.key)}
                                            >
                                                <span className="pl-fm-formkey">{f.label}</span>
                                                <span className="pl-fm-formq">{f.question}</span>
                                                <span className="pl-fm-state" data-state={f.state}>
                                                    {f.state} · {f.views} view
                                                    {f.views === 1 ? '' : 's'}
                                                </span>
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        ))}
                    </section>

                    <section className="pl-fm-panel" aria-label="Record state">
                        <h3>Record</h3>
                        <ul className="pl-fm-tabs" data-scenario-picker>
                            {scenariosFor(formKey).map((key) => (
                                <li key={key}>
                                    <button type="button" className="pl-fm-tab"
                                        data-scenario-option={key}
                                        aria-pressed={key === scenario}
                                        title={SCENARIO_NOTE[key]}
                                        onClick={() => { setScenario(key); setFocusId(null); }}>
                                        {key}
                                    </button>
                                </li>
                            ))}
                        </ul>
                        <p className="pl-fm-note" data-scenario-note={scenario}>
                            {SCENARIO_NOTE[scenario]}
                        </p>

                        {/* COMPARE REVISIONS. A second record of the same form, fed to any view
                            whose `needs` includes a comparison. Two panes, never superimposed. */}
                        <h4>Compare with</h4>
                        <ul className="pl-fm-tabs" data-compare-picker>
                            <li>
                                <button type="button" className="pl-fm-tab" data-compare-option="none"
                                    aria-pressed={!comparison} onClick={() => setComparison(null)}>
                                    nothing
                                </button>
                            </li>
                            {scenariosFor(formKey).filter((k) => k !== scenario).map((key) => (
                                <li key={key}>
                                    <button type="button" className="pl-fm-tab"
                                        data-compare-option={key}
                                        aria-pressed={comparison === key}
                                        onClick={() => setComparison(key)}>
                                        {key}
                                    </button>
                                </li>
                            ))}
                        </ul>
                        {comparison ? (
                            <p className="pl-fm-note" data-compare-note>
                                Compared by instance id, and by nothing else. Two members with the
                                same id and different geometry count as the same member here.
                            </p>
                        ) : null}
                    </section>
                </div>

                <div className="pl-fm-main">
                    <section className="pl-fm-panel" aria-label="Views">
                        <h3>Views</h3>
                        <ul className="pl-fm-tabs" role="tablist" data-view-picker={views.length}>
                            {views.map((v) => (
                                <li key={v.key} role="presentation">
                                    <button
                                        type="button"
                                        role="tab"
                                        className="pl-fm-tab"
                                        data-view-option={v.key}
                                        data-view-surface={v.surface}
                                        data-view-alternatives={v.alternatives ?? 'none'}
                                        aria-selected={v.key === view?.key}
                                        title={v.hint}
                                        onClick={() => { setViewKey(v.key); setFocusId(null); }}
                                    >
                                        {v.label}
                                    </button>
                                </li>
                            ))}
                        </ul>
                        <p className="pl-fm-note" data-view-hint={view?.key}>{view?.hint}</p>
                        {view?.needs?.includes('comparison') && !comparison ? (
                            <p className="pl-fm-why" data-needs-comparison>
                                This view compares two records and one is selected. Pick a second
                                in “Compare with”.
                            </p>
                        ) : null}
                    </section>

                    {/* THE THRESHOLD SWEEP. Shown only where the view declares one, and the
                        number is on screen whether it came from the record or from this slider —
                        a wash and a mask differ by exactly this number. */}
                    {view?.sweeps ? (
                        <section className="pl-fm-panel" aria-label="Threshold" data-sweep>
                            <h3>Threshold</h3>
                            {sweep?.available ? (
                                <>
                                    <label className="pl-fm-sweep">
                                        <span className="pl-fm-kicker">
                                            cut the field at
                                        </span>
                                        <input
                                            type="range"
                                            data-threshold-input
                                            min={sweep.lo}
                                            max={sweep.hi}
                                            step={(sweep.hi - sweep.lo) / 100}
                                            value={threshold ?? sweep.recorded ?? sweep.lo}
                                            onChange={(e) => setThreshold(Number(e.target.value))}
                                        />
                                        <span className="pl-fm-sweepvalue" data-threshold-value>
                                            {threshold ?? sweep.recorded ?? sweep.lo}
                                            {threshold === null
                                                ? ' — the number the producer recorded'
                                                : ' — chosen here, applied here only'}
                                        </span>
                                    </label>
                                    <ul className="pl-fm-tabs" data-sweep-stops={sweep.stops.length}>
                                        {sweep.recorded !== null ? (
                                            <li>
                                                <button type="button" className="pl-fm-tab"
                                                    data-sweep-stop="recorded"
                                                    aria-pressed={threshold === null}
                                                    onClick={() => setThreshold(null)}>
                                                    back to {sweep.recorded}
                                                </button>
                                            </li>
                                        ) : null}
                                        {sweep.stops.map((s) => (
                                            <li key={s}>
                                                <button type="button" className="pl-fm-tab"
                                                    data-sweep-stop={s}
                                                    aria-pressed={threshold === s}
                                                    onClick={() => setThreshold(s)}>
                                                    {s}
                                                </button>
                                            </li>
                                        ))}
                                    </ul>
                                </>
                            ) : (
                                <p className="pl-fm-why" data-sweep-unavailable>{sweep?.why}</p>
                            )}
                        </section>
                    ) : null}

                    {/* THE HYPOTHESIS PICKER. One reading at a time is the default for every form
                        that holds rivals; this is where a person chooses which. */}
                    {alternatives.length ? (
                        <section className="pl-fm-panel" aria-label="Readings" data-alternatives>
                            <h3>Readings</h3>
                            <ul className="pl-fm-tabs" data-hypothesis-picker={alternatives.length}>
                                {alternatives.map((a) => (
                                    <li key={a.id}>
                                        <button type="button" className="pl-fm-tab"
                                            data-hypothesis-option={a.id}
                                            aria-pressed={(hypothesisId ?? alternatives[0].id) === a.id}
                                            onClick={() => setHypothesisId(a.id)}>
                                            {a.id} · {a.weight}
                                        </button>
                                    </li>
                                ))}
                            </ul>
                            <div className="pl-fm-tabs">
                                <button type="button" className="pl-fm-btn"
                                    data-action="accept-hypothesis"
                                    onClick={() => propose({
                                        tool: 'hypothesis_choose',
                                        target: hypothesisId ?? alternatives[0].id,
                                        value: 'accepted',
                                        note: 'accepted on this page. Resolving a hypothesis '
                                            + 'produces a new artifact of a resolved form, and '
                                            + 'this laboratory writes none',
                                    })}>
                                    Accept this reading
                                </button>
                                <button type="button" className="pl-fm-btn"
                                    data-action="reject-hypothesis"
                                    onClick={() => propose({
                                        tool: 'hypothesis_choose',
                                        target: hypothesisId ?? alternatives[0].id,
                                        value: 'rejected',
                                        note: 'rejected on this page',
                                    })}>
                                    Reject it
                                </button>
                            </div>
                            <p className="pl-fm-note">
                                Accepting is a judgement, not a resolution. The record still holds
                                every reading, and this laboratory writes to no record.
                            </p>
                        </section>
                    ) : null}

                    {/* CORRECT FRAGMENT MEMBERSHIP. Offered only where the form declares the
                        tool, which is `extent.fragment_set` and nothing else. */}
                    {canGroup ? (
                        <section className="pl-fm-panel" aria-label="Membership" data-membership>
                            <h3>Membership</h3>
                            <p className="pl-fm-note">
                                Say which pieces you think belong together. A GROUPING is a
                                reading; the pieces stay measured, and the record is unchanged —
                                `unity_asserted` is{' '}
                                <code>{String(payload?.unity_asserted)}</code> and stays that way.
                            </p>
                            <ul className="pl-fm-formlist" data-membership-list>
                                {(payload?.fragments || []).map((frag) => (
                                    <li key={frag.fragment_id}>
                                        <button
                                            type="button"
                                            className="pl-fm-formbtn"
                                            data-membership-option={frag.fragment_id}
                                            aria-pressed={!!membership[frag.fragment_id]}
                                            onClick={() => {
                                                const grouped = membership[frag.fragment_id];
                                                setMembership((prev) => {
                                                    const next = { ...prev };
                                                    if (grouped) delete next[frag.fragment_id];
                                                    else next[frag.fragment_id] = 'group A';
                                                    return next;
                                                });
                                                propose({
                                                    tool: grouped ? 'fragment_split' : 'fragment_group',
                                                    target: frag.fragment_id,
                                                    value: grouped ? null : 'group A',
                                                    note: grouped
                                                        ? 'taken out of group A'
                                                        : 'proposed into group A',
                                                });
                                            }}
                                        >
                                            <span className="pl-fm-formkey">{frag.fragment_id}</span>
                                            <span className="pl-fm-formq">
                                                {membership[frag.fragment_id]
                                                    ? `proposed into ${membership[frag.fragment_id]}`
                                                    : 'not grouped'}
                                            </span>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    ) : null}

                    <FormSurface
                        view={out.view}
                        layers={out.layers}
                        sides={out.sides}
                        items={out.items}
                        natural={{ w: FIXTURE_SOURCE.natural_width, h: FIXTURE_SOURCE.natural_height }}
                        focusId={focusId}
                        onFocus={setFocusId}
                        hidden={hidden}
                        onToggle={toggle}
                        error={out.error}
                    />
                    <p className="pl-fm-note" data-ground-note>{FIXTURE_SOURCE.note}</p>
                </div>

                <div className="pl-fm-side">
                    <FormInspector
                        formKey={formKey}
                        payload={payload}
                        scenario={scenario}
                        scenarioNote={SCENARIO_NOTE[scenario]}
                    />
                    <LayerLineage layer={out.layers.find((l) => l.layer_id === focusId) || null} />
                    <ToolTray
                        formKey={formKey}
                        activeTool={activeTool}
                        onTool={setActiveTool}
                        focusLayer={focusId}
                        verdict={verdict}
                        onVerdict={(v) => {
                            setVerdict(v);
                            if (v) {
                                propose({
                                    tool: 'hypothesis_choose',
                                    target: `${formKey} · ${scenario}`,
                                    value: v,
                                    note: note || null,
                                });
                            }
                        }}
                        note={note}
                        onNote={setNote}
                        proposals={proposals}
                        onClear={() => setProposals([])}
                    />
                </div>
            </div>
        </div>
    );
}
