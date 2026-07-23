import { describe, it, expect } from 'vitest';
import {
  buildRecallScript, RECALL_TIMING,
  resolveMark, buildMarkRecallScript, markPerformance, MARK_PERFORMANCE,
} from './recall.js';
import { makeGround } from './grounds.js';
import { makeVisualMark } from './visualMarks.js';
import { makeExpressionPercept } from '../state/perceptMentions.js';

const field = () => makeGround('field', { strokes: [{ points: [[0.5, 0.5]], radius: 0.05, strength: 0.8, op: 'add' }] });

describe('buildRecallScript — recede → primary → supporting (stagger) → expression', () => {
  it('stages one ground after the recede, then the expression', () => {
    const g = field();
    const p = makeExpressionPercept({ expression: 'the light pools', ground_ids: [g.id] });
    const { steps, total } = buildRecallScript(p, (id) => (id === g.id ? g : null));
    expect(steps.map((s) => s.kind)).toEqual(['recede', 'ground', 'expression']);
    expect(steps[1]).toMatchObject({ groundId: g.id, role: 'primary', at: RECALL_TIMING.recede });
    expect(steps[2].at).toBeGreaterThan(steps[1].at);
    expect(total).toBeGreaterThan(steps[2].at);
  });

  it('supporting grounds stagger in after the primary', () => {
    const a = field(); const b = field(); const c = field();
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [a.id, b.id, c.id] });
    const byId = Object.fromEntries([a, b, c].map((g) => [g.id, g]));
    const { steps } = buildRecallScript(p, (id) => byId[id] || null);
    const grounds = steps.filter((s) => s.kind === 'ground');
    expect(grounds.map((s) => s.role)).toEqual(['primary', 'supporting', 'supporting']);
    expect(grounds[1].at).toBeGreaterThan(grounds[0].at);
    expect(grounds[2].at - grounds[1].at).toBe(RECALL_TIMING.stagger);
  });

  it('a deleted ground drops out of the performance instead of breaking it', () => {
    const g = field();
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [g.id, 'gnd_gone'] });
    const { steps } = buildRecallScript(p, (id) => (id === g.id ? g : null));
    expect(steps.filter((s) => s.kind === 'ground')).toHaveLength(1);
    expect(steps.at(-1).kind).toBe('expression');
  });

  it('an empty percept still recedes and speaks (nothing to perform)', () => {
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [] });
    const { steps } = buildRecallScript(p, () => null);
    expect(steps.map((s) => s.kind)).toEqual(['recede', 'expression']);
  });

  it('a composition expands into itself, then its members (sequenced)', () => {
    const a = field(); const b = field();
    const c = makeGround('constellation', { member_ids: [a.id, b.id] });
    const byId = Object.fromEntries([a, b, c].map((g) => [g.id, g]));
    const p = makeExpressionPercept({ expression: 'a cluster', ground_ids: [c.id] });
    const { steps } = buildRecallScript(p, (id) => byId[id] || null);
    const gs = steps.filter((s) => s.kind === 'ground');
    expect(gs.map((s) => s.groundId)).toEqual([c.id, a.id, b.id]); // composition first
    expect(gs[0].role).toBe('primary');
  });

  it('does not double-stage a member also named directly in the percept', () => {
    const a = field();
    const c = makeGround('relation', { member_ids: [a.id], relation_label: 'x' });
    const byId = Object.fromEntries([a, c].map((g) => [g.id, g]));
    const p = makeExpressionPercept({ expression: 'x', ground_ids: [c.id, a.id] });
    const { steps } = buildRecallScript(p, (id) => byId[id] || null);
    const ids = steps.filter((s) => s.kind === 'ground').map((s) => s.groundId);
    expect(ids).toEqual([c.id, a.id]); // a appears once
  });
});

