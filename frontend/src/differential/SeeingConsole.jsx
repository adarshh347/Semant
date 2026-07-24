import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ChevronDown, MoreHorizontal, Scan, Plus } from 'lucide-react';
import { SectionEyebrow } from '../components/brand/SectionEyebrow';
import {
    WayGlyph, SourceGlyph, DissectGlyph, SuggestGlyph, OperationMemoryGlyph,
} from '../components/brand/glyphs';
import { API_URL } from '../config/api';
import { useVisionActivity } from './useVisionActivity';
import {
    FIND_PARTS_LABEL, FIND_PARTS_BUSY, FIND_PARTS_TITLE,
    SPECIALIST_WAYS, BASE_WAY, chosenWays, toggleWay, isAutoWay, wayReason,
    GRAINS, sourceStrip, scheduledSources,
    memoryEntries, memorySummary, latestEntry, MEMORY_SCOPE, MEMORY_PROVENANCE,
} from './seeingConsole';
import './SeeingConsole.css';

/**
 * SeeingConsole — CIRCUIT-001 P2.
 *
 * The one place a curator asks the image to open itself, chooses how to attend to it, and
 * sees what the asking actually did. It replaces a loose row of controls (a select, a
 * primary button, an overflow menu, a profile chip block) and a rail bolted underneath.
 *
 * Three commitments, in order of how easy they are to break:
 *
 *  1. **The operation is `dissect` and the curator never reads that word.** Wire identity is
 *     untouched: same route, same payload keys, same telemetry ids. Only labels moved.
 *
 *  2. **Ways of looking are attention, not models.** The chips map 1:1 onto the domain-profile
 *     specialists the backend already accepts, and the mapping is pinned by tests so the
 *     humane label can never quietly select the wrong pass.
 *
 *  3. **The trace panel is a projection, and says so.** There is no stage stream — only the
 *     latest recorded run per operation, re-read on a bounded timer while one is running.
 *     `MEMORY_PROVENANCE` is rendered rather than assumed.
 *
 * All derivation and copy lives in ./seeingConsole (node-testable); this file is JSX.
 */

const BASE = `${API_URL}/api/v1/posts`;

function StatusDot({ tone }) {
    return <span className={`sc-dot sc-dot--${tone}`} aria-hidden="true" />;
}

/** One operation's recorded state. Stage rows disclose; diagnostics disclose separately. */
function MemoryEntry({ entry }) {
    const { present } = entry;
    if (entry.isUnreadable) {
        return (
            <div className="sc-mem-entry is-unreadable">
                <StatusDot tone="unreadable" />
                <span className="sc-mem-op">{entry.label}</span>
                <span className="sc-mem-state">Couldn’t read activity</span>
            </div>
        );
    }
    if (entry.isEmpty) {
        return (
            <div className="sc-mem-entry is-empty">
                <StatusDot tone="muted" />
                <span className="sc-mem-op">{entry.label}</span>
                <span className="sc-mem-state">No recorded activity</span>
            </div>
        );
    }
    const meta = [];
    if (entry.adapter) meta.push(entry.adapter);
    if (typeof entry.latencyMs === 'number') meta.push(`${entry.latencyMs} ms`);
    if (typeof entry.neighbours === 'number') {
        meta.push(`${entry.neighbours} neighbour${entry.neighbours === 1 ? '' : 's'}`);
    }
    return (
        <div className={`sc-mem-entry is-${present.tone}`}>
            <StatusDot tone={present.tone} />
            <span className="sc-mem-op">{entry.label}</span>
            <span className={`sc-mem-state is-${present.tone}`}>{present.label}</span>
            {entry.ageText && <span className="sc-mem-age">{entry.ageText}</span>}

            <p className="sc-mem-epistemic">{entry.epistemic}</p>

            {(entry.friendly || entry.fallbacks.length > 0 || entry.regionRef || entry.telemetryDegraded) && (
                <p className="sc-mem-notes">
                    {entry.friendly && <span className="sc-mem-note">{entry.friendly}</span>}
                    {entry.fallbacks.length > 0 && (
                        <span className="sc-mem-note is-fallback">Fell back to {entry.fallbacks.join(', ')}</span>
                    )}
                    {entry.regionRef && <span className="sc-mem-note">{entry.regionRef}</span>}
                    {entry.telemetryDegraded && <span className="sc-mem-note">Some telemetry was not recorded.</span>}
                </p>
            )}

            {meta.length > 0 && <p className="sc-mem-meta">{meta.join(' · ')}</p>}

            {entry.stages.length > 0 && (
                <details className="sc-stages">
                    <summary>{entry.stages.length} stages</summary>
                    <ol className="sc-stage-list">
                        {entry.stages.map((s, i) => (
                            <li key={`${s.id}-${i}`} className={`sc-stage is-${s.status}`}>
                                <span className="sc-stage-name">{s.human}</span>
                                {s.status !== 'succeeded' && <span className="sc-stage-status">{s.status}</span>}
                                {typeof s.latencyMs === 'number' && (
                                    <span className="sc-stage-lat">{Math.round(s.latencyMs)} ms</span>
                                )}
                                {s.fallbacks.length > 0 && <span className="sc-stage-fb">↳ {s.fallbacks.join(', ')}</span>}
                            </li>
                        ))}
                    </ol>
                </details>
            )}

            {/* Raw stored text is scrubbed upstream and stays behind a deliberate opening. */}
            {entry.diagnostics && (
                <details className="sc-diag">
                    <summary>Technical detail</summary>
                    <pre className="sc-diag-text">{entry.diagnostics}</pre>
                </details>
            )}
        </div>
    );
}

