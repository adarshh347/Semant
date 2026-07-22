import { describe, it, expect, beforeEach } from 'vitest';
import {
    LAYER_TYPES, createDefaultLayers, normalizeLayer, validateLayer,
    assignMarkToLayer, layerCanContainMark, getVisibleLayers, reorderLayers,
    toggleLayerVisibility, setLayerOpacity, lockLayer, unlockLayer,
    isSystemLayer, _resetLayerIds,
} from './visualLayers';

/**
 * CIRCUIT-001 P2D-A — the layer model. Contract §3.
 * Data model only. The one rule that carries weight: a suggestion cannot be filed onto the
 * evidence layer, expressed as a placement rule so the quarantine is structural.
 */

beforeEach(() => { _resetLayerIds(); });

const suggestion = { id: 'vm_s', source: 'model_suggested', status: 'suggested' };
const evidence = { id: 'vm_e', source: 'user', status: 'committed' };

describe('the four default layers', () => {
    it('ships exactly evidence, suggestion, recall, scratch', () => {
        const layers = createDefaultLayers();
        expect(layers.map((l) => l.layer_type).sort()).toEqual([...LAYER_TYPES].sort());
        expect(layers.every((l) => validateLayer(l).valid)).toBe(true);
    });

    it('renders suggestion above evidence, recall on top', () => {
        const layers = createDefaultLayers();
        const order = (t) => layers.find((l) => l.layer_type === t).order;
        expect(order('evidence')).toBeLessThan(order('suggestion'));
        expect(order('suggestion')).toBeLessThan(order('recall'));
    });

    it('makes recall a locked system layer', () => {
        const recall = createDefaultLayers().find((l) => l.layer_type === 'recall');
        expect(isSystemLayer(recall)).toBe(true);
        expect(recall.locked).toBe(true);
    });
});

describe('normalization', () => {
    it('rejects an unknown layer_type', () => {
        expect(normalizeLayer({ layer_type: 'holodeck' })).toBe(null);
    });
    it('forces a recall layer locked whatever the caller passed', () => {
        expect(normalizeLayer({ layer_type: 'recall', locked: false }).locked).toBe(true);
    });
    it('defaults visible and clamps opacity', () => {
        expect(normalizeLayer({ layer_type: 'evidence' }).visibility).toBe(true);
        expect(normalizeLayer({ layer_type: 'evidence', opacity: 5 }).opacity).toBe(1);
        expect(normalizeLayer({ layer_type: 'evidence', opacity: -1 }).opacity).toBe(0);
    });
});

describe('membership is the quarantine, expressed structurally', () => {
    const layers = createDefaultLayers();
    const layer = (t) => layers.find((l) => l.layer_type === t);

    it('a suggestion belongs ONLY on the suggestion layer', () => {
        expect(layerCanContainMark(layer('suggestion'), suggestion)).toBe(true);
        expect(layerCanContainMark(layer('evidence'), suggestion)).toBe(false);
        expect(layerCanContainMark(layer('scratch'), suggestion)).toBe(false);
    });

    it('evidence belongs anywhere but the suggestion and recall layers', () => {
        expect(layerCanContainMark(layer('evidence'), evidence)).toBe(true);
        expect(layerCanContainMark(layer('scratch'), evidence)).toBe(true);
        expect(layerCanContainMark(layer('suggestion'), evidence)).toBe(false);
        expect(layerCanContainMark(layer('recall'), evidence)).toBe(false);
    });

    it('a previewed mark is still quarantined', () => {
        const prev = { id: 'vm_p', source: 'user', status: 'previewed' };
        expect(layerCanContainMark(layer('suggestion'), prev)).toBe(true);
        expect(layerCanContainMark(layer('evidence'), prev)).toBe(false);
    });
});

describe('assignMarkToLayer', () => {
    it('places a mark and removes it from any other layer', () => {
        let layers = createDefaultLayers();
        const ev = layers.find((l) => l.layer_type === 'evidence').id;
        const sc = layers.find((l) => l.layer_type === 'scratch').id;
        layers = assignMarkToLayer(layers, evidence, sc, { mark: evidence });
        layers = assignMarkToLayer(layers, evidence, ev, { mark: evidence });
        expect(layers.find((l) => l.id === ev).mark_ids).toContain('vm_e');
        expect(layers.find((l) => l.id === sc).mark_ids).not.toContain('vm_e');
    });

    it('refuses to file a suggestion onto evidence', () => {
        const layers = createDefaultLayers();
        const ev = layers.find((l) => l.layer_type === 'evidence').id;
        const after = assignMarkToLayer(layers, suggestion, ev, { mark: suggestion });
        expect(after.find((l) => l.id === ev).mark_ids).not.toContain('vm_s');
    });

    it('refuses to add to a locked non-recall layer', () => {
        let layers = createDefaultLayers();
        const sc = layers.find((l) => l.layer_type === 'scratch').id;
        layers = lockLayer(layers, sc);
        const after = assignMarkToLayer(layers, evidence, sc, { mark: evidence });
        expect(after.find((l) => l.id === sc).mark_ids).not.toContain('vm_e');
    });
});

describe('view and mutation are immutable', () => {
    it('getVisibleLayers hides invisible and sorts by order', () => {
        let layers = createDefaultLayers();
        const sug = layers.find((l) => l.layer_type === 'suggestion').id;
        layers = toggleLayerVisibility(layers, sug);
        const visible = getVisibleLayers(layers);
        expect(visible.map((l) => l.layer_type)).not.toContain('suggestion');
        expect(visible.map((l) => l.order)).toEqual([...visible.map((l) => l.order)].sort((a, b) => a - b));
    });

    it('setLayerOpacity clamps and refuses non-numbers', () => {
        const layers = createDefaultLayers();
        const ev = layers.find((l) => l.layer_type === 'evidence').id;
        expect(setLayerOpacity(layers, ev, 0.5).find((l) => l.id === ev).opacity).toBe(0.5);
        expect(setLayerOpacity(layers, ev, 'x')).toBe(layers);
    });

    it('a system layer cannot be unlocked', () => {
        const layers = createDefaultLayers();
        const rc = layers.find((l) => l.layer_type === 'recall').id;
        expect(unlockLayer(layers, rc).find((l) => l.id === rc).locked).toBe(true);
    });

    it('reorder keeps recall on top however it is asked', () => {
        const layers = createDefaultLayers();
        const rc = layers.find((l) => l.layer_type === 'recall').id;
        const ids = layers.map((l) => l.id);
        // Ask for recall first — it must still end last.
        const reordered = reorderLayers(layers, [rc, ...ids.filter((i) => i !== rc)]);
        const recall = reordered.find((l) => l.id === rc);
        expect(recall.order).toBe(reordered.length - 1);
    });
});
