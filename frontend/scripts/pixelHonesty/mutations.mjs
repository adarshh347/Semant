/**
 * WAVE4 — the mutation table: one plausible lie per honesty guarantee.
 *
 * Each entry is a guarantee, the smallest edit that breaks it, the suite that claims to guard it,
 * and — added when this harness was wired into CI — `expect`: the FULL NAME of the test that must
 * be the one to die.
 *
 * That last field is the whole difference between a harness and a rubber stamp. Without it a
 * mutation counted as guarded when the suite went red for ANY reason, and five of them counted a
 * suite that did not exist. Naming the guard makes a renamed test, a deleted test, and a clumsy
 * mutation that broke something unrelated all read as HOLES rather than as proof.
 *
 * Two rules keep the list honest:
 *
 *   1. A REAL LIE, NOT A SYNTAX ERROR. Deleting a component reddens everything and proves nothing.
 *      Every mutation here is something a well-meaning change could plausibly do — reuse a class,
 *      drop a modifier, soften a distinction, hardcode a value that should have been read.
 *   2. ONE GUARANTEE AT A TIME. A mutation that reddens six unrelated files tells you nothing about
 *      the one you were probing.
 *
 * Scope is the honesty-critical set: the five make-it-seen views plus the provenance chip. It is
 * deliberately not every test in the frontend — a mutation list nobody can read is a mutation list
 * nobody maintains.
 */

