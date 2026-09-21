// An independently versioned semantic session extension, never a Differential Ground.
export const CONSTELLATION_VERSION = 'semantic-constellations.v1';
export const PRESERVATION_VALUES = ['not_assessed', 'preserved', 'partly_preserved', 'lost', 'unclear'];

export function normalizeConstellations(value) {
    const raw = value && typeof value === 'object' ? value : {};
    return {
        schema_version: raw.schema_version || '',
        known: raw.schema_version === CONSTELLATION_VERSION,
        recorded: raw.recorded === true,
        preparation: raw.preparation || 'not_requested',
        paused: raw.paused === true,
        // The strict versioned records pass through whole. No ancestry or judgment is inferred.
        current: Array.isArray(raw.current) ? raw.current : [],
        history: Array.isArray(raw.history) ? raw.history : [],
        sources: Array.isArray(raw.sources) ? raw.sources : [],
    };
}

export function selectedAnchor(source, start, end) {
    // DOM selection offsets count UTF-16 units; server spans count Unicode code points.
    return { origin: source.origin, source_id: source.source_id,
        span: [Array.from(source.text.slice(0, start)).length, Array.from(source.text.slice(0, end)).length],
        exact_text: source.text.slice(start, end) };
}
