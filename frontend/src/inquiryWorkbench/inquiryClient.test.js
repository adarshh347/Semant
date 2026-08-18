/**
 * INQUIRY WORKBENCH — the client, asserted against a fake fetch.
 *
 * The live client is exercised here rather than only the mock. The mock's job is to drive the
 * page; this suite's job is to prove the thing that will actually talk to Lane D sends the right
 * bodies and tells a 409 apart from every other failure.
 */
import { describe, it, expect, vi } from 'vitest';
import { createInquiryClient, createMockInquiryClient, InquiryRequestError }
    from './inquiryClient.js';
import { consultFixture, respondedFixture, conflictSessionFixture } from './inquiryFixtures.js';

const ok = (body) => ({
    ok: true, status: 200, statusText: 'OK', json: async () => body,
});

const fail = (status, body) => ({
    ok: false, status, statusText: 'Conflict', json: async () => body,
});

describe('the live client', () => {
    it('POSTs prompt, images and mode, and returns a normalised session', async () => {
        const fetchImpl = vi.fn(async () => ok(consultFixture()));
        const client = createInquiryClient({ fetchImpl });

        const session = await client.start({
            imageIds: ['p1', 'p2'], prompt: '  how does it gather?  ', mode: 'consult',
        });

        const [url, init] = fetchImpl.mock.calls[0];
        expect(url).toMatch(/\/api\/v1\/inquiries$/);
        expect(init.method).toBe('POST');
        expect(JSON.parse(init.body)).toEqual({
            prompt: 'how does it gather?', image_ids: ['p1', 'p2'], mode: 'consult',
            // Sent on every start, including the default one. See `startInquiryBody`: a request
            // that says what it wants does not depend on both sides agreeing about an omission.
            execution_scope: 'full',
        });
        expect(session.session_id).toBe('inqs_fixture_1');
        expect(session.state.value).toBe('awaiting_user');
    });

    it('reads a session by id', async () => {
        const fetchImpl = vi.fn(async () => ok(consultFixture()));
        await createInquiryClient({ fetchImpl }).get('inqs_fixture_1');
        expect(fetchImpl.mock.calls[0][0]).toMatch(/\/inquiries\/inqs_fixture_1$/);
    });

    it('POSTs a decision to the SAME session, carrying the expected revision', async () => {
        const fetchImpl = vi.fn(async () => ok(respondedFixture()));
        const client = createInquiryClient({ fetchImpl });

        const next = await client.respond('inqs_fixture_1', {
            decisionId: 'dec_extent_grain', responseId: 'res_1',
            optionId: 'opt_whole', expectedRevision: 3,
        });

        const [url, init] = fetchImpl.mock.calls[0];
        expect(url).toMatch(/\/inquiries\/inqs_fixture_1\/decisions$/);
        expect(JSON.parse(init.body)).toEqual({
            decision_id: 'dec_extent_grain', response_id: 'res_1', action: 'select',
            selected_option_id: 'opt_whole', expected_revision: 3,
        });
        // the same session, resumed — not a new one
        expect(next.session_id).toBe('inqs_fixture_1');
        expect(next.revision).toBe(5);
    });

    it('marks a 409 as a CONFLICT and carries the server session back with it', async () => {
        const fetchImpl = vi.fn(async () => fail(409, {
            detail: 'expected revision 3, session is at 6',
            session: conflictSessionFixture(),
        }));
        const client = createInquiryClient({ fetchImpl });

        const err = await client.respond('inqs_fixture_1', {
            decisionId: 'dec_extent_grain', responseId: 'res_1', expectedRevision: 3,
        }).catch((e) => e);

        expect(err).toBeInstanceOf(InquiryRequestError);
        expect(err.conflict).toBe(true);
        expect(err.status).toBe(409);
        expect(err.message).toMatch(/session is at 6/);
        // the page can refresh from the rejection itself rather than issuing a second read
        expect(err.session.revision).toBe(6);
    });

    it('a 500 is NOT a conflict, so the page cannot confuse the two', async () => {
        const fetchImpl = vi.fn(async () => fail(500, { detail: 'boom' }));
        const err = await createInquiryClient({ fetchImpl })
            .respond('s', { decisionId: 'd' }).catch((e) => e);
        expect(err.conflict).toBe(false);
        expect(err.status).toBe(500);
        expect(err.session).toBeNull();
    });

    it('a 409 with no body still reports as a conflict', async () => {
        const fetchImpl = vi.fn(async () => ({
            ok: false, status: 409, statusText: 'Conflict',
            json: async () => { throw new Error('no body'); },
        }));
        const err = await createInquiryClient({ fetchImpl })
            .respond('s', { decisionId: 'd' }).catch((e) => e);
        expect(err.conflict).toBe(true);
        expect(err.session).toBeNull();
        expect(err.message).toMatch(/409/);
    });
});

