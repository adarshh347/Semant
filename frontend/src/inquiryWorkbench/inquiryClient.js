/**
 * INQUIRY WORKBENCH — the session client. The only module here that knows a network exists.
 *
 * Same shape as `agentDemo/runClient.js` and `cognition/cognitionClient.js`, on purpose: every
 * component below takes a normalised session and renders it, so the mock and the live routes are
 * interchangeable and the page cannot tell them apart.
 *
 * ## Why this is not `createRunClient` with a different base URL
 *
 * The lane brief's rule is that cloning network semantics under new names needs a reason. Here it
 * is, and it is three concrete differences rather than a preference:
 *
 *   1. `runClient.watch` treats `awaiting_answer` as the one blocking state. This surface's
 *      lifecycle has twelve states, four of them terminal, and one unrecognised state must keep
 *      the watch alive rather than end it.
 *   2. A decision POST carries `expected_revision` and can come back 409. `runClient.answer`
 *      throws a bare `Error` on any non-2xx, which would collapse a stale-revision conflict into
 *      the same red box as a dropped connection. They need different UI, so they need different
 *      errors.
 *   3. `BASE` is captured inside `createRunClient`'s closure, so parameterising it would mean
 *      editing a file outside this lane's write set.
 *
 * What is genuinely shared is the transport shape (SSE with a poll fallback) and the reason for
 * it, which is documented there and not repeated here.
 */
import { API_URL } from '../config/api';
import { normalizeSession, normalizeFeatures, startInquiryBody, decisionResponseBody,
    SHOULD_KEEP_WATCHING } from './inquiryContract';

const BASE = `${API_URL}/api/v1/inquiries`;

const POLL_MS = 1200;

/**
 * A rejected write, with the reason kept machine-readable.
 *
 * `conflict` exists so the page can tell "your view of the session was stale" from "the network
 * failed" without string-matching a message. The two need opposite responses from the person: one
 * is re-read and try again with the same intent, the other is wait and retry unchanged.
 */
export class InquiryRequestError extends Error {
    constructor(message, { status = 0, conflict = false, session = null } = {}) {
        super(message);
        this.name = 'InquiryRequestError';
        this.status = status;
        this.conflict = conflict;
        // A 409 body may carry the server's current session. If it does, the page can refresh
        // from the rejection itself rather than issuing a second read.
        this.session = session;
    }
}

async function asJson(res) {
    if (res.ok) return res.json();

    let body = null;
    try { body = await res.json(); } catch { /* body may not be json */ }
    const detail = (body && (body.detail || body.message)) || '';
    const conflict = res.status === 409;
    throw new InquiryRequestError(
        detail || `${res.status} ${res.statusText}`,
        {
            status: res.status,
            conflict,
            session: conflict && body && body.session ? normalizeSession(body.session) : null,
        },
    );
}

