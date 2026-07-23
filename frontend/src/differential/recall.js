import { useEffect, useMemo, useRef, useState } from 'react';

import { resolveGround } from './grounds';
import { markSummary } from './visualMarks';

/**
 * Recall — the visual re-performance of a Percept from its Mention
 * (Differential v1 · increment B). One module, two consumers: the Differential
 * stage (per-Percept ▶ preview) and the Chiasm pane (Mention focus → replay).
 *
 * buildRecallScript is pure: percept + a ground resolver → a staged timeline.
 * useRecallPlayer turns the store's `recall` state into per-ground progress the
 * layers can render. Short and legible, not theatrical:
 *
 *   recede → primary ground → supporting grounds (staggered) → expression
 *
 * `prefers-reduced-motion` skips straight to the composed final state. The
 * final state is quiet (settled), and clearing recall restores calm.
 */

export const RECALL_TIMING = {
    recede: 380,        // the image steps back
    ground: 850,        // one ground performs (bloom / illuminate)
    stagger: 240,       // supporting grounds enter one after another
    expression: 1200,   // the caption breathes
};

// Per-type performance signatures land with their types (C/D); every type
// blooms/illuminates through the same progress ramp in B.
//
// `lookup` only answers "does this Ground exist?". Existing is NOT the same as
// resolving: a region-adapter Ground whose Region was replaced by a re-dissect
// still exists, but has nothing left to draw. Without `isResolved` such a Ground
// was given a full timed highlight step that rendered NOTHING, and the caption
// then asserted the Percept over empty evidence. Pass `isResolved` so unresolved
// evidence is reported instead of silently performed.
export function buildRecallScript(percept, lookup, { isResolved } = {}) {
    // Expand compositions: a Constellation/Relation performs itself and then its
    // members, in order — which is exactly the spec's "pulse sequential" /
    // "A, then B, then unite" via the existing stagger machinery.
    const seen = new Set();
    const grounds = [];
    // Two ledgers, not one. `citedCount` is the count of ground_ids the Percept
    // names, so anything counted against it must also be one of those ids —
    // otherwise an expanded member could push the numerator past the
    // denominator and the note would read "2 of 1 cited grounds no longer
    // resolve". Members are still reported, separately, so nothing is hidden.
    const unresolvedCited = [];
    const unresolvedMembers = [];
    const performs = (g) => !isResolved || isResolved(g);

    for (const id of percept?.ground_ids || []) {
        const g = lookup(id);
        // A cited Ground whose RECORD is gone (not merely whose region is) was
        // previously skipped in silence: it counted as neither resolved nor
        // unresolved, so a Percept citing only vanished records produced no note
        // at all. A citation that names nothing is the loudest kind of loss.
        if (!g) {
            if (!seen.has(id)) { seen.add(id); unresolvedCited.push(id); }
            continue;
        }
        if (seen.has(g.id)) continue;
        seen.add(g.id);
        if (!performs(g)) { unresolvedCited.push(g.id); continue; }
        grounds.push(g);
        // Only expand a composition that itself performs. An expanded member of
        // a detached composition has nothing to join.
        if ((g.ground_type === 'constellation' || g.ground_type === 'relation') && g.member_ids) {
            for (const mid of g.member_ids) {
                const m = lookup(mid);
                if (!m || seen.has(m.id)) continue;
                seen.add(m.id);
                if (!performs(m)) { unresolvedMembers.push(m.id); continue; }
                grounds.push(m);
            }
        }
    }

    const steps = [{ kind: 'recede', at: 0, dur: RECALL_TIMING.recede }];
    let t = RECALL_TIMING.recede;
    grounds.forEach((g, i) => {
        steps.push({
            kind: 'ground',
            groundId: g.id,
            ground_type: g.ground_type,
            role: i === 0 ? 'primary' : 'supporting',
            at: t,
            dur: RECALL_TIMING.ground,
        });
        // The primary finishes alone; supporters stagger in behind each other.
        t += i === 0 ? RECALL_TIMING.ground * 0.7 : RECALL_TIMING.stagger;
    });
    const expressionAt = grounds.length
        ? steps[steps.length - 1].at + RECALL_TIMING.ground * 0.6
        : RECALL_TIMING.recede;
    steps.push({ kind: 'expression', at: expressionAt, dur: RECALL_TIMING.expression });

    return {
        steps,
        total: expressionAt + RECALL_TIMING.expression,
        // Reported, never performed. `cited` is the denominator so a reader can
        // tell "1 of 3 gone" from "3 of 3 gone".
        unresolvedGroundIds: [...unresolvedCited, ...unresolvedMembers],
        // The subset that can be spoken about against `citedCount`.
        unresolvedCitedIds: unresolvedCited,
        unresolvedMemberIds: unresolvedMembers,
        resolvedCount: grounds.length,
        citedCount: (percept?.ground_ids || []).length,
    };
}