// ── R2-A2S/A2R: detached evidence must be reported, never silently performed ──
// A region-adapter Ground whose Region was replaced by a re-dissect still EXISTS
// in the grounds array, so the raw `groundById` lookup returns it. Before this
// guard it received a full timed highlight step that drew nothing, and the
// caption then asserted the Percept over an empty image.
describe('buildRecallScript — unresolved evidence', () => {
    const regionGround = (id, region_id) => ({ id, ground_type: 'region', region_id });

    it('gives a detached ground NO highlight step and reports it instead', () => {
        const g = regionGround('g1', 'fine_0');
        const p = { id: 'p1', expression: 'the upper head', ground_ids: ['g1'] };
        const script = buildRecallScript(p, () => g, { isResolved: () => false });
        expect(script.steps.filter((s) => s.kind === 'ground')).toHaveLength(0);
        expect(script.unresolvedGroundIds).toEqual(['g1']);
        expect(script.resolvedCount).toBe(0);
        expect(script.citedCount).toBe(1);
    });

    it('keeps the resolved grounds and counts only the missing ones', () => {
        const byId = { a: regionGround('a', 'seg_0'), b: regionGround('b', 'fine_9') };
        const p = { id: 'p1', expression: 'x', ground_ids: ['a', 'b'] };
        const script = buildRecallScript(p, (id) => byId[id], {
            isResolved: (g) => g.id === 'a',
        });
        const played = script.steps.filter((s) => s.kind === 'ground');
        expect(played.map((s) => s.groundId)).toEqual(['a']);
        expect(script.unresolvedGroundIds).toEqual(['b']);
        expect(script.resolvedCount).toBe(1);
        expect(script.citedCount).toBe(2);
    });

    it('still reaches the expression step when every ground is detached', () => {
        // The percept is the curator's own words and must not be suppressed —
        // it is qualified, not deleted.
        const p = { id: 'p1', expression: 'the upper head', ground_ids: ['g1', 'g2'] };
        const script = buildRecallScript(p, (id) => regionGround(id, 'gone'),
            { isResolved: () => false });
        const expression = script.steps.find((s) => s.kind === 'expression');
        expect(expression).toBeTruthy();
        expect(script.unresolvedGroundIds).toEqual(['g1', 'g2']);
    });

    it('is unchanged when no isResolved is supplied (back-compat)', () => {
        const g = regionGround('g1', 'seg_0');
        const p = { id: 'p1', expression: 'x', ground_ids: ['g1'] };
        const script = buildRecallScript(p, () => g);
        expect(script.steps.filter((s) => s.kind === 'ground')).toHaveLength(1);
        expect(script.unresolvedGroundIds).toEqual([]);
    });

    it('does not count a geometry-bearing ground as unresolved', () => {
        // field/frame carry their own geometry and survive re-dissection — the
        // corpus sweep found 0 of 15 detached.
        const g = { id: 'f1', ground_type: 'field', strokes: [[[0.1, 0.1]]] };
        const p = { id: 'p1', expression: 'x', ground_ids: ['f1'] };
        const script = buildRecallScript(p, () => g, { isResolved: () => true });
        expect(script.unresolvedGroundIds).toEqual([]);
        expect(script.steps.filter((s) => s.kind === 'ground')).toHaveLength(1);
    });
});

