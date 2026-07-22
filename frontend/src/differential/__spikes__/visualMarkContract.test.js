import { describe, it, expect, beforeEach } from 'vitest';
import {
    makeBrushField, makeTraceMark, makeRelationMark, makeVisualLayer,
    validateVisualMark, validateVisualLayer, serializeMark, serializeWorkspace,
    acceptSuggestion, supersedeMark, isCitable, citableMarks, relationNodes,
    markIsEditable, markRenderOpacity, assertPlainData, _resetSpikeIds,
} from './visualMarkContract';
import { fixtureWorkspace, markCenter } from './spikeFixture';

beforeEach(() => _resetSpikeIds());

describe('contract shapes', () => {
    it('every fixture mark validates', () => {
        const { marks } = fixtureWorkspace();
        for (const m of marks) {
            const r = validateVisualMark(m);
            expect(r.errors, `${m.type}/${m.role}`).toEqual([]);
            expect(r.ok).toBe(true);
        }
    });

    it('every fixture layer validates', () => {
        for (const l of fixtureWorkspace().layers) {
            expect(validateVisualLayer(l).errors).toEqual([]);
        }
    });

    it('each mark family serializes to its contract shape', () => {
        const { marks } = fixtureWorkspace();
        const brush = serializeMark(marks.find((m) => m.type === 'brush_field'));
        expect(Object.keys(brush)).toEqual(expect.arrayContaining([
            'id', 'type', 'role', 'source', 'status', 'geometry', 'style', 'derived_from', 'provenance',
        ]));
        expect(brush.geometry.kind).toBe('freehand_path');
        expect(brush.geometry.strokes[0].points[0].length).toBe(3);   // pressure survives

        const trace = serializeMark(marks.find((m) => m.type === 'trace_mark'));
        expect(trace.geometry.kind).toBe('polyline');
        expect(trace).toHaveProperty('anchors');
        expect(trace).toHaveProperty('ambiguous', true);

        const rel = serializeMark(marks.find((m) => m.type === 'relation_mark'));
        expect(rel.geometry).toEqual({ kind: 'derived' });
        expect(rel.source_refs).toHaveLength(1);
    });

    it('refuses a relation_mark that stores coordinates', () => {
        const bad = makeRelationMark({ geometry: { kind: 'polyline', points: [[0, 0], [1, 1]] } });
        const r = validateVisualMark(bad);
        expect(r.ok).toBe(false);
        expect(r.errors.join(' ')).toMatch(/kind:derived/);
    });

    it('refuses geometry outside normalized range', () => {
        const bad = makeTraceMark({ geometry: { kind: 'polyline', points: [[0.2, 0.3], [42, 0.5]] } });
        expect(validateVisualMark(bad).ok).toBe(false);
    });
});

describe('no renderer object may reach serialized output (contract §6)', () => {
    class FakeKonvaLine { constructor() { this.attrs = { points: [1, 2] }; this._id = 9; } }

    it('assertPlainData throws on a class instance', () => {
        expect(() => assertPlainData({ node: new FakeKonvaLine() })).toThrow(/renderer\/class object/);
    });

    it('assertPlainData throws on a function', () => {
        expect(() => assertPlainData({ draw: () => { } })).toThrow(/non-serializable function/);
    });

    it('serializeMark drops an attached renderer node rather than emitting it', () => {
        const m = makeBrushField({ status: 'committed' });
        // The realistic failure: something stashes the node on the mark.
        m._konvaNode = new FakeKonvaLine();
        m.konvaRef = new FakeKonvaLine();
        const out = serializeMark(m);
        expect(out).not.toHaveProperty('_konvaNode');
        expect(out).not.toHaveProperty('konvaRef');
        // The renderer node's OWN fields (attrs, the private _id:9) never appear.
        expect(JSON.stringify(out)).not.toMatch(/"attrs"|"_id"|FakeKonva/);
    });

    it('the whole serialized workspace is JSON-round-trippable and identical', () => {
        const ws = fixtureWorkspace();
        const out = serializeWorkspace(ws);
        expect(JSON.parse(JSON.stringify(out))).toEqual(out);
    });

    it('a renderer object nested deep inside geometry still throws', () => {
        const m = makeTraceMark({ status: 'committed' });
        m.geometry = { kind: 'polyline', points: [[0.1, 0.2]], shape: new FakeKonvaLine() };
        // `shape` is not whitelisted, so it cannot escape...
        expect(serializeMark(m).geometry).toEqual({ kind: 'polyline', points: [[0.1, 0.2]] });
        // ...and if it were, assertPlainData would refuse it.
        expect(() => assertPlainData(m.geometry)).toThrow();
    });
});