// ── mark recall (CIRCUIT-001 P3-A) ────────────────────────────────────────────
// A committed mark can be CITED in the Manuscript and PERFORMED on return, just as
// a percept can. Recall stays percept-centric above (a percept performs its
// grounds); this is its sibling for a single mark. `resolveMark` is to a mark what
// `resolveGround` is to a ground: it answers "does this mark still have something
// to draw?" so a citation that outlived its geometry degrades instead of asserting
// itself over an empty image.

// How each family re-performs on recall. This NAMES the intent; the renderer
// (GroundLayers / the field canvas, Lane B3) reads `step.performance` +
// `progressForMark` to actually bloom/draw.
// P3F: GroundLayers must consume the `kind: 'mark'` step — bloom a brush_field,
// draw-on a trace (the SVG pathLength idiom recall already uses for paths),
// perform-then-unite a relation over its member steps, illuminate a region_mask's
// region. The DATA is here; the rendering lands in B3's file (see report §recall).
export const MARK_PERFORMANCE = {
    brush_field: 'bloom',
    trace_mark: 'draw_on',
    relation_mark: 'perform_then_unite',
    collection_mark: 'gather',
    frame_mark: 'frame',
    region_mask: 'illuminate',
};
export const markPerformance = (mark) => MARK_PERFORMANCE[mark?.type] || 'bloom';

/**
 * Does a mark still resolve to something a renderer can perform? Returns
 * `{ detached, reason }` — the same shape `resolveGround` speaks in, so the player
 * treats a lost mark exactly as it treats a lost ground.
 *
 * A geometry-bearing family (brush/trace/frame) resolves iff it has real geometry.
 * A `region_mask` resolves iff the region it points at still exists (the mask lives
 * on the Region — contract v2 §7.2-C). A relation/collection derives its shape from
 * its refs, so it resolves iff it still names at least one.
 */
export function resolveMark(mark, { regions = [], marks = [] } = {}) {
    if (!mark) return { detached: true, reason: 'gone' };
    const geom = mark.geometry || {};
    if (mark.type === 'region_mask') {
        const rid = geom.mask_ref?.region_id;
        const region = (regions || []).find((r) => r.id === rid);
        return region ? { detached: false, reason: null } : { detached: true, reason: 'region_gone' };
    }
    if (mark.type === 'relation_mark' || mark.type === 'collection_mark') {
        const refs = [
            ...(mark.linked_ground_ids || []),
            // a relation MAY unite other marks; count a ref that still resolves to one
            ...(mark.linked_mark_ids || []).filter((id) => (marks || []).some((m) => m.id === id)),
        ];
        return refs.length ? { detached: false, reason: null } : { detached: true, reason: 'no_refs' };
    }
    if (!geom.kind || geom.kind === 'unresolved') return { detached: true, reason: 'no_geometry' };
    return { detached: false, reason: null };
}

/**
 * A mark → a staged recall timeline. Pure, and the mark analog of
 * `buildRecallScript`: recede → the mark performs → (relation/collection) its member
 * grounds stagger in → the caption. A detached mark yields a script that recedes and
 * names the loss, never a timed highlight over nothing (the same discipline the
 * ground path learned in P1A).
 */
