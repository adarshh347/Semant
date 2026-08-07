#!/usr/bin/env node
/**
 * WAVE4 — the pixel-honesty mutation audit. Proof that the guards bite.
 *
 * The curator-masks lane shipped an assertion that checked nothing: a `?raw` import inside a
 * `.catch()` failed silently, so the test passed while asserting nothing at all. It was caught by
 * accident. That is not a bug in one test — it is a whole class, and every view in the make-it-seen
 * wave rests on tests of exactly this shape: claims about PIXELS, asserted structurally, where a
 * green run is the only signal anybody ever looks at.
 *
 * A guard that cannot be made to fail is not a guard. So this script proves each one fails.
 *
 * For every honesty-critical guarantee below there is a MUTATION: a one-line edit to the component
 * or stylesheet that breaks that exact guarantee and nothing else. The script applies it, runs the
 * tests that claim to guard it, and requires them to go RED. Then it reverts. A mutation that
 * leaves the suite green is a hole, reported as such and exiting non-zero.
 *
 * Two rules kept the mutation list honest:
 *
 *   1. THE MUTATION MUST BE A REAL LIE, not a syntax error. Deleting a whole component makes
 *      everything fail and proves nothing. Each mutation here is something a well-meaning future
 *      change could plausibly do — soften a distinction, reuse a class, drop a modifier, let one
 *      status fall back to another's treatment.
 *   2. IT MUST BREAK ONE GUARANTEE. If a mutation reddens six unrelated files, the red tells you
 *      nothing about the guarantee you were probing.
 *
 * Usage:
 *     node scripts/pixelHonestyMutations.mjs           # all mutations
 *     node scripts/pixelHonestyMutations.mjs scene     # only those whose id contains "scene"
 *
 * It edits files in the working tree and restores them from the in-memory original, including on
 * SIGINT — but it is still a mutation tool. Run it on a clean tree.
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');

/**
 * Each entry: the guarantee in the project's own words, the file and the lie, and the suite that
 * must notice. `expect` names the test whose failure we want to see — the audit checks that the
 * run went red, and reports which tests died, so a mutation that reddens the WRONG test (a
 * coincidental break rather than the guard doing its job) is visible in the output.
 */
