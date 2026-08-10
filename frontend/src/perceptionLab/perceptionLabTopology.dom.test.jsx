// PERCEPTUAL-ORGANS-002 Lane E — the Topology instrument on a stage.
//
// Every test here drives the surface the way a person does: find extents, select two, switch
// organ, choose a typed operation, run it, read the answer. Nothing is constructed by hand,
// because the thing being checked is whether the LABORATORY keeps direction, basis and endpoint
// identity visible — not whether a component renders a hand-built prop.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import PerceptionLab from './PerceptionLab';
import { createFixtureClient, defaultCapabilityStates } from './clients/fixtureClient';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => {
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
};

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
});

const text = () => container.textContent;
const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => {
    if (!el) throw new Error('nothing to click');
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};
const organ = (family) => [...container.querySelectorAll('.pl-organ')]
    .find((o) => o.getAttribute('data-organ') === family);

/**
 * The ordinary path: find every extent on the controls scene, select the set, switch to Topology,
 * then ask one typed question of two named instances.
 */
const askAbout = async (operation, sourceIndex, targetIndex, options = {}) => {
    const client = createFixtureClient(options);
    await mount(<PerceptionLab client={client} />);
    await settle();
    await click(q('[data-source-id="scene_controls"]'));
    await click(q('[data-action="propose"]'));
    await click(q('[data-action="run-fixture"]'));
    const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
    await click(q(`[data-select="${artifactId}"]`));
    await click(organ('topology'));
    await click(q(`[data-operation="${operation}"]`));
    const instanceOptions = (role) => all(`[data-role-option^="${role}:"]`)
        .filter((b) => b.getAttribute('data-role-option').includes('#'));
    if (sourceIndex !== null) await click(instanceOptions('source')[sourceIndex]);
    if (targetIndex !== null) await click(instanceOptions('target')[targetIndex]);
    await click(q('[data-action="propose"]'));
    await click(q('[data-action="run-fixture"]'));
    return { client, artifactId, instanceIds: all('[data-instance]')
        .map((b) => b.getAttribute('data-instance')) };
};

// scene_controls instance order: outer, inner, bar_left, bar_right, disc_a, disc_b, far_dot.
const OUTER = 0; const INNER = 1; const BAR_L = 2; const BAR_R = 3; const FAR = 6;