export default function SeeingConsole({
    postId,
    profile = null,
    onProfile = null,
    regions = [],
    onFindParts = null,
    busy = false,
    grain = 'general',
    onGrain = null,
    intention = '',
    onIntention = null,
    onMarkPart = null,
    actionStatus = null,
    compact = false,
}) {
    const [caps, setCaps] = useState({});
    const [waysBusy, setWaysBusy] = useState(false);
    const [memoryOpen, setMemoryOpen] = useState(false);
    const [moreOpen, setMoreOpen] = useState(false);

    useEffect(() => {
        let live = true;
        fetch(`${BASE}/vision/capabilities`)
            .then((r) => r.json())
            .then((d) => {
                if (live) setCaps(Object.fromEntries((d.capabilities || []).map((c) => [c.name, c])));
            })
            .catch(() => { /* the strip degrades to `not reported`, which is the honest state */ });
        return () => { live = false; };
    }, []);

    const chosen = chosenWays(profile);
    const auto = isAutoWay(profile);
    const reason = wayReason(profile);
    const strip = useMemo(
        () => sourceStrip(profile?.scheduled_passes || ['yolo11n_seg', 'sam21_hiera_tiny'], caps),
        [profile, caps],
    );
    const active = scheduledSources(strip);

    const patchWays = useCallback(async (nextChosen) => {
        setWaysBusy(true);
        try {
            const r = await fetch(`${BASE}/${postId}/domain-profile`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chosen: nextChosen }),
            });
            const d = await r.json();
            onProfile?.(d.domain_profile);
        } catch { /* leave the chips as they were; the next read reconciles */ }
        finally { setWaysBusy(false); }
    }, [postId, onProfile]);

    const runAuto = useCallback(async () => {
        setWaysBusy(true);
        try {
            const r = await fetch(`${BASE}/${postId}/domain-profile/propose`, { method: 'POST' });
            const d = await r.json();
            onProfile?.(d.domain_profile);
        } catch { /* as above */ }
        finally { setWaysBusy(false); }
    }, [postId, onProfile]);

    // ── operation memory ─────────────────────────────────────────────────────
    const { results, loading, refresh } = useVisionActivity(postId, { actionStatus });
    const regionsById = useMemo(() => {
        const m = {};
        (regions || []).forEach((r) => { if (r && r.id) m[r.id] = r.label || r.part || r.category || r.id; });
        return m;
    }, [regions]);
    const now = Date.now();
    const entries = useMemo(
        () => memoryEntries(results, { regionsById, now }),
        [results, regionsById, now],
    );
    const summary = memorySummary(entries);
    const latest = latestEntry(entries, results);

    return (
        <section className={`sc${compact ? ' sc--compact' : ''}`} aria-label="Seeing console">
            {/* ── the operation ───────────────────────────────────────────── */}
            <div className="sc-op">
                <button
                    type="button"
                    className="sc-find"
                    onClick={() => onFindParts?.()}
                    disabled={busy || !onFindParts}
                    title={FIND_PARTS_TITLE}
                >
                    {busy ? <span className="sc-spin" /> : <DissectGlyph size={16} />}
                    <span className="sc-find-label">{busy ? FIND_PARTS_BUSY : FIND_PARTS_LABEL}</span>
                </button>

                <label className="sc-grain">
                    <span className="sc-sr">Grain of the looking</span>
                    <select
                        className="sc-select"
                        value={grain}
                        disabled={busy || !onGrain}
                        onChange={(e) => onGrain?.(e.target.value)}
                    >
                        {GRAINS.map((g) => <option key={g.key} value={g.key}>{g.label}</option>)}
                    </select>
                </label>

                {(onFindParts || onMarkPart) && (
                    <div className="sc-more-wrap">
                        <button
                            type="button" className="sc-icon" aria-label="More ways to look"
                            aria-expanded={moreOpen} disabled={busy}
                            onClick={() => setMoreOpen((o) => !o)}
                        >
                            <MoreHorizontal size={15} />
                        </button>
                        {moreOpen && (
                            <div className="sc-more" role="menu">
                                {onFindParts && (
                                    <button
                                        type="button" role="menuitem"
                                        onClick={() => { setMoreOpen(false); onFindParts({ coarseOnly: true }); }}
                                    >
                                        <Scan size={13} /> Large parts only
                                    </button>
                                )}
                                {onMarkPart && (
                                    <button
                                        type="button" role="menuitem"
                                        onClick={() => { setMoreOpen(false); onMarkPart(); }}
                                    >
                                        <Plus size={13} /> Mark a part yourself
                                    </button>
                                )}
                                {onIntention && (
                                    <input
                                        className="sc-intention" value={intention}
                                        placeholder="What are you looking for? (optional)"
                                        onChange={(e) => onIntention(e.target.value)}
                                        onKeyDown={(e) => { if (e.key === 'Enter') { setMoreOpen(false); onFindParts?.(); } }}
                                    />
                                )}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <p className="sc-op-hint">{FIND_PARTS_TITLE}</p>

            {/* ── ways of looking ─────────────────────────────────────────── */}
            <div className="sc-ways">
                <SectionEyebrow className="sc-eyebrow">Ways of looking</SectionEyebrow>
                <div className="sc-way-chips">
                    {/* The base pass is a statement, not a control: it is always on, and a
                        disabled button that looks like a chip invites a click that can never
                        do anything. */}
                    <span className="sc-way sc-way--base" title={BASE_WAY.hint}>
                        <WayGlyph way={BASE_WAY.key} size={13} className="sc-way-glyph" aria-hidden="true" />
                        {BASE_WAY.label}
                    </span>
                    {SPECIALIST_WAYS.map((w) => (
                        <button
                            key={w.key} type="button" title={w.hint}
                            className={`sc-way${chosen.includes(w.key) ? ' is-on' : ''}`}
                            aria-pressed={chosen.includes(w.key)}
                            data-way={w.key}
                            disabled={waysBusy || !postId}
                            onClick={() => patchWays(toggleWay(chosen, w.key))}
                        >
                            <WayGlyph way={w.key} size={13} className="sc-way-glyph" aria-hidden="true" />
                            {w.label}
                        </button>
                    ))}
                    <button
                        type="button"
                        className={`sc-way sc-way--auto${auto ? ' is-on' : ''}`}
                        disabled={waysBusy || !postId}
                        onClick={runAuto}
                        title="Let Semant propose how to attend to this image"
                    >
                        <SuggestGlyph size={13} className="sc-way-glyph" aria-hidden="true" />
                        {waysBusy ? '…' : 'Let it choose'}
                    </button>
                </div>
                {reason && <p className="sc-way-reason" title={reason}>{reason}</p>}
            </div>

            {/* ── sources ─────────────────────────────────────────────────── */}
            {active.length > 0 && (
                <div className="sc-sources">
                    <SectionEyebrow className="sc-eyebrow">Sources</SectionEyebrow>
                    <div className="sc-source-chips">
                        {active.map((s) => (
                            <span
                                key={s.name}
                                className={`sc-source is-${s.state}`}
                                title={`${s.name}${s.role ? ` · ${s.role}` : ''} — ${s.stateLabel}${s.detail ? ` · ${s.detail}` : ''}`}
                            >
                                <SourceGlyph source={s.name} size={12} className="sc-source-glyph" aria-hidden="true" />
                                <span className="sc-source-name">{s.label}</span>
                                {s.role && <span className="sc-source-role">{s.role}</span>}
                                {s.state !== 'ready' && <em className="sc-source-state">{s.stateLabel}</em>}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* ── operation memory ────────────────────────────────────────── */}
            <div className={`sc-memory${memoryOpen ? ' is-open' : ''}`}>
                <button
                    type="button" className="sc-mem-toggle"
                    aria-expanded={memoryOpen} onClick={() => setMemoryOpen((o) => !o)}
                >
                    <span className="sc-eyebrow sc-eyebrow--op">
                        <OperationMemoryGlyph size={12} className="sc-op-glyph" aria-hidden="true" />
                        Operation memory
                    </span>
                    {latest && !memoryOpen && (
                        <span className="sc-mem-latest">
                            <StatusDot tone={latest.present.tone} />
                            {latest.label} · {latest.present.label}
                            {latest.ageText ? ` · ${latest.ageText}` : ''}
                        </span>
                    )}
                    {(!latest || memoryOpen) && (
                        <span className={`sc-mem-summary is-${summary.tone}`}>{summary.text}</span>
                    )}
                    <ChevronDown size={13} className="sc-caret" aria-hidden="true" />
                </button>

                {memoryOpen && (
                    <div className="sc-mem-body">
                        {/* Both lines are load-bearing: the first bounds WHAT is recorded, the
                            second bounds HOW it is known. Without them a projection reads like
                            a live feed, which is a capability this panel does not have. */}
                        <p className="sc-mem-scope">{MEMORY_SCOPE}</p>
                        <p className="sc-mem-scope sc-mem-scope--how">{MEMORY_PROVENANCE}</p>
                        {entries.map((e) => <MemoryEntry key={e.operation} entry={e} />)}
                        <div className="sc-mem-foot">
                            <button type="button" className="sc-mem-refresh" onClick={refresh} disabled={loading}>
                                {loading ? 'refreshing…' : 'Refresh'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </section>
    );
}
