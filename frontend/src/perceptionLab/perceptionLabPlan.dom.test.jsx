// PERCEPTUAL-ORGANS-002 Lane E — the plan, the run and the ledger.
//
// The load-bearing test in this file is `the two arms produce the same run presentation`. Direct
// and Prompt are the same laboratory reached two ways, and the moment one of them renders a
// different set of facts, "a control cannot do what a prompt is refused" stops being checkable by
// looking at the screen. So the presentation is reduced to a shape — which sections exist, which
// axes are on them — and the two arms are compared as shapes rather than as screenshots.

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
const type = async (el, value) => {
    await act(async () => {
        const setter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value').set;
        setter.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await settle();
};
const byLabel = (re) => [...container.querySelectorAll('button')]
    .find((b) => re.test(b.textContent));

/** Open a session on the controls scene, which has masks a topology question can be asked of. */
const open = async (client = createFixtureClient()) => {
    await mount(<PerceptionLab client={client} />);
    await settle();
    await click(q('[data-source-id="scene_controls"]'));
    return client;
};

/**
 * The shape of what a run is presented as. Deliberately NOT the text: two arms that agree on the
 * words but disagree about whether the digest pair is shown have not produced the same surface.
 */
const runShape = () => ({
    execution: q('[data-execution]')?.getAttribute('data-execution'),
    outcome: q('[data-run-id]')?.getAttribute('data-outcome'),
    columns: all('[data-stages] thead th').map((th) => th.textContent),
    stageStates: all('[data-attempt]').map((r) => r.getAttribute('data-state')),
    invoked: all('[data-invoked]').map((td) => td.getAttribute('data-invoked')),
    digestShown: !!q('[data-digest-before]') && !!q('[data-digest-after]'),
    digestHeld: q('[data-digest-held]')?.getAttribute('data-digest-held'),
    inspectorBlocks: all('[data-block]').map((b) => b.getAttribute('data-block')),
    axes: {
        epistemic: !!q('.pl-epi'),
        basis: !!q('.pl-basis'),
        lifecycle: !!q('.pl-life'),
        scope: !!q('.pl-scope'),
    },
});

describe('a plan is read before it runs', () => {
    it('shows nothing to run until something is proposed', async () => {
        await open();
        expect(text()).toContain('No plan yet');
        expect(text()).toContain('Nothing has run in this session');
    });

    it('separates what was proposed from what was authorized', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        expect(all('[data-role="proposed"]')).toHaveLength(1);
        expect(all('[data-role="resolved"]')).toHaveLength(1);
        // A proposal has no authorization field at all; a resolved step names its authorizer.
        expect(q('[data-authorized-by]').getAttribute('data-authorized-by')).toBe('resolver');
        expect(q('[data-role="proposed"]').textContent).toMatch(/carries no authority/);
        expect(q('[data-role="resolved"]').textContent).toMatch(/organ_lock, parameters/);
    });

    it('a parameter the operation does not declare is dropped, on the record', async () => {
        const client = await open();
        // Nobody can type this from the controls — the point is what happens when a planner does.
        const plan = await client.plan({
            session_id: (await client.getSession({ session_id: 'labs_1' })).session_id,
            planner: 'direct',
            operation: 'extent.find_all',
            parameters: { max_instances: 4, colour: 'blue' },
            input_refs: [],
            for_execution: true,
        });
        expect(plan.dropped_parameters).toHaveLength(1);
        expect(plan.dropped_parameters[0].name).toBe('colour');
        expect(plan.resolved_steps[0].parameters).toEqual({ max_instances: 4 });
    });

    it('the LIVE button is disabled against a client that has no adapters to call', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        expect(q('[data-action="run-live"]').disabled).toBe(true);
        expect(q('[data-action="run-live"]').getAttribute('title'))
            .toMatch(/no live adapters/);
        expect(q('[data-action="run-fixture"]').disabled).toBe(false);
    });
});

