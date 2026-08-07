/**
 * WAVE4 — where the nodes go. Deterministic, and grouped by image on purpose.
 *
 * ## Why not a force layout
 *
 * A force-directed graph would place these fine and it would place them *differently every time*.
 * The distinction this whole view exists to make — depth THROUGH a picture versus a crossing
 * BETWEEN pictures — is a fact about which image a node lives in, and a layout that lets a physics
 * simulation decide where images sit would render that fact as an accident of the run. So images
 * are columns, in a stable order, and a node's column IS its image.
 *
 * That makes the two spans legible before any line is styled: a within-image edge stays inside one
 * column, and a between-images edge crosses the gap. The stroke treatment is a second channel, not
 * the only one.
 *
 * Pure: coordinates in, coordinates out, no DOM and no randomness.
 */

export const COLUMN_WIDTH = 260;
export const COLUMN_GAP = 96;
export const ROW_HEIGHT = 62;
export const PAD_TOP = 64;
export const PAD_X = 28;

/**
 * Group the nodes into image columns and give each a position.
 *
 * Column order puts the SEED's image first and the rest in the order they were reached, so the
 * picture a reader started from is where they expect it. Within a column, nodes are ordered by hop
 * then id — the seed at the top of its own column, and the walk's shape readable down the page.
 */
export function layout(nodes, { columnWidth = COLUMN_WIDTH, gap = COLUMN_GAP,
                                rowHeight = ROW_HEIGHT, padTop = PAD_TOP } = {}) {
    const seed = nodes.find((n) => n.is_seed);
    const order = [];
    if (seed) order.push(seed.post_id);
    for (const node of nodes) {
        if (!order.includes(node.post_id)) order.push(node.post_id);
    }

    const columns = order.map((postId, index) => {
        const members = nodes
            .filter((n) => n.post_id === postId)
            .sort((a, b) => (a.hop - b.hop) || a.node_id.localeCompare(b.node_id));
        return {
            post_id: postId,
            index,
            x: index * (columnWidth + gap),
            width: columnWidth,
            nodes: members,
        };
    });

    const positions = {};
    for (const column of columns) {
        column.nodes.forEach((node, row) => {
            positions[node.node_id] = {
                x: column.x + columnWidth / 2,
                y: padTop + row * rowHeight,
                column: column.index,
            };
        });
    }

    const rows = Math.max(1, ...columns.map((c) => c.nodes.length));
    return {
        columns,
        positions,
        width: Math.max(columnWidth, columns.length * (columnWidth + gap) - gap) + PAD_X * 2,
        height: padTop + rows * rowHeight + 40,
    };
}

/**
 * A gentle curve between two points, bowed away from the straight line.
 *
 * Straight lines between nodes in the same column overlap into one stripe when several parts sit
 * in front of one wall — which is the commonest shape in this corpus, and it rendered as a single
 * thick line hiding five separate claims. The bow is proportional to the vertical distance so
 * neighbours separate without the long edges becoming loops.
 */
function control(from, to, bow) {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    if (from.column !== to.column) {
        // Between columns: bow VERTICALLY, so a crossing reads as an arc over the gap rather than
        // a straight stab through whatever sits between.
        return { x: from.x + dx / 2,
                 y: from.y + dy / 2 - Math.max(26, Math.abs(dx) * bow * 0.4) };
    }
    // Within a column: bow LEFT, and the direction is not arbitrary. A node's text is drawn to the
    // RIGHT of its dot, so a rightward bow runs every edge straight through the labels it belongs
    // to — which is what the first render did, five occlusions crossing five region names. Left is
    // the empty side.
    //
    // The magnitude scales with the vertical span, so several claims converging on one node
    // separate into distinct arcs instead of stacking into a single stroke.
    return { x: from.x - Math.max(30, Math.abs(dy) * bow),
             y: from.y + dy / 2 };
}

export function curve(from, to, { bow = 0.55 } = {}) {
    const c = control(from, to, bow);
    return `M ${from.x} ${from.y} Q ${c.x} ${c.y} ${to.x} ${to.y}`;
}

/** The midpoint of that curve, for a label — a quadratic Bezier at t = 0.5. */
export function curveMid(from, to, { bow = 0.55 } = {}) {
    const c = control(from, to, bow);
    return { x: 0.25 * from.x + 0.5 * c.x + 0.25 * to.x,
             y: 0.25 * from.y + 0.5 * c.y + 0.25 * to.y };
}
