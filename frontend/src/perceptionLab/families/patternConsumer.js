export function patchCells(x, y, width, height, shape) {
    const [rows, columns] = shape;
    if (![x, y, width, height].every(Number.isInteger) || width < 1 || height < 1
        || x < 0 || y < 0 || x + width > columns || y + height > rows
        || width * height > 4096) throw new Error('Choose a patch of 1–4096 cells inside the field.');
    return Array.from({ length: width * height }, (_, index) =>
        [x + index % width, y + Math.floor(index / width)]);
}

export function descriptor(data, points) {
    const [height, width, count] = data.preview.shape;
    if (data.preview.stride !== 1 || data.metadata.shape[0] !== height
        || data.metadata.shape[1] !== width) throw new Error('Full saved grid is needed for patch comparison.');
    const support = points.map(([x, y]) => y * width + x);
    const valid = support.filter((index) => data.preview.valid[index]);
    if (!valid.length) throw new Error('The selected patch has no valid cells.');
    return { fieldHash: data.measurement_hash, support: points,
        channels: data.metadata.channels,
        means: Array.from({ length: count }, (_, c) => valid.reduce((sum, index) =>
            sum + data.preview.values[index * count + c], 0) / valid.length) };
}

export function similarity(data, reference, patchWidth, patchHeight) {
    if (reference.fieldHash !== data.measurement_hash
        || JSON.stringify(reference.channels) !== JSON.stringify(data.metadata.channels)) {
        throw new Error('Reference descriptor uses another saved field or channel space.');
    }
    const [height, width, count] = data.preview.shape;
    const norm = (v) => Math.hypot(...v);
    const refNorm = norm(reference.means);
    if (refNorm < 1e-12) throw new Error('Reference has no pattern response.');
    const values = [], valid = [];
    for (let y = 0; y < height; y += 1) for (let x = 0; x < width; x += 1) {
        const x0 = Math.max(0, x - Math.floor(patchWidth / 2));
        const y0 = Math.max(0, y - Math.floor(patchHeight / 2));
        const indices = [];
        for (let yy = y0; yy < Math.min(height, y0 + patchHeight); yy += 1) {
            for (let xx = x0; xx < Math.min(width, x0 + patchWidth); xx += 1) indices.push(yy * width + xx);
        }
        if (indices.some((index) => !data.preview.valid[index])) {
            values.push(0); valid.push(false); continue;
        }
        const local = Array.from({ length: count }, (_, c) => indices.reduce((sum, index) =>
            sum + data.preview.values[index * count + c], 0) / indices.length);
        const localNorm = norm(local);
        valid.push(localNorm > 1e-12);
        values.push(localNorm > 1e-12 ? local.reduce((sum, v, i) =>
            sum + v * reference.means[i], 0) / (localNorm * refNorm) : 0);
    }
    return { shape: [height, width, 1], stride: 1, values, valid };
}

