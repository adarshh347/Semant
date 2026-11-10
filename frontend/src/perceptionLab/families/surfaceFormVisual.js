/** Read-only display semantics; not a normal estimator or a quality claim. */
export const NORMAL_CONVENTION = 'directed-unit-camera-normal.v1; right-handed; +x=image-right; +y=image-down; +z=away-from-camera; locations=field-pixel-xy-topleft; source_to_field-transforms-locations-not-vectors; no-calibration-implied';
const CHANNELS = ['x', 'y', 'z'].map((axis) => ({
    name: `n${axis}`, quantity: `camera_normal_${axis}`, unit: '1',
}));

export function validateNormalPreview(data) {
    const { metadata, preview } = data || {};
    if (metadata?.kind !== 'normal_camera_3d' || metadata.frame !== 'camera_xyz'
        || metadata.units !== '1' || metadata.value_convention !== NORMAL_CONVENTION
        || !Array.isArray(metadata.channels) || metadata.channels.length !== 3
        || metadata.channels.some((channel, i) => Object.entries(CHANNELS[i]).some(
            ([key, value]) => channel[key] !== value))) {
        throw new Error('Unsupported directed camera-normal convention, channels or units.');
    }
    const shape = preview?.shape;
    const stride = preview?.stride;
    if (!Array.isArray(shape) || shape.length !== 3 || shape[2] !== 3
        || shape.some((n) => !Number.isInteger(n) || n < 1)
        || shape[0] * shape[1] > 65536 || !Number.isInteger(stride) || stride < 1
        || !Array.isArray(metadata.shape) || metadata.shape.length !== 3 || metadata.shape[2] !== 3
        || metadata.shape.some((n) => !Number.isInteger(n) || n < 1)
        || shape[0] !== Math.ceil(metadata.shape[0] / stride)
        || shape[1] !== Math.ceil(metadata.shape[1] / stride)
        || !Array.isArray(preview.values) || !Array.isArray(preview.valid)
        || preview.values.length !== shape[0] * shape[1] * 3
        || preview.valid.length !== shape[0] * shape[1]) {
        throw new Error('Invalid bounded camera-normal preview.');
    }
    preview.valid.forEach((valid, index) => {
        const vector = preview.values.slice(index * 3, index * 3 + 3);
        if (typeof valid !== 'boolean' || vector.some((v) => !Number.isFinite(v))
            || (!valid && vector.some((v) => v !== 0))
            || (valid && Math.abs(Math.hypot(...vector) - 1) > 1e-4)) {
            throw new Error('Normal preview requires finite unit vectors and explicit invalid support.');
        }
    });
    return data;
}

export function normalColour(vector) {
    if (!Array.isArray(vector) || vector.length !== 3
        || vector.some((v) => !Number.isFinite(v)) || Math.abs(Math.hypot(...vector) - 1) > 1e-4) {
        throw new Error('A finite unit camera normal is required.');
    }
    return vector.map((value) => Math.round(Math.max(0, Math.min(1, (value + 1) / 2)) * 255));
}

export function readPreviewNormal(data, x, y) {
    validateNormalPreview(data);
    const { stride, shape, valid, values } = data.preview;
    if (!Number.isInteger(x) || !Number.isInteger(y) || x < 0 || y < 0
        || x >= data.metadata.shape[1] || y >= data.metadata.shape[0]
        || x % stride || y % stride) {
        throw new Error('Choose an exact preview sample on its declared field-pixel stride.');
    }
    const index = (y / stride) * shape[1] + x / stride;
    return { x, y, valid: valid[index], vector: valid[index] ? values.slice(index * 3, index * 3 + 3) : null };
}

export function normalGlyphs(data, step = 1) {
    validateNormalPreview(data);
    if (!Number.isInteger(step) || step < 1) throw new Error('Glyph step must be a positive integer.');
    const { shape: [height, width], stride, valid, values } = data.preview;
    // Bound thin panoramas too, not only approximately square images.
    const effectiveStep = Math.max(step, Math.ceil(height / 16), Math.ceil(width / 16));
    const glyphs = [];
    for (let y = 0; y < height; y += effectiveStep) {
        for (let x = 0; x < width; x += effectiveStep) {
            const index = y * width + x;
            if (!valid[index]) continue;
            const vector = values.slice(index * 3, index * 3 + 3);
            glyphs.push({ x: x + .5, y: y + .5,
                endX: x + .5 + vector[0] * .35, endY: y + .5 + vector[1] * .35,
                fieldX: x * stride, fieldY: y * stride, vector, colour: normalColour(vector) });
        }
    }
    return glyphs;
}
