/**
 * AGENT-DEMO — the run client. The only module that knows a network exists.
 *
 * Everything else on this surface takes a RunView and renders it, so the swap from Lane B's
 * fixture to Lane A's live routes happens HERE and nowhere else. That is the point of the file:
 * `createRunClient()` talks to the backend, `createMockRunClient()` walks the fixture, and the
 * page cannot tell them apart. The component tests use the mock; nothing in them is a stub of a
 * thing the real client does differently.
 *
 * Transport, per the contract: SSE for progress, poll as the FALLBACK, both returning the same
 * shape. The fallback is not decorative — EventSource cannot carry the API-key header this app
 * installs, corporate proxies buffer text/event-stream into uselessness, and a demo that dies
 * behind either is worse than one that polls. So `watch()` tries the stream and falls back on
 * its first error, and the caller never learns which it got.
 */
import { API_URL } from '../config/api';
import { normalizeRunView, startRunBody, IS_TERMINAL } from './runContract';

const BASE = `${API_URL}/api/v1/runs`;

const POLL_MS = 1200;

async function asJson(res) {
    if (!res.ok) {
        let detail = '';
        try { detail = (await res.json())?.detail || ''; } catch { /* body may not be json */ }
        throw new Error(detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
}

/** The live client. */
export function createRunClient({ fetchImpl = null } = {}) {
    const f = fetchImpl || ((...a) => globalThis.fetch(...a));

    async function start(input) {
        const data = await asJson(await f(BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(startRunBody(input)),
        }));
        return String(data?.run_id || '');
    }

    async function get(runId) {
        return normalizeRunView(await asJson(await f(`${BASE}/${runId}`)));
    }

    async function answer(runId, text) {
        return normalizeRunView(await asJson(await f(`${BASE}/${runId}/answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answer: String(text) }),
        })));
    }

    /**
     * Watch a run to a terminal state (or to `awaiting_answer`, which is terminal FOR THE WATCH —
     * the run cannot advance until a human answers, so holding a stream open would be a
     * connection spent waiting on a person).
     *
     * Returns an unsubscribe. `onView` fires per delta; `onError` only for a failure that ends
     * the watch, never for the stream error that merely triggers the fallback.
     */
    function watch(runId, { onView, onError, pollMs = POLL_MS } = {}) {
        let stopped = false;
        let timer = null;
        let source = null;

        const emit = (raw) => {
            if (stopped) return;
            const view = normalizeRunView(raw);
            onView?.(view);
            // `awaiting_answer` ends the watch too: the page restarts it after POSTing an answer.
            if (IS_TERMINAL(view.status) || view.status === 'awaiting_answer') stop();
        };

        function stop() {
            stopped = true;
            if (timer) { clearTimeout(timer); timer = null; }
            if (source) { try { source.close(); } catch { /* already closed */ } source = null; }
        }

        async function poll() {
            if (stopped) return;
            try {
                emit(await asJson(await f(`${BASE}/${runId}`)));
            } catch (e) {
                stop();
                onError?.(e);
                return;
            }
            if (!stopped) timer = setTimeout(poll, pollMs);
        }

        // Try the stream; fall back to polling the moment it complains.
        if (typeof globalThis.EventSource === 'function') {
            try {
                source = new globalThis.EventSource(`${BASE}/${runId}/events`);
                source.onmessage = (ev) => {
                    try { emit(JSON.parse(ev.data)); } catch { /* a malformed frame is not fatal */ }
                };
                source.onerror = () => {
                    if (stopped) return;
                    try { source.close(); } catch { /* noop */ }
                    source = null;
                    poll();                       // the fallback, silently
                };
            } catch {
                poll();
            }
        } else {
            poll();
        }

        return stop;
    }

    return { start, get, answer, watch };
}

/**
 * The mock. Walks a scripted sequence of RunViews so the whole surface — including the
 * ask→answer→continue thread — can be driven with no backend.
 *
 * `answer()` advances to the post-answer view, which is what makes the A3 round-trip testable:
 * the same run id, resumed, not a new run.
 */
export function createMockRunClient({ script = [], afterAnswer = null, stepMs = 0 } = {}) {
    let i = 0;
    let answered = false;
    const answers = [];

    // Once answered, the run HAS moved on — every subsequent read returns the resumed view, not
    // the question again. Without this the page re-watches after POSTing an answer, the mock
    // replays the `awaiting_answer` entry still sitting at the end of the script, and the
    // question reappears under the user. That is a mock artefact, but the bug it would mask is
    // real, so the mock is made faithful rather than the assertion loosened.
    const viewAt = (n) => normalizeRunView(
        (answered && afterAnswer) ? afterAnswer : script[Math.min(n, script.length - 1)]);

    async function start() {
        i = 0;
        answered = false;
        return viewAt(0).run_id || 'run_mock';
    }

    async function get() {
        return viewAt(i);
    }

    async function answer(runId, text) {
        answers.push(String(text));
        answered = true;
        const next = afterAnswer ? normalizeRunView(afterAnswer) : viewAt(script.length - 1);
        i = script.length - 1;
        return next;
    }

    function watch(runId, { onView } = {}) {
        let stopped = false;
        const tick = () => {
            if (stopped) return;
            const view = viewAt(i);
            onView?.(view);
            if (IS_TERMINAL(view.status) || view.status === 'awaiting_answer') return;
            // End of script with a still-running view: deliver it and STOP. `viewAt` clamps to
            // the last entry, so advancing past it would re-emit the same non-terminal view
            // forever — which starves the microtask queue and kills the worker rather than
            // failing a test. A mock that hangs is worse than one that ends early.
            if (i >= script.length - 1) return;
            i += 1;
            if (stepMs > 0) setTimeout(tick, stepMs); else queueMicrotask(tick);
        };
        if (stepMs > 0) setTimeout(tick, stepMs); else queueMicrotask(tick);
        return () => { stopped = true; };
    }

    return { start, get, answer, watch, _answers: answers, _answered: () => answered };
}
