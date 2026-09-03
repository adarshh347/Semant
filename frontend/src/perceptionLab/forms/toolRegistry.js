// PERCEPTUAL-FORMS-001E — the human tools, and the line they are not allowed to cross.
//
// THE BUILD SAYS: no save, no promotion, no real API. That is easy to honour by accident today
// and easy to break by accident in six weeks, so it is written down as a shape rather than as a
// habit. Every tool here declares `writes: 'nothing'` and produces a PROPOSAL — a plain object
// that goes into React state, is rendered as unsaved, and is discarded when the page reloads.
// There is no client on this surface at all: nothing in `forms/` imports `clients/`, and
// `toolRegistry.test.js` asserts that the module graph stays that way.
//
// THE TOOLS ARE THE CONTRACT'S OWN. `manual_tools` is a declared field on every form, drawn from
// the closed `manual_tool_kinds` set, and this file reads it rather than inventing a menu. So a
// tool offered on a form is a tool that form says it accepts — and a form that accepts
// `hypothesis_choose` gets an accept/reject control for exactly that reason, not because a
// designer thought hypotheses looked like they needed buttons.
//
// WHAT A PROPOSAL IS NOT. It is not a correction to the record. `extent.hard_mask` is `measured`,
// and a person dragging a vertex in this laboratory has not re-measured anything; they have said
// "this looks wrong, and here is what I think it should be". The two are different claims, the
// panel says which one is on screen, and the export in a later commit carries the proposals in a
// block of their own rather than merged into the payload.

import { form, MANUAL_TOOL_KINDS, REVIEW_VERDICTS } from '../contract/perceptionLabContract';

/**
 * What each contract tool kind does on this surface, and what it produces.
 *
 * `gesture` is what the stage listens for. `produces` is the proposal kind. `writes` is `nothing`
 * on every row, and the uniformity is the point — a row that ever needs a different value is a
 * row that has left this lane.
 */
export const TOOL_BEHAVIOUR = Object.freeze({
    mask_brush: {
        label: 'Brush',
        gesture: 'freehand',
        produces: 'proposed_mask',
        hint: 'draw an extent by hand where nothing found one',
    },
    polygon: {
        label: 'Polygon',
        gesture: 'polygon',
        produces: 'proposed_ring',
        hint: 'place vertices for a boundary',
    },
    foreground_background_points: {
        label: 'Points',
        gesture: 'points',
        produces: 'proposed_points',
        hint: 'foreground and background clicks — the polarity belongs to the whole refinement, '
            + 'not to each point, because the contract\'s point_list is pairs and nothing else',
    },
    refinement_box: {
        label: 'Box',
        gesture: 'box',
        produces: 'proposed_box',
        hint: 'drag a box to bound a refinement',
    },
    region_picker: {
        label: 'Select',
        gesture: 'select',
        produces: 'focus',
        hint: 'click a shape to focus it — the only tool here that changes nothing at all',
    },
    region_set_picker: {
        label: 'Select several',
        gesture: 'multiselect',
        produces: 'focus_set',
        hint: 'shift-click to gather several',
    },
    pair_picker: {
        label: 'Pick a pair',
        gesture: 'pair',
        produces: 'focus_pair',
        hint: 'choose the two ends a relation stands between',
    },
    endpoint_correct: {
        label: 'Correct an endpoint',
        gesture: 'select',
        produces: 'proposed_endpoint',
        hint: 'say that a relation names the wrong instance',
    },
    relation_reject: {
        label: 'Reject a relation',
        gesture: 'select',
        produces: 'proposed_rejection',
        hint: 'mark a relation as not standing — a rejection is a claim and is recorded as one',
    },
    ring_edit: {
        label: 'Edit the boundary',
        gesture: 'vertices',
        produces: 'proposed_ring',
        hint: 'drag a recorded vertex. The record is unchanged; the drag is a proposal beside it',
    },
    hole_mark: {
        label: 'Mark a void',
        gesture: 'polygon',
        produces: 'proposed_hole',
        hint: 'outline an enclosed void the record missed',
    },
    fragment_group: {
        label: 'Group',
        gesture: 'multiselect',
        produces: 'proposed_membership',
        hint: 'say these pieces belong together — a GROUPING, which is a reading and not a fusion',
    },
    fragment_split: {
        label: 'Split',
        gesture: 'select',
        produces: 'proposed_membership',
        hint: 'take a piece out of a group',
    },
    partition_paint: {
        label: 'Paint a part',
        gesture: 'freehand',
        produces: 'proposed_partition',
        hint: 'say which pixels are visible, inferred, or unknown',
    },
    hierarchy_link: {
        label: 'Link',
        gesture: 'pair',
        produces: 'proposed_parent',
        hint: 'propose that one extent nests inside another',
    },
    hypothesis_choose: {
        label: 'Accept / reject',
        gesture: 'select',
        produces: 'proposed_verdict',
        hint: 'accept or reject one reading. Accepting does not resolve it — resolving a '
            + 'hypothesis produces a new artifact of a resolved form, and nothing here writes one',
    },
});

