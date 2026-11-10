/** Pure readers of saved relative inverse depth; no inference or metric conversion. */
export function parseDepthCells(text) {
    const parts = text.split(';');
    if (!text.trim() || parts.length > 4096) throw new Error('Enter 1–4096 explicit native-field cells.');
    return parts.map((part) => {
        if (!/^\s*\d+\s*,\s*\d+\s*$/.test(part)) throw new Error('Use integer native-field coordinates: x,y; x,y');
        const pair = part.split(',').map(Number);
        if (pair.some((value) => !Number.isSafeInteger(value))) throw new Error('Coordinate is too large.');
        return pair;
    });
}

export function depthProfileSegments(samples, [low, high]) {
    if (!Number.isFinite(low) || !Number.isFinite(high) || high <= low) return [];
    const segments = []; let segment = [];
    samples.forEach((sample, index) => {
        if (sample.valid && Number.isFinite(sample.values?.[0])) {
            segment.push(`${index / Math.max(1, samples.length - 1) * 100},${100 - (sample.values[0] - low) / (high - low) * 100}`);
        } else if (segment.length) { segments.push(segment); segment = []; }
    });
    if (segment.length) segments.push(segment);
    return segments;
}

export function compatibleDepth(left, right) {
    return ['shape', 'kind', 'channels', 'frame', 'units', 'source_digest', 'source_to_field', 'value_convention']
        .every((key) => JSON.stringify(left[key]) === JSON.stringify(right[key]));
}

export function depthReceipt(run) {
    const detail = run?.stage_attempts?.find((attempt) => attempt.detail?.includes('; producer receipt '))?.detail;
    if (!detail) return null;
    try { return JSON.parse(detail.split('; producer receipt ')[1]); } catch { return null; }
}
