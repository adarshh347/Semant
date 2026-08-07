import React, { useState } from 'react';
import { LEDGER_COMMITTED } from './curatorService';

/**
 * WAVE4 — the commit, as a deliberate act.
 *
 * This is the only control in the surface that changes anything, and it is built to be *harder to
 * press than a button*. Three things stand between a curator and the ledger, and none of them is
 * friction for its own sake:
 *
 *   1. **A name is required.** Not defaulted, not remembered from the browser, not filled in from
 *      a session. An anonymous commit is a claim in the ledger that nobody stands behind, and the
 *      entire justification for this seam is that a person did.
 *   2. **The consequence is stated before the act**, in the specific: which mark, to which post,
 *      and what it will read afterwards. "Are you sure?" is not a consequence.
 *   3. **A second, explicit confirm.** The first press opens the consequence; the second performs
 *      it. One click cannot commit.
 *
 * ## What is NOT here
 *
 * No "commit all", no "commit the rest", no shortcut that fires without the confirm, and no undo —
 * because there is no uncommit route, and a button implying one would promise something the ledger
 * cannot do. #172 left every one of these out of the API deliberately; a client that assembled one
 * from a loop would put them all back.
 */
export default function CommitAction({ proposal, onCommitted }) {
    const [curator, setCurator] = useState('');
    const [note, setNote] = useState('');
    const [confirming, setConfirming] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');

    const committed = proposal.ledger_status === LEDGER_COMMITTED;

    if (committed) {
        return (
            <div className="cur-commit cur-commit--done">
                <p className="cur-commit-done">
                    Committed by <strong>{proposal.committed_by}</strong> on{' '}
                    <time dateTime={proposal.committed_at}>
                        {String(proposal.committed_at).slice(0, 19).replace('T', ' ')}
                    </time>.
                </p>
                <p className="cur-commit-note">
                    This mark is in the ledger. There is no undo here — removing a committed mark is
                    a destructive edit to the shared record and deserves its own design, so this
                    surface does not offer one it cannot honour.
                </p>
            </div>
        );
    }

    const run = async () => {
        setBusy(true); setError('');
        try {
            const result = await onCommitted(proposal.proposal_id, { curator, note });
            if (result) setConfirming(false);
        } catch (e) {
            // The backend's own reason, verbatim — it says whether the commit happened.
            setError(e && e.detail ? e.detail : 'The commit did not happen.');
        } finally {
            setBusy(false);
        }
    };

    return (
        <div className="cur-commit">
            <label className="cur-field">
                <span className="cur-field-label">your name, for the ledger</span>
                <input
                    className="cur-input"
                    value={curator}
                    onChange={(e) => { setCurator(e.target.value); setConfirming(false); }}
                    placeholder="who is accepting this"
                    aria-label="curator name"
                />
            </label>

            <label className="cur-field">
                <span className="cur-field-label">note (optional)</span>
                <input
                    className="cur-input"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="why you accepted it"
                    aria-label="commit note"
                />
            </label>

            {!confirming ? (
                <button
                    type="button"
                    className="cur-btn cur-btn--primary"
                    disabled={!curator.trim()}
                    onClick={() => setConfirming(true)}
                >
                    Commit this to the ledger…
                </button>
            ) : (
                <div className="cur-confirm">
                    <p className="cur-confirm-what">
                        This appends mark <code>{proposal.mark_id}</code> to post{' '}
                        <code>{proposal.post_id}</code>, under your name. Afterwards the ledger reads{' '}
                        <strong>committed</strong> and every reader in the system finds it — the
                        movement edges, the agents' observations and the joint hypotheses have all
                        been reading <em>proposed</em> only because this mark was absent.
                    </p>
                    <p className="cur-confirm-what">
                        It will still read <strong>{proposal.epistemic || 'no status'}</strong>:
                        accepting a claim makes it durable and cannot make an estimate into a
                        measurement.
                    </p>
                    <div className="cur-confirm-row">
                        <button type="button" className="cur-btn cur-btn--commit"
                                disabled={busy} onClick={run}>
                            {busy ? 'committing…' : `Yes — commit as ${curator.trim()}`}
                        </button>
                        <button type="button" className="cur-btn cur-btn--ghost"
                                disabled={busy} onClick={() => setConfirming(false)}>
                            Cancel
                        </button>
                    </div>
                </div>
            )}

            {error ? <p className="cur-error" role="alert">{error}</p> : null}
        </div>
    );
}