/**
 * The verdicts a person may mark, taken from the contract's own closed set.
 *
 * The build asks for correct / partial / wrong / unclear. The contract's `review_verdicts` is the
 * authority on what those are called, so this reads it and fails loudly if the set has moved —
 * a laboratory offering a verdict the record cannot hold is offering a dead end.
 */
export const VERDICTS = Object.freeze(REVIEW_VERDICTS.map((v) => Object.freeze({
    key: v,
    label: v.replace(/_/g, ' '),
})));

export const VERDICT_NOTE = Object.freeze({
    correct: 'the form answered its question, and the answer is right',
    partial: 'right about some of it. Say which part in the note — a bare "partial" is a feeling',
    wrong: 'the answer is wrong. This is about the MEASUREMENT, not about the drawing',
    unclear: 'the record does not let you tell. This is the honest verdict when a field is behind '
        + 'a ref, an endpoint does not resolve, or a raster is too coarse to judge',
});

/**
 * The tools a form declares, resolved to behaviour.
 *
 * Reads `manual_tools` off the form registry. A tool kind in the contract with no behaviour here
 * throws rather than being silently dropped, because a form declaring a tool the lab does not
 * offer is exactly the gap this registry is meant to make visible.
 */
export function toolsFor(formKey) {
    return (form(formKey).manual_tools || []).map((kind) => {
        const behaviour = TOOL_BEHAVIOUR[kind];
        if (!behaviour) {
            throw new Error(`${formKey} declares the manual tool "${kind}" and this laboratory `
                + `offers no behaviour for it. The contract's kinds are `
                + `${MANUAL_TOOL_KINDS.join(', ')}`);
        }
        return Object.freeze({ kind, ...behaviour, writes: 'nothing' });
    });
}

/**
 * A proposal. The only thing any tool produces.
 *
 * Frozen, stamped, and carrying the form and the target it is about — a proposal that cannot say
 * what it is a proposal ABOUT is a note, and notes do not survive being read a week later.
 * `at` is passed in rather than read from a clock, because this whole directory is deterministic
 * and a screenshot taken twice must be the same screenshot.
 */
export function proposal({ tool, formKey, target, value, at = null, note = null }) {
    const behaviour = TOOL_BEHAVIOUR[tool];
    if (!behaviour) throw new Error(`"${tool}" is not a manual tool this laboratory offers`);
    return Object.freeze({
        kind: behaviour.produces,
        tool,
        form: formKey,
        target,
        value,
        note,
        at,
        // Said on the object, not only in the panel that renders it. A proposal that leaks into
        // an export or a log still says what it is.
        writes: 'nothing',
        status: 'unsaved — this laboratory has no client and writes to no record',
    });
}

/** Whether a proposal is a verdict rather than a geometry change. */
export const isVerdict = (p) => p?.kind === 'proposed_verdict';

/**
 * The proposals grouped by what they are about, for the panel and for the export.
 *
 * Deliberately keyed by target rather than flat: five proposals about one instance are a
 * disagreement about that instance, and a flat list buries that under chronology.
 */
export function groupProposals(proposals = []) {
    const byTarget = new Map();
    for (const p of proposals) {
        const key = typeof p.target === 'string' ? p.target : JSON.stringify(p.target);
        byTarget.set(key, [...(byTarget.get(key) || []), p]);
    }
    return [...byTarget.entries()].map(([target, list]) => ({
        target,
        proposals: list,
        verdicts: list.filter(isVerdict),
        geometry: list.filter((p) => !isVerdict(p)),
    }));
}
