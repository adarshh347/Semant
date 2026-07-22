import { useEffect, useMemo, useRef, useState } from 'react';

import { resolveGround } from './grounds';

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
    const unresolved = [];
    const take = (g) => {
        if (isResolved && !isResolved(g)) { unresolved.push(g.id); return; }
        grounds.push(g);
    };
    for (const id of percept?.ground_ids || []) {
        const g = lookup(id);
        if (!g || seen.has(g.id)) continue;
        seen.add(g.id);
        take(g);
        if ((g.ground_type === 'constellation' || g.ground_type === 'relation') && g.member_ids) {
            for (const mid of g.member_ids) {
                const m = lookup(mid);
                if (m && !seen.has(m.id)) { seen.add(m.id); take(m); }
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
        unresolvedGroundIds: unresolved,
        resolvedCount: grounds.length,
        citedCount: (percept?.ground_ids || []).length,
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
    const { recall, percepts, groundById = () => null, grounds, regions } = store || {};
    const [elapsed, setElapsed] = useState(0);
    const rafRef = useRef(null);

    const percept = useMemo(
        () => (recall ? (percepts || []).find((p) => p.id === recall.perceptId) || null : null),
        [recall, percepts],
    );

    // resolveGround is the authority on whether a Ground still has evidence to
    // show — the same function GroundLayers uses to decide what to draw. Feeding
    // it here keeps the script and the render in agreement.
    const script = useMemo(
        () => (percept
            ? buildRecallScript(percept, groundById, {
                isResolved: (g) => !resolveGround(g, {
                    regions: regions || [], grounds: grounds || [],
                })?.detached,
            })
            : null),
        [percept, groundById, regions, grounds],
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

    const expressionStep = script?.steps.find((s) => s.kind === 'expression');
    const captionVisible = active && expressionStep && elapsed >= expressionStep.at;

    const unresolvedCount = script?.unresolvedGroundIds.length || 0;

    return {
        active,
        settled,
        receding: active,                 // the image stays receded until cleared
        caption: captionVisible ? (percept?.expression || '') : '',
        percept,
        progressFor,
        // Honesty channel. A Percept can outlive the evidence it cites; when it
        // does, say so beside the caption rather than letting the caption stand
        // alone over an empty image. Appears with the caption, not before it.
        unresolvedCount,
        citedCount: script?.citedCount || 0,
        evidenceNote: captionVisible && unresolvedCount
            ? (script.resolvedCount === 0
                ? `Detached evidence — none of the ${script.citedCount} cited ground${script.citedCount === 1 ? '' : 's'} still resolves.`
                : `Detached evidence — ${unresolvedCount} of ${script.citedCount} cited grounds no longer resolve.`)
            : '',
    };
}