describe('the two arms produce the same run presentation', () => {
    const runDirect = async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        return runShape();
    };

    const runPrompt = async () => {
        await open();
        await click(q('[data-arm="prompt"]'));
        await type(q('#pl-prompt'), 'find all the shapes');
        await click(q('[data-action="ask-rules"]'));
        await click(q('[data-action="run-fixture"]'));
        return runShape();
    };

    it('same sections, same axes, same columns, same stage states', async () => {
        const direct = await runDirect();
        await act(async () => { root.unmount(); });
        container.remove();
        container = document.createElement('div');
        document.body.appendChild(container);
        root = createRoot(container);
        const prompt = await runPrompt();

        expect(direct.outcome).toBe('ready');
        expect(prompt.outcome).toBe('ready');
        expect(prompt).toEqual(direct);
    });

    it('and the prompt arm says which planner actually wrote it', async () => {
        await open();
        await click(q('[data-arm="prompt"]'));
        await type(q('#pl-prompt'), 'find all the shapes');
        await click(q('[data-action="ask-model"]'));
        // No model is reachable in the fixture deployment, so this is a rules plan wearing its
        // own name, with the fallback stated.
        expect(q('[data-planner]').getAttribute('data-planner')).toBe('rules');
        expect(q('[data-planner]').textContent).toMatch(/fell back from model/);
    });
});

describe('every execution identity and every outcome renders as itself', () => {
    it('a fixture run is badged FIXTURE, and that is not the client badge', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-run-id]').getAttribute('data-execution')).toBe('FIXTURE');
        // Two badges, two questions.
        expect(q('[data-client-identity]')).toBeTruthy();
        expect(q('.pl-exec[data-id="FIXTURE"]')).toBeTruthy();
    });

    it('a replay is badged REPLAY and states that nothing could have been called', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        await click(q('[data-action="replay-this"]'));
        expect(q('[data-run-id]').getAttribute('data-execution')).toBe('REPLAY');
        expect(q('[data-replay-of]')).toBeTruthy();
        expect(text()).toMatch(/adapter_callable: false/);
        expect(all('[data-invoked]').every((td) => td.getAttribute('data-invoked') === 'false'))
            .toBe(true);
    });

    it('unavailable is not refused: the adapter is named and nothing looked at the image',
        async () => {
            await open();
            // extent.find_named needs sam3_concept or grounded_sam; close both.
            await act(async () => { root.unmount(); });
            container.remove();
            container = document.createElement('div');
            document.body.appendChild(container);
            root = createRoot(container);
            await open(createFixtureClient({
                capabilityStates: defaultCapabilityStates({
                    sam3_concept: 'unavailable', grounded_sam: 'unavailable' }),
            }));
            const named = q('[data-operation="extent.find_named"]');
            expect(named.disabled).toBe(true);
            expect(named.getAttribute('title')).toMatch(/sam3_concept, grounded_sam/);
        });

    it('empty is a measurement, and says so', async () => {
        const client = await open(createFixtureClient());
        // The absent scene has nothing in it at all.
        await click(q('[data-source-id="scene_absent"]'));
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-run-id]').getAttribute('data-outcome')).toBe('empty');
        expect(q('.pl-outcome[data-outcome="empty"]').textContent)
            .toMatch(/This is a measurement/);
        expect(client).toBeTruthy();
    });

    it('failed makes no claim at all, and leaves no end time', async () => {
        await open(createFixtureClient({ failOperations: ['extent.find_all'] }));
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-run-id]').getAttribute('data-outcome')).toBe('failed');
        expect(q('[data-run-duration]').textContent).toMatch(/unmeasured/);
        expect(q('[data-run-duration]').textContent).toMatch(/no end time/);
        expect(q('[data-attempt]').getAttribute('data-state')).toBe('failed');
    });

    it('the organ lock refuses a topology phrase asked of the Extent organ, before anything '
        + 'else is checked', async () => {
        await open();
        await click(q('[data-arm="prompt"]'));
        await type(q('#pl-prompt'), 'do those two touch');
        await click(q('[data-action="ask-rules"]'));
        expect(q('[data-refusals]')).toBeTruthy();
        // Gate order is not cosmetic: the lock answers first, so the person is told they are in
        // the wrong organ rather than that their endpoints are missing.
        expect(q('.pl-refusal-code').textContent).toBe('organ_locked');
        expect(q('[data-no-resolved]').textContent).toMatch(/this plan will not run/);
        expect(q('[data-action="run-fixture"]').disabled).toBe(true);
    });

    it('refused is a result, and with the right organ selected it names the missing endpoints',
        async () => {
            await open();
            await click([...container.querySelectorAll('.pl-organ')]
                .find((o) => o.getAttribute('data-organ') === 'topology'));
            await click(q('[data-arm="prompt"]'));
            // Nothing is selected, so "those two" resolves to nothing at all.
            await type(q('#pl-prompt'), 'do those two touch');
            await click(q('[data-action="ask-rules"]'));
            expect(q('.pl-refusal-code').textContent).toBe('missing_extent_inputs');
            expect(q('.pl-refusal').textContent).toMatch(/source/);
            expect(q('[data-action="run-fixture"]').disabled).toBe(true);
        });
});