export const MUTATIONS = [
    // ── the visual kinds: no two statuses share a treatment ─────────────────
    {
        id: 'curator/status-class-dropped',
        guarantee: 'every status value carries its own class into the DOM, so the stylesheet\'s '
            + 'four treatments can actually land on something',
        file: 'src/curator/StatusPair.jsx',
        find: 'className={`cur-badge cur-badge--epistemic cur-badge--${epistemic}`}',
        replace: 'className={"cur-badge cur-badge--epistemic"}',
        suites: ['src/curator/curator.dom.test.jsx'],
        expect: 'the two statuses are never one carries each status VALUE into the DOM, so the '
            + 'treatments land on something',
    },
    {
        id: 'curator/measured-looks-committed',
        guarantee: 'measured and committed do not share a treatment',
        file: 'src/curator/curator.css',
        cssRule: 'cur-badge--measured',
        copyRuleFrom: 'cur-badge--committed',
        suites: ['src/curator/curator.dom.test.jsx'],
        expect: 'the two statuses are never one gives every status value its own visual treatment',
    },
    {
        id: 'constellation/interpretive-looks-measured',
        guarantee: 'an interpretive edge is dashed; a measured one is not',
        file: 'src/constellation/constellation.css',
        cssRule: 'con-edge--interpretive',
        copyRuleFrom: 'con-edge--measured',
        suites: ['src/constellation/constellation.dom.test.jsx'],
        expect: 'an edge carries its three facts on three channels gives measured, interpretive, '
            + 'unreadable, proposed and committed distinct treatments',
    },
    {
        id: 'constellation/unreadable-called-interpretive',
        guarantee: 'a mark nobody could read is its own state, never softened into interpretive',
        file: 'src/constellation/ConstellationGraph.jsx',
        find: "const known = edge.epistemic || 'no readable mark';",
        replace: "const known = edge.epistemic || 'interpretive';",
        suites: ['src/constellation/constellation.dom.test.jsx'],
        expect: 'an edge carries its three facts on three channels renders an unreadable mark as '
            + 'its own state, never as interpretive',
    },
    {
        id: 'cognition/proposed-looks-measured',
        guarantee: 'a proposed percept does not wear the measured treatment',
        file: 'src/cognition/WalkStream.jsx',
        find: "if (status === 'proposed') return 'cog-status cog-status--proposed';",
        replace: "if (status === 'proposed') return 'cog-status cog-status--measured';",
        suites: ['src/cognition/cognition.dom.test.jsx'],
        expect: 'TestStatusIsDistinct gives every status its own class, not just the one the '
            + 'fixture happens to carry',
    },
    {
        id: 'cognition/status-treatments-collapse',
        guarantee: 'measured, interpretive and proposed are visually distinct in the stylesheet',
        file: 'src/cognition/cognition.css',
        cssRule: 'cog-status--interpretive',
        copyRuleFrom: 'cog-status--measured',
        suites: ['src/cognition/cognition.dom.test.jsx'],
        expect: 'TestStatusIsDistinct gives those classes different treatments in the stylesheet',
    },
    {
        id: 'society/outcomes-collapse',
        guarantee: 'composed, coexistent and incommensurable are three visibly different verdicts',
        file: 'src/society/society.css',
        cssRule: 'soc-verdict--incommensurable',
        copyRuleFrom: 'soc-verdict--composed',
        suites: ['src/society/society.dom.test.jsx'],
        expect: 'TestNoCrossSenseNumber gives those three outcomes three different treatments',
    },
    {
        id: 'scene/interpretive-drawn-solid',
        guarantee: 'a box-basis relation is dashed on the photograph — the founding pathology, '
            + 'in CSS',
        file: 'src/pages/ScenePage.css',
        find: '.scene-link.is-interpretive line { stroke-dasharray: 7 5;',
        replace: '.scene-link.is-interpretive line { stroke-dasharray: none;',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
        expect: 'a relation is drawn as what it is gives the two a different stroke, not a '
            + 'different shade of the same one',
    },
    {
        id: 'scene/status-class-from-nothing',
        guarantee: 'the stroke follows the relation\'s own admissibility, not a constant',
        file: 'src/pages/ScenePage.jsx',
        find: "+ (rel.admissible ? ' is-measured' : ' is-interpretive')",
        replace: "+ ' is-measured'",
        suites: ['src/pages/ScenePage.dom.test.jsx'],
        expect: 'a relation is drawn as what it is draws a box-basis relation as interpretive, '
            + 'never as measured',
    },
    {
        id: 'scene/badge-disagrees-with-stroke',
        guarantee: 'the badge prints the status the stroke was drawn from — the page does not '
            + 'argue with itself',
        file: 'src/pages/ScenePage.jsx',
        find: '<b data-status={rel.epistemic}>{rel.epistemic}</b>',
        replace: '<b data-status="measured">measured</b>',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
        expect: 'the stroke and the badge say the same thing carries the same status in the '
            + 'drawing and in the list',
    },
    {
        id: 'scene/absences-conflated',
        guarantee: 'never-derived and derived-and-none-here stay two different absences',
        file: 'src/pages/ScenePage.jsx',
        find: 'never derived: {absent.join(\', \')}',
        replace: 'never derived: {[...absent, ...(noneHere || [])].join(\', \')}',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
        expect: 'an absence is stated as the kind of absence it is separates "never derived" from '
            + '"derived and none here"',
    },
    {
        id: 'scene/proposed-marker-filled',
        guarantee: 'a proposed relation\'s marker is hollow — filled means a curator accepted it',
        file: 'src/pages/ScenePage.css',
        find: '.scene-link.is-proposed circle { fill: none; }',
        replace: '.scene-link.is-proposed circle { fill: currentColor; }',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
        expect: 'a relation is drawn as what it is keeps a proposed marker hollow and a committed '
            + 'one filled',
    },

    // ── incommensurable shows no number ────────────────────────────────────
    {
        id: 'society/incommensurable-grows-a-number',
        guarantee: 'a refused cross-sense comparison carries no number, in any notation',
        file: 'src/society/SocietyPage.jsx',
        find: '<p className="soc-verdict-detail">{verdict.detail}</p>',
        replace: '<p className="soc-verdict-detail">{verdict.detail} (87%)</p>',
        suites: ['src/society/society.dom.test.jsx'],
        expect: 'TestNoCrossSenseNumber renders the incommensurable pair with its refusal and no '
            + 'number',
    },
    {
        id: 'markProvenance/chip-bypasses-summarize',
        guarantee: 'the workspace\'s real chip goes through summarizeProvenance, so the stand-in '
            + 'that suite mounts cannot drift away from it unnoticed',
        file: 'src/differential/DifferentialWorkspace.jsx',
        find: '{summarizeProvenance(gm)}',
        replace: '{gm.source}',
        suites: ['src/differential/markProvenance.dom.test.jsx'],
        expect: 'the chip above is the chip the workspace actually renders renders every '
            + 'provenance chip through summarizeProvenance',
    },
    {
        id: 'markProvenance/confidence-rendered',
        guarantee: 'a suggestion never shows a confidence number',
        file: 'src/differential/suggestionQuarantine.js',
        find: "case 'model_suggested': return 'Model suggestion — not accepted';",
        replace: "case 'model_suggested': return 'Model suggestion — not accepted (0.94)';",
        suites: ['src/differential/markProvenance.dom.test.jsx'],
        expect: 'the provenance chip on a committed ground never renders a confidence number',
    },

    // ── refusals render as content ─────────────────────────────────────────
    {
        id: 'cognition/refusal-swallowed',
        guarantee: 'a refusal is rendered, not dropped',
        file: 'src/cognition/WalkStream.jsx',
        find: '<li className="cog-refusal" data-about={row.about}>',
        replace: '<li className="cog-refusal" data-about={row.about} hidden '
            + 'style={{display:"none"}}>',
        suites: ['src/cognition/cognition.dom.test.jsx'],
        expect: 'TestRefusalsRender renders a refusal as something a person can actually see',
    },
    {
        id: 'cognition/refusal-families-merged',
        guarantee: 'the two families of refusal stay distinguishable',
        file: 'src/cognition/WalkStream.jsx',
        find: 'data-about={row.about}',
        replace: 'data-about="edge"',
        suites: ['src/cognition/cognition.dom.test.jsx'],
        expect: 'TestRefusalsRender keeps the two families of refusal visually distinguishable',
    },

    // ── no shape where a measurement is missing; one renderer ──────────────
    {
        id: 'curatorMasks/box-drawn-for-missing-mask',
        guarantee: 'no shape is drawn where a mask is missing — the WAVE2.5 failure at the seam '
            + 'where it would become durable',
        file: 'src/curator/ProposalMasks.jsx',
        find: `    const drawable = !!pair
        && (pair.front.polygons || []).length > 0
        && (pair.back.polygons || []).length > 0;`,
        replace: '    const drawable = !!pair;',
        suites: ['src/curator/proposalMasks.dom.test.jsx'],
        expect: 'no shape is drawn where a measurement is missing degrades to a stated absence '
            + 'when a region has no outline',
    },
    {
        id: 'curatorMasks/second-renderer',
        guarantee: 'shapes are drawn by the one shared overlay, not a private copy',
        file: 'src/curator/ProposalMasks.jsx',
        find: "import RegionOverlay from '../components/RegionOverlay';",
        replace: 'const RegionOverlay = ({ className }) => <svg className={className} />;',
        suites: ['src/curator/proposalMasks.dom.test.jsx'],
        expect: 'one renderer draws through the shared RegionOverlay rather than a second '
            + 'implementation',
    },
    {
        id: 'curatorMasks/front-and-back-alike',
        guarantee: 'the region in front is visibly the figure — the whole claim',
        file: 'src/curator/ProposalMasks.jsx',
        find: 'litIds={new Set([pair.front.id])}',
        replace: 'litIds={new Set()}',
        suites: ['src/curator/proposalMasks.dom.test.jsx'],
        expect: 'front and back are distinguishable, because that is the claim lights the front '
            + 'region and grounds the one behind',
    },

    // ── a proposal never looks accepted ────────────────────────────────────
    {
        id: 'curatorMasks/ledger-status-hardcoded',
        guarantee: 'the overlay carries the proposal\'s real statuses, not an assumed one',
        file: 'src/curator/ProposalMasks.jsx',
        find: "data-epistemic={proposal?.epistemic || 'unknown'}",
        replace: "data-epistemic={'measured'}",
        suites: ['src/curator/proposalMasks.dom.test.jsx'],
        expect: 'the overlay never implies the proposal is accepted marks a box-basis proposal so '
            + 'the stroke can say it is an estimate',
    },
    {
        id: 'world/oversells',
        guarantee: 'the front door reads the ledger rather than asserting what has been settled',
        file: 'src/pages/WorldPage.jsx',
        find: 'queue. <b>{committed}</b>',
        replace: 'queue. <b>{0}</b>',
        suites: ['src/pages/WorldPage.dom.test.jsx'],
        expect: 'the front door does not oversell reads the number from the ledger rather than '
            + 'asserting it',
    },
    {
        id: 'world/unreachable-rendered-as-link',
        guarantee: 'a surface whose backend is silent is not-a-door, not a dim link',
        file: 'src/pages/WorldPage.jsx',
        find: 'const reachable = state === LIVE;',
        replace: 'const reachable = true;',
        suites: ['src/pages/WorldPage.dom.test.jsx'],
        expect: 'liveness is probed, not declared marks an unreachable surface as not-a-door '
            + 'rather than a dim link',
    },
];

// ── applying a lie ─────────────────────────────────────────────────────────

function ruleBody(css, name) {
    const m = css.match(new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`));
    return m ? m[1] : null;
}

/** Make one rule's body identical to another's — "these two look the same now". */
function collapseRule(css, target, source) {
    const body = ruleBody(css, source);
    if (body === null) throw new Error(`no rule .${source} to copy from`);
    const re = new RegExp(`(\\.${target}\\s*\\{)([^}]*)(\\})`);
    if (!re.test(css)) throw new Error(`no rule .${target} to collapse`);
    return css.replace(re, `$1${body}$3`);
}

export function mutate(m, original) {
    if (m.cssRule) return collapseRule(original, m.cssRule, m.copyRuleFrom);
    if (!original.includes(m.find)) throw new Error(`anchor not found: ${m.find.slice(0, 60)}…`);
    return original.replace(m.find, m.replace);
}