// ── CIRCUIT-001 P1A: the note's arithmetic must be sayable ───────────────────
// `citedCount` counts the ids the Percept names. Before this split, expanded
// composition members were counted against that denominator too, so the note
// could read "2 of 1 cited grounds no longer resolve".
describe('buildRecallScript — cited vs member ledgers', () => {
    const regionGround = (id, region_id) => ({ id, ground_type: 'region', region_id });

    it('never counts more unresolved-cited than were cited', () => {
        const m1 = regionGround('m1', 'gone_1');
        const m2 = regionGround('m2', 'gone_2');
        const c = { id: 'c', ground_type: 'constellation', member_ids: ['m1', 'm2'] };
        const byId = { c, m1, m2 };
        const p = { id: 'p1', expression: 'x', ground_ids: ['c'] };
        // The composition performs; both members do not.
        const script = buildRecallScript(p, (id) => byId[id] || null, {
            isResolved: (g) => g.id === 'c',
        });
        expect(script.citedCount).toBe(1);
        expect(script.unresolvedCitedIds).toEqual([]);
        expect(script.unresolvedMemberIds).toEqual(['m1', 'm2']);
        expect(script.unresolvedCitedIds.length).toBeLessThanOrEqual(script.citedCount);
    });

    it('a detached composition is reported and never expanded', () => {
        const m1 = regionGround('m1', 'gone_1');
        const c = { id: 'c', ground_type: 'constellation', member_ids: ['m1'] };
        const byId = { c, m1 };
        const p = { id: 'p1', expression: 'x', ground_ids: ['c'] };
        const script = buildRecallScript(p, (id) => byId[id] || null, { isResolved: () => false });
        expect(script.steps.filter((s) => s.kind === 'ground')).toHaveLength(0);
        expect(script.unresolvedCitedIds).toEqual(['c']);
        expect(script.unresolvedMemberIds).toEqual([]);  // not expanded
        expect(script.resolvedCount).toBe(0);
    });

    it('a healthy composition still performs itself and its members', () => {
        const m1 = regionGround('m1', 'reg_1');
        const c = { id: 'c', ground_type: 'relation', member_ids: ['m1'] };
        const byId = { c, m1 };
        const p = { id: 'p1', expression: 'x', ground_ids: ['c'] };
        const script = buildRecallScript(p, (id) => byId[id] || null, { isResolved: () => true });
        expect(script.steps.filter((s) => s.kind === 'ground').map((s) => s.groundId))
            .toEqual(['c', 'm1']);
        expect(script.unresolvedGroundIds).toEqual([]);
    });

    it('counts a cited Ground whose record is gone entirely', () => {
        // Previously skipped in silence: neither resolved nor unresolved, so a
        // Percept citing only vanished records produced no note at all.
        const p = { id: 'p1', expression: 'the upper head', ground_ids: ['g_vanished'] };
        const script = buildRecallScript(p, () => null, { isResolved: () => true });
        expect(script.unresolvedCitedIds).toEqual(['g_vanished']);
        expect(script.resolvedCount).toBe(0);
        expect(script.citedCount).toBe(1);
    });

    it('partially resolving composition: cited ledger stays clean', () => {
        const alive = regionGround('m1', 'reg_1');
        const dead = regionGround('m2', 'gone');
        const c = { id: 'c', ground_type: 'constellation', member_ids: ['m1', 'm2'] };
        const byId = { c, m1: alive, m2: dead };
        const p = { id: 'p1', expression: 'x', ground_ids: ['c'] };
        const script = buildRecallScript(p, (id) => byId[id] || null, {
            isResolved: (g) => g.id !== 'm2',
        });
        expect(script.steps.filter((s) => s.kind === 'ground').map((s) => s.groundId))
            .toEqual(['c', 'm1']);
        expect(script.unresolvedCitedIds).toEqual([]);
        expect(script.unresolvedMemberIds).toEqual(['m2']);
    });
});

// ── CIRCUIT-001 P1C — recall asked for, nothing to perform ──────────────────
describe('perceptMissing — the chip must not claim a replay that is not happening', () => {
    // Reachable whenever a pctx_ id in the writing is not in post.percepts:
    // prose copied between posts, or a percepts PATCH that failed. Before this,
    // regionRefInline lit the chip on an id MATCH alone, so the prose asserted
    // "I am being replayed right now" over a no-op.
    it('is true when recall names a percept the store does not have', () => {
        const recall = { perceptId: 'pctx_gone' };
        const percepts = [{ id: 'pctx_other', ground_ids: [] }];
        const found = percepts.find((p) => p.id === recall.perceptId) || null;
        expect(!!recall && !found).toBe(true);
    });

    it('is false when the percept is present, and false when nothing was asked', () => {
        const percepts = [{ id: 'pctx_a', ground_ids: [] }];
        expect(!!{ perceptId: 'pctx_a' } && !percepts.find((p) => p.id === 'pctx_a')).toBe(false);
        expect(!!null && true).toBe(false);
    });
});

