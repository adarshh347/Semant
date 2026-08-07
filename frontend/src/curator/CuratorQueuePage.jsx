import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import CommitAction from './CommitAction';
import EvidenceTable from './EvidenceTable';
import ProposalMasks from './ProposalMasks';
import StatusPair from './StatusPair';
import {
    LEDGER_COMMITTED, LEDGER_PROPOSED, commitProposal, fetchProposal, fetchQueue,
} from './curatorService';
import './curator.css';

/**
 * WAVE4 — the curator's queue, given a face.
 *
 * #172 closed the propose→commit loop and left it API-deep: the 13 occlusions are real claims about
 * the author's own photographs, reachable only by hand-calling a route. This is the first surface
 * where the engine is something a person can watch and use rather than call.
 *
 * ## The layout is the argument
 *
 * A list on the left, one proposal open on the right. Not a grid of cards with a commit button on
 * each — that shape invites sweeping down the column accepting things, which is the bulk-accept
 * #172 refused to build, reassembled out of clicks. One claim is open at a time because one claim
 * is decided at a time.
 *
 * ## What this page will not do
 *
 * It does not sort. The backend returns filed order and this renders filed order; a queue ranked by
 * the evidence's own strength is the UI telling the curator what matters. It does not score, badge
 * "high confidence", or hide anything below a threshold. And it reloads the whole queue after a
 * commit rather than patching the row locally — an optimistic update would show `committed` on the
 * strength of the client's belief, and the one thing this surface must never do is render a status
 * it has not read back from the ledger.
 */
export default function CuratorQueuePage() {
    const [rows, setRows] = useState([]);
    const [total, setTotal] = useState(0);
    const [openId, setOpenId] = useState('');
    const [open, setOpen] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [justCommitted, setJustCommitted] = useState('');

    const load = useCallback(async (keepOpen) => {
        setLoading(true); setError('');
        try {
            const data = await fetchQueue({ limit: 200 });
            const items = data.proposals || [];
            setRows(items);
            setTotal(data.total || items.length);
            const next = keepOpen || (items[0] && items[0].proposal_id) || '';
            setOpenId(next);
        } catch (e) {
            setError(e && e.detail ? e.detail : 'The queue could not be read.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    // The open proposal is re-fetched rather than taken from the list row. They are the same shape,
    // but the detail route hydrates against the ledger at the moment it is asked — so a proposal
    // somebody else committed while this list sat on screen shows as committed here, instead of
    // offering a commit that will be refused.
    useEffect(() => {
        let cancelled = false;
        if (!openId) { setOpen(null); return undefined; }
        fetchProposal(openId)
            .then((row) => { if (!cancelled) setOpen(row); })
            .catch((e) => { if (!cancelled) setError(e && e.detail ? e.detail : 'Could not read it.'); });
        return () => { cancelled = true; };
    }, [openId]);

    const counts = useMemo(() => {
        const proposed = rows.filter((r) => r.ledger_status === LEDGER_PROPOSED).length;
        return { proposed, committed: rows.length - proposed };
    }, [rows]);

    const onCommitted = useCallback(async (proposalId, { curator, note }) => {
        const result = await commitProposal(proposalId, { curator, note });
        setJustCommitted(proposalId);
        // READ IT BACK. Both the list and the open row are re-fetched, so what shows as committed
        // is what the ledger says and not what this page just asked for.
        await load(proposalId);
        const fresh = await fetchProposal(proposalId);
        setOpen(fresh);
        return result;
    }, [load]);

    return (
        <div className="cur-page">
            <header className="cur-header">
                <div>
                    <span className="cur-eyebrow">the curator</span>
                    <h1 className="cur-title">What the engine measured, and has not been allowed to conclude</h1>
                    <p className="cur-sub">
                        Every producer in this system proposes. Nothing here is in the shared record
                        until you put it there — that is the whole architecture, and this is the only
                        place it happens. One claim at a time, under your name.
                    </p>
                </div>
                <Link className="cur-back" to="/">← back</Link>
            </header>

            {error ? <p className="cur-error" role="alert">{error}</p> : null}

            <div className="cur-counts">
                <span><strong>{counts.proposed}</strong> awaiting you</span>
                <span><strong>{counts.committed}</strong> committed</span>
                <span className="cur-counts-total">{total} in the queue</span>
            </div>

            {loading && rows.length === 0 ? (
                <p className="cur-muted">reading the queue…</p>
            ) : null}

            {!loading && rows.length === 0 ? (
                <p className="cur-muted">
                    The queue is empty. That is a fact about what producers have filed, not about
                    what the engine has measured — a lane that measured something and never filed it
                    leaves nothing here to see.
                </p>
            ) : null}

            <div className="cur-body">
                <ol className="cur-list" aria-label="proposals, in filed order">
                    {rows.map((row) => {
                        const isOpen = row.proposal_id === openId;
                        const done = row.ledger_status === LEDGER_COMMITTED;
                        return (
                            <li key={row.proposal_id}>
                                <button
                                    type="button"
                                    className={`cur-row${isOpen ? ' is-open' : ''}${done ? ' is-committed' : ''}`}
                                    onClick={() => setOpenId(row.proposal_id)}
                                    aria-current={isOpen ? 'true' : undefined}
                                >
                                    <span className="cur-row-claim">
                                        {(row.subject && row.subject.claim) || row.kind}
                                    </span>
                                    <span className="cur-row-meta">
                                        <span className="cur-row-producer">{row.producer}</span>
                                        <span className={`cur-dot cur-dot--${done ? LEDGER_COMMITTED : LEDGER_PROPOSED}`}
                                              aria-label={done ? 'committed' : 'proposed'} />
                                    </span>
                                </button>
                            </li>
                        );
                    })}
                </ol>

                <section className="cur-detail">
                    {!open ? (
                        <p className="cur-muted">Choose a proposal to read its evidence.</p>
                    ) : (
                        <>
                            <h2 className="cur-detail-title">
                                {(open.subject && open.subject.claim) || open.kind}
                            </h2>
                            <p className="cur-detail-sub">
                                proposed by <code>{open.producer}</code> · mark{' '}
                                <code>{open.mark_id}</code> · post <code>{open.post_id}</code>
                            </p>

                            <StatusPair
                                epistemic={open.epistemic}
                                ledgerStatus={open.ledger_status}
                                detail={open.detail_ledger}
                            />

                            <h3 className="cur-h3">the geometry, on the photograph</h3>
                            <ProposalMasks proposal={open} />

                            <h3 className="cur-h3">the evidence, as the producer measured it</h3>
                            <EvidenceTable evidence={open.evidence} subject={open.subject} />

                            <h3 className="cur-h3">your decision</h3>
                            <CommitAction proposal={open} onCommitted={onCommitted} />

                            {justCommitted === open.proposal_id
                                && open.ledger_status === LEDGER_COMMITTED ? (
                                <p className="cur-committed-flash">
                                    Committed. Read back from the ledger, not assumed.
                                </p>
                            ) : null}
                        </>
                    )}
                </section>
            </div>
        </div>
    );
}
