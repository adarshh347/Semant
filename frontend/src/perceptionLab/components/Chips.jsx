import React from 'react';
import {
    BASIS, CAPABILITY, EXECUTION, EPISTEMIC, LIFECYCLE, OUTCOME, PLANNER, SCOPE, STAGE, VERDICT,
    ceilingNote, describe,
} from '../display';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — one chip per axis, and no chip that serves two.
 *
 * Each of these renders a `data-` attribute the stylesheet keys off, and a `title` carrying the
 * axis's own sentence. The sentences are the point: `kept` and `correct` look different AND say
 * different things, so a person who hovers either one is told which axis they are on.
 *
 * `describe()` throws on an unknown value rather than rendering it raw, which is deliberate. A
 * status the vocabulary has never heard of, rendered as itself, is a status a person will read as
 * whatever it happens to look like.
 */

const Chip = ({ cls, attr, value, table, prefix = null, suffix = null, extraTitle = null }) => {
    const { label, hint } = describe(table, value);
    return (
        <span className={`pl-chip ${cls}`} {...{ [attr]: value }}
            title={extraTitle ? `${hint} — ${extraTitle}` : hint}>
            {prefix}{label}{suffix}
        </span>
    );
};

/** LIVE / REPLAY / FIXTURE. Comes from the RUN, never from the client and never from a URL. */
export const ExecutionChip = ({ identity }) => (
    <Chip cls="pl-exec" attr="data-id" value={identity} table={EXECUTION} />
);

export const OutcomeChip = ({ outcome }) => (
    <Chip cls="pl-outcome-chip" attr="data-outcome" value={outcome} table={OUTCOME} />
);

/** The block form: the outcome as the header of whatever it is the outcome of. */
export const OutcomeBanner = ({ outcome, children }) => {
    const { label, hint } = describe(OUTCOME, outcome);
    return (
        <div className="pl-outcome" data-outcome={outcome} role="status">
            <span className="pl-outcome-name">{label}</span>
            <span className="pl-outcome-hint">{hint}</span>
            {children}
        </div>
    );
};

export const EpistemicChip = ({ status }) => (
    <Chip cls="pl-epi" attr="data-status" value={status} table={EPISTEMIC} />
);

export const BasisChip = ({ basis }) => (
    <Chip cls="pl-basis" attr="data-basis" value={basis} table={BASIS}
        extraTitle={ceilingNote(basis)} />
);

export const LifecycleChip = ({ status }) => (
    <Chip cls="pl-life" attr="data-status" value={status} table={LIFECYCLE} />
);

export const VerdictChip = ({ verdict }) => (
    <Chip cls="pl-verdict" attr="data-verdict" value={verdict} table={VERDICT} />
);

export const PlannerChip = ({ planner, fellBackFrom = null }) => {
    const { label, hint } = describe(PLANNER, planner);
    return (
        <span className="pl-chip pl-planner" data-planner={planner}
            title={fellBackFrom
                ? `${hint}. The ${fellBackFrom} planner was not reachable, so this is a fallback `
                    + 'and is not wearing its name.'
                : hint}>
            {label}{fellBackFrom ? ` · fell back from ${fellBackFrom}` : ''}
        </span>
    );
};

export const CapabilityChip = ({ adapter, state }) => (
    <Chip cls="pl-cap" attr="data-state" value={state} table={CAPABILITY}
        prefix={<span className="pl-cap-name">{adapter}&nbsp;</span>} />
);

export const ScopeChip = ({ scope }) => (
    <Chip cls="pl-scope" attr="data-scope" value={scope} table={SCOPE} />
);

export const StageChip = ({ state }) => (
    <Chip cls="pl-stage-chip" attr="data-stage" value={state} table={STAGE} />
);

/**
 * Anything this page computed rather than received.
 *
 * Used on every contact band, intersection, endpoint line and wash. The laboratory can draw a
 * measurement without the drawing becoming one, but only if the drawing says so where it is.
 */
export const DerivedChip = ({ why = null }) => (
    <span className="pl-chip pl-derived" data-derived="true"
        title={why || 'computed in this browser to show where the measurement lives. It is not '
            + 'the measurement.'}>
        derived projection
    </span>
);

/** A refusal, rendered as the result it is. */
export const Refusal = ({ refusal }) => (
    <div className="pl-refusal" role="note">
        <span className="pl-refusal-code">{refusal.code}</span>
        <span>{refusal.message}</span>
        {refusal.missing?.length ? (
            <span className="pl-refusal-remedy">missing: {refusal.missing.join(', ')}</span>
        ) : null}
        {refusal.remedy ? (
            <span className="pl-refusal-remedy">what to do: {refusal.remedy}</span>
        ) : null}
    </div>
);

/**
 * A deliberate nothing.
 *
 * Every data view in this lab has one, because rendering nothing reads as a bug and a person
 * cannot tell a bug from a finding.
 */
export const EmptyState = ({ title, hint, children = null }) => (
    <div className="pl-empty">
        <span className="pl-empty-title">{title}</span>
        <span className="pl-empty-hint">{hint}</span>
        {children}
    </div>
);