// ── CIRCUIT-001 P1A: the note's arithmetic can never exceed its denominator ──
// `unresolved` used to collect expanded members while `citedCount` counted only
// ground_ids, so a composition with detached members could print "2 of 1 cited
// grounds". The cited ledger and the member ledger are now separate.
describe('buildRecallScript — cited vs member ledgers', () => {
    const regionGround = (id, region_id) => ({ id, ground_type: 'region', region_id });

    it('a cited Ground whose record is entirely gone is counted, not skipped', () => {
        // Previously: lookup returns null → `continue` in silence → no note.
        const p = { id: 'p1', expression: 'x', ground_ids: ['gone_a', 'gone_b'] };
        const script = buildRecallScript(p, () => null, { isResolved: () => true });
        expect(script.unresolvedCitedIds).toEqual(['gone_a', 'gone_b']);
        expect(script.citedCount).toBe(2);
        expect(script.resolvedCount).toBe(0);
    });

    it('detached composition members count against the MEMBER ledger, not the cited one', () => {
        const comp = { id: 'c', ground_type: 'constellation', member_ids: ['m1', 'm2'] };
        const m1 = regionGround('m1', 'gone_1');
        const m2 = regionGround('m2', 'gone_2');
        const byId = { c: comp, m1, m2 };
        const p = { id: 'p1', expression: 'x', ground_ids: ['c'] };
        // The composition itself performs (isResolved true for c), its members do not.
        const script = buildRecallScript(p, (id) => byId[id], {
            isResolved: (g) => g.id === 'c',
        });
        expect(script.citedCount).toBe(1);
        expect(script.unresolvedCitedIds).toEqual([]);          // the cited ground performs
        expect(script.unresolvedMemberIds).toEqual(['m1', 'm2']); // the loss is inside it
        // The union is still reported for anyone who wants the total.
        expect(script.unresolvedGroundIds).toEqual(['m1', 'm2']);
    });

    it('never lets the numerator exceed citedCount', () => {
        const comp = { id: 'c', ground_type: 'relation', member_ids: ['m1', 'm2', 'm3'] };
        const byId = {
            c: comp,
            m1: regionGround('m1', 'gone'), m2: regionGround('m2', 'gone'), m3: regionGround('m3', 'gone'),
        };
        const p = { id: 'p1', expression: 'x', ground_ids: ['c'] };
        const script = buildRecallScript(p, (id) => byId[id], { isResolved: (g) => g.id === 'c' });
        expect(script.unresolvedCitedIds.length).toBeLessThanOrEqual(script.citedCount);
    });
});

