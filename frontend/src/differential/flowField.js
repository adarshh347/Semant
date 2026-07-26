/**
 * Flow-field geometry (CIRCUIT-001 GEOM-001) — the pure reader for the dense direction kind.
 *
 * A `flow_field` is the geometry a `fall_of_light` (and later `gaze_address` / `architectural_axis`)
 * trace mark carries: a UNIT direction + a magnitude at every cell of a coarse lattice. A scalar
 * `soft_mask` says how STRONG a field is at each cell; a `flow_field` says which WAY it points —
 * which is a different fact and needs a different kind. `vector` holds ONE direction (from→to);
 * this holds a direction per cell.
 *
 * Descriptor (matches the backend `shading_flow_field` / `suggestion_from_fall_of_light` output):
 *   { kind: 'flow_field', cols, rows, cells: [[dx, dy, m], ...] }   // row-major, len = cols*rows
 * per cell: (dx, dy) a unit direction (or [0,0] for a null cell), m ∈ [0,1] the magnitude.
 *
 * This module authors no pixels and touches no DOM: it validates a descriptor and turns it into
 * cell-centre samples in NORMALIZED image space, which a renderer (`FlowFieldLayer`) maps to px.
 * Read-only — the field is produced, not hand-drawn (editing is a later gate).
 */

export const FLOW_FIELD_KIND = 'flow_field';

const isNum = (v) => typeof v === 'number' && Number.isFinite(v);
const isCell = (c) => Array.isArray(c) && c.length >= 3 && isNum(c[0]) && isNum(c[1]) && isNum(c[2]);

/** Is this geometry a flow_field? (kind only — validity is `normalizeFlowField`.) */
export function isFlowField(geometry) {
    return !!geometry && typeof geometry === 'object' && geometry.kind === FLOW_FIELD_KIND;
}

/**
 * Validate + normalize a flow_field descriptor. Returns `{ cols, rows, cells }` with exactly
 * `cols*rows` well-formed cells, or `null` when the shape is wrong (bad dims, wrong cell count,
 * a malformed cell). A refusal here is honest: a broken field renders as nothing, never as a
 * guess. Magnitudes are clamped to [0,1]; a null/short direction collapses to a null cell.
 */
export function normalizeFlowField(geometry) {
    if (!isFlowField(geometry)) return null;
    const cols = geometry.cols;
    const rows = geometry.rows;
    if (!Number.isInteger(cols) || !Number.isInteger(rows) || cols < 1 || rows < 1) return null;
    const raw = geometry.cells;
    if (!Array.isArray(raw) || raw.length !== cols * rows) return null;
    const cells = [];
    for (const c of raw) {
        if (!isCell(c)) return null;
        const dx = c[0];
        const dy = c[1];
        const m = Math.min(1, Math.max(0, c[2]));
        const len = Math.hypot(dx, dy);
        // A cell with no direction (or a degenerate one) is a null cell — nothing to draw there.
        if (len <= 1e-9 || m <= 0) cells.push([0, 0, 0]);
        else cells.push([dx / len, dy / len, m]);   // re-unitize defensively
    }
    return { cols, rows, cells };
}

/**
 * The drawable cells of a flow_field, as samples in NORMALIZED [0,1] image space. One entry per
 * NON-null cell (a null cell has no direction, so it contributes nothing):
 *   { col, row, cx, cy, dx, dy, m }
 * `cx, cy` is the cell centre; `dx, dy` the unit direction; `m` the magnitude. Empty array for a
 * missing/invalid/all-null field. A renderer scales `(dx, dy)` by `m` and a length to get a segment.
 */
export function flowFieldCells(geometry) {
    const f = normalizeFlowField(geometry);
    if (!f) return [];
    const out = [];
    for (let row = 0; row < f.rows; row++) {
        for (let col = 0; col < f.cols; col++) {
            const [dx, dy, m] = f.cells[row * f.cols + col];
            if (m <= 0) continue;                   // null cell — honest absence
            out.push({
                col, row,
                cx: (col + 0.5) / f.cols,
                cy: (row + 0.5) / f.rows,
                dx, dy, m,
            });
        }
    }
    return out;
}

/**
 * A one-line reading ABOUT a flow_field — counts and its coherence, never geometry. `coherence`
 * is the magnitude-weighted mean resultant length of the unit directions in [0,1]: 1.0 is a single
 * raking light (every arrow parallel), near 0 a swirling field. Mirrors the backend's
 * `flow_field_coherence` so the frontend can state the same fact the producer's confidence carries.
 */
export function flowFieldStats(geometry) {
    const f = normalizeFlowField(geometry);
    if (!f) return { cells: 0, active: 0, meanMagnitude: 0, coherence: 0 };
    let active = 0;
    let sumM = 0;
    let sx = 0;
    let sy = 0;
    for (const [dx, dy, m] of f.cells) {
        if (m <= 0) continue;
        active++;
        sumM += m;
        sx += dx * m;
        sy += dy * m;
    }
    const total = f.cols * f.rows;
    return {
        cells: total,
        active,
        meanMagnitude: active ? round4(sumM / active) : 0,
        coherence: sumM > 1e-9 ? round4(Math.hypot(sx, sy) / sumM) : 0,
    };
}

const round4 = (v) => Math.round(v * 1e4) / 1e4;