describe('suggestion quarantine (OH §5G)', () => {
    it('a model_suggested mark is not citable', () => {
        const { marks } = fixtureWorkspace();
        const s = marks.find((m) => m.source === 'model_suggested');
        expect(s).toBeTruthy();
        expect(isCitable(s)).toBe(false);
        expect(citableMarks(marks).map((m) => m.id)).not.toContain(s.id);
    });

    it('the contract refuses to let a suggestion be committed directly', () => {
        const s = makeBrushField({ source: 'model_suggested', status: 'committed' });
        expect(validateVisualMark(s).errors.join(' ')).toMatch(/never hold status:committed/);
    });

    it('acceptance mints a new user_confirmed mark with derived_from lineage', () => {
        const { marks, layers } = fixtureWorkspace();
        const s = marks.find((m) => m.source === 'model_suggested');
        const evidence = layers.find((l) => l.layer_type === 'evidence');

        const { confirmed, suggestion } = acceptSuggestion(s, { layerId: evidence.id });

        expect(confirmed.id).not.toBe(s.id);
        expect(confirmed.source).toBe('user_confirmed');
        expect(confirmed.status).toBe('committed');
        expect(confirmed.derived_from).toBe(s.id);
        expect(confirmed.layer_id).toBe(evidence.id);
        expect(isCitable(confirmed)).toBe(true);
        expect(validateVisualMark(confirmed).errors).toEqual([]);
        // The geometry came across intact.
        expect(confirmed.geometry.strokes[0].points).toEqual(s.geometry.strokes[0].points);
        // The prediction survives untouched (Label Studio §3.5.1).
        expect(suggestion).toBe(s);
        expect(s.status).toBe('staged');
        expect(s.source).toBe('model_suggested');
        // And the confirmed mark carries NO renderer residue.
        expect(() => assertPlainData(serializeMark(confirmed))).not.toThrow();
    });

    it('user_confirmed without derived_from is refused — no laundering', () => {
        const m = makeBrushField({ source: 'user_confirmed', status: 'committed' });
        expect(validateVisualMark(m).errors.join(' ')).toMatch(/derived_from/);
    });

    it('acceptSuggestion refuses a mark that was not a suggestion', () => {
        expect(() => acceptSuggestion(makeBrushField())).toThrow(/not a model_suggested/);
    });
});

describe('supersede, not replace', () => {
    it('keeps the old mark recoverable and links the new one', () => {
        const old = makeTraceMark({ status: 'committed', geometry: { kind: 'polyline', points: [[0.1, 0.1], [0.9, 0.9]] } });
        const { next, superseded } = supersedeMark(old, {
            geometry: { kind: 'polyline', points: [[0.1, 0.1], [0.5, 0.4], [0.9, 0.9]] },
        });
        expect(superseded.status).toBe('superseded');
        expect(superseded.id).toBe(old.id);
        expect(next.derived_from).toBe(old.id);
        expect(next.geometry.points).toHaveLength(3);
        expect(isCitable(superseded)).toBe(false);
    });
});

describe('layers', () => {
    it('a locked layer makes its marks uneditable; a hidden one renders at 0', () => {
        const { marks, layers } = fixtureWorkspace();
        const evidence = layers.find((l) => l.layer_type === 'evidence');
        const m = marks.find((x) => x.layer_id === evidence.id);

        expect(markIsEditable(m, layers)).toBe(true);

        const locked = layers.map((l) => (l.id === evidence.id ? { ...l, locked: true } : l));
        expect(markIsEditable(m, locked)).toBe(false);

        const hidden = layers.map((l) => (l.id === evidence.id ? { ...l, visibility: false } : l));
        expect(markIsEditable(m, hidden)).toBe(false);
        expect(markRenderOpacity(m, hidden)).toBe(0);
    });

    it('layer opacity multiplies the mark opacity, and the wash ceiling holds', () => {
        const { marks, layers } = fixtureWorkspace();
        const scratch = layers.find((l) => l.layer_type === 'scratch');   // opacity 0.8
        const m = marks.find((x) => x.layer_id === scratch.id);
        // brush style opacity 0.28, under the 0.32 ceiling → 0.28 × 0.8
        expect(markRenderOpacity(m, layers)).toBeCloseTo(0.224, 6);

        const greedy = { ...m, style: { ...m.style, opacity: 0.9 } };
        expect(markRenderOpacity(greedy, layers)).toBeCloseTo(0.32 * 0.8, 6);
    });

    it('a recall layer may not be locked', () => {
        const l = makeVisualLayer({ layer_type: 'recall', locked: true });
        expect(validateVisualLayer(l).errors.join(' ')).toMatch(/must not be lockable/);
    });
});

describe('relation geometry is derived, never stored', () => {
    it('nodes come from the referenced marks at call time and follow them', () => {
        const { marks } = fixtureWorkspace();
        const rel = marks.find((m) => m.type === 'relation_mark');

        const nodes = relationNodes(rel, markCenter(marks));
        expect(nodes).toHaveLength(2);

        // Move the referenced light field; the connector must follow with no
        // write to the relation mark at all.
        const moved = marks.map((m) => (m.id === rel.source_refs[0].ref
            ? { ...m, geometry: { ...m.geometry, strokes: [{ ...m.geometry.strokes[0], points: m.geometry.strokes[0].points.map(([x, y, p]) => [x, y + 0.2, p]) }] } }
            : m));
        const moved2 = relationNodes(rel, markCenter(moved));
        expect(moved2[0][1]).toBeCloseTo(nodes[0][1] + 0.2, 6);
        expect(serializeMark(rel).geometry).toEqual({ kind: 'derived' });
    });

    it('a ref that stops resolving simply drops out — no stale coordinate', () => {
        const { marks } = fixtureWorkspace();
        const rel = marks.find((m) => m.type === 'relation_mark');
        const without = marks.filter((m) => m.id !== rel.source_refs[0].ref);
        expect(relationNodes(rel, markCenter(without))).toHaveLength(1);
    });
});
