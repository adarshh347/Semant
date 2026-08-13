// PERCEPTUAL-ORGANS-002 Lane E — the Extent instrument on a stage.
//
// jsdom does not decode images, so `useNaturalSize` never fires and the DECLARED size from the
// session is what the overlay uses. That is not a limitation being worked around: it is the
// fallback behaving as designed, and the alignment assertions below are exactly as strong either
// way, because what is asserted is the viewBox contract rather than a rendered pixel.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import PerceptionLab from './PerceptionLab';
import { createFixtureClient } from './clients/fixtureClient';

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
const key = async (k) => {
    await act(async () => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
    });
    await settle();
};

/** Open the multi-instance scene and find everything in it. */
const findAll = async (sceneId = 'scene_instances', options = {}) => {
    const client = createFixtureClient(options);
    await mount(<PerceptionLab client={client} />);
    await settle();
    await click(q(`[data-source-id="${sceneId}"]`));
    await click(q('[data-action="propose"]'));
    await click(q('[data-action="run-fixture"]'));
    return client;
};

describe('the stage draws the measurement, and says it is a drawing of one', () => {
    it('uses the natural-pixel viewBox and the shared letterbox, so shapes cannot drift',
        async () => {
            await findAll();
            const svg = q('.pl-svg');
            // scene_instances is 900×600. The overlay letterboxes exactly as `object-fit:
            // contain` does, which is the whole alignment contract in two attributes.
            expect(svg.getAttribute('viewBox')).toBe('0 0 900 600');
            expect(svg.getAttribute('preserveAspectRatio')).toBe('xMidYMid meet');
        });

    it('traces the mask rather than drawing the box', async () => {
        await findAll();
        // A traced boundary is a <path>; a box would be a <rect>. Five instances, five paths.
        expect(all('.pl-svg path.rs-shape')).toHaveLength(5);
        expect(all('.pl-svg rect.rs-shape')).toHaveLength(0);
    });

    it('badges the drawing as derived and never as the measurement', async () => {
        await findAll();
        expect(q('[data-extent-stage] [data-derived="true"]')).toBeTruthy();
        expect(q('[data-extent-stage] [data-derived="true"]').getAttribute('title'))
            .toMatch(/The measurement is the RLE/);
    });

    it('says how coarse the grid the measurement was taken on is', async () => {
        await findAll();
        const note = q('[data-raster-coarseness]');
        // scene_instances measures on a 100×150 raster over a 900×600 image: 6px per cell.
        expect(note.getAttribute('data-raster-coarseness')).toBe('coarse');
        expect(note.textContent).toMatch(/mask raster 100×150/);
        expect(note.textContent).toMatch(/drawn crisply and was not measured crisply/);
    });
});

describe('view and basis are two controls', () => {
    it('outline, mask and focus are three views of one measurement', async () => {
        await findAll();
        expect(q('.pl-stage').getAttribute('data-view')).toBe('mask');
        await click(q('[data-view-mode="outline"]'));
        expect(q('.pl-stage').getAttribute('data-view')).toBe('outline');
        await click(q('[data-view-mode="focus"]'));
        expect(q('.pl-stage').getAttribute('data-view')).toBe('focus');
        // The shapes did not change — only how they are shown.
        expect(all('.pl-svg path.rs-shape')).toHaveLength(5);
    });

    it('focus lights one instance and dims the rest', async () => {
        await findAll();
        await click(q('[data-view-mode="focus"]'));
        await click(all('[data-naming-row]')[1]);
        expect(all('.pl-svg .rs-shape.is-lit')).toHaveLength(1);
        expect(all('.pl-svg .rs-shape.is-dim')).toHaveLength(4);
    });

    it('the box basis redraws the same instances as boxes and states the ceiling', async () => {
        await findAll();
        await click(q('[data-basis-mode="box"]'));
        expect(q('[data-drawn-basis]').getAttribute('data-drawn-basis')).toBe('box');
        expect(q('[data-box-basis-note]').textContent)
            .toMatch(/interpretive however confident the number/);
        // Boxes are still paths — four-point rings — but they wear the box class, so nothing on
        // this stage can be a box that looks like a mask.
        expect(all('.pl-svg .rs-shape--box').length).toBe(5);
        expect(all('.pl-svg .rs-shape--mask')).toHaveLength(0);
    });
});

