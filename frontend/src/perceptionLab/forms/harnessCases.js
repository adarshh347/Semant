// PERCEPTUAL-FORMS-001E — the scenes the harness and the screenshot script both drive.
//
// Split out of `FormHarness.jsx` so that file exports only components (react-refresh), and
// because a screenshot index and a responsive suite should be reading the SAME list as the page:
// a screenshot of a scene nobody tests, or a test of a scene nobody photographs, is how the two
// drift apart.
//
// Each case is chosen for a specific thing it is hard to get right, named in `why`. That sentence
// becomes the caption in the screenshot index.

export const HARNESS_CASES = Object.freeze([
    {
        key: 'hard_mask_fill',
        label: 'Hard mask',
        form: 'extent.hard_mask',
        view: 'fill',
        at: '2026-08-22T00:00:00Z',
        why: 'an 8×8 run-length mask landing at the right eighths of a 4:3 frame, with the '
            + 'box-only instance refusing rather than showing a rectangle in a mask\'s place',
    },
    {
        key: 'partition_tricolor',
        label: 'Visible · inferred · unknown',
        form: 'extent.visible_inferred_partition',
        view: 'tricolor',
        at: '2026-08-22T00:00:00Z',
        why: 'the three treatments side by side — solid, hatched at 45°, and a graded field. This '
            + 'is the picture the "inferred is never indistinguishable from visible" rule exists '
            + 'to produce',
    },
    {
        key: 'soft_field_threshold',
        label: 'Threshold sweep',
        form: 'extent.soft_field',
        view: 'threshold',
        at: '2026-08-22T00:00:00Z',
        why: 'a scalar field cut into a binary one, with the number on screen and the whole field '
            + 'still visible underneath it',
    },
    {
        key: 'hypothesis_split',
        label: 'Alternatives, split',
        form: 'extent.hypothesis_set',
        view: 'split',
        at: '2026-08-22T00:00:00Z',
        why: 'three readings in three panes. Nothing is superimposed, and the default view is the '
            + 'one that shows a single reading at a time',
    },
    {
        key: 'adjacency_matrix',
        label: 'Adjacency matrix',
        form: 'topology.adjacency_graph',
        view: 'matrix',
        at: '2026-08-22T00:00:00Z',
        why: 'six pairs examined, three edges recorded — and the blank cells say "examined and '
            + 'unrelated" rather than being empty space in a node-link drawing',
    },
    {
        key: 'negative_space',
        label: 'Negative space',
        form: 'topology.negative_space_field',
        view: 'wash',
        at: '2026-08-22T00:00:00Z',
        why: 'the measured field absent because it lives behind a ref this page cannot read, and '
            + 'the browser-computed field beside it, stamped as the browser\'s own work',
    },
    {
        key: 'containment_tree',
        label: 'Containment tree',
        form: 'topology.containment_tree',
        view: 'tree',
        at: '2026-08-22T00:00:00Z',
        why: 'a diagram in diagram space, with every edge directed and the direction also written '
            + 'out — and three endpoints that do not resolve, drawn hollow and named',
    },
    {
        key: 'dense_relations',
        label: 'Dense relations',
        form: 'topology.pair_relation',
        view: 'list',
        at: '2026-08-22T00:00:00Z',
        why: 'eighteen relations, six kinds, mixed bases and one stale — a layout that was only '
            + 'tested with two would break here',
    },
]);
