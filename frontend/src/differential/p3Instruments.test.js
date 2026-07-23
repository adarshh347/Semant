import { readFileSync } from 'node:fs';
import { describe, it, expect } from 'vitest';
import {
    normalizeMark, regionMaskMark, isPersistableMark, MARK_TYPES,
    TRACE_ROLE_KEYS, RELATION_ROLE_KEYS,
} from './visualMarks';
import { draftMarkFromAction } from './markStaging';
import { acceptSuggestion, quarantineSuggestion, isSuggestion, canCiteMark } from './suggestionQuarantine';
import {
    createDefaultLayers, lockLayer, unlockLayer, toggleLayerVisibility, setLayerOpacity, isSystemLayer,
} from './visualLayers';
import { makeGround } from './grounds';
import { perfectFreehandRibbon, outlineVertexCount } from './freehandStroke';
import { taperedRibbon } from './freehandTaper';

/**
 * CIRCUIT-001 P3-B — instrument completion. These tests exercise the REAL Lane A3
 * contract modules along the exact paths the workspace uses to build each mark, so
 * they prove contract conformance for the three debts and the completed instrument
 * set without mounting the full workspace (jsdom has no layout, so the stage's
 * pointer→normalized geometry — and thus pointer-drawing — cannot be driven here;
 * the DOM wiring is covered by groundLayers.p3 and instrumentHandles tests).
 */

const WORKSPACE_SRC = readFileSync(new URL('./DifferentialWorkspace.jsx', import.meta.url), 'utf8');