describe('the live client watching a session', () => {
    it('polls until the session stops being watchable, then stops', async () => {
        const states = ['compiling', 'executing', 'complete'];
        let i = 0;
        const fetchImpl = vi.fn(async () =>
            ok({ ...consultFixture(), state: states[Math.min(i++, states.length - 1)] }));

        const seen = [];
        const client = createInquiryClient({ fetchImpl });
        const stop = client.watch('inqs_fixture_1', {
            onSession: (s) => seen.push(s.state.value), pollMs: 0,
        });

        await vi.waitFor(() => expect(seen).toContain('complete'));
        stop();
        expect(seen).toEqual(['compiling', 'executing', 'complete']);
        // stopped: no further reads after the terminal one
        const calls = fetchImpl.mock.calls.length;
        await new Promise((r) => setTimeout(r, 5));
        expect(fetchImpl.mock.calls.length).toBe(calls);
    });

    it('stops on awaiting_user rather than holding a connection open on a person', async () => {
        const fetchImpl = vi.fn(async () => ok(consultFixture()));
        const seen = [];
        createInquiryClient({ fetchImpl }).watch('s', {
            onSession: (s) => seen.push(s.state.value), pollMs: 0,
        });
        await vi.waitFor(() => expect(seen).toEqual(['awaiting_user']));
        await new Promise((r) => setTimeout(r, 5));
        expect(fetchImpl).toHaveBeenCalledTimes(1);
    });

    it('an unrecognised state keeps the watch alive', async () => {
        let i = 0;
        const fetchImpl = vi.fn(async () =>
            ok({ ...consultFixture(), state: i++ === 0 ? 'reconciling' : 'complete' }));
        const seen = [];
        createInquiryClient({ fetchImpl }).watch('s', {
            onSession: (s) => seen.push(s.state.value), pollMs: 0,
        });
        await vi.waitFor(() => expect(seen).toEqual(['reconciling', 'complete']));
    });

    it('reports the failure that ENDS a watch', async () => {
        const fetchImpl = vi.fn(async () => fail(503, { detail: 'gone' }));
        const errors = [];
        createInquiryClient({ fetchImpl }).watch('s', {
            onSession: () => {}, onError: (e) => errors.push(e.message), pollMs: 0,
        });
        await vi.waitFor(() => expect(errors).toEqual(['gone']));
    });
});

describe('the mock client', () => {
    it('resumes the same session after a response instead of replaying the question', async () => {
        const client = createMockInquiryClient({
            script: [consultFixture()], afterResponse: respondedFixture(),
        });
        const first = await client.start();
        expect(first.state.value).toBe('awaiting_user');

        const next = await client.respond(first.session_id, {
            decisionId: 'dec_extent_grain', responseId: 'res_1',
            optionId: 'opt_whole', expectedRevision: 3,
        });
        expect(next.state.value).toBe('judging');
        expect(client._responses[0].expected_revision).toBe(3);

        // a later read does NOT hand the open decision back
        expect((await client.get()).state.value).toBe('judging');
    });

    it('conflictOnce rejects the first response and accepts the second', async () => {
        const client = createMockInquiryClient({
            script: [consultFixture()],
            afterResponse: respondedFixture(),
            conflictOnce: true,
            conflictSession: conflictSessionFixture(),
        });
        const err = await client.respond('s', { decisionId: 'd' }).catch((e) => e);
        expect(err.conflict).toBe(true);
        expect(err.session.revision).toBe(6);

        const next = await client.respond('s', { decisionId: 'd', optionId: 'opt_whole' });
        expect(next.state.value).toBe('judging');
    });
});
