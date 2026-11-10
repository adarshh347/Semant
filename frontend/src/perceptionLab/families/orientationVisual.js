/** Display-only projections of the saved doubled-angle tangent carrier. */
export function orientationMeta(data) {
    try { return JSON.parse(data?.metadata?.value_convention || '{}'); }
    catch { return {}; }
}

export function headlessMarks(data, spacing = 12) {
    if (data?.metadata.kind !== 'axial_orientation_2d') return [];
    const [height, width, count] = data.preview.shape;
    const stride = data.preview.stride || 1;
    const step = Math.max(1, Math.round(spacing / stride));
    const marks = [];
    for (let row = Math.floor(step / 2); row < height; row += step) {
        for (let col = Math.floor(step / 2); col < width; col += step) {
            const index = row * width + col;
            if (!data.preview.valid[index]) continue;
            const [c, s] = data.preview.values.slice(index * count, index * count + 2);
            const theta = Math.atan2(s, c) / 2;
            const length = spacing * .35;
            const x = col * stride; const y = row * stride;
            marks.push({ x1: x - Math.cos(theta) * length, y1: y - Math.sin(theta) * length,
                x2: x + Math.cos(theta) * length, y2: y + Math.sin(theta) * length,
                coherence: Math.hypot(c, s) });
        }
    }
    return marks;
}

export function coherenceView(data) {
    if (data?.metadata.kind !== 'axial_orientation_2d') return data;
    const [height, width] = data.preview.shape;
    return { ...data, metadata: { ...data.metadata, kind: 'scalar',
        channels: [{ name: 'coherence', quantity: 'structure_tensor_anisotropy', unit: '1' }] },
    preview: { ...data.preview, shape: [height, width, 1],
        values: data.preview.valid.map((_, i) => Math.hypot(
            data.preview.values[2 * i], data.preview.values[2 * i + 1])) } };
}

export function axisReading(values) {
    if (!values || values.length !== 2) return null;
    return { degrees: ((Math.atan2(values[1], values[0]) * 90 / Math.PI) + 180) % 180,
        coherence: Math.hypot(...values) };
}

export function localCells(data, seed, radius) {
    const [height, width] = data.metadata.shape;
    const points = [];
    for (let y = Math.max(0, seed[1] - radius); y <= Math.min(height - 1, seed[1] + radius); y += 1) {
        for (let x = Math.max(0, seed[0] - radius); x <= Math.min(width - 1, seed[0] + radius); x += 1) {
            points.push([x, y]);
        }
    }
    return points;
}
