import React, { useCallback, useRef, useState } from 'react';
import Convergence from './Convergence.jsx';
import { API_URL } from '../config/api';
import '../cognition/cognition.css';
import './society.css';

/**
 * SOCIETY — watch agents meet.
 *
 * The cognition view shows ONE agent walking. This shows several arriving at one locus and the
 * partition of what holds between them. It reuses `cognition.css` for the status marks rather
 * than restating them: `measured` / `interpretive` / `proposed` must look the same everywhere in
 * this app, and a second palette is a second place for the distinction to soften.
 *
 * THREE RENDERING RULES ARE LOAD-BEARING:
 *
 *   · A JOINT HYPOTHESIS SHOWS `proposed`, with `contributed`/`received` per mark. Two agents
 *     agreeing is the most persuasive thing this system makes, and rendering it as one voice —
 *     or as `measured` — is the fabrication `hydrate_hypothesis` has no code path to produce.
 *   · AN INCOMMENSURABLE PAIR SHOWS NO NUMBER. `CompatibilityLeak` at the pixel level. It renders
 *     the refusal's own words and nothing quantitative, because "just show something comparable"
 *     is exactly the pressure a surface puts on this.
 *   · A WHOLLY-RECEIVED BELIEF SHOWS REFUSED, not held-with-a-caveat. A supported way to display
 *     a claim no organ of the holder measured is a supported way to launder one.
 */

const OUTCOME_GLOSS = {
    composed: 'made a claim neither made alone',
    coexistent: 'could be about the same things, and are not',
    incommensurable: 'no shared frame — not "nothing found", but nothing to find',
    undetermined: 'one of them measured nothing here, so the question cannot be answered',
    same_body: 'two copies of one world',
};

function Verdict({ verdict }) {
    return (
        <li className={`soc-verdict soc-verdict--${verdict.outcome}`}>
            <div className="soc-verdict-head">
                <span className="soc-pair">{verdict.left} ↔ {verdict.right}</span>
                <span className="soc-outcome">{verdict.outcome}</span>
            </div>
            <p className="soc-outcome-gloss">{OUTCOME_GLOSS[verdict.outcome] || ''}</p>
            {/* The refusal's OWN words for an incommensurable pair — no number is rendered here
                because there is none to render, and inventing one is the whole thing this
                surface must not do. */}
            <p className="soc-verdict-detail">{verdict.detail}</p>
            {verdict.shared_subjects?.length > 0 && (
                <p className="cog-percept-meta">
                    shared subjects: {verdict.shared_subjects.join(', ')}
                </p>
            )}
        </li>
    );
}

function Hypothesis({ hypothesis }) {
    return (
        <li className="soc-hypothesis">
            <div className="soc-hyp-head">
                <span className="soc-claim">{hypothesis.claim}</span>
                {/* PROPOSED, always. Rendered with the same status mark the rest of the app uses. */}
                <span className="cog-status cog-status--proposed">{hypothesis.ledger_status}</span>
                <span className="cog-percept-meta">marks live {hypothesis.marks_live}</span>
            </div>
            <p className="soc-hyp-agents">
                composed by {hypothesis.agent_ids.join(' + ')}
                {hypothesis.about_region_id && ` — about ${hypothesis.about_region_id}`}
            </p>
            <ul className="soc-rests">
                {hypothesis.rests_on.map((row, i) => (
                    <li key={i} className="soc-rest">
                        <span className="soc-rest-agent">{row.agent_id}</span>
                        <span className="cog-percept-meta">
                            {row.organ} · {row.relation} · {row.basis} · mark {row.mark_id}
                        </span>
                    </li>
                ))}
            </ul>
            <p className="soc-hyp-ledger">{hypothesis.detail_ledger}</p>
        </li>
    );
}

