/** Pure display mappings. They never edit source samples or validity. */
export function fieldRgb(kind, values, valid, [low, high], view = 'colour') {
    if (!valid) return [110, 110, 110, 255];
    const unit = (v) => Math.max(0, Math.min(1, (v - low) / (high - low || 1)));
    if (kind === 'normal_camera_3d' && view === 'colour') {
        return [...values.slice(0, 3).map((v) => Math.round((v + 1) * 127.5)), 255];
    }
    if (kind === 'directed_vector_2d' || kind === 'axial_orientation_2d') {
        if (view === 'magnitude') {
            const magnitude = Math.hypot(...values.slice(0, 2));
            const gray = Math.round(unit(magnitude) * 255);
            return [gray, gray, gray, 255];
        }
        const angle = Math.atan2(values[1], values[0])
            * (kind === 'axial_orientation_2d' ? .5 : 1);
        const hue = ((angle / (2 * Math.PI) + 1) % 1) * 6;
        const x = 1 - Math.abs(hue % 2 - 1);
        const sectors = [[1, x, 0], [x, 1, 0], [0, 1, x],
            [0, x, 1], [x, 0, 1], [1, 0, x]];
        return [...sectors[Math.floor(hue)].map((v) => Math.round(v * 255)), 255];
    }
    const t = unit(values[0]);
    if (view === 'grayscale' || view === 'magnitude') {
        const gray = Math.round(t * 255);
        return [gray, gray, gray, 255];
    }
    return [Math.round(t * 255), Math.round((1 - Math.abs(t - .5) * 2) * 210),
        Math.round((1 - t) * 255), 255];
}

export function previewPixels({ metadata, preview }, scale, view) {
    const [height, width, channels] = preview.shape;
    if (width * height > 65536 || preview.values.length !== width * height * channels
        || preview.valid.length !== width * height) {
        throw new Error('invalid bounded field preview');
    }
    const pixels = new Uint8ClampedArray(width * height * 4);
    for (let index = 0; index < width * height; index += 1) {
        const colour = fieldRgb(metadata.kind,
            preview.values.slice(index * channels, (index + 1) * channels),
            preview.valid[index], scale, view);
        if (!preview.valid[index] && ((Math.floor(index / width) + index % width) % 2)) {
            colour[0] = 70; colour[1] = 70; colour[2] = 70;
        }
        pixels.set(colour, index * 4);
    }
    return { width, height, pixels };
}

export function pixelAt(clientX, clientY, rect, metadata, preview = null) {
    const [height, width] = preview?.shape || metadata.shape;
    const stride = preview?.stride || 1;
    const x = Math.min(width - 1, Math.max(0,
        Math.floor((clientX - rect.left) / rect.width * width)));
    const y = Math.min(height - 1, Math.max(0,
        Math.floor((clientY - rect.top) / rect.height * height)));
    return [x * stride, y * stride];
}