export function buildMarkRecallScript(mark, { regions = [], marks = [], groundById } = {}) {
    const resolution = resolveMark(mark, { regions, marks });
    const detached = resolution.detached;
    const steps = [{ kind: 'recede', at: 0, dur: RECALL_TIMING.recede }];
    let t = RECALL_TIMING.recede;

    if (!detached) {
        steps.push({
            kind: 'mark',
            markId: mark.id,
            mark_type: mark.type,
            role: mark.role,
            performance: markPerformance(mark),
            at: t,
            dur: RECALL_TIMING.ground,
        });
        t += RECALL_TIMING.ground * 0.7;
        // "perform its refs then unite" — a relation/collection stages its member
        // grounds behind itself, reusing the ground step the renderer already knows.
        if (mark.type === 'relation_mark' || mark.type === 'collection_mark') {
            const seen = new Set();
            for (const gid of mark.linked_ground_ids || []) {
                const g = groundById?.(gid);
                if (!g || seen.has(g.id)) continue;
                seen.add(g.id);
                steps.push({
                    kind: 'ground', groundId: g.id, ground_type: g.ground_type,
                    role: 'supporting', at: t, dur: RECALL_TIMING.ground,
                });
                t += RECALL_TIMING.stagger;
            }
        }
    }

    const lastPerforming = steps[steps.length - 1];
    const expressionAt = detached
        ? RECALL_TIMING.recede
        : lastPerforming.at + RECALL_TIMING.ground * 0.6;
    steps.push({ kind: 'expression', at: expressionAt, dur: RECALL_TIMING.expression });

    return {
        steps,
        total: expressionAt + RECALL_TIMING.expression,
        markId: mark?.id || null,
        markResolved: !detached,
        markPerformance: detached ? null : markPerformance(mark),
        detachedReason: detached ? resolution.reason : null,
    };
}

const easeOut = (t) => 1 - (1 - t) * (1 - t);

/**
 * Drive the store's recall through its script.
 * Returns { active, settled, receding, caption, progressFor(groundId) }.
 *   - progressFor → 0..1 while playing, 1 once settled, 0 when uninvolved.
 *   - `settled` keeps the composed state on screen until clearRecall.
 */
