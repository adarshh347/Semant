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

    // ── HARNESS-002 · the inquiry workbench ─────────────────────────────────
    //
    // Handed here by Lane C, which wrote the guards and could not add the mutations: this file is
    // outside its write set. They are the same shape as the ones above and probe the one thing
    // Phase 1 rests on entirely — that a SIMULATED capability receipt cannot be read as a finding.
    // Its payload is a plausible-looking region on purpose, so these are the mutations that matter
    // most in the whole table.
    {
        id: 'inquiry/simulated-label-dropped',
        guarantee: 'the SIMULATED label sits beside the payload in text, permanently, and not in '
            + 'a badge a reader can scroll past',
        file: 'src/inquiryWorkbench/CapabilityActivity.jsx',
        find: '<p className="iw-simulated" data-simulated="true">',
        replace: '<p className="iw-quiet" data-simulated="false">',
        suites: ['src/inquiryWorkbench/inquiryOutput.dom.test.jsx'],
        expect: 'the SIMULATED label sits beside the payload in TEXT, not in a tooltip',
    },
    {
        id: 'inquiry/simulated-not-repeated-beside-geometry',
        guarantee: 'the label is repeated beside the geometry itself, so a reader who expanded one '
            + 'row out of a long list does not have to remember which one they opened',
        file: 'src/inquiryWorkbench/CapabilityActivity.jsx',
        find: 'SIMULATED — not evidence. This geometry was produced by a',
        replace: 'This geometry was produced by a',
        suites: ['src/inquiryWorkbench/simulationHonesty.dom.test.jsx'],
        expect: 'the SIMULATED label is where a reader cannot miss it says it AGAIN beside the '
            + 'geometry once the payload is open',
    },
    {
        id: 'inquiry/simulated-can-be-evidence',
        guarantee: 'a simulated object never supports a claim, whatever its usable flag says',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '    if (obj.simulated) return false;',
        replace: '',
        suites: ['src/inquiryWorkbench/simulationHonesty.dom.test.jsx'],
        expect: 'a simulated receipt cannot be talked into being evidence a fixture receipt that '
            + 'arrived claiming to be usable is still not evidence',
    },
    {
        id: 'inquiry/reading-ceiling-lifted',
        guarantee: 'a scene reading is interpretive at strongest, and an over-declared one is '
            + 'capped VISIBLY rather than rendered or silently downgraded',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '        capped_from: overreach ? declared : null,',
        replace: '        capped_from: null,',
        suites: ['src/inquiryWorkbench/inquiryGraph.dom.test.jsx'],
        expect: 'the provisional reading a reading that arrived claiming measured is capped, and '
            + 'the cap is SHOWN',
    },
    {
        id: 'inquiry/fixture-outcome-reads-as-its-status',
        guarantee: 'a fixture execution mode is `simulated` whatever the backend called the status '
            + '— the one place the client overrides a supplied value, and only downward',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "    receipt.simulated = receipt.execution_mode.value === 'fixture'\n        || receipt.status.value === 'simulated';",
        replace: "    receipt.simulated = receipt.status.value === 'simulated';",
        suites: ['src/inquiryWorkbench/simulationHonesty.dom.test.jsx'],
        expect: 'a simulated receipt cannot be talked into being evidence a fixture receipt whose '
            + 'status contradicts its mode still reads as simulated',
    },
    {
        id: 'inquiry/unknown-state-ends-the-watch',
        guarantee: 'a state this client does not recognise means the server is newer, and "not '
            + 'finished yet" is the only reading of it that cannot lose work',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '    !IS_TERMINAL_STATE(state) && !IS_AWAITING_USER(state);',
        replace: '    SESSION_STATES.includes(state) && !IS_TERMINAL_STATE(state) '
            + '&& !IS_AWAITING_USER(state);',
        suites: ['src/inquiryWorkbench/inquiryContract.test.js'],
        expect: 'the session lifecycle keeps watching an UNRECOGNISED state rather than calling '
            + 'it finished',
    },
    {
        id: 'inquiry/missing-usable-flag-reads-as-permission',
        guarantee: 'a missing `usable_as_evidence` is not permission; every gate tests === true',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '    return obj.usable_as_evidence === true;',
        replace: '    return obj.usable_as_evidence !== false;',
        suites: ['src/inquiryWorkbench/simulationHonesty.dom.test.jsx'],
        expect: 'a simulated receipt cannot be talked into being evidence an evidence object that '
            + 'does not say whether it is usable is not usable',
    },
    {
        id: 'inquiry/simulated-wears-the-live-treatment',
        guarantee: 'simulated and live do not share a visual treatment',
        file: 'src/inquiryWorkbench/inquiryWorkbench.css',
        cssRule: 'iw-outcome--simulated',
        copyRuleFrom: 'iw-outcome--live',
        suites: ['src/inquiryWorkbench/inquiryWorkbench.dom.test.jsx'],
        expect: 'the stylesheet keeps the distinctions it claims never lets simulated wear the '
            + 'live treatment',
    },
    {
        id: 'inquiry/gap-looks-like-unavailable',
        guarantee: '"nothing exists that could do this" and "it exists and is not running" are '
            + 'different rows, because only one of them is worth retrying',
        file: 'src/inquiryWorkbench/inquiryWorkbench.css',
        cssRule: 'iw-outcome--capability_gap',
        copyRuleFrom: 'iw-outcome--unavailable',
        suites: ['src/inquiryWorkbench/inquiryWorkbench.dom.test.jsx'],
        expect: 'the stylesheet keeps the distinctions it claims gives every capability outcome '
            + 'its own treatment',
    },
    {
        id: 'inquiry/absent-latency-rendered-as-zero',
        guarantee: 'a measurement that was never taken is an em dash, never an instant one',
        file: 'src/inquiryWorkbench/CapabilityActivity.jsx',
        find: "{r.latency_ms === null ? '—' : `${r.latency_ms} ms`}",
        replace: '{`${r.latency_ms || 0} ms`}',
        suites: ['src/inquiryWorkbench/inquiryOutput.dom.test.jsx'],
        expect: 'capability activity a missing latency is an em dash, never 0 ms',
    },
    {
        id: 'inquiry/attempted-not-printed',
        guarantee: '`attempted` is the single field separating "ran and found nothing" from "was '
            + 'never there", and it is printed rather than inferred',
        file: 'src/inquiryWorkbench/CapabilityActivity.jsx',
        find: "                    {r.attempted === false ? 'not attempted' : null}",
        replace: '                    {null}',
        suites: ['src/inquiryWorkbench/inquiryOutput.dom.test.jsx'],
        expect: 'capability activity prints whether anything was ATTEMPTED, which is what '
            + 'separates empty from unavailable',
    },

    // ── HARNESS-003C · the mechanism made visible ───────────────────────────
    //
    // Lane C's second hand-off, taken here for the same reason as the first: this file is outside
    // its write set. Its finding said "twenty-six entries are now waiting (eleven from 002C,
    // fifteen from here)" and both halves of that are wrong — the eleven landed with 002D, and the
    // fifteen was written before the reconciliation added five more. TWENTY is the number, and it
    // is the count of guarantees below.
    //
    // The last five are not pixel honesty at all. They are the two product failures 002R actually
    // hit — a truncated run reading as a completed one, a fixture reading as a finding — plus the
    // three distinctions the repair turned on, and they now fail a test rather than a rehearsal.
    {
        id: 'inquiry/truncated-reads-as-completed',
        guarantee: 'a run that stopped on its output budget is an underperformance, so the '
            + 'diagnosis appears for it at all',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "export const UNDERPERFORMING_OUTCOMES = ['thin', 'truncated', 'empty'];",
        replace: "export const UNDERPERFORMING_OUTCOMES = ['thin', 'empty'];",
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestTruncatedIsNotComplete a truncated run cannot look like a completed one',
    },
    {
        id: 'inquiry/diagnosis-collapsed',
        guarantee: 'the diagnosis is OPEN and above the prose — a collapsed one under a fluent '
            + 'paragraph is a diagnosis nobody reads',
        file: 'src/inquiryWorkbench/DiagnosisCard.jsx',
        find: '            <h2 className="iw-diagnosis-head">',
        replace: '            <button type="button" aria-expanded="false">Details</button>\n'
            + '            <h2 className="iw-diagnosis-head">',
        suites: ['src/inquiryWorkbench/diagnosis.dom.test.jsx'],
        expect: 'the diagnosis card appears OPEN for a truncated run — no toggle to find',
    },
    {
        id: 'inquiry/absence-zeroes-dropped',
        guarantee: 'what a run did not create is printed as a zero, because a blank where a count '
            + 'belongs reads as "pending" to every reader',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '<li data-absent="grounds"><b>grounds created: 0</b></li>',
        replace: '<li data-absent="grounds"><b>grounds created</b></li>',
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestAbsenceIsPrinted grounds, percepts, evidence and Atlas are printed as zeroes',
    },
    {
        id: 'inquiry/absence-reads-as-pending',
        guarantee: 'a finished run says it DID not create them, never that it will',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: "? 'This run is over and created none of these. '",
        replace: "? 'These will be created once the run finishes. '",
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestAbsenceIsPrinted says a finished run did not create them, never that they '
            + 'are pending',
    },
    {
        id: 'inquiry/simulated-label-lost-in-ledger',
        guarantee: 'SIMULATED survives into the artifact ledger — the one place a receipt is read '
            + 'beside real artifacts, and so the one place the label is easiest to lose',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '                                    {r.simulated ? (',
        replace: '                                    {false ? (',
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestSimulationSurvivesTheLedger a fixture receipt still says SIMULATED inside '
            + 'the artifact ledger',
    },
    {
        id: 'inquiry/reading-only-note-dropped',
        guarantee: 'a run whose only prose is the scene reading says so BEFORE the reading — the '
            + 'exact shape of the 002R rehearsal, where a perceptive paragraph stood in for an '
            + 'inquiry that never happened',
        file: 'src/inquiryWorkbench/DiagnosisCard.jsx',
        find: '            {readingOnly ? (',
        replace: '            {false ? (',
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestReadingOnlyIsDeclared a barren run says the prose below is only the scene '
            + 'reading',
    },
    {
        id: 'inquiry/null-duration-rendered-as-zero',
        guarantee: 'a duration nobody measured is an em dash; 0 ms is a measurement',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "    if (ms === null || ms === undefined || !Number.isFinite(ms)) return '—';",
        replace: '    if (ms === null || ms === undefined || !Number.isFinite(ms)) '
            + 'return `${ms || 0} ms`;',
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestElapsedIsNotDuration an unmeasured duration is an em dash, never zero',
    },
    {
        id: 'inquiry/elapsed-counted-from-nothing',
        guarantee: 'a clock counting up from an unknown start is a fabricated measurement, and '
            + 'the most believable kind',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '    if (!from) return null;',
        replace: '    if (!from) return 0;',
        suites: ['src/inquiryWorkbench/stageActivity.dom.test.jsx'],
        expect: 'a duration nobody measured refuses to count elapsed from an origin the stage '
            + 'never gave',
    },
    {
        id: 'inquiry/lost-source-unit-reads-as-remainder',
        guarantee: 'a source unit with NO disposition is one the compiler lost; a remainder is a '
            + 'decision, and the two send a reader to opposite repairs',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '    const covered = new Set((graph?.coverage || []).map((c) => c.source_unit_id));\n'
            + '    return (graph?.source_units || []).filter((u) => !covered.has(u.source_unit_id));',
        replace: '    return [];',
        suites: ['src/inquiryWorkbench/artifactLedger.dom.test.jsx'],
        expect: 'the dissolution ledger names a source unit that received NO disposition, as lost '
            + 'rather than as remainder',
    },
    {
        id: 'inquiry/search-scope-note-dropped',
        guarantee: 'a filter over a partly-loaded corpus says what it filtered, so "no results" '
            + 'cannot read as "the archive does not contain this"',
        file: 'src/inquiryCorpus/CorpusPicker.jsx',
        find: '            {query.trim() ? (\n'
            + '                <p className="ic-scope" role="status" data-scope-note="true">',
        replace: '            {false ? (\n'
            + '                <p className="ic-scope" role="status" data-scope-note="true">',
        suites: ['src/inquiryCorpus/corpusPicker.dom.test.jsx'],
        expect: 'filtering says what it filtered names the loaded fraction while the corpus is '
            + 'incomplete',
    },
    {
        id: 'inquiry/upload-success-on-failure',
        guarantee: 'the upload failure path ENDS at the catch: a network error is reported as '
            + 'itself, never as a success that happened to return nothing',
        file: 'src/components/UploadForm.jsx',
        // The obvious lie — dropping the `return` alone — is a CRASH, not a lie: `created` is
        // undefined on that path. Adding the `created = []` a refactorer would have to add is
        // what makes this the mutation the table's first rule asks for.
        find: '      setBusy(false);\n      return;\n    }',
        replace: '      setBusy(false);\n      created = [];\n    }',
        suites: ['src/inquiryCorpus/uploadAndInclude.dom.test.jsx'],
        expect: 'uploading from the inquiry, end to end a failed upload changes nothing about the '
            + 'selection or the draft',
    },
    {
        id: 'inquiry/derived-count-invented',
        guarantee: 'a count this surface worked out is a guess wearing the backend\'s authority, '
            + 'and the numbers ARE the diagnosis',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '            ?? (Array.isArray(v.output_refs) ? v.output_refs.length : null),',
        replace: '            ?? 0,',
        suites: ['src/inquiryWorkbench/diagnosis.dom.test.jsx'],
        expect: 'what entered and what emerged says "not recorded" rather than inventing a count',
    },
    {
        id: 'inquiry/export-ships-the-derived-view',
        guarantee: 'the exported file is the BACKEND\'s body — a file mixing in this client\'s '
            + 'inferences lets a reader attribute them to the runtime',
        file: 'src/inquiryWorkbench/SessionExport.jsx',
        find: "    const body = session.raw && typeof session.raw === 'object' ? session.raw : {};",
        replace: '    const body = session;',
        suites: ['src/inquiryWorkbench/diagnosis.dom.test.jsx'],
        expect: 'taking the session away exports the BACKEND\'s body, not this page\'s reading of it',
    },
    {
        id: 'inquiry/selection-lost-across-pages',
        guarantee: 'the tray is the person\'s OWN selection, not the intersection of it with '
            + 'whatever the grid is currently showing',
        file: 'src/inquiryCorpus/CorpusPicker.jsx',
        find: '                        {selected.map((p) => (',
        replace: '                        {shown.filter((q) => selectedIds.has(q.id)).map((p) => (',
        suites: ['src/inquiryCorpus/corpusPicker.dom.test.jsx'],
        // Lane C paired this with the paging test, which no single lie can reach: `mergePosts`
        // keeps every page loaded, so a tray derived from the grid still holds all three. The
        // filter case in the same block is where the lie shows, so that is the guard named.
        expect: 'a selection that survives the corpus moving under it keeps a selected image in '
            + 'the tray when a filter hides it from the grid',
    },
    {
        id: 'inquiry/archive-store-forked',
        guarantee: 'the picker reads the Archive\'s cache under the Archive\'s key, so the two '
            + 'surfaces cannot hold different ideas of what page 3 contains',
        file: 'src/inquiryCorpus/corpusClient.js',
        find: '            queryKey: PAGE_KEY(tag, n),',
        replace: "            queryKey: ['inquiry', 'posts', tag, n],",
        suites: ['src/inquiryCorpus/corpusPicker.dom.test.jsx'],
        expect: 'the picker reads the Archive\'s cache, not a second copy serves a page the '
            + 'Archive already fetched without touching the network',
    },
    {
        id: 'inquiry/truncation-unknown-reads-as-none',
        guarantee: '`unknown` says nothing could be consulted and `none` says something was '
            + 'consulted and said no — collapsing them reports an unchecked stage as a verified one',
        file: 'src/inquiryWorkbench/StageActivity.jsx',
        find: "                {s.truncation_source.value && s.truncation_source.value !== 'none' ? (",
        replace: "                {s.truncation_source.value && s.truncation_source.value !== 'none'\n"
            + "                    && s.truncation_source.value !== 'unknown' ? (",
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestTruncationSourceIsNotCollapsed `unknown` and `none` do not render alike',
    },
    {
        id: 'inquiry/declared-underperformance-ignored',
        guarantee: 'the backend declares `underperformed` from checks this client cannot see, and '
            + 'a client that recomputed it would be second-guessing the runtime that knows',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "    stage.underperformed = typeof v.underperformed === 'boolean'\n"
            + '        ? v.underperformed\n'
            + '        : UNDERPERFORMING_OUTCOMES.includes(stage.outcome.value);',
        replace: '    stage.underperformed = '
            + 'UNDERPERFORMING_OUTCOMES.includes(stage.outcome.value);',
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestDeclaredUnderperformanceWins honours the backend\'s `underperformed`, rather '
            + 'than second-guessing it',
    },
    {
        id: 'inquiry/execution-failure-called-thinking',
        guarantee: 'a stage that RAISED and a stage that came back thin are different failures — '
            + 'merging them sends a reader to raise an output budget when the process was killed',
        file: 'src/inquiryWorkbench/DiagnosisCard.jsx',
        find: "                        data-failure-kind={worst.failed ? 'execution' : 'semantic'}",
        replace: '                        data-failure-kind="semantic"',
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestExecutionFailureIsNotThinking separates a stage that RAISED from one that '
            + 'came back thin',
    },
    {
        id: 'inquiry/named-counts-replaced-by-numbers',
        guarantee: 'the stage\'s own counts line is rendered — "2 images in → 8 reading blocks '
            + 'out" says what the numbers COUNT, and bare numbers do not',
        file: 'src/inquiryWorkbench/StageActivity.jsx',
        find: '<p className="iw-stage-counts" data-counts-line="true">{s.counts_line}</p>',
        replace: '<p className="iw-stage-counts" data-counts-line="true">'
            + '{`${s.input_count} → ${s.output_count}`}</p>',
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestNamedCountsSurvive renders the backend\'s own counts line rather than bare '
            + 'numbers',
    },
    {
        id: 'inquiry/execution-mode-none-unrecognised',
        guarantee: '`none` is a real execution mode — every framer and steward attempt carries '
            + 'it, and a vocabulary of two renders all of them as unrecognised',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "export const EXECUTION_MODES = ['fixture', 'live', 'none'];",
        replace: "export const EXECUTION_MODES = ['fixture', 'live'];",
        suites: ['src/inquiryWorkbench/mechanismHonesty.dom.test.jsx'],
        expect: 'TestExecutionModeNoneIsNotUnknown renders `none` as its own mode',
    },

    // ── HARNESS-003D · the council made visible ─────────────────────────────
    //
    // This lane's own, added here rather than handed on. Everything above was written by a lane
    // that could not reach this file; there is no reason for that to be a tradition.
    //
    // What is new in D is that the compiler stopped being one call. Five passes, each able to come
    // back differently disappointing, and a provider allowance now sits between the run and its
    // answer — so the two lies these guard against are "the compilation was thin" standing in for
    // "the dissector was rate-limited out", and a run that gave up rendering as one still going.
    {
        id: 'inquiry/sends-collapsed-into-calls',
        guarantee: 'transport sends and semantic calls are separate numbers: four sends for two '
            + 'calls is an account allowance, never the compiler asking more',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '                {pass.transport_attempts !== null '
            + '&& pass.transport_attempts !== pass.call_count ? (',
        replace: '                {false ? (',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'TestSendsAreNotCalls prints sends separately where the same bytes went twice',
    },
    {
        id: 'inquiry/unwaited-pass-rendered-as-zero',
        guarantee: '`waited_ms: 0` says a pacer answered and reported no wait; a pass nothing '
            + 'paced reports null, and the two are different facts about the provider',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '        waited_ms: numOrNull(v.waited_ms),',
        replace: '        waited_ms: numOrNull(v.waited_ms) ?? 0,',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'TestWaitingIsVisible a pass that never waited has no waiting row, rather than a '
            + 'zero',
    },
    {
        id: 'inquiry/refused-wait-reads-as-a-wait',
        guarantee: 'a wait the budget REFUSED is the gate closing, not one more wait — the whole '
            + 'point of the pacing design is that a run ends honestly short',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '                            {w.taken === false\n'
            + '                                ? <b>the run stopped waiting</b>',
        replace: '                            {false\n'
            + '                                ? <b>the run stopped waiting</b>',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'TestWaitingIsVisible a wait the budget REFUSED says the run stopped, not that it '
            + 'waited',
    },
    {
        id: 'inquiry/capacity-limit-note-dropped',
        guarantee: 'a graph the pacer cut short says so at the row above it, because a barren '
            + 'atom list and a rate-limited one look identical from below',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '                    note={g.passes.some((p) => p.capacity_limited)',
        replace: '                    note={false && g.passes.some((p) => p.capacity_limited)',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'TestWaitingIsVisible says at the row that what is below is what it got to, not '
            + 'what there was',
    },
    {
        id: 'inquiry/undeclared-deployment-reads-as-live',
        guarantee: 'a response that did not say what produced it has said nothing, and silence '
            + 'may not be rendered as a claim that it was live',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "    const kind = declared ? str(v.kind) : 'undeclared';",
        replace: "    const kind = str(v.kind) || 'live';",
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'TestDeploymentIsDeclared an UNDECLARED deployment is its own answer, never a '
            + 'quiet live',
    },
    {
        id: 'inquiry/replay-wears-the-live-treatment',
        guarantee: 'a replay is visually its own thing, so a disappointing run cannot be mistaken '
            + 'for a disappointing MODEL when it was a replay of a frozen one',
        file: 'src/inquiryWorkbench/inquiryWorkbench.css',
        cssRule: 'iw-deployment--replay',
        copyRuleFrom: 'iw-deployment--live',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'the stylesheet keeps the council\'s distinctions never lets a replay wear the '
            + 'live treatment',
    },
    {
        id: 'inquiry/pass-outcomes-collapse',
        guarantee: 'the eight pass outcomes are eight treatments — `coverage_failed` in '
            + 'particular has no equivalent in the stage vocabulary and must not borrow one',
        file: 'src/inquiryWorkbench/inquiryWorkbench.css',
        cssRule: 'iw-pass-outcome--thin',
        copyRuleFrom: 'iw-pass-outcome--completed',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'the stylesheet keeps the council\'s distinctions gives every pass outcome its '
            + 'own treatment',
    },
    {
        id: 'inquiry/coverage-summary-recomputed',
        guarantee: 'the coverage summary is the BACKEND\'s arithmetic; recomputing it from the '
            + 'rows this client happens to hold would absorb every divergence instead of showing it',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '                            {cs.disposed} of {cs.source_units} source unit(s) '
            + 'disposed of',
        replace: '                            {g.coverage.length} of {g.source_units.length} '
            + 'source unit(s) disposed of',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'TestCoverageSummaryIsTheBackends shows the backend\'s number even when the rows '
            + 'below disagree with it',
    },
    {
        id: 'inquiry/stage-sentence-printed-twice',
        guarantee: 'a stage that filled two fields with the same sentence has it printed once — '
            + 'saying it twice reads as the stage having done the thing twice',
        file: 'src/inquiryWorkbench/StageActivity.jsx',
        find: '            {s.counts_line && s.counts_line !== s.summary '
            + '&& s.counts_line !== s.detail ? (',
        replace: '            {s.counts_line ? (',
        suites: ['src/inquiryWorkbench/stageActivity.dom.test.jsx'],
        expect: 'TestOneSentenceIsPrintedOnce prints a stage\'s own sentence once when two fields '
            + 'carry it',
    },
    {
        id: 'inquiry/coverage-imbalance-softened',
        guarantee: 'a ledger that does not balance says so in those words',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: "                                <> · the ledger {cs.complete ? 'balances' "
            + ": 'does NOT balance'}</>",
        replace: '                                <> · the ledger balances</>',
        suites: ['src/inquiryWorkbench/visibleCouncil.dom.test.jsx'],
        expect: 'TestCoverageSummaryIsTheBackends prints the backend\'s own numbers, with lost as '
            + 'its own',
    },

    // ── HARNESS-003E · the partition, and the pairs nobody compared ─────────
    {
        id: 'inquiry/short-pair-coverage-unmarked',
        guarantee: 'a pass that compared only some of its batch pairs is MARKED as short, rather '
            + 'than leaving a reader to notice that two numerals differ',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: "                                className={pass.batch_plan.pairs_complete === false\n"
            + "                                    ? 'iw-pass-pairs--short' : ''}",
        replace: "                                className={''}",
        suites: ['src/inquiryWorkbench/batchedCouncil.dom.test.jsx'],
        expect: 'TestEveryPairOfBatchesIsAccountedFor marks short coverage rather than leaving it '
            + 'to be read off two numerals',
    },
    {
        id: 'inquiry/unexamined-pairs-counted-not-named',
        guarantee: 'every pair nothing compared is named WITH ITS REASON — a relation nobody '
            + 'looked for is a fact a person can act on, and a count of them is not',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '                                    {p.reason ? <span className="iw-quiet"> · {p.reason}</span>\n'
            + '                                        : null}',
        replace: '                                    {null}',
        suites: ['src/inquiryWorkbench/batchedCouncil.dom.test.jsx'],
        expect: 'TestEveryPairOfBatchesIsAccountedFor prints every unexamined pair with the reason '
            + 'it was not examined',
    },
    {
        id: 'inquiry/one-batch-reads-as-nothing-compared',
        guarantee: 'one batch means there was nothing ACROSS, which is not a comparison that came '
            + 'up short; `0 of 0` in the same place would report a whole pass as an empty one',
        file: 'src/inquiryWorkbench/ArtifactLedger.jsx',
        find: '                            <li data-fact="pairs-none" className="iw-quiet">\n'
            + '                                one batch, so there was nothing across to compare\n'
            + '                            </li>',
        replace: '                            <li data-fact="pairs" className="iw-quiet">\n'
            + '                                0 of 0 batch pairs compared across 0 rounds\n'
            + '                            </li>',
        suites: ['src/inquiryWorkbench/batchedCouncil.dom.test.jsx'],
        expect: 'TestEveryPairOfBatchesIsAccountedFor says one batch had nothing across rather '
            + 'than printing 0 of 0',
    },
    {
        id: 'inquiry/a-plan-invented-for-an-unpartitioned-pass',
        guarantee: 'a pass that was never partitioned carries NO plan; an empty one would report a '
            + 'partition that never happened on the ledger and the audit, which make no request',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "    if (!raw || typeof raw !== 'object') return null;",
        replace: "    if (!raw || typeof raw !== 'object') raw = {};",
        suites: ['src/inquiryWorkbench/batchedCouncil.dom.test.jsx'],
        expect: 'TestTheBatchPlanIsReadAsSent is null where the backend sent nothing, and null is '
            + 'not an empty plan',
    },
    // ── the declared execution scope (HARNESS-003F) ────────────────────────
    //
    // A slice produces FEWER claims and observables than a full run, so an unbadged one does not
    // read as bounded — it reads as THIN, and a thin result is evidence about the images. Every lie
    // below is a way that could happen without anybody editing a word of prose.
    {
        id: 'inquiry/scoped-run-loses-its-badge',
        guarantee: 'a run that investigated a declared subset says so beside the state, on every '
            + 'session, in words',
        file: 'src/inquiryWorkbench/ScopePanel.jsx',
        find: '    if (!scope || !scope.bounded) return null;\n    const kind = scope.mode.known',
        replace: '    if (!scope || !scope.recorded) return null;\n    const kind = scope.mode.known',
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the badge says what a screenshot would otherwise hide survives onto a session '
            + 'that never reached the compiler',
    },
    {
        id: 'inquiry/scope-banner-becomes-a-tooltip',
        guarantee: 'the banner sentence is IN the badge, not behind a hover a touchscreen does '
            + 'not have and a screenshot never shows',
        file: 'src/inquiryWorkbench/ScopePanel.jsx',
        find: '            <span className="iw-scope-line">{SCOPE_BANNER}</span>',
        replace: '            <span className="iw-scope-line" title={SCOPE_BANNER} />',
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the badge says what a screenshot would otherwise hide prints SCOPED LIVE '
            + 'REHEARSAL and the banner as WORDS',
    },
    {
        id: 'inquiry/unknown-scope-reads-as-unbounded',
        guarantee: 'a scope this client cannot place is treated as BOUNDED — an older client must '
            + 'not render a newer scope as a complete reading',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: "    scope.bounded = !(scope.mode.known && scope.mode.value === 'full');",
        replace: "    scope.bounded = scope.mode.value === 'vertical_slice';",
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the badge says what a screenshot would otherwise hide treats a mode this client '
            + 'cannot place as bounded, never as unbounded',
    },
    {
        id: 'inquiry/full-coverage-recomputed-from-the-mode',
        guarantee: '`full_coverage` is READ from the record the backend refuses to let lie, never '
            + 'recomputed from the mode by a client free to disagree with it',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '        full_coverage: boolOrNull(v.full_coverage),',
        replace: "        full_coverage: str(v.mode) !== 'vertical_slice',",
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the badge says what a screenshot would otherwise hide reads full_coverage rather '
            + 'than recomputing it from the mode',
    },
    {
        id: 'inquiry/exclusions-counted-not-named',
        guarantee: 'every excluded source unit, atom and claim is named with its reason — a count '
            + 'tells a reader the size of the gap and not where it is',
        file: 'src/inquiryWorkbench/ScopePanel.jsx',
        find: '                        {scope.exclusions.map((e) => (',
        replace: '                        {scope.exclusions.slice(0, 0).map((e) => (',
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the mechanism panel names every excluded item with its reason, never as a count '
            + 'alone',
    },
    {
        id: 'inquiry/a-bound-reads-as-the-partition',
        guarantee: 'how many requests were SENT is its own number — a plan reporting only the '
            + 'partition size renders a bounded pass as a complete one',
        file: 'src/inquiryWorkbench/inquiryContract.js',
        find: '        batches_sent: numOrNull(raw.batches_sent),',
        replace: '        batches_sent: numOrNull(raw.batches_sent ?? raw.batches),',
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the batch plan tells the partition from what was sent carries batches_sent apart '
            + 'from batches',
    },
    {
        id: 'inquiry/scope-control-offered-without-a-declaration',
        guarantee: 'the temporary scope is offered only where the backend declared it — the '
            + 'absence of a declaration is not a declaration',
        file: 'src/inquiryWorkbench/InquiryEntry.jsx',
        find: '    const scopeOffered = features?.scoped_rehearsal?.available === true;',
        replace: '    const scopeOffered = features?.scoped_rehearsal?.available !== false;',
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the entry control is absent until the backend declares the feature',
    },
    {
        id: 'inquiry/scope-badge-wears-the-deployment-treatment',
        guarantee: '"was this read or replayed" and "was all of it looked at" are two questions '
            + 'and neither is a degree of the other',
        file: 'src/inquiryWorkbench/inquiryWorkbench.css',
        cssRule: 'iw-scope--unknown',
        copyRuleFrom: 'iw-scope',
        suites: ['src/inquiryWorkbench/scopedRehearsal.dom.test.jsx'],
        expect: 'the stylesheet carries none of the meaning gives an unrecognised scope its own '
            + 'treatment rather than the softer one',
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
