import { describe, expect, it } from 'vitest';
import fixture from '../../../../contracts/perception-lab-families/surface_form-normal-fixture.v1.json';
import contract from '../../../../contracts/perception-lab-families/surface_form.json';
import { SLOT } from './surface_form';
import { fieldRgb } from '../fields/fieldVisual';
import { NORMAL_CONVENTION, normalColour, normalGlyphs, readPreviewNormal,
    validateNormalPreview } from './surfaceFormVisual';

const fresh = () => JSON.parse(JSON.stringify(fixture));

describe('Surface form remains an explicit instrument gap', () => {
    it('does not expose fake forms, producers, prompts or model admission', () => {
        expect(SLOT.available).toBe(false);
        expect(SLOT.forms).toEqual([]);
        expect(SLOT.operations).toEqual([]);
        expect(SLOT.promptIntents).toEqual([]);
        expect(contract.available).toBe(false);
        expect(contract.producer_keys).toEqual([]);
        expect(contract.models).toEqual([]);
        expect(SLOT.reason).toBe(contract.reason);
        expect(SLOT.reason).toMatch(/checkpoint permission/);
        expect(SLOT.reason).toMatch(/Mac runtime/);
        expect(SLOT.reason).toMatch(/DSINE/);
    });
});

describe('analytical normal renderer semantics, not model quality', () => {
    it('uses a versioned right-handed convention separate from sample location axes', () => {
        expect(fixture.execution_identity).toBe('FIXTURE');
        expect(fixture.metadata.value_convention).toBe(NORMAL_CONVENTION);
        expect(validateNormalPreview(fixture)).toBe(fixture);
    });

    it.each([
        [[1, 0, 0], [255, 128, 128]], [[-1, 0, 0], [0, 128, 128]],
        [[0, 1, 0], [128, 255, 128]], [[0, -1, 0], [128, 0, 128]],
        [[0, 0, 1], [128, 128, 255]], [[0, 0, -1], [128, 128, 0]],
    ])('encodes directed vector %j with fixed RGB axes', (vector, rgb) => {
        expect(normalColour(vector)).toEqual(rgb);
        expect(fieldRgb('normal_camera_3d', vector, true, [-1, 1], 'colour')).toEqual([...rgb, 255]);
    });

    it('reads unit vectors and invalid support without changing values', () => {
        const before = JSON.stringify(fixture);
        expect(readPreviewNormal(fixture, 0, 0).vector).toEqual([1, 0, 0]);
        expect(readPreviewNormal(fixture, 6, 0)).toEqual({ x: 6, y: 0, valid: false, vector: null });
        const read = readPreviewNormal(fixture, 0, 0);
        read.vector[0] = 999;
        normalGlyphs(fixture);
        expect(JSON.stringify(fixture)).toBe(before);
    });

    it('projects X right and Y down; Z has no artificial XY length', () => {
        const glyphs = normalGlyphs(fixture);
        expect(glyphs).toHaveLength(6);
        expect(glyphs[0].endX).toBeGreaterThan(glyphs[0].x);
        expect(glyphs[1].endY).toBeGreaterThan(glyphs[1].y);
        expect(glyphs[2].endX).toBe(glyphs[2].x);
        expect(glyphs[2].endY).toBe(glyphs[2].y);
        expect(glyphs[3].endX).toBeLessThan(glyphs[3].x);
        expect(glyphs[4].endY).toBeLessThan(glyphs[4].y);
        expect(glyphs[5].colour).not.toEqual(glyphs[2].colour);
    });

    it('does not rotate vector components when source positions are flipped', () => {
        const saved = fresh();
        saved.metadata.source_to_field = [-1, 0, 6, 0, 1, 0, 0, 0, 1];
        expect(normalGlyphs(saved)[0].vector).toEqual([1, 0, 0]);
    });

    it('preserves source field locations with a strided preview and refuses interpolated reads', () => {
        const saved = fresh();
        saved.preview.stride = 2;
        saved.metadata.shape = [1, 13, 3];
        expect(normalGlyphs(saved)[2].fieldX).toBe(4);
        expect(readPreviewNormal(saved, 4, 0).vector).toEqual([0, 0, 1]);
        expect(() => readPreviewNormal(saved, 3, 0)).toThrow(/exact preview/);
    });

    it('bounds glyph count for panoramas', () => {
        const saved = fresh();
        saved.metadata.shape = saved.preview.shape = [1, 65536, 3];
        saved.preview.valid = Array(65536).fill(true);
        saved.preview.values = Array.from({ length: 65536 }, () => [0, 0, 1]).flat();
        expect(normalGlyphs(saved).length).toBeLessThanOrEqual(256);
    });

    it.each(['kind', 'frame', 'units', 'value_convention'])('refuses incompatible %s', (key) => {
        const saved = fresh(); saved.metadata[key] = 'unknown';
        expect(() => validateNormalPreview(saved)).toThrow(/convention/);
    });

    it.each([NaN, Infinity, 2, true])('refuses malformed component %s', (value) => {
        const saved = fresh(); saved.preview.values[0] = value;
        expect(() => validateNormalPreview(saved)).toThrow(/finite unit/);
    });

    it('refuses zero valid normals, missing support, dimensions and incorrect axes', () => {
        const zero = fresh(); zero.preview.values[0] = 0;
        expect(() => validateNormalPreview(zero)).toThrow(/finite unit/);
        const absent = fresh(); absent.preview.valid = [];
        expect(() => validateNormalPreview(absent)).toThrow(/bounded/);
        const shape = fresh(); shape.preview.shape = [1, 8, 3];
        expect(() => validateNormalPreview(shape)).toThrow(/bounded/);
        const wrong = fresh(); wrong.metadata.channels.reverse();
        expect(() => validateNormalPreview(wrong)).toThrow(/convention/);
        expect(() => readPreviewNormal(fixture, -1, 0)).toThrow(/exact preview/);
        expect(() => normalGlyphs(fixture, 0)).toThrow(/positive integer/);
    });
});