export function useRecallPlayer(store) {
    // Tolerates a null store (RegionSurface mounts standalone in the lab).
    const {
        recall, percepts, groundById = () => null, grounds, regions,
        visualMarks = [],
    } = store || {};
    const [elapsed, setElapsed] = useState(0);
    const rafRef = useRef(null);

    // Recall carries EITHER a perceptId (perform its grounds) or a markId (perform
    // the mark). The two never coexist — playRecall/playMarkRecall set one or the
    // other — so a single script drives both, and the layers below don't care which.
    const isMarkRecall = !!recall?.markId;

    const percept = useMemo(
        () => (recall && !isMarkRecall
            ? (percepts || []).find((p) => p.id === recall.perceptId) || null
            : null),
        [recall, isMarkRecall, percepts],
    );

    const mark = useMemo(
        () => (isMarkRecall ? (visualMarks || []).find((m) => m.id === recall.markId) || null : null),
        [isMarkRecall, recall, visualMarks],
    );

    // resolveGround is the authority on whether a Ground still has evidence to
    // show — the same function GroundLayers uses to decide what to draw. Feeding
    // it here keeps the script and the render in agreement. A mark recall builds
    // the mark script instead, resolved through `resolveMark`.
    const script = useMemo(
        () => {
            if (isMarkRecall) {
                return mark
                    ? buildMarkRecallScript(mark, { regions: regions || [], marks: visualMarks || [], groundById })
                    : null;
            }
            return percept
                ? buildRecallScript(percept, groundById, {
                    isResolved: (g) => !resolveGround(g, {
                        regions: regions || [], grounds: grounds || [],
                    })?.detached,
                })
                : null;
        },
        [isMarkRecall, mark, percept, groundById, regions, grounds, visualMarks],
    );

    useEffect(() => {
        if (!script) { setElapsed(0); return undefined; }
        const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        if (reduced) { setElapsed(script.total); return undefined; }
        const start = performance.now();
        const tick = (now) => {
            const e = now - start;
            setElapsed(e);
            if (e < script.total) rafRef.current = requestAnimationFrame(tick);
        };
        rafRef.current = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(rafRef.current);
    }, [script]);

    const active = !!script;
    const settled = active && elapsed >= script.total;

    const progressFor = (groundId) => {
        if (!script) return 0;
        const step = script.steps.find((s) => s.kind === 'ground' && s.groundId === groundId);
        if (!step) return 0;
        return easeOut(Math.max(0, Math.min(1, (elapsed - step.at) / step.dur)));
    };

    // The mark's own performance progress, keyed by mark id (a `kind: 'mark'` step).
    // GroundLayers reads this the way it reads progressFor(groundId). P3F.
    const progressForMark = (markId) => {
        if (!script) return 0;
        const step = script.steps.find((s) => s.kind === 'mark' && s.markId === markId);
        if (!step) return 0;
        return easeOut(Math.max(0, Math.min(1, (elapsed - step.at) / step.dur)));
    };

    const expressionStep = script?.steps.find((s) => s.kind === 'expression');
    const captionVisible = active && expressionStep && elapsed >= expressionStep.at;

    // The caption a mark speaks with — its label, or an honest role summary. A
    // percept speaks its expression (below); a mark has no prose, so it names itself.
    const markCaption = mark ? (mark.label || markSummary(mark)) : '';

    // Ground-ledger fields exist only on a percept script; a mark script has none.
    const unresolvedCount = script?.unresolvedGroundIds?.length || 0;
    // The note speaks about what the Percept CITES, so its numerator must come
    // from the cited ledger. Members that could not perform are still counted in
    // `unresolvedCount`; they just cannot be phrased against `citedCount`.
    const unresolvedCitedCount = script?.unresolvedCitedIds?.length || 0;

    return {
        active,
        settled,
        receding: active,                 // the image stays receded until cleared
        caption: captionVisible ? (isMarkRecall ? markCaption : (percept?.expression || '')) : '',
        percept,
        // CIRCUIT-001 P3-A — the mark being performed, and its recall channel.
        mark,
        isMarkRecall,
        progressForMark,
        markPerformance: script?.markPerformance || null,
        // The mark id was asked for but the store has no such mark (prose citing a
        // mark that a later edit removed) — the mark analog of `perceptMissing`.
        markMissing: isMarkRecall && !mark,
        // A cited mark that outlived its geometry/region. Say so beside the caption,
        // exactly as the ground path says "detached evidence".
        markDetached: isMarkRecall && !!script && script.markResolved === false,
        markNote: (isMarkRecall && captionVisible && script && script.markResolved === false)
            ? (script.detachedReason === 'region_gone'
                ? 'Detached mark — the region it segmented is gone.'
                : script.detachedReason === 'no_refs'
                    ? 'Detached mark — nothing left for it to unite.'
                    : 'Detached mark — its geometry no longer resolves.')
            : '',
        // CIRCUIT-001 P1C — recall was ASKED FOR and there is no percept to
        // perform. Previously the chip lit itself (`store.recall.perceptId`
        // matches, regardless of whether the percept exists) while nothing
        // played: the prose asserted "I am being replayed right now" over a
        // no-op. Reachable whenever a `pctx_` id in the writing is not in
        // `post.percepts` — prose copied between posts, or a percepts PATCH that
        // failed. States the absence; never a cause.
        perceptMissing: !!recall && !isMarkRecall && !percept,
        progressFor,
        // Honesty channel. A Percept can outlive the evidence it cites; when it
        // does, say so beside the caption rather than letting the caption stand
        // alone over an empty image. Appears with the caption, not before it.
        unresolvedCount,
        unresolvedCitedCount,
        citedCount: script?.citedCount || 0,
        evidenceNote: captionVisible && unresolvedCount
            ? (script.resolvedCount === 0
                ? `Detached evidence — none of the ${script.citedCount} cited ground${script.citedCount === 1 ? '' : 's'} still resolves.`
                : unresolvedCitedCount
                    ? `Detached evidence — ${unresolvedCitedCount} of ${script.citedCount} cited ground${script.citedCount === 1 ? '' : 's'} no longer resolve${unresolvedCitedCount === 1 ? 's' : ''}.`
                    // Every cited Ground performs; what is missing sits inside a
                    // composition. Say that, rather than borrowing the cited
                    // denominator for a number that does not belong to it.
                    : `Partial evidence — ${unresolvedCount} ground${unresolvedCount === 1 ? '' : 's'} inside this composition no longer resolve${unresolvedCount === 1 ? 's' : ''}.`)
            : '',
    };
}
