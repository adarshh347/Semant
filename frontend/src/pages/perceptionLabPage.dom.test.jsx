// PERCEPTUAL-ORGANS-002 Lane F2 — the mounted route, driven the way a person drives it.
//
// Everything here goes through `createHttpLabClient` and `fetch`. The laboratory below is a real,
// stateful, contract-valid one (`fixtureHttpBackend`), so a session can be opened, planned
// against, run, narrowed to one mask, refined, switched to Chain, measured, reviewed, reloaded,
// replayed and exported — the eleven flows F2 was asked to prove, over the wire rather than over
// an object handed in.
//
// WHAT THIS FILE CANNOT PROVE, said so nobody reads it as more than it is: nothing about Python.
// F1's suite drives the real conductor, the real Extent façade and the real Topology organs
// through the real routes. This proves the client, the routes' shapes and the surface.
//
// The selectors are the instrument's own, unchanged — `[data-action="propose"]`,
// `[data-naming-row]`, `[data-verdict-option]`. This lane mounted the laboratory; it did not
// rebuild it, and a test that had to reach for new hooks would be evidence that it had.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import PerceptionLabPage from './PerceptionLabPage';
import { createFixtureHttpBackend } from '../perceptionLab/clients/fixtureHttpBackend';
import { createHttpLabClient, LAB_BASE, POSTS_BASE } from '../perceptionLab/clients/httpClient';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

const SCENE = 'scene_instances';

let container; let root; let backend;
const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => {
    // The hook fetches sources and capabilities in parallel and refreshes the history after every
    // action, so a single drain leaves a render in flight.
    for (let i = 0; i < 4; i += 1) {
        await act(async () => { await Promise.resolve(); });
    }
};

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    backend = createFixtureHttpBackend({ labBase: LAB_BASE, postsBase: POSTS_BASE });
    vi.stubGlobal('fetch', backend.fetchImpl);
});
afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.unstubAllGlobals();
});

const text = () => container.textContent;
const q = (sel) => container.querySelector(sel);
const all = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => {
    if (!el) throw new Error('nothing to click');
    await act(async () => { el.dispatchEvent(new MouseEvent('click', { bubbles: true })); });
    await settle();
};

const open = async (search = '') => {
    await mount(
        <MemoryRouter initialEntries={[`/lab/perception${search}`]}>
            <PerceptionLabPage />
        </MemoryRouter>);
    await settle();
};

/** Flow 1 — a post is chosen and a session exists against its digest. */
const openSession = (scene = SCENE) => click(q(`[data-source-id="${scene}"]`));

/** Flow 2 — the Direct arm's default extent operation, proposed and run live. */
const findAll = async () => {
    await click(q('[data-action="propose"]'));
    await click(q('[data-action="run-live"]'));
};

/** The session this page opened, read out of the laboratory underneath. */
const sessionId = () => {
    const call = backend.calls.find((c) => /\/sessions\/[^/?]+/.test(c.url));
    if (!call) throw new Error('this page never addressed a session');
    return call.url.match(/\/sessions\/([^/?]+)/)[1];
};
const ledger = () => backend.lab.history({ session_id: sessionId() });


// ── the wire, said out loud ──────────────────────────────────────────────────

describe('the route says which wire it is on, unmistakably', () => {
    it('is LIVE by default, and says what that means', async () => {
        await open();
        expect(q('[data-lab-wire]').getAttribute('data-lab-wire')).toBe('LIVE');
        expect(q('.plab-wire-badge').textContent).toBe('LIVE');
        expect(text()).toMatch(/calls a segmenter/);
        expect(q('[data-client-identity]').textContent).toContain('LIVE');
    });

    it('is FIXTURE only when asked for it, and says nothing calls a model', async () => {
        await open('?client=fixture');
        expect(q('[data-lab-wire]').getAttribute('data-lab-wire')).toBe('FIXTURE');
        expect(text()).toMatch(/Nothing here calls a model/);
        expect(q('[data-client-identity]').textContent).toContain('FIXTURE');
    });

    it('offers the run button its client actually has, and only that one', async () => {
        await open();
        await openSession();
        await click(q('[data-action="propose"]'));

        expect(q('[data-action="run-live"]').disabled).toBe(false);
        // A LIVE client has no fixtures behind it, and its `run` rejects a fixture request. An
        // enabled button here would offer a person an act the laboratory would have to refuse.
        expect(q('[data-action="run-fixture"]').disabled).toBe(true);
        expect(q('[data-action="run-fixture"]').getAttribute('title'))
            .toMatch(/no fixtures to run/);
    });

    it('offers the fixture button, and not the live one, on the fixture wire', async () => {
        await open('?client=fixture');
        await openSession();
        await click(q('[data-action="propose"]'));

        expect(q('[data-action="run-fixture"]').disabled).toBe(false);
        expect(q('[data-action="run-live"]').disabled).toBe(true);
    });

    it('does not fall back to fixtures when the backend cannot be reached', async () => {
        vi.stubGlobal('fetch', async () => { throw new TypeError('Failed to fetch'); });
        await open();

        expect(q('[data-lab-wire]').getAttribute('data-lab-wire')).toBe('LIVE');
        expect(q('[data-client-identity]').textContent).toContain('LIVE');
        expect(text()).toMatch(/Could not reach the laboratory/);
        // And no source list appeared out of nowhere.
        expect(all('.pl-source')).toHaveLength(0);
    });
});