const MUTATIONS = [
    // ── the four visual kinds: no two statuses share a treatment ────────────
    {
        id: 'curator/status-class-dropped',
        guarantee: 'every status value carries its own class into the DOM, so the stylesheet\'s '
            + 'four treatments can actually land on something',
        file: 'src/curator/StatusPair.jsx',
        find: 'className={`cur-badge cur-badge--epistemic cur-badge--${epistemic}`}',
        replace: 'className={"cur-badge cur-badge--epistemic"}',
        suites: ['src/curator/curator.dom.test.jsx'],
    },
    {
        id: 'curator/measured-looks-committed',
        guarantee: 'measured and committed do not share a treatment',
        file: 'src/curator/curator.css',
        cssRule: 'cur-badge--measured',
        copyRuleFrom: 'cur-badge--committed',
        suites: ['src/curator/curator.dom.test.jsx'],
    },
    {
        id: 'constellation/interpretive-looks-measured',
        guarantee: 'an interpretive edge is dashed; a measured one is not',
        file: 'src/constellation/constellation.css',
        cssRule: 'con-edge--interpretive',
        copyRuleFrom: 'con-edge--measured',
        suites: ['src/constellation/constellation.dom.test.jsx'],
    },
    {
        id: 'constellation/unreadable-called-interpretive',
        guarantee: 'a mark nobody could read is its own state, never softened into interpretive',
        file: 'src/constellation/ConstellationGraph.jsx',
        find: "const known = edge.epistemic || 'no readable mark';",
        replace: "const known = edge.epistemic || 'interpretive';",
        suites: ['src/constellation/constellation.dom.test.jsx'],
    },
    {
        id: 'cognition/proposed-looks-measured',
        guarantee: 'a proposed percept does not wear the measured treatment',
        file: 'src/cognition/WalkStream.jsx',
        find: "if (status === 'proposed') return 'cog-status cog-status--proposed';",
        replace: "if (status === 'proposed') return 'cog-status cog-status--measured';",
        suites: ['src/cognition/cognition.dom.test.jsx'],
    },
    {
        id: 'cognition/status-treatments-collapse',
        guarantee: 'measured, interpretive and proposed are visually distinct in the stylesheet',
        file: 'src/cognition/cognition.css',
        cssRule: 'cog-status--interpretive',
        copyRuleFrom: 'cog-status--measured',
        suites: ['src/cognition/cognition.dom.test.jsx'],
    },
    {
        id: 'society/outcomes-collapse',
        guarantee: 'composed, coexistent and incommensurable are three visibly different verdicts',
        file: 'src/society/society.css',
        cssRule: 'soc-verdict--incommensurable',
        copyRuleFrom: 'soc-verdict--composed',
        suites: ['src/society/society.dom.test.jsx'],
    },
    {
        id: 'scene/interpretive-drawn-solid',
        guarantee: 'a box-basis relation is dashed on the photograph — the founding pathology, in CSS',
        file: 'src/pages/ScenePage.css',
        find: '.scene-link.is-interpretive line { stroke-dasharray: 7 5;',
        replace: '.scene-link.is-interpretive line { stroke-dasharray: none;',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
    },
    {
        id: 'scene/status-class-from-nothing',
        guarantee: 'the stroke follows the relation\'s own admissibility, not a constant',
        file: 'src/pages/ScenePage.jsx',
        find: "+ (rel.admissible ? ' is-measured' : ' is-interpretive')",
        replace: "+ ' is-measured'",
        suites: ['src/pages/ScenePage.dom.test.jsx'],
    },
    {
        id: 'scene/badge-disagrees-with-stroke',
        guarantee: 'the badge prints the status the stroke was drawn from — the page does not '
            + 'argue with itself',
        file: 'src/pages/ScenePage.jsx',
        find: '<b data-status={rel.epistemic}>{rel.epistemic}</b>',
        replace: '<b data-status="measured">measured</b>',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
    },
    {
        id: 'scene/absences-conflated',
        guarantee: 'never-derived and derived-and-none-here stay two different absences',
        file: 'src/pages/ScenePage.jsx',
        find: 'never derived: {absent.join(\', \')}',
        replace: 'never derived: {[...absent, ...(noneHere || [])].join(\', \')}',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
    },
    {
        id: 'scene/proposed-marker-filled',
        guarantee: 'a proposed relation\'s marker is hollow — filled means a curator accepted it',
        file: 'src/pages/ScenePage.css',
        find: '.scene-link.is-proposed circle { fill: none; }',
        replace: '.scene-link.is-proposed circle { fill: currentColor; }',
        suites: ['src/pages/ScenePage.dom.test.jsx'],
    },

    // ── incommensurable shows no number ────────────────────────────────────
    {
        id: 'society/incommensurable-grows-a-number',
        guarantee: 'a refused cross-sense comparison carries no number, in any notation',
        file: 'src/society/SocietyPage.jsx',
        find: '<p className="soc-verdict-detail">{verdict.detail}</p>',
        replace: '<p className="soc-verdict-detail">{verdict.detail} (87%)</p>',
        suites: ['src/society/society.dom.test.jsx'],
    },
    {
        id: 'markProvenance/chip-bypasses-summarize',
        guarantee: 'the workspace\'s real chip goes through summarizeProvenance, so the stand-in '
            + 'this suite mounts cannot drift away from it unnoticed',
        file: 'src/differential/DifferentialWorkspace.jsx',
        find: '{summarizeProvenance(gm)}',
        replace: '{gm.source}',
        suites: ['src/differential/markProvenance.dom.test.jsx'],
    },
    {
        id: 'markProvenance/confidence-rendered',
        guarantee: 'a suggestion never shows a confidence number',
        file: 'src/differential/suggestionQuarantine.js',
        find: "case 'model_suggested': return 'Model suggestion — not accepted';",
        replace: "case 'model_suggested': return 'Model suggestion — not accepted (0.94)';",
        suites: ['src/differential/markProvenance.dom.test.jsx'],
    },

    // ── refusals render as content ─────────────────────────────────────────
    {
        id: 'cognition/refusal-swallowed',
        guarantee: 'a refusal is rendered, not dropped',
        file: 'src/cognition/WalkStream.jsx',
        find: '<li className="cog-refusal" data-about={row.about}>',
        replace: '<li className="cog-refusal" data-about={row.about} hidden style={{display:"none"}}>',
        suites: ['src/cognition/cognition.dom.test.jsx'],
    },
    {
        id: 'cognition/refusal-families-merged',
        guarantee: 'the two families of refusal stay distinguishable',
        file: 'src/cognition/WalkStream.jsx',
        find: 'data-about={row.about}',
        replace: 'data-about="edge"',
        suites: ['src/cognition/cognition.dom.test.jsx'],
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
    },
    {
        id: 'curatorMasks/second-renderer',
        guarantee: 'shapes are drawn by the one shared overlay, not a private copy',
        file: 'src/curator/ProposalMasks.jsx',
        find: "import RegionOverlay from '../components/RegionOverlay';",
        replace: 'const RegionOverlay = ({ className }) => <svg className={className} />;',
        suites: ['src/curator/proposalMasks.dom.test.jsx'],
    },
    {
        id: 'curatorMasks/front-and-back-alike',
        guarantee: 'the region in front is visibly the figure — the whole claim',
        file: 'src/curator/ProposalMasks.jsx',
        find: 'litIds={new Set([pair.front.id])}',
        replace: 'litIds={new Set()}',
        suites: ['src/curator/proposalMasks.dom.test.jsx'],
    },

    // ── a proposal never looks accepted ────────────────────────────────────
    {
        id: 'curatorMasks/ledger-status-hardcoded',
        guarantee: 'the overlay carries the proposal\'s real statuses, not an assumed one',
        file: 'src/curator/ProposalMasks.jsx',
        find: "data-epistemic={proposal?.epistemic || 'unknown'}",
        replace: "data-epistemic={'measured'}",
        suites: ['src/curator/proposalMasks.dom.test.jsx'],
    },
    {
        id: 'world/oversells',
        guarantee: 'the front door reads the ledger rather than asserting what has been settled',
        file: 'src/pages/WorldPage.jsx',
        find: 'queue. <b>{committed}</b>',
        replace: 'queue. <b>{0}</b>',
        suites: ['src/pages/WorldPage.dom.test.jsx'],
    },
    {
        id: 'world/unreachable-rendered-as-link',
        guarantee: 'a surface whose backend is silent is not-a-door, not a dim link',
        file: 'src/pages/WorldPage.jsx',
        find: 'const reachable = state === LIVE;',
        replace: 'const reachable = true;',
        suites: ['src/pages/WorldPage.dom.test.jsx'],
    },
];

