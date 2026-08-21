// PERCEPTUAL-FORMS-001E — the laboratory, driven the way a person drives it.
//
// Nothing is constructed by hand here. Every test clicks: pick a form, pick a view, drag a
// threshold, choose a reading, group a fragment, mark a verdict. What is asserted is not that a
// component rendered a prop, but that the SURFACE keeps the declaration visible while a person
// moves around inside it — which is the only claim this lane actually makes.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';

import FormRendererLab from './FormRendererLab';
import { PERCEPTUAL_FORMS, form } from '../contract/perceptionLabContract';
import { viewsFor } from './rendererRegistry';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => { await act(async () => { await Promise.resolve(); }); };

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
});

const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const text = () => container.textContent;
const click = async (el) => {
    if (!el) throw new Error('nothing to click');
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};
const change = async (el, value) => {
    await act(async () => {
        const setter = Object.getOwnPropertyDescriptor(
            el instanceof HTMLInputElement ? HTMLInputElement.prototype : el.constructor.prototype,
            'value').set;
        setter.call(el, String(value));
        el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await settle();
};

const open = async (props = {}) => {
    await mount(<FormRendererLab now="2026-08-22T00:00:00Z" {...props} />);
    await settle();
};

describe('the form picker', () => {
    it('lists all nineteen forms, grouped by organ, with their state', async () => {
        await open();
        const options = all('[data-form-option]');
        expect(options).toHaveLength(19);
        expect(all('[data-organ-group]').map((g) => g.getAttribute('data-organ-group')))
            .toEqual(['extent', 'topology']);
        // Sixteen of the nineteen have no operation that produces them. A lab that showed them
        // without saying so would imply a pipeline that does not exist.
        expect(all('[data-form-option] .pl-fm-state[data-state="deferred"]')).toHaveLength(7);
        expect(all('[data-form-option] .pl-fm-state[data-state="experimental"]')).toHaveLength(9);
    });

    it('shows each form\'s question, which is what the form is for', async () => {
        await open();
        expect(text()).toContain('Which pixels are it?');
        expect(q('[data-form-question]').textContent).toBe(form('extent.hard_mask').question);
    });

    it.each(PERCEPTUAL_FORMS)('opens %s and renders its default view', async (key) => {
        await open();
        await click(q(`[data-form-option="${key}"]`));
        expect(q('.pl-fm').getAttribute('data-form')).toBe(key);
        expect(q('[data-form-question]').textContent).toBe(form(key).question);
        // Something is always on the page — a drawing, or a layer that says why there is none.
        expect(all('.pl-fm-legendrow').length).toBeGreaterThan(0);
    });

    it('offers exactly the views the registry declares, and no others', async () => {
        await open();
        for (const key of ['extent.hard_mask', 'topology.adjacency_graph', 'extent.hierarchy']) {
            await click(q(`[data-form-option="${key}"]`));
            expect(all('[data-view-option]').map((b) => b.getAttribute('data-view-option')))
                .toEqual(viewsFor(key).map((v) => v.key));
        }
    });

    it('keeps a verdict when the form changes', async () => {
        // A person who marked one form wrong and moved on has not withdrawn the mark.
        await open();
        await click(q('[data-verdict="wrong"]'));
        expect(q('[data-proposal-count]').getAttribute('data-proposal-count')).toBe('1');
        await click(q('[data-form-option="extent.hierarchy"]'));
        expect(q('[data-proposal-count]').getAttribute('data-proposal-count')).toBe('1');
    });
});

describe('toggling views', () => {
    it('switches surface with the view', async () => {
        await open();
        await click(q('[data-view-option="contact_sheet"]'));
        expect(q('.pl-fm-surface').getAttribute('data-surface')).toBe('sheet');
        await click(q('[data-view-option="fill"]'));
        expect(q('.pl-fm-surface').getAttribute('data-surface')).toBe('stage');
    });

    it('says what a view is for before it is chosen', async () => {
        await open();
        expect(q('[data-view-option="outline"]').getAttribute('title'))
            .toMatch(/traced in this browser/);
    });

    it('says when a view needs a second record and none is chosen', async () => {
        await open();
        await click(q('[data-view-option="before_after"]'));
        expect(q('[data-needs-comparison]')).toBeTruthy();
        expect(q('[data-needs-comparison]').textContent).toMatch(/Pick a second/);
    });
});

describe('the record state picker', () => {
    it('offers contract and empty everywhere, and explains each', async () => {
        await open();
        const options = all('[data-scenario-option]').map((b) => b.getAttribute('data-scenario-option'));
        expect(options).toContain('contract');
        expect(options).toContain('empty');
        await click(q('[data-scenario-option="empty"]'));
        expect(q('[data-scenario-note="empty"]').textContent)
            .toMatch(/examination counter kept/);
    });

    it('renders the empty record as a measurement, not as a blank page', async () => {
        await open();
        await click(q('[data-form-option="topology.pair_relation"]'));
        await click(q('[data-scenario-option="empty"]'));
        expect(q('[data-why-absent]').textContent)
            .toMatch(/pairs were compared and none stood in any of the asked-for relations/);
        expect(q('[data-why-absent]').textContent).toMatch(/not a refusal/);
        // The counter survives, which is the whole distinction.
        expect(q('[data-inspect-value="pairs_examined"]').textContent).toContain('3');
    });

    it('survives the dense record without dropping members', async () => {
        await open();
        await click(q('[data-scenario-option="dense"]'));
        expect(all('.pl-fm-legendrow')).toHaveLength(18);
        expect(q('[data-legend-count]').getAttribute('data-legend-count')).toBe('18');
    });
});

describe('the threshold sweep', () => {
    const openSweep = async () => {
        await open();
        await click(q('[data-form-option="extent.soft_field"]'));
        await click(q('[data-view-option="threshold"]'));
    };

    it('appears only on a view that declares one', async () => {
        await open();
        expect(q('[data-sweep]')).toBeNull();
        await openSweep();
        expect(q('[data-sweep]')).toBeTruthy();
    });

    it('starts at the number the producer recorded, and says so', async () => {
        await openSweep();
        expect(q('[data-threshold-value]').textContent)
            .toMatch(/0\.5 — the number the producer recorded/);
        expect(q('[data-decl-value="threshold"]').textContent)
            .toMatch(/threshold_would_be, recorded by the producer/);
    });

    it('moves, and the number on screen moves with it', async () => {
        await openSweep();
        await change(q('[data-threshold-input]'), 0.8);
        expect(q('[data-threshold-value]').textContent).toMatch(/0\.8 — chosen here/);
        expect(q('[data-decl-value="threshold"]').getAttribute('data-threshold')).toBe('0.8');
        expect(q('[data-decl-value="threshold"]').textContent)
            .toMatch(/chosen on this page, and applied here only/);
    });

    it('offers stops inside the field\'s declared range, and a way back to the record', async () => {
        await openSweep();
        expect(all('[data-sweep-stop]').map((b) => b.getAttribute('data-sweep-stop')))
            .toEqual(['recorded', '0.167', '0.333', '0.5', '0.667', '0.833']);
        await click(q('[data-sweep-stop="0.833"]'));
        expect(q('[data-decl-value="threshold"]').getAttribute('data-threshold')).toBe('0.833');
        await click(q('[data-sweep-stop="recorded"]'));
        expect(q('[data-decl-value="threshold"]').getAttribute('data-threshold')).toBe('0.5');
    });

    it('refuses to sweep a field it cannot read', async () => {
        await openSweep();
        await click(q('[data-scenario-option="withheld"]'));
        expect(q('[data-sweep-unavailable]').textContent).toMatch(/held behind data_ref/);
        expect(q('[data-threshold-input]')).toBeNull();
    });
});

describe('accepting and rejecting a reading', () => {
    const openHypotheses = async () => {
        await open();
        await click(q('[data-form-option="extent.hypothesis_set"]'));
    };

    it('shows one reading at a time by default', async () => {
        await openHypotheses();
        expect(q('[data-view-option="tabs"]').getAttribute('aria-selected')).toBe('true');
        expect(q('[data-view-option="tabs"]').getAttribute('data-view-alternatives'))
            .toBe('one_at_a_time');
    });

    it('lists every reading with its weight', async () => {
        await openHypotheses();
        const options = all('[data-hypothesis-option]');
        expect(options).toHaveLength(3);
        expect(options[0].textContent).toBe('alt_one_object · 0.62');
    });

    it('switches which reading is drawn', async () => {
        await openHypotheses();
        await click(q('[data-hypothesis-option="alt_two_objects"]'));
        expect(all('[data-decl-value="hypothesis"]').map((d) => d.textContent))
            .toEqual(['alt_two_objects', 'alt_two_objects']);
    });

    it('records an acceptance as a proposal that writes nothing', async () => {
        await openHypotheses();
        await click(q('[data-action="accept-hypothesis"]'));
        expect(q('[data-proposal-count]').getAttribute('data-proposal-count')).toBe('1');
        expect(q('[data-proposal-target="alt_one_object"]')).toBeTruthy();
        expect(text()).toMatch(/Resolving a hypothesis \n?\s*produces a new artifact/);
    });

    it('records a rejection distinctly from an acceptance', async () => {
        await openHypotheses();
        await click(q('[data-action="accept-hypothesis"]'));
        await click(q('[data-hypothesis-option="alt_two_objects"]'));
        await click(q('[data-action="reject-hypothesis"]'));
        expect(all('[data-proposal-target]')).toHaveLength(2);
        expect(text()).toContain('accepted on this page');
        expect(text()).toContain('rejected on this page');
    });

    it('says accepting is not resolving, when the form carries a hypothesis', async () => {
        await openHypotheses();
        await click(q('[data-verdict="correct"]'));
        expect(q('[data-hypothesis-verdict-note]').textContent)
            .toMatch(/judgement about\s+the READING, not a resolution of it/);
    });
});

describe('correcting fragment membership', () => {
    const openFragments = async () => {
        await open();
        await click(q('[data-form-option="extent.fragment_set"]'));
    };

    it('is offered because the form declares the tool, and only there', async () => {
        await open();
        expect(q('[data-membership]')).toBeNull();
        await openFragments();
        expect(q('[data-membership]')).toBeTruthy();
        expect(all('[data-membership-option]')).toHaveLength(3);
    });

    it('proposes a grouping and says the record is unchanged', async () => {
        await openFragments();
        await click(q('[data-membership-option="frag_2"]'));
        expect(q('[data-membership-option="frag_2"]').getAttribute('aria-pressed')).toBe('true');
        expect(q('[data-proposal-target="frag_2"]')).toBeTruthy();
        expect(q('[data-proposal-kind="proposed_membership"]').textContent)
            .toMatch(/proposed membership via fragment_group/);
        // `unity_asserted` stays false — a grouping is a reading, not a fusion.
        expect(text()).toMatch(/unity_asserted.*is\s*false/s);
    });

    it('shows the proposal on the layer itself, marked as not in the record', async () => {
        await openFragments();
        await click(q('[data-membership-option="frag_2"]'));
        const row = q('.pl-fm-legendrow[data-layer="fragment_cluster:frag_2"]');
        expect(row.textContent).toContain('→ group A');
        expect(row.textContent).toMatch(/not in the record and nothing here writes it there/);
    });

    it('splits a fragment back out, and records that as its own proposal', async () => {
        await openFragments();
        await click(q('[data-membership-option="frag_2"]'));
        await click(q('[data-membership-option="frag_2"]'));
        expect(q('[data-membership-option="frag_2"]').getAttribute('aria-pressed')).toBe('false');
        expect(q('[data-proposal-cluster]').textContent).toMatch(/2 proposals about this one thing/);
        expect(text()).toContain('taken out of group A');
    });
});

describe('lineage', () => {
    it('is empty until a layer is focused, and says how to fill it', async () => {
        await open();
        expect(q('[data-lineage]')).toBeNull();
        expect(text()).toMatch(/Select a layer in the legend/);
    });

    it('names the artifact, the instance and the raster a layer was measured on', async () => {
        await open();
        await click(q('[data-focus-layer="mask_fill:inst_1"]'));
        expect(q('[data-lineage]').getAttribute('data-lineage')).toBe('mask_fill:inst_1');
        expect(q('[data-inspect-value="artifact"]').textContent).toBe('art_extent_1');
        expect(q('[data-inspect-value="instance"]').textContent).toBe('inst_1');
        expect(q('[data-inspect-value="raster"]').textContent)
            .toMatch(/8×8.*drawn crisply and was not measured crisply/);
    });

    it('flags a revision gap, which is the way this goes wrong quietly', async () => {
        // A relation measured at rev 0 and drawn against rev 1 looks perfectly fine and describes
        // geometry that is no longer there.
        await open();
        await click(q('[data-form-option="topology.transition"]'));
        const stale = all('[data-focus-layer]')
            .find((b) => b.textContent.includes('@rev 1'));
        expect(stale).toBeTruthy();
        await click(stale);
        expect(q('[data-revision-gap]').textContent)
            .toMatch(/not the geometry this claim was\s+measured against/);
    });

    it('says a canonical Region is out of this laboratory\'s reach', async () => {
        await open();
        await click(q('[data-form-option="extent.hierarchy"]'));
        await click(q('[data-view-option="nested_focus"]'));
        expect(text()).toMatch(/reg_7 is a canonical Region/);
        expect(text()).toMatch(/fixture-only and does not reach into Semant/);
    });
});

describe('comparing records', () => {
    it('feeds a second record into a comparison view, in its own pane', async () => {
        await open();
        await click(q('[data-compare-option="dense"]'));
        await click(q('[data-view-option="before_after"]'));
        const panes = all('[data-pane]');
        expect(panes).toHaveLength(2);
        expect(q('[data-pane-label="A"]').textContent).toBe('extent.hard_mask · contract');
        expect(q('[data-pane-label="B"]').textContent).toBe('extent.hard_mask · dense');
    });

    it('computes the difference by instance id, and says that is all it did', async () => {
        await open();
        await click(q('[data-compare-option="empty"]'));
        await click(q('[data-view-option="difference"]'));
        expect(q('[data-row-value="only in A"]').textContent).toBe('inst_1, inst_2');
        expect(q('[data-row-value="only in B"]').textContent).toBe('nothing');
        expect(text()).toMatch(/set difference and not a geometric one/);
    });
});

describe('the record inspector', () => {
    it('states what the form may claim, and what caps it', async () => {
        await open();
        expect(q('[data-inspect-value="ceiling"]').textContent)
            .toMatch(/measured.*from mask, box, manual, declared/s);
        expect(q('[data-inspect-value="state"]').textContent).toMatch(/produced by extent\.find_all/);
    });

    it('says plainly when nothing produces a form yet', async () => {
        await open();
        await click(q('[data-form-option="extent.soft_field"]'));
        expect(q('[data-produced-by]').getAttribute('data-produced-by')).toBe('0');
        expect(q('[data-inspect-value="state"]').textContent)
            .toMatch(/no operation produces this form yet/);
    });

    it('says what a hypothesis-carrying form may never become', async () => {
        await open();
        await click(q('[data-form-option="extent.hypothesis_set"]'));
        expect(q('[data-inspect-value="hypothesis"]').textContent)
            .toMatch(/may not be kept or promoted/);
    });

    it('puts the fixture set\'s limits on screen rather than in a readme', async () => {
        await open();
        expect(q('[data-resolvable]').textContent)
            .toMatch(/art_extent_1#inst_1, art_extent_1#inst_2/);
        expect(q('[data-resolvable]').textContent)
            .toMatch(/would draw a shape nobody measured/);
    });

    it('says what an empty record would have meant, before it is empty', async () => {
        await open();
        expect(q('[data-empty-means]').textContent)
            .toMatch(/found no instance of it/);
    });
});

describe('the tools write nothing', () => {
    it('says so, in the tray, before anything is clicked', async () => {
        await open();
        expect(q('[data-writes="nothing"]').textContent)
            .toMatch(/no client at all/);
    });

    it('offers exactly the tools each form declares', async () => {
        await open();
        expect(all('[data-tool]').map((b) => b.getAttribute('data-tool')))
            .toEqual(form('extent.hard_mask').manual_tools);
        await click(q('[data-form-option="topology.pair_relation"]'));
        expect(all('[data-tool]').map((b) => b.getAttribute('data-tool')))
            .toEqual(form('topology.pair_relation').manual_tools);
    });

    it('offers the four verdicts the contract names, each with its meaning', async () => {
        await open();
        expect(all('[data-verdict]').map((b) => b.getAttribute('data-verdict')))
            .toEqual(['correct', 'partial', 'wrong', 'unclear']);
        await click(q('[data-verdict="unclear"]'));
        expect(q('[data-verdict-note="unclear"]').textContent)
            .toMatch(/behind a ref, an endpoint does not resolve, or a raster is too coarse/);
    });

    it('discards every proposal on request, since none of them is saved anywhere', async () => {
        await open();
        await click(q('[data-verdict="partial"]'));
        expect(all('[data-proposal-target]')).toHaveLength(1);
        await click(q('[data-action="clear-proposals"]'));
        expect(q('[data-no-proposals]')).toBeTruthy();
    });
});

describe('hiding a layer', () => {
    it('removes it from the drawing and leaves its row in the legend', async () => {
        // A hidden layer that vanished from the legend too would be a layer a person could not
        // find their way back to, and one they might forget is there.
        await open();
        await click(q('[data-toggle-layer="mask_fill:inst_1"]'));
        expect(q('.pl-fm-shape[data-layer="mask_fill:inst_1"]')).toBeNull();
        expect(q('.pl-fm-legendrow[data-layer="mask_fill:inst_1"]')).toBeTruthy();
        expect(q('.pl-fm-legendrow[data-layer="mask_fill:inst_1"]').getAttribute('data-hidden'))
            .toBe('true');
    });
});