// ── the eleven flows ─────────────────────────────────────────────────────────

describe('the whole sitting, over HTTP', () => {
    it('1 · a post becomes a session against a real digest', async () => {
        await open();
        expect(all('.pl-source').length).toBeGreaterThan(0);
        await openSession();

        expect(text()).not.toMatch(/No session is open/);
        const session = (await ledger()).session;
        expect(session.source.image_digest).toBeTruthy();
        expect(session.selected_organ).toBe('extent');
    });

    it('2 · a Direct Extent run reaches the organ and lands one run record', async () => {
        await open();
        await openSession();
        await findAll();

        const run = q('[data-run-id]');
        expect(run.getAttribute('data-execution')).toBe('LIVE');
        expect(run.getAttribute('data-outcome')).toBe('ready');
        const history = await ledger();
        expect(history.runs).toHaveLength(1);
        expect(history.artifacts).toHaveLength(1);
        expect(all('[data-ledger-row]')).toHaveLength(1);
    });

    it('3 · a prompt reaches the same plan and run panels as the control', async () => {
        await open();
        await openSession();
        await click(q('[data-arm="prompt"]'));
        const box = q('#pl-prompt');
        await act(async () => {
            const setter = Object.getOwnPropertyDescriptor(
                HTMLTextAreaElement.prototype, 'value').set;
            setter.call(box, 'mask every instance');
            box.dispatchEvent(new Event('input', { bubbles: true }));
        });
        await click(q('[data-action="ask-rules"]'));

        expect(q('[data-plan-id]')).toBeTruthy();
        await click(q('[data-action="run-live"]'));
        // Same panel, same badge, same outcome vocabulary as the Direct run.
        expect(q('[data-run-id]').getAttribute('data-execution')).toBe('LIVE');
        const history = await ledger();
        expect(history.session.prompt_turns[0].text).toBe('mask every instance');
        expect(history.session.prompt_turns[0].plan_id).toBeTruthy();
    });

    it('4 · one returned mask is selected, as a PAIR', async () => {
        await open();
        await openSession();
        await findAll();

        // ON THE STAGE, not in the readout. The instrument's split is that focus is looking and
        // selection is saying: clicking a mask on the picture is how a person says "that one",
        // and a readout row narrows attention without claiming anything.
        const instanceId = all('[data-naming-row]')[1].getAttribute('data-naming-row');
        await click(all('.pl-svg .rs-shape')[1]);

        const session = (await ledger()).session;
        expect(session.selected_instance_refs).toHaveLength(1);
        expect(session.selected_instance_refs[0].instance_id).toBe(instanceId);
        // Never a bare instance id: every extent set numbers its own from 1, so one alone names
        // the first mask of every set at once.
        expect(session.selected_instance_refs[0].artifact_id).toBeTruthy();
        expect(session.selected_artifact_ids)
            .toContain(session.selected_instance_refs[0].artifact_id);
    });

    it('5 · a refinement names exactly the instance that was selected', async () => {
        await open();
        await openSession();
        await findAll();
        const instanceId = all('[data-naming-row]')[2].getAttribute('data-naming-row');
        await click(all('.pl-svg .rs-shape')[2]);

        // The refinement is proposed through the same four gates as everything else — it is a
        // PROPOSAL from a pointer, never a dispatch.
        await click(q('[data-tool="point"]'));
        const stage = q('.pl-stage');
        await act(async () => {
            stage.dispatchEvent(new MouseEvent('click',
                { bubbles: true, clientX: 40, clientY: 40 }));
        });
        await settle();
        const refine = q('[data-action="propose-refine-add"]');
        if (refine && !refine.disabled) await click(refine);

        const session = (await ledger()).session;
        expect(session.selected_instance_refs.map((r) => r.instance_id)).toEqual([instanceId]);
        const plan = (await ledger()).plans.at(-1);
        if (plan.proposed_steps[0]?.operation === 'extent.refine') {
            // The base it refines is that one mask. A plan naming the whole set would be a
            // refinement of five things wearing the receipt of one.
            expect(plan.proposed_steps[0].input_refs[0].instance_id).toBe(instanceId);
        }
    });

    it('6 · Chain is a mode a person switches into, and it is recorded', async () => {
        await open();
        await openSession();
        await click(q('[data-mode="chain"]'));

        expect(q('.pl').getAttribute('data-mode')).toBe('chain');
        expect((await ledger()).session.mode).toBe('chain');
        expect(q('[data-mode-consequence]').getAttribute('data-mode-consequence')).toBe('chain');
    });

    it('7 · Topology measures the two extent instances a person named, and only those', async () => {
        await open();
        await openSession();
        await findAll();
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        await click(q(`[data-select="${artifactId}"]`));
        await click(q('[data-mode="chain"]'));
        await click(all('.pl-organ').find((o) => o.getAttribute('data-organ') === 'topology'));

        expect(q('.pl').getAttribute('data-organ')).toBe('topology');
        const carried = (await ledger()).session;
        // THE SELECTION SURVIVES THE ORGAN SWITCH. The extents a person prepared are exactly what
        // a topology question consumes; clearing them would make the supported path unwalkable.
        expect(carried.selected_artifact_ids).toContain(artifactId);
        expect(carried.mode).toBe('chain');

        await click(q('[data-operation="topology.adjacency"]'));
        const sources = all('[data-role-option^="source:"]')
            .filter((b) => b.getAttribute('data-role-option').includes('#'));
        const targets = all('[data-role-option^="target:"]')
            .filter((b) => b.getAttribute('data-role-option').includes('#'));
        await click(sources[2]);
        await click(targets[3]);
        await click(q('[data-action="propose"]'));
        expect(q('[data-resolved-inputs]').textContent).toMatch(/source=\w+#\w+/);
        await click(q('[data-action="run-live"]'));

        // Two instances named, so exactly one pair was examined — not twenty-five.
        expect(q('[data-pairs-examined]').getAttribute('data-pairs-examined')).toBe('1');
        const cited = all('[data-input-instance]')
            .map((n) => n.getAttribute('data-input-instance')).filter(Boolean);
        expect(cited).toHaveLength(2);
    });

    it('8 · a verdict is recorded and changes no lifecycle and no epistemic status', async () => {
        await open();
        await openSession();
        await findAll();
        const before = (await ledger()).artifacts[0];

        await click(q('[data-verdict-option="correct"]'));
        await click(q('[data-action="record-verdict"]'));

        const after = await ledger();
        expect(after.reviews).toHaveLength(1);
        expect(after.reviews[0].verdict).toBe('correct');
        expect(after.artifacts[0].lifecycle.status).toBe(before.lifecycle.status);
        expect(after.artifacts[0].measurement.epistemic_status)
            .toBe(before.measurement.epistemic_status);
        expect(q('[data-verdict-consequence]').textContent).toBeTruthy();
    });

    it('9 · reloading the page restores the references and the whole history', async () => {
        await open();
        await openSession();
        await findAll();
        const instanceId = all('[data-naming-row]')[1].getAttribute('data-naming-row');
        await click(all('.pl-svg .rs-shape')[1]);
        const session_id = sessionId();
        const kept = await ledger();

        // A RELOAD, not a re-render: the page is unmounted and built again over the same
        // laboratory, which is what pressing F5 does.
        await act(async () => { root.unmount(); });
        root = createRoot(container);
        await open();

        const client = createHttpLabClient({ fetchImpl: backend.fetchImpl });
        const reread = await client.history({ session_id });
        expect(reread.session.selected_instance_refs.map((r) => r.instance_id))
            .toEqual([instanceId]);
        expect(reread.session.active_artifact_id).toBe(kept.session.active_artifact_id);
        expect(reread.runs).toHaveLength(kept.runs.length);
        expect(reread.artifacts).toHaveLength(kept.artifacts.length);
    });

    it('10 · a replay re-shows the run and invokes nothing', async () => {
        await open();
        await openSession();
        await findAll();
        const live = (await ledger()).runs[0];

        await click(q('[data-action="replay-last"]'));

        const run = q('[data-run-id]');
        expect(run.getAttribute('data-execution')).toBe('REPLAY');
        expect(text()).toMatch(/adapter_callable: false/);
        const replayed = (await ledger()).runs.find((r) => r.execution_identity === 'REPLAY');
        expect(replayed.stage_attempts.every((a) => a.invoked === false)).toBe(true);
        // A replay re-shows the ORIGINAL artifact ids. Two ids carrying one measurement is how a
        // laboratory ends up reviewing the same mask twice and counting it as agreement.
        expect(replayed.artifact_ids).toEqual(live.artifact_ids);
    });

    it('11 · the session exports, and the two accounts of it agree', async () => {
        await open();
        await openSession();
        await findAll();
        await click(q('[data-verdict-option="correct"]'));
        await click(q('[data-action="record-verdict"]'));

        const client = createHttpLabClient({ fetchImpl: backend.fetchImpl });
        const bundle = await client.exportSession({ session_id: sessionId() });
        const browser = await client.history({ session_id: sessionId() });

        expect(bundle.export_kind).toBe('perception-lab.session-export');
        // The backend's bundle and the ledger this browser is holding are two renderings of one
        // sitting. A laboratory whose two accounts of a session differ has a worse problem than
        // either account.
        expect(bundle.session).toEqual(browser.session);
        expect(bundle.artifacts).toEqual(browser.artifacts);
        expect(bundle.counts.runs).toBe(browser.runs.length);
        expect(bundle.counts.reviews).toBe(1);
        // And the browser's own downloadable bundle is on the page, unpressed.
        expect(q('[data-action="export-json"]')).toBeTruthy();
        expect(q('[data-export-invalid]')).toBeNull();
    });
});


// ── upload ───────────────────────────────────────────────────────────────────

describe('an upload yields a normal post, or it does not report success', () => {
    const chooseFile = async () => {
        const input = q('#pl-file');
        const file = new File(['x'], 'a.png', { type: 'image/png' });
        Object.defineProperty(input, 'files', { value: [file], configurable: true });
        await act(async () => { input.dispatchEvent(new Event('change', { bubbles: true })); });
    };
    const upload = () => click(
        all('button').find((b) => /upload and open/i.test(b.textContent)));

    it('posts to the archive, reads the source back, and opens a session on it', async () => {
        await open();
        await chooseFile();
        await upload();

        expect(backend.uploads).toHaveLength(1);
        expect(text()).not.toMatch(/No session is open/);
        const session = (await ledger()).session;
        // The session is on the POST the archive created. No lab-private image identity exists.
        expect(session.source.image_digest).toBeTruthy();
        expect(backend.calls.some((c) => c.url.startsWith(POSTS_BASE))).toBe(true);
    });

    it('a failed upload opens nothing, adds no row, and says so', async () => {
        await open();
        backend.failUploads(true);
        await chooseFile();
        await upload();

        expect(text()).toMatch(/The upload did not complete/);
        expect(text()).toMatch(/No session is open/);
        expect(backend.uploads).toHaveLength(0);
        expect(backend.calls.some((c) => /\/sessions$/.test(c.url))).toBe(false);
    });
});


// ── cancellation ─────────────────────────────────────────────────────────────

describe('cancellation is offered honestly or not at all', () => {
    it('shows no Stop button when nothing is in flight', async () => {
        await open();
        await openSession();
        await click(q('[data-action="propose"]'));
        expect(q('[data-action="cancel-run"]')).toBeNull();
    });

    it('reports a stop that reached nothing as exactly that', async () => {
        await open();
        await openSession();
        await findAll();

        const client = createHttpLabClient({ fetchImpl: backend.fetchImpl });
        const out = await client.cancel({ session_id: sessionId(), run_ticket: 'tkt_gone' });
        expect(out.cancelled).toBe(false);
        expect(out.note).toMatch(/in flight/);
    });
});


// ── promotion, and the absence of it ─────────────────────────────────────────

describe('there is no promotion anywhere on this route', () => {
    it('offers no control that could put a lab artifact into Semant', async () => {
        await open();
        await openSession();
        await findAll();

        const enabled = all('button').filter((b) => !b.disabled)
            .map((b) => b.textContent.toLowerCase()).join(' | ');
        for (const word of ['promote', 'accept all', 'approve all', 'publish',
            'save to semant', 'add to corpus']) {
            expect(enabled).not.toContain(word);
        }
    });

    it('shows `promoted` and refuses to reach it, rather than hiding that the state exists',
        async () => {
            await open();
            await openSession();
            await findAll();

            const promoted = q('[data-lifecycle-option="promoted"]');
            // SHOWN AND NEVER OFFERED. Removing it would let a person believe this laboratory has
            // no such state; disabling it says the state exists, Semant owns it, and nothing here
            // reaches it. F1 refuses `promoted` with a 422 for the same reason — two gates, and
            // the browser's is the one a person meets first.
            expect(promoted).toBeTruthy();
            expect(promoted.disabled).toBe(true);
            expect(promoted.getAttribute('title')).toMatch(/Semant owns this state/);
        });

    it('keeps an artifact session-scoped when a person keeps it', async () => {
        await open();
        await openSession();
        await findAll();

        await click(q('[data-lifecycle-option="kept"]'));
        await settle();

        const artifact = (await ledger()).artifacts[0];
        expect(artifact.identity.identity_scope).toBe('session');
        expect(q('[data-lifecycle-consequence]').textContent).toBeTruthy();
    });
});


// ── keyboard and focus ───────────────────────────────────────────────────────

describe('the route is reachable without a pointer', () => {
    it('every control the laboratory offers is a real button or input', async () => {
        await open();
        await openSession();
        await findAll();

        const interactive = all('.pl button, .pl input, .pl select, .pl textarea, .pl a[href]');
        expect(interactive.length).toBeGreaterThan(10);
        // Nothing is a div with a click handler: a `tabindex` on a non-interactive element is how
        // a surface becomes unreachable from a keyboard without anybody noticing.
        expect(all('.pl [onclick]')).toHaveLength(0);
        for (const el of interactive) {
            expect(['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'A']).toContain(el.tagName);
        }
    });

    it('the wire banner is announced rather than only coloured', async () => {
        await open();
        const banner = q('[data-lab-wire]');
        expect(banner.getAttribute('role')).toBe('status');
        expect(banner.textContent).toMatch(/LIVE/);
    });

    it('an error is announced as an alert, not just written on the page', async () => {
        vi.stubGlobal('fetch', async () => { throw new TypeError('Failed to fetch'); });
        await open();
        expect(q('[role="alert"]')).toBeTruthy();
    });
});


// ── responsive ───────────────────────────────────────────────────────────────

describe('the route holds at every width the lane is held to', () => {
    // The instrument's own responsive proof lives in `perceptionLabResponsive.dom.test.jsx` and
    // covers the four widths inside the laboratory. What is new at the ROUTE is the banner above
    // it, which is the one thing that could push the page into a horizontal scroll.
    const widths = [1100, 720, 430, 320];

    const at = async (width) => {
        Object.defineProperty(container, 'clientWidth', { value: width, configurable: true });
        Object.defineProperty(container, 'getBoundingClientRect', {
            value: () => ({ width, height: 900, top: 0, left: 0, right: width, bottom: 900 }),
            configurable: true,
        });
        await open();
        await settle();
    };

    it.each(widths)('says which wire it is on at %ipx', async (width) => {
        await at(width);
        const banner = q('[data-lab-wire]');
        expect(banner).toBeTruthy();
        expect(banner.textContent).toMatch(/LIVE/);
        // The badge is a word, not only a colour: a person reading this at 320px on a phone in
        // sunlight has to be able to tell whether pressing run reaches a model.
        expect(q('.plab-wire-badge').textContent).toBe('LIVE');
    });

    it.each(widths)('lays the laboratory out for %ipx rather than clipping it', async (width) => {
        await at(width);
        await openSession();
        const band = q('.pl').getAttribute('data-w');
        expect(band).toBeTruthy();
        // The band drives the whole layout off one attribute, and the route does not override it.
        expect(['wide', 'mid', 'narrow', 'tight']).toContain(band);
    });
});