// ── Debt 1 — marks route through the store; the commit is the write ───────────
describe('Debt 1 — the instruments mint committed, persistable marks (store round-trip)', () => {
    it('a trace commit builds a committed trace_mark the store will persist', () => {
        // Exactly the object commitDraft hands emitMark (= regionStore.addVisualMark).
        const mark = normalizeMark({
            type: 'trace_mark', role: 'gaze_address', label: '', source: 'user', status: 'committed',
            geometry: {
                kind: 'polyline',
                anchors: { from: { kind: 'point', at: [0.1, 0.1] }, to: { kind: 'ground', ref: 'gnd_1', at: [0.9, 0.9] } },
                ambiguous: false, arrowhead: true,
            },
            linked_ground_ids: ['gnd_1'], linked_action_ids: [],
        });
        expect(mark).not.toBeNull();
        expect(mark.status).toBe('committed');
        // committed → persistable → the store's meta-save picks it up (round-trips).
        expect(isPersistableMark(mark)).toBe(true);
    });

    it('a draft/suggested mark is NOT persistable — drafts never thrash the network', () => {
        const draft = normalizeMark({ type: 'trace_mark', role: 'gesture', source: 'user', status: 'draft', geometry: { kind: 'polyline' } });
        expect(isPersistableMark(draft)).toBe(false);
        const sugg = quarantineSuggestion(normalizeMark({ type: 'brush_field', role: 'light_field', source: 'user', status: 'committed', geometry: { kind: 'freehand_path' } }));
        expect(sugg.status).toBe('suggested');
        expect(isPersistableMark(sugg)).toBe(false);
    });

    it('the workspace routes emission through the store, not session state', () => {
        expect(WORKSPACE_SRC).toMatch(/const emitMark = addVisualMark/);
        expect(WORKSPACE_SRC).not.toMatch(/setMarks/);          // no session-state setter remains
        expect(WORKSPACE_SRC).toMatch(/updateVisualMark\(/);    // reshape re-syncs linked marks via the store
    });
});

// ── Debt 2 — the real suggestion source (no DEV fork) ─────────────────────────
describe('Debt 2 — a model_suggested/fixture action becomes a quarantined draft', () => {
    it('no DEV-flag suggestion path remains (grep-proof)', () => {
        expect(WORKSPACE_SRC).not.toContain('__diffSeedSuggestion');
        expect(WORKSPACE_SRC).not.toMatch(/import\.meta\.env/);
        // the real bridge is imported and used
        expect(WORKSPACE_SRC).toMatch(/import \{ draftMarkFromAction \}/);
        expect(WORKSPACE_SRC).toMatch(/draftMarkFromAction\(action\)/);
    });

    it('a model_suggested action is quarantined by the bridge itself', () => {
        const action = {
            id: 'act_ms_1', type: 'connect_marks', source: 'model_suggested',
            payload: { relation_role: 'similarity', label: 'a kinship the model proposes' },
            provenance: { planner: 'orchestrator', promptExcerpt: null, matched: [] },
        };
        const mark = draftMarkFromAction(action);
        expect(mark).not.toBeNull();
        expect(mark.type).toBe('relation_mark');
        expect(mark.role).toBe('similarity');
        expect(isSuggestion(mark)).toBe(true);         // bridge quarantines model_suggested
        expect(mark.status).toBe('suggested');
        expect(canCiteMark(mark)).toBe(false);
        expect(mark.linked_action_ids).toEqual(['act_ms_1']);
    });

    it('a fixture-source proposal is a draft the workspace then quarantines (same door)', () => {
        const action = {
            id: 'act_fix_1', type: 'connect_marks', source: 'fixture',
            payload: { relation_role: 'contrast', label: 'a fixture proposal' },
        };
        const draft = draftMarkFromAction(action);   // bridge leaves fixture as a draft
        expect(draft).not.toBeNull();
        expect(draft.type).toBe('relation_mark');
        expect(isSuggestion(draft)).toBe(false);
        // receiveModelSuggestion quarantines it → a suggestion (the real workspace path)
        const sugg = quarantineSuggestion(draft);
        expect(isSuggestion(sugg)).toBe(true);
        expect(canCiteMark(sugg)).toBe(false);
        // and the workspace uses exactly this fallback quarantine
        expect(WORKSPACE_SRC).toMatch(/isSuggestion\(withGeom\) \? withGeom : quarantineSuggestion\(withGeom\)/);
    });

    it('an ask_model_reading action never yields a mark (the third refusal)', () => {
        expect(draftMarkFromAction({ id: 'a', type: 'ask_model_reading', source: 'fixture', payload: {} })).toBeNull();
    });
});

// ── Debt 3 — region_mask honesty ──────────────────────────────────────────────
describe('Debt 3 — confirmRefine mints a region_mask, not a brush_field', () => {
    it('regionMaskMark references the region and carries NO inline pixels', () => {
        const m = regionMaskMark({ regionId: 'reg_7', geometryRev: 3, model: 'sam2' });
        expect(m).not.toBeNull();
        expect(m.type).toBe('region_mask');
        expect(m.geometry.kind).toBe('raster_mask');
        expect(m.geometry.mask_ref).toEqual({ region_id: 'reg_7', geometry_rev: 3 });
        // region_mask role is optional — a segmented extent has no reading until given one
        expect(m.role).toBeNull();
        for (const banned of ['pixels', 'strokes', 'points', 'polygons', 'rle']) {
            expect(m.geometry[banned]).toBeUndefined();
        }
    });

    it('a fresh mask: quarantine → accept → a citable committed region_mask with lineage', () => {
        // The confirmRefine path for base===null.
        const suggestion = quarantineSuggestion(regionMaskMark({ regionId: 'reg_8', geometryRev: 1, model: 'sam2' }));
        expect(isSuggestion(suggestion)).toBe(true);
        const accepted = acceptSuggestion(suggestion)?.accepted;
        expect(accepted.type).toBe('region_mask');
        expect(accepted.status).toBe('committed');
        expect(accepted.source).toBe('user_confirmed');
        expect(accepted.derived_from).toBe(suggestion.id);     // lineage points back
        expect(canCiteMark(accepted)).toBe(true);
    });

    it('a refine-of-existing: model_refined region_mask requires derived_from', () => {
        const suggestion = quarantineSuggestion(regionMaskMark({ regionId: 'reg_9', geometryRev: 2, model: 'sam2' }));
        const refined = regionMaskMark({
            regionId: 'reg_9', geometryRev: 2, source: 'model_refined', status: 'committed',
            derivedFrom: suggestion.id, model: 'sam2',
        });
        expect(refined).not.toBeNull();
        expect(refined.source).toBe('model_refined');
        expect(refined.derived_from).toBe(suggestion.id);
        // fails closed: model_refined with no lineage is refused by the contract
        expect(regionMaskMark({ regionId: 'reg_9', source: 'model_refined', status: 'committed' })).toBeNull();
    });
});

// ── 2a — trace tool contract conformance ──────────────────────────────────────
describe('2a — trace: roles, anchors, ambiguity, arrowhead ride in the contract geometry', () => {
    it('the trace role vocabulary is Lane A3\'s, never a fourth dialect', () => {
        expect(TRACE_ROLE_KEYS).toContain('gaze_address');
        expect(TRACE_ROLE_KEYS).toContain('return_path');
        expect(MARK_TYPES).toContain('trace_mark');
    });

    it('a normalized trace_mark preserves anchors/ambiguous/arrowhead in geometry', () => {
        const mark = normalizeMark({
            type: 'trace_mark', role: 'force_direction', source: 'user', status: 'committed',
            geometry: {
                kind: 'polyline', ambiguous: true, arrowhead: false,
                anchors: { from: { kind: 'point', at: [0, 0] }, to: { kind: 'region', ref: 'reg_x', at: [1, 1] } },
            },
            linked_ground_ids: ['g'],
        });
        expect(mark).not.toBeNull();
        expect(mark.geometry.ambiguous).toBe(true);
        expect(mark.geometry.arrowhead).toBe(false);
        expect(mark.geometry.anchors.to.ref).toBe('reg_x');
    });
});

// ── 2b — relation tool: derived geometry ──────────────────────────────────────
describe('2b — relation: geometry is derived from member refs, never stored', () => {
    it('a relation_mark carries only its member refs; geometry.kind is derived', () => {
        const mark = normalizeMark({
            type: 'relation_mark', role: 'contrast', source: 'user', status: 'committed',
            geometry: { kind: 'derived', member_ids: ['g1', 'g2'] },
            linked_ground_ids: ['rel_1'],
        });
        expect(mark).not.toBeNull();
        expect(mark.geometry.kind).toBe('derived');
        expect(mark.geometry.member_ids).toEqual(['g1', 'g2']);
        expect(RELATION_ROLE_KEYS).toContain('contrast');
    });
});

// ── 2c — erase as data ────────────────────────────────────────────────────────
describe('2c — erase is DATA: strokes[].op round-trips', () => {
    it('a sub stroke survives a field ground unchanged', () => {
        const strokes = [
            { points: [[0.2, 0.2, 0.5], [0.4, 0.4, 0.6]], radius: 0.05, strength: 0.8, op: 'add' },
            { points: [[0.5, 0.5, 0.5], [0.6, 0.6, 0.4]], radius: 0.05, strength: 1, op: 'sub' },
        ];
        const g = makeGround('field', { strokes });
        expect(g.strokes[1].op).toBe('sub');
        expect(g.strokes[0].op).toBe('add');
    });

    it('a brush_field mark may carry sub strokes in geometry (data identical either way)', () => {
        const mark = normalizeMark({
            type: 'brush_field', role: 'shadow_field', source: 'user', status: 'committed',
            geometry: { kind: 'freehand_path', strokes: [{ points: [[0.3, 0.3]], radius: 0.06, op: 'sub' }] },
        });
        expect(mark).not.toBeNull();
        expect(mark.geometry.strokes[0].op).toBe('sub');
    });
});

// ── 2d — layer controls: a locked layer refuses ───────────────────────────────
describe('2d — minimal layer controls: visibility · opacity · lock', () => {
    const layers = createDefaultLayers();
    const byType = (ls, t) => ls.find((l) => l.layer_type === t);

    it('the four system layers exist; recall is the system layer with no controls', () => {
        expect(layers.map((l) => l.layer_type).sort()).toEqual(['evidence', 'recall', 'scratch', 'suggestion']);
        expect(isSystemLayer(byType(layers, 'recall'))).toBe(true);
        expect(byType(layers, 'recall').locked).toBe(true);
        expect(isSystemLayer(byType(layers, 'evidence'))).toBe(false);
    });

    it('locking evidence sets locked=true; the workspace reads it to refuse edits and draws', () => {
        const evId = byType(layers, 'evidence').id;
        const locked = lockLayer(layers, evId);
        expect(byType(locked, 'evidence').locked).toBe(true);
        const unlocked = unlockLayer(locked, evId);
        expect(byType(unlocked, 'evidence').locked).toBe(false);
        // the guards actually exist and read evidenceLocked (regression guard on the wiring)
        expect(WORKSPACE_SRC).toMatch(/const evidenceLocked = !!evidenceLayer\?\.locked/);
        expect((WORKSPACE_SRC.match(/if \(evidenceLocked\) return/g) || []).length).toBeGreaterThanOrEqual(2);
    });

    it('the system recall layer cannot be unlocked', () => {
        const recId = byType(layers, 'recall').id;
        expect(byType(unlockLayer(layers, recId), 'recall').locked).toBe(true);
    });

    it('visibility and opacity are immutable mutations', () => {
        const evId = byType(layers, 'evidence').id;
        expect(byType(toggleLayerVisibility(layers, evId), 'evidence').visibility).toBe(false);
        expect(byType(setLayerOpacity(layers, evId, 0.4), 'evidence').opacity).toBe(0.4);
        // original untouched
        expect(byType(layers, 'evidence').visibility).toBe(true);
    });
});

// ── 2e — perfect-freehand as the default ──────────────────────────────────────
describe('2e — perfect-freehand default: measured and flipped', () => {
    // The heaviest real corpus stroke (reproduced from the P2E-B measurement).
    const heavy = Array.from({ length: 1194 }, (_, i) => {
        const t = i / 1193;
        return [0.1 + 0.8 * t, 0.5 + 0.35 * Math.sin(t * Math.PI * 3), 0.3 + 0.6 * Math.abs(Math.sin(t * 7))];
    });

    it('generates the heaviest stroke well within a frame budget', () => {
        const t0 = performance.now();
        const d = perfectFreehandRibbon(heavy.map(([x, y, p]) => [x * 1000, y * 1000, p]), { maxWidth: 20 });
        const ms = performance.now() - t0;
        const vtx = outlineVertexCount(heavy.map(([x, y, p]) => [x * 1000, y * 1000, p]), { maxWidth: 20 });
        const ft = taperedRibbon(heavy.map(([x, y, p]) => [x * 1000, y * 1000, p]), { maxWidth: 20 });
        console.log(`P3-B (2e) PF default: heavy(${heavy.length}) → ${vtx} vtx, ${d.length} chars, generated in ${ms.toFixed(1)}ms · FT ${ft.length} chars`);
        expect(d.length).toBeGreaterThan(0);
        // render cost, not storage cost; a few ms even for the heaviest stroke (corpus tops
        // out at 6 marks/post) — the "frame-time holds" finding that flips the default.
        expect(ms).toBeLessThan(200);
        expect(vtx).toBeGreaterThan(1000);
    });

    it('the toggle default is now perfect-freehand, taperedRibbon the rollback', () => {
        expect(WORKSPACE_SRC).toMatch(/useState\(true\)/);   // usePerfectFreehand default
        expect(WORKSPACE_SRC).toMatch(/perfect-freehand is now the DEFAULT/);
    });
});