describe('refinement goes through the resolver, like everything else', () => {
    it('will not refine until an instance is focused — it does not pick the first one', async () => {
        await findAll();
        await click(q('[data-tool="point"]'));
        expect(q('[data-action="propose-refine-add"]').disabled).toBe(true);
        expect(q('[data-no-focus]').textContent).toMatch(/will not pick the first one for you/);
    });

    it('a keyboard user reaches the tools', async () => {
        await findAll();
        await key('b');
        expect(q('[data-tool="box"]').getAttribute('aria-pressed')).toBe('true');
        await key('p');
        expect(q('[data-tool="point"]').getAttribute('aria-pressed')).toBe('true');
        await key('n');
        expect(q('[data-negative]').getAttribute('aria-pressed')).toBe('true');
        await key('Escape');
        expect(q('[data-tool="none"]').getAttribute('aria-pressed')).toBe('true');
    });

    it('a gesture is evidence and says so until it is sent', async () => {
        await findAll();
        await click(q('[data-tool="point"]'));
        expect(q('[data-gesture-state]').textContent).toMatch(/nothing has been proposed yet/);
        expect(q('[data-gesture-state]').textContent).toMatch(/same resolver as everything else/);
    });
});

describe('one extent inside a multi-extent artifact', () => {
    it('an input can name a single instance, and the record says how many pairs that was',
        async () => {
            await findAll();
            const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
            await click(q(`[data-select="${artifactId}"]`));
            await click([...container.querySelectorAll('.pl-organ')]
                .find((o) => o.getAttribute('data-organ') === 'topology'));
            await click(q('[data-operation="topology.adjacency"]'));

            // The role picker offers the whole set AND each instance inside it.
            const wholeSet = q(`[data-role-option="source:${artifactId}"]`);
            expect(wholeSet.textContent).toMatch(/all 5, and every cross pair is measured/);
            const instanceOptions = all('[data-role-option^="source:"]')
                .filter((b) => b.getAttribute('data-role-option').includes('#'));
            expect(instanceOptions).toHaveLength(5);

            await click(instanceOptions[2]);   // figure_3, drapery
            await click(all('[data-role-option^="target:"]')
                .filter((b) => b.getAttribute('data-role-option').includes('#'))[3]);
            await click(q('[data-action="propose"]'));

            // The plan preview names the instance too. Showing only the artifact would mean the
            // thing a person reads before pressing the button disagrees with the record.
            expect(q('[data-resolved-inputs]').textContent).toMatch(/source=\w+#\w+/);
            expect(q('[data-resolved-inputs]').textContent).toMatch(/target=\w+#\w+/);

            await click(q('[data-action="run-fixture"]'));

            // Two instances named, so exactly one pair was examined — not twenty-five.
            expect(q('[data-pairs-examined]').getAttribute('data-pairs-examined')).toBe('1');
            const refs = all('[data-input-instance]')
                .map((s) => s.getAttribute('data-input-instance')).filter(Boolean);
            expect(refs).toHaveLength(2);
        });

    it('asking the whole set is a different question, and the count says which was asked',
        async () => {
            await findAll();
            const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
            await click(q(`[data-select="${artifactId}"]`));
            await click([...container.querySelectorAll('.pl-organ')]
                .find((o) => o.getAttribute('data-organ') === 'topology'));
            await click(q('[data-operation="topology.adjacency"]'));
            await click(q(`[data-role-option="source:${artifactId}"]`));
            await click(q(`[data-role-option="target:${artifactId}"]`));
            await click(q('[data-action="propose"]'));
            await click(q('[data-action="run-fixture"]'));
            // 5 × 5 crossings minus the five self-pairs: nothing is adjacent to itself, and the
            // organ does not pad the count with pairs it declined to measure.
            expect(q('[data-pairs-examined]').getAttribute('data-pairs-examined')).toBe('20');
        });
});

describe('the readings beside the picture', () => {
    it('finds the near-duplicate pair the adapter failed to separate', async () => {
        await findAll();
        // scene_instances has two overlapping drapery rectangles, on purpose.
        expect(q('[data-pairs-compared]').getAttribute('data-pairs-compared')).toBe('10');
        expect(q('[data-overlapping]').getAttribute('data-overlapping')).toBe('1');
        expect(Number(q('[data-duplicate-pairs]').getAttribute('data-duplicate-pairs')))
            .toBeGreaterThan(0);
        expect(q('[data-duplicates-block]').textContent)
            .toMatch(/one thing the adapter failed to separate/);
    });

    it('shows the producer’s duplicate list beside its own, and agrees with it', async () => {
        await findAll();
        // Both are IoU ≥ 0.6 over the same rasters, so they must name the same pair. If this
        // ever fails, one of the two is measuring something other than what it says — which is
        // the finding, not a flake.
        expect(q('[data-recorded-duplicates]').getAttribute('data-recorded-duplicates')).toBe('1');
        expect(q('[data-duplicate-disagreement]')).toBe(null);
        expect(q('[data-threshold-note]').textContent)
            .toMatch(/A duplicate is a THRESHOLD and not a fact/);
        const recorded = q('[data-recorded-duplicate]').getAttribute('data-recorded-duplicate');
        const derived = q('[data-duplicate-pair]').getAttribute('data-duplicate-pair');
        expect(recorded.split('|').sort()).toEqual(derived.split('|').sort());
    });

    it('keeps named, withheld and uncertain as three states with three sentences', async () => {
        await findAll();
        const states = all('[data-naming-state]')
            .map((r) => r.getAttribute('data-naming-state'));
        expect(states).toHaveLength(5);
        expect(new Set(states).size).toBeGreaterThan(1);
        const withheld = all('[data-naming-state="withheld"]');
        if (withheld.length) {
            expect(withheld[0].textContent).toMatch(/withheld/);
        }
    });

    it('an unrelated set is not lineage — nothing was derived from anything', async () => {
        await findAll();
        expect(q('[data-no-lineage]').textContent).toMatch(/Nothing was derived from anything/);
    });

    it('repeat is only offered when there is a second run to compare against', async () => {
        await findAll();
        expect(q('[data-repeat-block]')).toBe(null);
        // Ask the same question again: a second run, a second answer, and now stability is a
        // question that can be asked.
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-repeat-block]')).toBeTruthy();
        expect(q('[data-repeat-matched]').getAttribute('data-repeat-matched')).toBe('5');
        expect(q('[data-repeat-block]').textContent).toMatch(/Stability, not duplication/);
    });
});

/**
 * jsdom lays nothing out, so `getBoundingClientRect` is 0×0 and the letterbox math has nothing to
 * work with. Stubbing the stage's box is not a workaround for a broken test — it is the only way
 * to exercise `pointerToNormalized`, which is the exact function whose absence causes shapes to
 * land on the wrong part of the picture. A 900×600 stage on a 900×600 image letterboxes to
 * nothing, so a click at (450, 300) is normalized (0.5, 0.5) and any drift shows up immediately.
 */
const withStageBox = (w = 900, h = 600) => {
    const original = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function rect() {
        if (this.classList?.contains('pl-stage')) {
            return { x: 0, y: 0, left: 0, top: 0, right: w, bottom: h, width: w, height: h };
        }
        return original.call(this);
    };
    return () => { Element.prototype.getBoundingClientRect = original; };
};

describe('a refinement is proposed, not dispatched', () => {
    it('carries the mode, the evidence and the ONE instance it is refining', async () => {
        const restore = withStageBox();
        try {
            await findAll();
            const focused = all('[data-naming-row]')[2].getAttribute('data-naming-row');
            await click(all('[data-naming-row]')[2]);
            await click(q('[data-tool="point"]'));
            const stage = q('.pl-stage');
            await act(async () => {
                stage.dispatchEvent(new MouseEvent('click', {
                    bubbles: true, clientX: 450, clientY: 300 }));
            });
            await settle();
            expect(q('[data-gesture-state]').textContent).toMatch(/^1 point ·/);
            // Polarity is a property of the refinement, not of the click — the contract's
            // `point_list` is pairs, so a labelled point would be rejected as "not a point_list"
            // and the surface must not offer one.
            expect(q('[data-gesture-state]').textContent)
                .toMatch(/not to each click/);

            await click(q('[data-action="propose-refine-add"]'));
            // It went through the resolver: a plan, with the four gates named on the step.
            const resolved = q('[data-role="resolved"]');
            expect(resolved.textContent).toMatch(/extent\.refine/);
            expect(resolved.textContent).toMatch(/"mode":"add"/);
            expect(q('[data-authorized-by]').getAttribute('data-authorized-by')).toBe('resolver');

            await click(q('[data-action="run-fixture"]'));
            // The refinement preserved the identity and moved the revision.
            expect(q('[data-artifact-summary]').textContent).toBe('1 extent');
            // The ref names the instance the person focused — the third one, not the first.
            expect(q('[data-input-instance]').getAttribute('data-input-instance')).toBe(focused);
            expect(q('[data-instances] [data-instance]').getAttribute('data-instance'))
                .toBe(focused);
            expect(q('[data-basis-detail]').textContent)
                .toMatch(/the identity is preserved and geometry_rev moves to 1/);
        } finally {
            restore();
        }
    });

    it('refuses when the named instance is not in the set, rather than refining another one',
        async () => {
            const client = await findAll();
            const session = await client.getSession({ session_id: 'labs_1' });
            const artifactId = [...(await client.history({ session_id: session.session_id }))
                .artifacts][0].identity.artifact_id;
            await client.select({ session_id: session.session_id, artifact_ids: [artifactId],
                active_artifact_id: artifactId });
            const plan = await client.plan({
                session_id: session.session_id,
                planner: 'direct',
                operation: 'extent.refine',
                parameters: { mode: 'add', points: [[0.5, 0.5]] },
                input_refs: [{ role: 'base', scope: 'session', artifact_id: artifactId,
                    instance_id: 'ext_not_here', region_id: null, geometry_rev: null }],
                for_execution: false,
            });
            // It dies at the REFERENCE gate now, one gate earlier than it used to. The session
            // declared the artifact and never that mask, so the step is refused before anything
            // is measured — and the message names `art#instance`, because a bare `ext_not_here`
            // would send a person looking for it in every set they have open.
            expect(plan.resolved_steps).toHaveLength(0);
            expect(plan.refusals[0].code).toBe('unknown_reference');
            expect(plan.refusals[0].missing).toEqual([`${artifactId}#ext_not_here`]);

            const out = await client.run({ session_id: session.session_id,
                plan_id: plan.plan_id });
            expect(out.run.outcome).toBe('refused');
        });

    it('refines exactly the instance that was selected, and not its neighbour', async () => {
        const client = await findAll();
        const session = await client.getSession({ session_id: 'labs_1' });
        const artifact = [...(await client.history({ session_id: session.session_id }))
            .artifacts][0];
        const artifactId = artifact.identity.artifact_id;
        const second = artifact.measurement.payload.instances[1].instance_id;
        await client.select({ session_id: session.session_id, artifact_ids: [artifactId],
            active_artifact_id: artifactId,
            selected_instance_refs: [{ artifact_id: artifactId, instance_id: second }] });
        const plan = await client.plan({
            session_id: session.session_id,
            planner: 'direct',
            operation: 'extent.refine',
            parameters: { mode: 'add', points: [[0.5, 0.5]] },
            input_refs: [{ role: 'base', scope: 'session', artifact_id: artifactId,
                instance_id: second, region_id: null, geometry_rev: null }],
            for_execution: false,
        });
        expect(plan.resolved_steps[0].input_refs[0].instance_id).toBe(second);
        const out = await client.run({ session_id: session.session_id, plan_id: plan.plan_id });
        expect(out.run.outcome).toBe('ready');
        expect(out.artifacts[0].identity.input_refs[0].instance_id).toBe(second);
    });
});

describe('a hand-drawn extent never reads as a segmented one', () => {
    it('proposes extent.draw, and the result is visible/manual rather than measured/mask',
        async () => {
            const restore = withStageBox();
            try {
                await findAll();
                await click(q('[data-tool="freehand"]'));
                const stage = q('.pl-stage');
                await act(async () => {
                    stage.dispatchEvent(new PointerEvent('pointerdown', {
                        bubbles: true, clientX: 180, clientY: 120 }));
                    for (const [x, y] of [[540, 120], [540, 420], [180, 420]]) {
                        stage.dispatchEvent(new PointerEvent('pointermove', {
                            bubbles: true, clientX: x, clientY: y }));
                    }
                    stage.dispatchEvent(new PointerEvent('pointerup', { bubbles: true }));
                });
                await settle();
                expect(q('[data-freehand]')).toBeTruthy();
                expect(q('[data-gesture-state]').textContent).toMatch(/4 points traced/);

                await click(q('[data-action="propose-draw"]'));
                await click(q('[data-action="run-fixture"]'));

                // The drawn extent is `visible` on a `manual` basis: someone can point at it and
                // nothing computed it. The ceiling sentence says so on the chip.
                expect(q('[data-block="measurement"] .pl-epi').getAttribute('data-status'))
                    .toBe('visible');
                expect(q('[data-block="measurement"] .pl-basis').getAttribute('data-basis'))
                    .toBe('manual');
                expect(q('[data-block="measurement"] .pl-basis').getAttribute('title'))
                    .toMatch(/a drawn basis may claim at most visible/);
                expect(q('[data-producer-kind]').getAttribute('data-producer-kind')).toBe('human');
                // And it is drawn in the manual treatment, not the segmented one.
                expect(all('.pl-svg .rs-shape--manual').length).toBeGreaterThan(0);
            } finally {
                restore();
            }
        });
});

describe('an empty set is drawn as an empty set', () => {
    it('renders the image, the empty measurement, and no shapes', async () => {
        await findAll('scene_absent');
        expect(all('.pl-svg .rs-shape')).toHaveLength(0);
        expect(q('[data-empty-extent]').textContent).toMatch(/This is a measurement/);
        expect(text()).toMatch(/Nothing was found, so nothing was named/);
    });
});