/** The live client. */
export function createInquiryClient({ fetchImpl = null } = {}) {
    const f = fetchImpl || ((...a) => globalThis.fetch(...a));

    async function start(input) {
        const data = await asJson(await f(BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(startInquiryBody(input)),
        }));
        return normalizeSession(data);
    }

    async function get(sessionId) {
        return normalizeSession(await asJson(await f(`${BASE}/${sessionId}`)));
    }

    /**
     * What this deployment will serve, from the LISTING route rather than a route of its own.
     *
     * The entry form has to know before a session exists whether the temporary scoped rehearsal is
     * available — a checkbox that is always shown and 422s half the time is a control that lies
     * about what it does — and the listing is the one route a client can call with nothing in hand.
     *
     * It THROWS rather than returning a default, and the caller shows no control. An unreachable
     * API and an older server both mean nobody declared the feature, and the absence of a
     * declaration is not a declaration.
     */
    async function features() {
        const data = await asJson(await f(`${BASE}?limit=1`));
        return normalizeFeatures(data && data.features);
    }

    /**
     * Answer an open decision. Returns the session AS THE SERVER NOW HAS IT — the same session id,
     * resumed, never a new one.
     */
    async function respond(sessionId, response) {
        const data = await asJson(await f(`${BASE}/${sessionId}/decisions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(decisionResponseBody(response)),
        }));
        return normalizeSession(data);
    }

    /**
     * Watch a session until it is finished or blocked on a person. Returns an unsubscribe.
     *
     * `onError` fires only for a failure that ENDS the watch, never for the stream error that
     * merely triggers the poll fallback.
     */
    function watch(sessionId, { onSession, onError, pollMs = POLL_MS } = {}) {
        let stopped = false;
        let timer = null;
        let source = null;

        const emit = (raw) => {
            if (stopped) return;
            const session = normalizeSession(raw);
            onSession?.(session);
            if (!SHOULD_KEEP_WATCHING(session.state.value)) stop();
        };

        function stop() {
            stopped = true;
            if (timer) { clearTimeout(timer); timer = null; }
            if (source) { try { source.close(); } catch { /* already closed */ } source = null; }
        }

        async function poll() {
            if (stopped) return;
            try {
                emit(await asJson(await f(`${BASE}/${sessionId}`)));
            } catch (e) {
                stop();
                onError?.(e);
                return;
            }
            if (!stopped) timer = setTimeout(poll, pollMs);
        }

        if (typeof globalThis.EventSource === 'function') {
            try {
                source = new globalThis.EventSource(`${BASE}/${sessionId}/events`);
                source.onmessage = (ev) => {
                    try { emit(JSON.parse(ev.data)); } catch { /* a malformed frame is not fatal */ }
                };
                source.onerror = () => {
                    if (stopped) return;
                    try { source.close(); } catch { /* noop */ }
                    source = null;
                    poll();                        // the fallback, silently
                };
            } catch {
                poll();
            }
        } else {
            poll();
        }

        return stop;
    }

    return { start, get, respond, watch, features, live: true };
}

/**
 * The mock. Walks a scripted sequence of sessions so the whole surface — including the
 * pause → respond → resume thread — can be driven with no backend.
 *
 * `conflictOnce` makes the first response come back 409 and the second succeed, which is the only
 * honest way to test that a conflict does not eat the person's input: the page must still hold
 * their selection when the retry goes out.
 */
export function createMockInquiryClient({
    script = [], afterResponse = null, conflictOnce = false, conflictSession = null,
    features: declaredFeatures = null,
} = {}) {
    let i = 0;
    let responded = false;
    let conflicted = false;
    const responses = [];
    const starts = [];

    // Once answered the session HAS moved on, so every later read returns the resumed view rather
    // than replaying the open decision under the person. Same faithfulness fix `createMockRunClient`
    // documents: the mock is made accurate rather than the assertion loosened.
    const sessionAt = (n) => normalizeSession(
        (responded && afterResponse) ? afterResponse : script[Math.min(n, script.length - 1)]);

    async function start(input) {
        i = 0;
        responded = false;
        // KEPT, not ignored. A mock that dropped its input would let a test assert the surface
        // sends `execution_scope` while the body it built went nowhere.
        starts.push(startInquiryBody(input || {}));
        return sessionAt(0);
    }

    async function get() {
        return sessionAt(i);
    }

    async function respond(sessionId, response) {
        if (conflictOnce && !conflicted) {
            conflicted = true;
            throw new InquiryRequestError(
                'This session moved on while you were deciding.',
                {
                    status: 409,
                    conflict: true,
                    session: conflictSession ? normalizeSession(conflictSession) : null,
                },
            );
        }
        responses.push(decisionResponseBody(response));
        responded = true;
        i = script.length - 1;
        return afterResponse ? normalizeSession(afterResponse) : sessionAt(i);
    }

    function watch(sessionId, { onSession } = {}) {
        let stopped = false;
        const tick = () => {
            if (stopped) return;
            const session = sessionAt(i);
            onSession?.(session);
            if (!SHOULD_KEEP_WATCHING(session.state.value)) return;
            // End of script on a still-running session: deliver it and STOP. `sessionAt` clamps,
            // so advancing past the end would re-emit the same view forever and starve the
            // microtask queue — a hanging mock is worse than one that ends early.
            if (i >= script.length - 1) return;
            i += 1;
            queueMicrotask(tick);
        };
        queueMicrotask(tick);
        return () => { stopped = true; };
    }

    /** Undeclared by default, so a test that says nothing gets a surface offering nothing. */
    async function features() {
        if (declaredFeatures === null) throw new InquiryRequestError('no feature declaration',
            { status: 404 });
        return normalizeFeatures(declaredFeatures);
    }

    return {
        start, get, respond, watch, features, live: false,
        _responses: responses,
        _starts: starts,
        _responded: () => responded,
    };
}