describe('a typed relation reaches the screen typed', () => {
    it('containment reads as a direction, not as "these two are related"', async () => {
        await askAbout('topology.containment', INNER, OUTER);
        const row = q('[data-relation-row]');
        expect(row.getAttribute('data-relation-kind')).toBe('nested_within');
        expect(q('[data-relation-sentence]').textContent).toMatch(/ is inside /);
        expect(q('[data-relation-direction]').getAttribute('data-relation-direction'))
            .toBe('directed');
    });

    it('the direction is reversible, and reversing it changes the claim', async () => {
        await askAbout('topology.containment', OUTER, INNER);
        // Asked the other way round, the same two extents produce `contains`, not `nested_within`.
        expect(q('[data-relation-row]').getAttribute('data-relation-kind')).toBe('contains');
        expect(q('[data-relation-sentence]').textContent).toMatch(/ contains /);
    });

    it('a symmetric relation is not dressed as a directed one', async () => {
        await askAbout('topology.adjacency', BAR_L, BAR_R);
        expect(q('[data-relation-row]').getAttribute('data-relation-kind')).toBe('meets');
        expect(q('[data-relation-direction]').getAttribute('data-relation-direction'))
            .toBe('symmetric');
        expect(q('[data-relation-sentence]').textContent).toMatch(/ touches /);
        // No arrowhead, because no asymmetry was measured.
        expect(q('[data-arrowhead]')).toBe(null);
    });

    it('endpoint identity survives beside the readable name', async () => {
        await askAbout('topology.adjacency', BAR_L, BAR_R);
        // The sentence reads with the NAMES, which are interpretive and can collide…
        expect(q('[data-relation-sentence]').textContent).toBe('left bar touches right bar');
        // …so the ids are shown too, in the direction they were measured. Without them a
        // relation between two things both called "drapery" could not be checked at all.
        const identity = q('[data-endpoint-identity]');
        expect(identity.querySelector('[data-endpoint-source]')
            .getAttribute('data-endpoint-source')).toBeTruthy();
        expect(identity.querySelector('[data-endpoint-target]')
            .getAttribute('data-endpoint-target')).toBeTruthy();
        expect(identity.querySelector('[data-endpoint-source]').textContent)
            .toMatch(/^art_\w+#/);
    });
});

describe('the relation is placed on the image, and labelled as a drawing', () => {
    it('an adjacency draws a contact band, badged derived', async () => {
        await askAbout('topology.adjacency', BAR_L, BAR_R);
        const layer = q('[data-relation-layer]');
        expect(layer.getAttribute('data-projection-kind')).toBe('contact_band');
        expect(layer.getAttribute('data-derived')).toBe('true');
        expect(q('[data-topology-stage] [data-derived="true"]').getAttribute('title'))
            .toMatch(/computed in this browser/);
        expect(q('.pl-band')).toBeTruthy();
    });

    it('an overlap draws the exact intersection', async () => {
        await askAbout('topology.overlap', OUTER, INNER);
        expect(q('[data-relation-layer]').getAttribute('data-projection-kind'))
            .toBe('intersection_area');
        expect(q('.pl-intersection')).toBeTruthy();
    });

    it('a directed relation draws an arrowhead and a symmetric one does not', async () => {
        await askAbout('topology.containment', INNER, OUTER);
        expect(q('[data-arrowhead]')).toBeTruthy();
        expect(q('[data-directed]').getAttribute('data-directed')).toBe('true');
    });

    it('a disjoint pair draws the clearance between the nearest points', async () => {
        await askAbout('topology.disjoint', INNER, FAR);
        expect(q('[data-relation-row]').getAttribute('data-relation-kind')).toBe('disjoint');
        expect(q('[data-endpoint="source"]')).toBeTruthy();
        expect(q('.pl-endpoint-line')).toBeTruthy();
    });

    it('the derived number is printed beside the producer’s', async () => {
        await askAbout('topology.overlap', OUTER, INNER);
        const agreement = q('[data-agreement]');
        expect(agreement.getAttribute('data-agreement')).toBe('iou');
        expect(agreement.getAttribute('data-agrees')).toBe('true');
        expect(agreement.textContent).toMatch(/recorded .* this browser derived/);
    });
});

describe('mask basis and box basis are visibly different claims', () => {
    it('a mask-basis relation is measured, a box-basis one is interpretive', async () => {
        await askAbout('topology.containment', INNER, OUTER);
        expect(q('[data-relation-row] .pl-basis').getAttribute('data-basis')).toBe('mask');
        expect(q('[data-relation-row] .pl-epi').getAttribute('data-status')).toBe('measured');
    });

    it('asking on boxes drops the claim to interpretive and says why on the chip', async () => {
        const client = createFixtureClient();
        await mount(<PerceptionLab client={client} />);
        await settle();
        await click(q('[data-source-id="scene_controls"]'));
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${artifactId}"]`));
        await click(organ('topology'));
        await click(q('[data-operation="topology.containment"]'));
        // `basis` is a declared enum parameter on containment, so it can be asked for directly.
        const select = q('[data-parameter="basis"]');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                window.HTMLSelectElement.prototype, 'value').set;
            setter.call(select, 'box');
            select.dispatchEvent(new Event('change', { bubbles: true }));
        });
        await settle();
        const instanceOptions = (role) => all(`[data-role-option^="${role}:"]`)
            .filter((b) => b.getAttribute('data-role-option').includes('#'));
        await click(instanceOptions('source')[INNER]);
        await click(instanceOptions('target')[OUTER]);
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));

        expect(q('[data-relation-row] .pl-basis').getAttribute('data-basis')).toBe('box');
        expect(q('[data-relation-row] .pl-epi').getAttribute('data-status')).toBe('interpretive');
        expect(q('[data-relation-row] .pl-basis').getAttribute('title'))
            .toMatch(/a box basis may claim at most interpretive/);
        expect(q('[data-basis-detail]').textContent).toMatch(/WAVE2\.5/);
    });
});