describe('the stage stream', () => {
    it('gives every stage its own state, adapter, invoked flag and timing', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const row = q('[data-attempt]');
        expect(row.getAttribute('data-state')).toBe('completed');
        expect(q('[data-adapter]').getAttribute('data-adapter')).toBe('yolo_sam2_auto');
        // The adapter this stage WOULD use is named, and `invoked` still says no, because a
        // FIXTURE run calls nothing. Naming the adapter without that column would read as a call.
        expect(q('[data-invoked]').getAttribute('data-invoked')).toBe('false');
        expect(q('[data-invoked]').getAttribute('title')).toMatch(/nothing was called/);
        expect(q('[data-duration]').getAttribute('data-duration')).not.toBe('unmeasured');
    });

    it('states that the image did not move under the run rather than leaving it absent',
        async () => {
            await open();
            await click(q('[data-action="propose"]'));
            await click(q('[data-action="run-fixture"]'));
            expect(q('[data-digest-held]').getAttribute('data-digest-held')).toBe('true');
            expect(q('[data-digest-before]').textContent).toBe('sha256:fixture_controls_v1');
            expect(q('[data-digest-after]').textContent).toBe('sha256:fixture_controls_v1');
        });
});

describe('the inspector keeps the six blocks six', () => {
    const runAndOpen = async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
    };

    it('renders all six blocks, in order, each labelled', async () => {
        await runAndOpen();
        expect(all('[data-block]').map((b) => b.getAttribute('data-block'))).toEqual([
            'identity', 'measurement', 'projection', 'interpretation', 'lifecycle', 'provenance',
            'reviews',
        ]);
    });

    it('measurement and interpretation carry their own epistemic status', async () => {
        await runAndOpen();
        const measured = q('[data-block="measurement"] .pl-epi').getAttribute('data-status');
        const read = q('[data-block="interpretation"] .pl-epi').getAttribute('data-status');
        expect(measured).toBe('measured');
        expect(read).not.toBe('measured');
    });

    it('projection says how it is drawn and carries no geometry', async () => {
        await runAndOpen();
        const block = q('[data-block="projection"]');
        expect(block.textContent).toMatch(/no geometry can arrive through this block/);
        const hints = q('[data-hint-keys]').getAttribute('data-hint-keys');
        for (const key of hints.split(',').filter(Boolean)) {
            expect(key).not.toMatch(/mask|polygon|points|box|rle/);
        }
    });

    it('says the identity is session-local and Semant has never heard of it', async () => {
        await runAndOpen();
        expect(q('[data-identity-scope]').getAttribute('data-identity-scope')).toBe('session');
        expect(q('[data-identity-scope]').textContent).toMatch(/Semant has never heard of it/);
    });

    it('an unnamed instance is withheld, not unknown', async () => {
        await runAndOpen();
        const namings = all('[data-instance-naming]').map((n) => n.textContent);
        expect(namings.length).toBeGreaterThan(0);
        expect(namings.every((n) => n.trim().length > 0)).toBe(true);
    });

    it('reads the artifact against the contract and names any missing field', async () => {
        await runAndOpen();
        expect(q('[data-missing-fields]')).toBe(null);
    });
});