// ── css helper: make one rule's body identical to another's ────────────────

function ruleBody(css, name) {
    const m = css.match(new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`));
    return m ? m[1] : null;
}

function collapseRule(css, target, source) {
    const body = ruleBody(css, source);
    if (body === null) throw new Error(`no rule .${source} to copy from`);
    const re = new RegExp(`(\\.${target}\\s*\\{)([^}]*)(\\})`);
    if (!re.test(css)) throw new Error(`no rule .${target} to collapse`);
    return css.replace(re, `$1${body}$3`);
}

// ── the run ────────────────────────────────────────────────────────────────

function mutate(m, original) {
    if (m.cssRule) return collapseRule(original, m.cssRule, m.copyRuleFrom);
    if (m.appendToRender) {
        // Add a number where none may appear, without touching structure.
        const anchor = original.lastIndexOf('</span>');
        if (anchor < 0) throw new Error('no </span> to append after');
        return `${original.slice(0, anchor)}</span><span>0.94</span>${original.slice(anchor + 7)}`;
    }
    if (!original.includes(m.find)) throw new Error(`anchor not found: ${m.find.slice(0, 60)}…`);
    return original.replace(m.find, m.replace);
}

const REPORT = resolve(ROOT, 'node_modules/.cache/pixel-honesty-report.json');

/**
 * Run the suites and report both WHETHER it went red and WHICH tests died.
 *
 * The names matter as much as the colour. A mutation that reddens some unrelated test has not
 * proven the guarantee is guarded — it has proven the mutation was clumsy. Reading the report back
 * is the only way to tell those apart, so a report that cannot be parsed is an error rather than a
 * shrug: this script's first draft swallowed that parse in a bare `catch {}` and printed BITES
 * with an empty reason, which is the same species of quiet as the bug it was written to hunt.
 */
function runSuites(suites) {
    let red = false;
    try {
        execFileSync('npx',
            ['vitest', 'run', ...suites, '--reporter=json', `--outputFile=${REPORT}`],
            { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    } catch {
        red = true;
    }
    let failed = [];
    let unreadable = null;
    try {
        const report = JSON.parse(readFileSync(REPORT, 'utf8'));
        failed = (report.testResults || [])
            .flatMap((f) => (f.assertionResults || []))
            .filter((a) => a.status === 'failed')
            .map((a) => a.fullName);
        // A collection error (a suite that would not even load) leaves no assertion results.
        if (red && !failed.length) unreadable = 'red with no failed assertion — the suite crashed '
            + 'rather than a guard firing';
    } catch (err) {
        unreadable = `could not read the run report: ${err.message}`;
    }
    return { red, failed, unreadable };
}

const filter = process.argv[2] || '';
const selected = MUTATIONS.filter((m) => m.id.includes(filter));
const holes = [];
const results = [];

/**
 * A red run only means something if the SAME command is green unmutated.
 *
 * The first draft of this script did not check that, and every `scene/*` mutation reported BITES
 * while the suite it named did not exist — vitest exited non-zero on the missing file and the
 * harness read that as the guard doing its job. Which is precisely the failure this lane exists to
 * find, committed by the tool built to find it. So: the file must exist, and it must pass clean,
 * before any red is believed.
 */
const baselines = new Map();
function baselineGreen(suites) {
    const key = suites.join(' ');
    if (!baselines.has(key)) {
        const missing = suites.filter((s) => !existsSync(resolve(ROOT, s)));
        if (missing.length) baselines.set(key, `no such suite: ${missing.join(', ')}`);
        else baselines.set(key, runSuites(suites).red ? 'suite is already red unmutated' : null);
    }
    return baselines.get(key);
}

for (const m of selected) {
    const path = resolve(ROOT, m.file);
    const original = readFileSync(path, 'utf8');
    const restore = () => writeFileSync(path, original);
    process.once('SIGINT', restore);
    let outcome;
    const broken = baselineGreen(m.suites);
    if (broken) {
        outcome = { red: false, failed: [], error: broken };
    } else {
        try {
            writeFileSync(path, mutate(m, original));
            outcome = runSuites(m.suites);
        } catch (err) {
            outcome = { red: false, failed: [], error: String(err.message || err) };
        } finally {
            restore();
        }
    }
    const ok = outcome.red && !outcome.error && !outcome.unreadable && outcome.failed.length > 0;
    if (!ok) holes.push(m);
    results.push({ m, outcome, ok });
    const mark = ok ? 'BITES  ' : 'HOLE   ';
    process.stdout.write(`${mark} ${m.id}\n         ${m.guarantee}\n`);
    if (outcome.error) process.stdout.write(`         ! ${outcome.error}\n`);
    if (outcome.unreadable) process.stdout.write(`         ! ${outcome.unreadable}\n`);
    for (const name of outcome.failed.slice(0, 3)) {
        process.stdout.write(`         ↳ red: ${name}\n`);
    }
}

process.stdout.write(`\n${selected.length - holes.length}/${selected.length} guarantees proven `
    + 'to fail when broken\n');
if (holes.length) {
    process.stdout.write('\nUNGUARDED — a lie the suite would ship:\n');
    for (const m of holes) process.stdout.write(`  · ${m.id} — ${m.guarantee}\n`);
}
process.exit(holes.length ? 1 : 0);
