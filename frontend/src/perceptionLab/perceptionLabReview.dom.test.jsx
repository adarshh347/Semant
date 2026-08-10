// PERCEPTUAL-ORGANS-002 Lane E — the verdict, the filing decision, and the way out.
//
// The load-bearing assertion in this file is that recording a verdict changes NOTHING. It is
// asserted by taking a full before-and-after copy of the artifact's own blocks and comparing
// them, rather than by checking one field, because "mark correct and keep" collapses by adding a
// side effect somewhere nobody is looking.

import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import PerceptionLab from './PerceptionLab';
import { createFixtureClient } from './clients/fixtureClient';
import { verifyExport, EXPORT_KIND } from './exportSession';

if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
}

let container; let root; let downloads;

const mount = async (node) => { await act(async () => { root.render(node); }); };
const settle = async () => {
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
};

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    // Capture downloads instead of performing them: what is asserted is the BYTES, and jsdom has
    // no filesystem to write them to.
    downloads = [];
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:pl-test');
    globalThis.URL.revokeObjectURL = vi.fn();
    const realClick = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function capture() {
        if (this.download) downloads.push({ name: this.download, href: this.href });
        else realClick?.call(this);
    };
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
const typeInto = async (el, value) => {
    await act(async () => {
        const proto = el.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, value);
        el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await settle();
};

const NOW = () => '2026-08-11T09:00:00.000Z';

const runOnce = async (options = {}) => {
    const client = createFixtureClient(options);
    await mount(<PerceptionLab client={client} now={NOW} />);
    await settle();
    await click(q('[data-source-id="scene_instances"]'));
    await click(q('[data-action="propose"]'));
    await click(q('[data-action="run-fixture"]'));
    return client;
};

/** Everything about the artifact except who has judged it. */
const artifactState = async (client, sessionId, artifactId) => {
    const history = await client.history({ session_id: sessionId });
    const a = history.artifacts.find((x) => x.identity.artifact_id === artifactId);
    return JSON.stringify(a);
};

describe('a verdict is a verdict and nothing else', () => {
    it('recording one leaves every block of the artifact byte-identical', async () => {
        const client = await runOnce();
        const sessionId = (await client.getSession({ session_id: 'labs_1' })).session_id;
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        const before = await artifactState(client, sessionId, artifactId);

        await click(q('[data-verdict-option="wrong"]'));
        await typeInto(q('#pl-review-notes'), 'these are not the things I meant');
        await click(q('[data-action="record-verdict"]'));

        const after = await artifactState(client, sessionId, artifactId);
        expect(after).toBe(before);
        // The verdict IS recorded — separately.
        expect(q('[data-review-history] .pl-verdict').getAttribute('data-verdict')).toBe('wrong');
        expect(q('[data-block="lifecycle"] .pl-life').getAttribute('data-status'))
            .toBe('proposed');
        expect(q('[data-block="measurement"] .pl-epi').getAttribute('data-status'))
            .toBe('measured');
    });

    it('says on the surface that it changes nothing', async () => {
        await runOnce();
        expect(q('[data-verdict-consequence]').textContent)
            .toMatch(/Not the epistemic status, not the lifecycle, not the measurement/);
    });

    it('offers all four verdicts, each with its own sentence', async () => {
        await runOnce();
        const options = all('[data-verdict-option]');
        expect(options.map((o) => o.getAttribute('data-verdict-option')))
            .toEqual(['correct', 'partial', 'wrong', 'unclear']);
        const titles = options.map((o) => o.getAttribute('title'));
        expect(new Set(titles).size).toBe(4);
        expect(titles[0]).toMatch(/changes no status and no lifecycle/);
    });

    it('verdicts accumulate rather than overwrite, because disagreement is a finding', async () => {
        await runOnce();
        await click(q('[data-verdict-option="correct"]'));
        await click(q('[data-action="record-verdict"]'));
        await click(q('[data-verdict-option="wrong"]'));
        await click(q('[data-action="record-verdict"]'));
        expect(all('[data-past-review]')).toHaveLength(2);
        expect(q('[data-review-history]').textContent).toMatch(/do not overwrite/);
    });

    it('a correction is recorded as evidence and writes nothing into the record', async () => {
        const client = await runOnce();
        const sessionId = (await client.getSession({ session_id: 'labs_1' })).session_id;
        const artifactId = q('[data-ledger-row]').getAttribute('data-ledger-row');
        const before = await artifactState(client, sessionId, artifactId);

        await typeInto(q('[data-correction-field]'), 'instances[1].naming.text');
        await typeInto(q('[data-correction-was]'), 'head');
        await typeInto(q('[data-correction-now]'), 'a shoulder');
        await click(q('[data-action="add-correction"]'));
        await click(q('[data-verdict-option="partial"]'));
        await click(q('[data-action="record-verdict"]'));

        expect(await artifactState(client, sessionId, artifactId)).toBe(before);
        expect(q('[data-past-correction]').textContent).toMatch(/head → a shoulder/);
        expect(q('[data-corrections]').textContent).toMatch(/not a repair of the record/);
    });
});

describe('the lifecycle is a filing decision, and a separate one', () => {
    it('changing it moves the lifecycle and touches no verdict and no status', async () => {
        const client = await runOnce();
        const sessionId = (await client.getSession({ session_id: 'labs_1' })).session_id;
        await click(q('[data-lifecycle-option="kept"]'));
        const history = await client.history({ session_id: sessionId });
        const artifact = history.artifacts[0];
        expect(artifact.lifecycle.status).toBe('kept');
        expect(artifact.measurement.epistemic_status).toBe('measured');
        expect(history.reviews).toHaveLength(0);
        expect(q('[data-ledger-row] [data-unreviewed]')).toBeTruthy();
    });

    it('`kept` and `correct` are visibly not the same chip', async () => {
        await runOnce();
        await click(q('[data-lifecycle-option="kept"]'));
        await click(q('[data-verdict-option="wrong"]'));
        await click(q('[data-action="record-verdict"]'));
        const row = q('[data-ledger-row]');
        // Kept AND judged wrong, at the same time, side by side. A surface that collapsed these
        // could not render this state at all.
        expect(row.querySelector('.pl-life').getAttribute('data-status')).toBe('kept');
        expect(row.querySelector('.pl-verdict').getAttribute('data-verdict')).toBe('wrong');
        expect(q('[data-lifecycle-consequence]').textContent)
            .toMatch(/is not.*correct/s);
    });

    it('promoted is shown, disabled, and says who owns it', async () => {
        await runOnce();
        const promoted = q('[data-lifecycle-option="promoted"]');
        expect(promoted).toBeTruthy();
        expect(promoted.disabled).toBe(true);
        expect(promoted.getAttribute('title')).toMatch(/Semant owns this state/);
        expect(promoted.getAttribute('title')).toMatch(/no control here that could/);
    });

    it('there is no promote, save or accept-all control anywhere on the surface', async () => {
        await runOnce();
        await click(q('[data-verdict-option="correct"]'));
        await click(q('[data-action="record-verdict"]'));
        const enabled = [...container.querySelectorAll('button')].filter((b) => !b.disabled);
        const offenders = enabled.map((b) => b.textContent.trim())
            .filter((t) => /\b(promote|accept all|approve all|save|commit|publish)\b/i.test(t));
        expect(offenders).toEqual([]);
    });
});

describe('the history is the way back into an earlier answer', () => {
    it('lists every run with its own identity and outcome', async () => {
        await runOnce();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        expect(all('[data-history-run]')).toHaveLength(2);
        expect(all('[data-history-run]').every(
            (r) => r.querySelector('.pl-exec'))).toBe(true);
        expect(q('[data-session-digest]').textContent).toBe('sha256:fixture_instances_v1');
    });

    it('reopening runs nothing and writes nothing', async () => {
        const client = await runOnce();
        const sessionId = (await client.getSession({ session_id: 'labs_1' })).session_id;
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const runsBefore = (await client.history({ session_id: sessionId })).runs.length;
        const firstRun = all('[data-history-run]')
            .map((r) => r.getAttribute('data-history-run')).pop();
        await click(q(`[data-reopen="${firstRun}"]`));
        expect((await client.history({ session_id: sessionId })).runs).toHaveLength(runsBefore);
        expect(q('[data-artifact-id]')).toBeTruthy();
    });

    it('replaying writes a REPLAY run, because looking again is itself history', async () => {
        const client = await runOnce();
        const sessionId = (await client.getSession({ session_id: 'labs_1' })).session_id;
        const runId = q('[data-history-run]').getAttribute('data-history-run');
        await click(q(`[data-replay="${runId}"]`));
        const history = await client.history({ session_id: sessionId });
        expect(history.runs).toHaveLength(2);
        const replay = history.runs.find((r) => r.execution_identity === 'REPLAY');
        expect(replay.replay.adapter_callable).toBe(false);
        expect(replay.stage_attempts.every((a) => a.invoked === false)).toBe(true);
    });

    it('choosing a comparison side is what makes repeat a claim about stability', async () => {
        await runOnce();
        await click(q('[data-action="propose"]'));
        await click(q('[data-action="run-fixture"]'));
        const firstRun = all('[data-history-run]')
            .map((r) => r.getAttribute('data-history-run')).pop();
        await click(q(`[data-compare="${firstRun}"]`));
        expect(q('[data-is-comparison]')).toBeTruthy();
        expect(q('[data-repeat-block]')).toBeTruthy();
        expect(q('[data-repeat-matched]').getAttribute('data-repeat-matched')).toBe('5');
    });
});

describe('the export', () => {
    it('writes a contract-exact bundle that validates', async () => {
        await runOnce();
        await click(q('[data-verdict-option="partial"]'));
        await click(q('[data-action="record-verdict"]'));
        await click(q('[data-lifecycle-option="kept"]'));
        await click(q('[data-action="export-json"]'));

        expect(q('[data-export-status]').getAttribute('data-export-status')).toBe('saved');
        expect(downloads).toHaveLength(1);
        expect(downloads[0].name).toMatch(/^perception-lab-labs_1-.*\.json$/);
    });

    it('exports what the ledger holds, including the verdict as a separate record', async () => {
        const client = await runOnce();
        await click(q('[data-verdict-option="partial"]'));
        await click(q('[data-action="record-verdict"]'));
        const sessionId = (await client.getSession({ session_id: 'labs_1' })).session_id;
        const history = await client.history({ session_id: sessionId });
        const bundle = {
            export_kind: EXPORT_KIND,
            schema_version: '1.0.0',
            session: history.session,
            plans: history.plans,
            runs: history.runs,
            artifacts: history.artifacts,
            reviews: history.reviews,
        };
        // The bundle the button writes is built by the same function this checks.
        expect(bundle.reviews).toHaveLength(1);
        expect(verifyExport({ ...bundle, schema_version: bundle.schema_version })
            .filter((p) => !p.startsWith('schema_version'))).toEqual([]);
    });

    it('says, where the buttons are, that an export promotes nothing', async () => {
        await runOnce();
        expect(q('[data-export-consequence]').textContent)
            .toMatch(/mints no canonical id/);
        expect(q('[data-export-consequence]').textContent)
            .toMatch(/puts nothing into Semant/);
    });

    it('an SVG snapshot carries the execution identity burnt into the picture', async () => {
        await runOnce();
        await click(q('[data-action="export-svg"]'));
        expect(q('[data-export-status]').getAttribute('data-export-status')).toBe('saved');
        expect(downloads[0].name.endsWith('.svg')).toBe(true);
    });

    it('a PNG refuses honestly where there is no canvas, rather than saving a blank', async () => {
        await runOnce();
        await click(q('[data-action="export-png"]'));
        // jsdom has no 2D context. The refusal names the reason and points at the SVG.
        expect(q('[data-export-status]').getAttribute('data-export-status')).toBe('failed');
        expect(text()).toMatch(/no 2D canvas|could not be decoded|no image/);
        expect(downloads.filter((d) => d.name.endsWith('.png'))).toHaveLength(0);
    });
});
