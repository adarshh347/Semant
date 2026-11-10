/** Pure display conversions; no saved field array is mutated. */
export function labSwatch([L, a, b]) {
    const fy = (L + 16) / 116;
    const cube = (t) => t > 6 / 29 ? t ** 3 : 3 * (6 / 29) ** 2 * (t - 4 / 29);
    const x = .950456 * cube(fy + a / 500);
    const y = cube(fy);
    const z = 1.088754 * cube(fy - b / 200);
    const linear = [3.2404542 * x - 1.5371385 * y - .4985314 * z,
        -.9692660 * x + 1.8760108 * y + .0415560 * z,
        .0556434 * x - .2040259 * y + 1.0572252 * z];
    const encoded = linear.map((v) => v <= .0031308 ? 12.92 * v
        : 1.055 * Math.max(0, v) ** (1 / 2.4) - .055);
    return `rgb(${encoded.map((v) => Math.round(Math.max(0, Math.min(1, v)) * 255)).join(', ')})`;
}

export function pixelsFor(data, channel, opacity, viewRange) {
    const [height, width, count] = data.preview.shape;
    const bytes = new Uint8ClampedArray(height * width * 4);
    const meta = JSON.parse(data.metadata.value_convention);
    const op = meta.form;
    const [lo, hi] = viewRange;
    for (let i = 0; i < width * height; i += 1) {
        const good = data.preview.valid[i];
        const value = data.preview.values[i * count + channel];
        const t = Math.max(0, Math.min(1, (value - lo) / (hi - lo || 1)));
        let colour;
        if (!good) colour = ((i % width + Math.floor(i / width)) % 2)
            ? [70, 70, 70] : [130, 130, 130];
        else if (op === 'channels' && channel < 3) colour = [t * 255, t * 255, t * 255];
        else if (op === 'palette-membership') {
            const hue = ((value * 137.508) % 360) / 60;
            const x = 1 - Math.abs(hue % 2 - 1);
            const sectors = [[1, x, 0], [x, 1, 0], [0, 1, x],
                [0, x, 1], [x, 0, 1], [1, 0, x]];
            colour = sectors[Math.floor(hue)].map((part) => 50 + part * 190);
        } else colour = [Math.round(255 * t), Math.round(210 * (1 - Math.abs(t - .5) * 2)),
            Math.round(255 * (1 - t))];
        bytes.set([...colour, good ? Math.round(opacity * 255) : 255], i * 4);
    }
    return { width, height, bytes };
}