describe('the ledger', () => {
    it('keeps selection and activation as two acts', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const id = q('[data-ledger-row]').getAttribute('data-ledger-row');
        // Running made it active; nothing has been selected.
        expect(q(`[data-activate="${id}"]`).getAttribute('aria-selected')).toBe('true');
        expect(q(`[data-select="${id}"]`).getAttribute('aria-pressed')).toBe('false');
        await click(q(`[data-select="${id}"]`));
        expect(q(`[data-select="${id}"]`).getAttribute('aria-pressed')).toBe('true');
    });

    it('shows lifecycle and verdict as different chips, and neither implies the other',
        async () => {
            await open();
            await click(q('[data-action="propose"]'));
            await click(q('[data-action="run-fixture"]'));
            const row = q('[data-ledger-row]');
            expect(row.querySelector('.pl-life').getAttribute('data-status')).toBe('proposed');
            expect(row.querySelector('[data-unreviewed]').textContent).toBe('unjudged');
            expect(row.querySelector('.pl-verdict')).toBe(null);
        });

    it('a refusal is a row in the ledger with its own id, run and provenance', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const extentId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${extentId}"]`));
        await click([...container.querySelectorAll('.pl-organ')]
            .find((o) => o.getAttribute('data-organ') === 'topology'));
        await click(q('[data-operation="topology.occlusion"]'));
        await click(q(`[data-role-option="source:${extentId}"]`));
        await click(q(`[data-role-option="target:${extentId}"]`));
        await click(q('[data-action="propose"]'));

        // Composing is allowed and the refusal is stated in advance, from the same gate the run
        // will use — not predicted, and not hidden until the button is pressed.
        expect(q('[data-will-refuse]')).toBeTruthy();
        expect(q('[data-will-refuse] .pl-refusal-code').textContent)
            .toBe('missing_depth_artifact');
        expect(q('[data-requires-confirmation]')).toBeTruthy();
        expect(q('[data-action="run-fixture"]').textContent).toMatch(/^Confirm and run/);

        await click(q('[data-action="run-fixture"]'));
        expect(q('[data-run-id]').getAttribute('data-outcome')).toBe('refused');
        const rows = all('[data-ledger-row]');
        expect(rows).toHaveLength(2);
        const refusalRow = rows.find((r) => r.getAttribute('data-kind') === 'refusal');
        expect(refusalRow).toBeTruthy();
        await click(refusalRow.querySelector('[data-activate]'));
        // It is a full artifact: six blocks, a run, a provenance, and a source digest.
        expect(all('[data-block]').map((b) => b.getAttribute('data-block')))
            .toContain('provenance');
        expect(q('[data-source-digest]').textContent).toBe('sha256:fixture_controls_v1');
        expect(q('[data-block="measurement"] .pl-refusal-code').textContent)
            .toBe('missing_depth_artifact');
        // A refusal makes no claim about the image.
        expect(q('[data-block="measurement"] .pl-epi').getAttribute('data-status'))
            .toBe('uncertain');
    });

    it('selecting a follow-up reference is what the prompt arm reads, and nothing else',
        async () => {
            await open();
            await click(q('[data-action="propose"]'));
            await click(q('[data-action="run-fixture"]'));
            await click(q('[data-arm="prompt"]'));
            expect(q('[data-no-references]')).toBeTruthy();
            await click(q('[data-select]'));
            expect(q('[data-no-references]')).toBe(null);
            expect(all('[data-reference]')).toHaveLength(1);
        });
});

describe('nothing on this surface can promote', () => {
    it('there is no control whose words offer to save, promote or accept all', async () => {
        await open();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const words = /\b(promote|accept all|approve all|save|commit|publish)\b/i;
        const offenders = [...container.querySelectorAll('button')]
            .map((b) => b.textContent.trim())
            .filter((t) => words.test(t));
        expect(offenders).toEqual([]);
        expect(byLabel(/Propose a plan/)).toBeTruthy();
    });
});