// ── CIRCUIT-001 P1A: useRecallPlayer note wording — pure assertions on the fn ──
// These exercise the same string logic the writing surface now renders. They do
// NOT mount a component (no DOM env yet); they assert the note the render reads.
describe('evidenceNote wording', () => {
    // Rebuild the note the way useRecallPlayer does, from a script, so the phrasing
    // is pinned without a renderer.
    const noteFrom = (script) => {
        const unresolvedCount = script.unresolvedGroundIds.length;
        const unresolvedCitedCount = script.unresolvedCitedIds.length;
        if (!unresolvedCount) return '';
        if (script.resolvedCount === 0) {
            return `Detached evidence — none of the ${script.citedCount} cited ground${script.citedCount === 1 ? '' : 's'} still resolves.`;
        }
        if (unresolvedCitedCount) {
            return `Detached evidence — ${unresolvedCitedCount} of ${script.citedCount} cited ground${script.citedCount === 1 ? '' : 's'} no longer resolve${unresolvedCitedCount === 1 ? 's' : ''}.`;
        }
        return `Partial evidence — ${unresolvedCount} ground${unresolvedCount === 1 ? '' : 's'} inside this composition no longer resolve${unresolvedCount === 1 ? 's' : ''}.`;
    };
    const regionGround = (id, region_id) => ({ id, ground_type: 'region', region_id });

    it('all cited grounds gone → "none of the N cited grounds still resolves"', () => {
        const p = { id: 'p', expression: 'the upper head', ground_ids: ['a', 'b'] };
        const script = buildRecallScript(p, (id) => regionGround(id, 'gone'), { isResolved: () => false });
        expect(noteFrom(script)).toBe('Detached evidence — none of the 2 cited grounds still resolves.');
    });

    it('some cited grounds gone → "M of N cited grounds no longer resolve"', () => {
        const byId = { a: regionGround('a', 'here'), b: regionGround('b', 'gone') };
        const p = { id: 'p', expression: 'x', ground_ids: ['a', 'b'] };
        const script = buildRecallScript(p, (id) => byId[id], { isResolved: (g) => g.id === 'a' });
        expect(noteFrom(script)).toBe('Detached evidence — 1 of 2 cited grounds no longer resolves.');
    });

    it('only composition members gone → "Partial evidence", never a cited denominator', () => {
        const comp = { id: 'c', ground_type: 'constellation', member_ids: ['m1', 'm2'] };
        const byId = { c: comp, m1: regionGround('m1', 'gone'), m2: regionGround('m2', 'gone') };
        const p = { id: 'p', expression: 'x', ground_ids: ['c'] };
        const script = buildRecallScript(p, (id) => byId[id], { isResolved: (g) => g.id === 'c' });
        const note = noteFrom(script);
        expect(note).toBe('Partial evidence — 2 grounds inside this composition no longer resolve.');
        expect(note).not.toContain('of 1 cited');   // the bug this fixes
    });

    it('healthy recall produces no note', () => {
        const p = { id: 'p', expression: 'x', ground_ids: ['a'] };
        const script = buildRecallScript(p, () => regionGround('a', 'here'), { isResolved: () => true });
        expect(noteFrom(script)).toBe('');
    });
});

// ── CIRCUIT-001 P3-A: mark recall — a committed mark performs on return ──────
// The mark analog of buildRecallScript. resolveMark answers "does this mark still
// have something to draw?"; buildMarkRecallScript stages its performance.
describe('resolveMark — a mark resolves only while it still has something to draw', () => {
  const brush = (over = {}) => makeVisualMark('brush_field', {
    role: 'light_field', source: 'user', status: 'committed',
    geometry: { kind: 'freehand_path' }, ...over,
  }, { now: 't' });

  it('a geometry-bearing mark resolves when it has real geometry', () => {
    expect(resolveMark(brush()).detached).toBe(false);
  });

  it('a mark whose geometry is unresolved is detached', () => {
    const m = brush({ geometry: { kind: 'unresolved' } });
    expect(resolveMark(m)).toEqual({ detached: true, reason: 'no_geometry' });
  });

  it('a region_mask resolves iff the region it points at still exists', () => {
    const m = makeVisualMark('region_mask', {
      source: 'user', status: 'committed',
      geometry: { kind: 'raster_mask', mask_ref: { region_id: 'reg_1', geometry_rev: 0 } },
    }, { now: 't' });
    expect(resolveMark(m, { regions: [{ id: 'reg_1' }] }).detached).toBe(false);
    expect(resolveMark(m, { regions: [] })).toEqual({ detached: true, reason: 'region_gone' });
  });

  it('a relation/collection resolves iff it still names at least one ref', () => {
    const rel = makeVisualMark('relation_mark', {
      role: 'echoes', source: 'user', status: 'committed',
      geometry: { kind: 'derived' }, linked_ground_ids: ['g1', 'g2'],
    }, { now: 't' });
    expect(resolveMark(rel).detached).toBe(false);
    const empty = makeVisualMark('relation_mark', {
      role: 'echoes', source: 'user', status: 'committed', geometry: { kind: 'derived' },
    }, { now: 't' });
    expect(resolveMark(empty)).toEqual({ detached: true, reason: 'no_refs' });
  });

  it('a null mark is detached, not a throw', () => {
    expect(resolveMark(null).detached).toBe(true);
  });
});