export default function SocietyPage({ client = null }) {
    const fetchMeeting = useRef(client || {
        meeting: async (params) => {
            const query = Object.entries(params)
                .filter(([, v]) => v !== '' && v != null)
                .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
            const res = await fetch(`${API_URL}/api/v1/society/meeting?${query}`);
            if (!res.ok) {
                let detail = '';
                try { detail = (await res.json())?.detail || ''; } catch { /* not json */ }
                throw new Error(detail || `${res.status} ${res.statusText}`);
            }
            return res.json();
        },
    }).current;

    const [postId, setPostId] = useState('');
    const [regionId, setRegionId] = useState('');
    const [meeting, setMeeting] = useState(null);
    const [error, setError] = useState('');
    const [untravelled, setUntravelled] = useState(false);
    const [busy, setBusy] = useState(false);

    const convene = useCallback(async () => {
        if (!postId.trim()) { setError('a post id is needed — a society meets somewhere'); return; }
        setBusy(true); setError(''); setUntravelled(false); setMeeting(null);
        try {
            setMeeting(await fetchMeeting.meeting({
                post_id: postId.trim(), region_id: regionId.trim(), steps: 2,
            }));
        } catch (err) {
            const detail = err.message || String(err);
            setError(detail);
            // The 409 family, told apart by the guards' own words rather than by a status code the
            // client would have to carry separately.
            setUntravelled(/travell|walked|society|perceiv/i.test(detail));
        } finally {
            setBusy(false);
        }
    }, [fetchMeeting, postId, regionId]);

    const held = meeting?.held || {};
    const refusals = meeting?.refusals_to_hold || [];

    return (
        <div className="cog-shell">
            <header className="cog-head">
                <h1 className="cog-title">Watch agents meet</h1>
                <p className="cog-lede">
                    Differently-bodied agents <em>walk</em> to one locus and are convened there. Some
                    pairs compose a claim neither made alone; some merely coexist; some have no
                    shared frame at all — and that last one is shown as what it is, never as a
                    number.
                </p>
            </header>

            <form className="cog-controls" onSubmit={(e) => { e.preventDefault(); convene(); }}>
                <label className="cog-field">
                    <span>post id</span>
                    <input value={postId} onChange={(e) => setPostId(e.target.value)}
                           placeholder="where they set out from" />
                </label>
                <label className="cog-field">
                    <span>region (optional)</span>
                    <input value={regionId} onChange={(e) => setRegionId(e.target.value)} />
                </label>
                <button className="cog-go" type="submit" disabled={busy}>
                    {busy ? 'convening…' : 'convene'}
                </button>
            </form>

            {/* A GROUP THAT COULD NOT MEET is a different finding from one that met and composed
                nothing, and the two must not render alike. The route says so with a 409; this says
                so with its own block rather than the generic error line. */}
            {error && (untravelled
                ? <section className="soc-untravelled" role="alert">
                    <h2 className="soc-h2">nobody travelled far enough</h2>
                    <p className="soc-untravelled-detail">{error}</p>
                    <p className="soc-untravelled-note">
                        This is not an empty partition. No meeting happened at all — a meeting is
                        earned by travel, and this group could not reach one another. What the
                        graph affords, rather than what these bodies found.
                    </p>
                  </section>
                : <p className="cog-error" role="alert">{error}</p>)}

            {meeting && (
                <>
                    <section className="soc-members">
                        <h2 className="soc-h2">at {meeting.node_id}</h2>
                        <ul className="soc-member-list">
                            {meeting.members.map((m) => (
                                <li key={m.id} className="soc-member">
                                    <span className="soc-member-id">{m.id}</span>
                                    <span className="cog-percept-meta">
                                        {m.organ_set.join(', ')} · measured {m.measured}
                                    </span>
                                </li>
                            ))}
                        </ul>
                        <p className="soc-classes">
                            comparability classes:{' '}
                            {meeting.classes.map((c) => `{${c.join(', ')}}`).join('  ')}
                            {meeting.silent.length > 0 && (
                                <span> · silent (in no class): {meeting.silent.join(', ')}</span>
                            )}
                        </p>
                    </section>

                    <Convergence walks={meeting.walks} nodeId={meeting.node_id} />

                    <section className="soc-partition">
                        <h2 className="soc-h2">the partition</h2>
                        <ul className="soc-verdicts">
                            {meeting.verdicts.map((v, i) => <Verdict key={i} verdict={v} />)}
                        </ul>
                    </section>

                    {meeting.hypotheses.length > 0 && (
                        <section className="soc-hypotheses">
                            <h2 className="soc-h2">what they composed</h2>
                            <ul className="soc-hyp-list">
                                {meeting.hypotheses.map((h) => (
                                    <Hypothesis key={h.hypothesis_id} hypothesis={h} />
                                ))}
                            </ul>
                        </section>
                    )}

                    <section className="soc-holding">
                        <h2 className="soc-h2">what each may hold</h2>
                        <ul className="soc-hold-list">
                            {Object.entries(held).map(([agentId, rows]) => (
                                <li key={agentId} className="soc-hold">
                                    <span className="soc-member-id">{agentId}</span>
                                    {rows.length === 0
                                        ? <span className="cog-percept-meta">holds nothing here</span>
                                        : rows.map((r, i) => (
                                            <span key={i} className="soc-hold-row">
                                                <span className="cog-status cog-status--interpretive">
                                                    {r.epistemic_status}
                                                </span>
                                                {r.claim} — contributed {r.contributed},
                                                received {r.received}
                                            </span>
                                        ))}
                                </li>
                            ))}
                        </ul>

                        {refusals.length > 0 && (
                            /* REFUSED, not held-with-a-caveat. A supported way to display a claim
                               no organ of the holder measured is a supported way to launder one. */
                            <ul className="cog-list soc-refusals">
                                {refusals.map((r, i) => (
                                    <li key={i} className="cog-refusal" data-about="traveller">
                                        <span className="cog-refusal-tag">
                                            {r.agent_id} refused to hold — {r.reason}
                                        </span>
                                        <span className="cog-refusal-gloss">{r.detail}</span>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>
                </>
            )}
        </div>
    );
}