describe('a graph and a list are two arrangements of one measurement', () => {
    it('the graph counts degree, which a list of pairs does not show', async () => {
        // All-pairs over the whole set: one node in many relations.
        const client = createFixtureClient();
        await mount(<PerceptionLab client={client} />);
        await settle();
        await click(q('[data-source-id="scene_controls"]'));
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${artifactId}"]`));
        await click(organ('topology'));
        await click(q('[data-operation="topology.all_pairs"]'));
        // `members` declares min 2, and a ref is one member. One ref naming the whole set is one
        // member, however many instances are inside it — so the set is named instance by
        // instance, and the count on the artifact is a count of what was actually asked.
        for (const option of all('[data-role-option^="members:"]')
            .filter((b) => b.getAttribute('data-role-option').includes('#')).slice(0, 4)) {
            await click(option);
        }
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));

        expect(Number(q('[data-relation-list]') ? all('[data-relation-row]').length : 0))
            .toBeGreaterThan(0);
        await click(q('[data-arrange="graph"]'));
        expect(q('[data-relation-graph]')).toBeTruthy();
        const degrees = all('[data-node-degree]')
            .map((n) => Number(n.getAttribute('data-node-degree')));
        expect(Math.max(...degrees)).toBeGreaterThan(1);
        // Every edge names its kind — the graph did not become "related to".
        const kinds = all('[data-edge-kind]').map((k) => k.textContent);
        expect(kinds.every((k) => k && k !== 'related')).toBe(true);
    });

    it('the bound that was applied is on the record and on the screen', async () => {
        const client = createFixtureClient();
        await mount(<PerceptionLab client={client} />);
        await settle();
        await click(q('[data-source-id="scene_controls"]'));
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${artifactId}"]`));
        await click(organ('topology'));
        await click(q('[data-operation="topology.all_pairs"]'));
        // `members` declares min 2, and a ref is one member. One ref naming the whole set is one
        // member, however many instances are inside it — so the set is named instance by
        // instance, and the count on the artifact is a count of what was actually asked.
        for (const option of all('[data-role-option^="members:"]')
            .filter((b) => b.getAttribute('data-role-option').includes('#')).slice(0, 4)) {
            await click(option);
        }
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-examined-note]').textContent).toMatch(/pairs examined/);
        expect(q('[data-bounded-to]')).toBeTruthy();
    });
});

describe('empty, unavailable and refused are three different answers', () => {
    it('pairs examined with no relation is a finding, not a blank', async () => {
        await askAbout('topology.containment', INNER, FAR);
        expect(q('[data-pairs-examined]').getAttribute('data-pairs-examined')).toBe('1');
        expect(q('[data-empty-relations]').textContent)
            .toMatch(/none held that relation/);
        expect(q('[data-empty-relations]').textContent)
            .toMatch(/zero pairs examined would have been an absence of measurement/);
    });

    it('occlusion refuses for a missing depth field, and the refusal is the result', async () => {
        const client = createFixtureClient();
        await mount(<PerceptionLab client={client} />);
        await settle();
        await click(q('[data-source-id="scene_controls"]'));
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${artifactId}"]`));
        await click(organ('topology'));
        await click(q('[data-operation="topology.occlusion"]'));
        const instanceOptions = (role) => all(`[data-role-option^="${role}:"]`)
            .filter((b) => b.getAttribute('data-role-option').includes('#'));
        await click(instanceOptions('source')[INNER]);
        await click(instanceOptions('target')[OUTER]);
        await click(q('[data-action="propose"]'));
        expect(q('[data-will-refuse] .pl-refusal-code').textContent)
            .toBe('missing_depth_artifact');
        expect(q('[data-will-refuse]').textContent)
            .toMatch(/optional to plan and required to run/);
        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-run-id]').getAttribute('data-outcome')).toBe('refused');
        // Nothing invoked. The Depth organ is registered and disabled; this is the end of the
        // path rather than a placeholder for a call the lab could make if it tried.
        expect(q('[data-invoked]').getAttribute('data-invoked')).toBe('false');
        expect(text()).toMatch(/supply a prepared depth artifact/);
    });

    it('an unavailable topology adapter is unavailable, and never empty', async () => {
        const client = createFixtureClient({
            capabilityStates: defaultCapabilityStates({ distance_transform: 'unavailable' }),
        });
        await mount(<PerceptionLab client={client} />);
        await settle();
        await click(q('[data-source-id="scene_controls"]'));
        await click(organ('topology'));
        const negative = q('[data-operation="topology.negative_space"]');
        expect(negative.disabled).toBe(true);
        expect(negative.getAttribute('title')).toMatch(/distance_transform/);
    });
});

describe('negative space is drawn only where it can be drawn honestly', () => {
    it('refuses the measured field and derives its own, saying which is which', async () => {
        const client = createFixtureClient();
        await mount(<PerceptionLab client={client} />);
        await settle();
        await click(q('[data-source-id="scene_controls"]'));
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${artifactId}"]`));
        await click(organ('topology'));
        await click(q('[data-operation="topology.negative_space"]'));
        await click(all('[data-role-option^="figure:"]')
            .filter((b) => b.getAttribute('data-role-option').includes('#'))[INNER]);
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));

        expect(q('[data-measured-field-absent]').textContent)
            .toMatch(/held behind `field_ref`/);
        expect(q('[data-measured-field-absent]').textContent)
            .toMatch(/a wash drawn from them would be invented/);
        expect(q('[data-layer="scalar_wash"]')).toBeTruthy();
        expect(q('[data-layer="scalar_wash"]').getAttribute('data-derived')).toBe('true');
        expect(q('[data-wash-note]').textContent).toMatch(/derived here/);
        expect(q('[data-field-ref]')).toBeTruthy();
    });
});