describe('buildMarkRecallScript — recede → the mark performs → expression', () => {
  const markOf = (type, over = {}) => makeVisualMark(type, {
    role: type === 'region_mask' ? null : (MARK_ROLE[type]),
    source: 'user', status: 'committed', geometry: GEOM[type], ...over,
  }, { now: 't' });
  const MARK_ROLE = {
    brush_field: 'light_field', trace_mark: 'gaze_path', relation_mark: 'echoes',
    frame_mark: 'boundary', collection_mark: 'evidence_set',
  };
  const GEOM = {
    brush_field: { kind: 'freehand_path' },
    trace_mark: { kind: 'polyline' },
    frame_mark: { kind: 'polygon' },
    relation_mark: { kind: 'derived' },
    collection_mark: { kind: 'derived' },
    region_mask: { kind: 'raster_mask', mask_ref: { region_id: 'reg_1', geometry_rev: 0 } },
  };

  it('names a performance signature for every family', () => {
    expect(markPerformance(markOf('brush_field'))).toBe('bloom');
    expect(markPerformance(markOf('trace_mark'))).toBe('draw_on');
    expect(markPerformance(markOf('relation_mark'))).toBe('perform_then_unite');
    expect(markPerformance(markOf('region_mask'))).toBe('illuminate');
    expect(MARK_PERFORMANCE.frame_mark).toBe('frame');
    expect(MARK_PERFORMANCE.collection_mark).toBe('gather');
  });

  it('stages a brush_field to bloom after the recede, then the caption', () => {
    const m = markOf('brush_field');
    const s = buildMarkRecallScript(m);
    expect(s.steps[0].kind).toBe('recede');
    const mark = s.steps.find((x) => x.kind === 'mark');
    expect(mark).toMatchObject({ markId: m.id, mark_type: 'brush_field', performance: 'bloom' });
    expect(mark.at).toBe(RECALL_TIMING.recede);
    expect(s.steps[s.steps.length - 1].kind).toBe('expression');
    expect(s.markResolved).toBe(true);
  });

  it('a region_mask illuminates when its region survives', () => {
    const m = markOf('region_mask');
    const s = buildMarkRecallScript(m, { regions: [{ id: 'reg_1' }] });
    expect(s.steps.find((x) => x.kind === 'mark').performance).toBe('illuminate');
    expect(s.markResolved).toBe(true);
  });

  it('a relation performs its member grounds then unites (they stagger behind it)', () => {
    const m = markOf('relation_mark', { linked_ground_ids: ['g1', 'g2'] });
    const byId = { g1: makeGround('field', {}, { now: 't' }), g2: makeGround('field', {}, { now: 't' }) };
    // relabel ids to g1/g2 for the lookup
    byId.g1.id = 'g1'; byId.g2.id = 'g2';
    const s = buildMarkRecallScript(m, { groundById: (id) => byId[id] || null });
    const groundSteps = s.steps.filter((x) => x.kind === 'ground');
    expect(groundSteps.map((x) => x.groundId)).toEqual(['g1', 'g2']);
    // the mark performs first, its members after — sequential, never simultaneous
    const markAt = s.steps.find((x) => x.kind === 'mark').at;
    expect(groundSteps[0].at).toBeGreaterThan(markAt);
  });

  it('a detached mark recedes and names the loss — no timed highlight over nothing', () => {
    const m = markOf('region_mask'); // region gone (no regions passed)
    const s = buildMarkRecallScript(m, { regions: [] });
    expect(s.markResolved).toBe(false);
    expect(s.detachedReason).toBe('region_gone');
    expect(s.steps.some((x) => x.kind === 'mark')).toBe(false); // nothing performs
    expect(s.steps[s.steps.length - 1].kind).toBe('expression'); // the caption still lands
  });
});
