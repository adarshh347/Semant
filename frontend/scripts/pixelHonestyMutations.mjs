#!/usr/bin/env node
/**
 * WAVE4 — the pixel-honesty mutation audit. Proof that the guards bite, run by CI.
 *
 * The curator-masks lane shipped an assertion that checked nothing: a `?raw` import inside a
 * `.catch()` failed silently, so the test passed while asserting nothing at all. That is not one
 * bug — every view in the make-it-seen wave rests on tests of the same shape, claims about PIXELS
 * asserted structurally, where a green run is the only signal anybody reads.
 *
 * A guard that cannot be made to fail is not a guard. So this proves each one fails: apply a lie
 * that breaks exactly one honesty guarantee, run the suite that claims to guard it, require the
 * NAMED test to die, revert.
 *
 * ## What changed when this was wired into CI
 *
 * The audit found a false-positive in itself: five `scene/*` mutations reported BITES against a
 * suite that did not exist, because vitest exits non-zero on a missing file and the runner read
 * non-zero as "the guard fired". A harness with that bug, running in CI, goes green on a DELETED
 * suite — the failure it hunts, automated and believed.
 *
 * Three things now stand between a red run and a bite:
 *
 *   1. THE SUITE MUST EXIST AND PASS UNMUTATED. A baseline that is missing or already red disquali-
 *      fies every mutation pointed at it, because nothing that follows would mean anything.
 *   2. THE NAMED GUARD MUST BE THE ONE THAT DIED. `expect` in the mutation table carries the test's
 *      full name; red where some other test broke is a HOLE, not a bite. A renamed or deleted guard
 *      lands here rather than passing.
 *   3. THE VERDICT IS A PURE FUNCTION (`pixelHonesty/classify.mjs`), unit-tested in the ordinary
 *      suite, so the false-positive is pinned by something CI already runs rather than by a comment
 *      promising it was thought about.
 *
 * Usage:
 *     node scripts/pixelHonestyMutations.mjs              # every mutation; non-zero on any hole
 *     node scripts/pixelHonestyMutations.mjs scene        # only ids containing "scene"
 *     node scripts/pixelHonestyMutations.mjs --self-test  # prove the harness cannot false-positive
 *     npm run audit:honesty                               # self-test, then every mutation (CI)
 *
 * It edits files in the working tree and restores them from the in-memory original, including on
 * SIGINT — but it is still a mutation tool. Run it on a clean tree.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { MUTATIONS, mutate } from './pixelHonesty/mutations.mjs';
import { classify, BITTEN } from './pixelHonesty/classify.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CACHE = resolve(ROOT, 'node_modules/.cache');
const REPORT = resolve(CACHE, 'pixel-honesty-report.json');
const VITEST = resolve(ROOT, 'node_modules/vitest/vitest.mjs');

// ── running a suite, and reading back WHICH tests died ─────────────────────

/**
 * The names matter as much as the colour. A mutation that reddens some unrelated test has not
 * shown the guarantee is guarded — it has shown the mutation was clumsy. Reading the report back
 * is the only way to tell those apart, so a report that cannot be read is an ERROR rather than a
 * shrug: the first draft of this script swallowed that parse in a bare `catch {}`.
 */
function runSuites(suites) {
    mkdirSync(CACHE, { recursive: true });
    rmSync(REPORT, { force: true });   // never read a previous run's verdict as this one's
    let red = false;
    try {
        execFileSync(process.execPath,
            [VITEST, 'run', ...suites, '--reporter=json', `--outputFile=${REPORT}`],
            { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
    } catch {
        red = true;
    }
    try {
        const report = JSON.parse(readFileSync(REPORT, 'utf8'));
        const failed = (report.testResults || [])
            .flatMap((f) => (f.assertionResults || []))
            .filter((a) => a.status === 'failed')
            .map((a) => a.fullName);
        return { red, failed, reportError: null };
    } catch (err) {
        // A run that produced no readable report tells us nothing — including when it was red.
        return { red, failed: [], reportError: `could not read the run report: ${err.message}` };
    }
}

/**
 * A red run only means something if the same command is green unmutated. Memoised: the suites
 * repeat across mutations and a baseline is the most expensive thing here.
 */
const baselines = new Map();
function baselineError(suites) {
    const key = suites.join(' ');
    if (!baselines.has(key)) {
        const missing = suites.filter((s) => !existsSync(resolve(ROOT, s)));
        if (missing.length) {
            baselines.set(key, `no such suite: ${missing.join(', ')}`);
        } else {
            const base = runSuites(suites);
            baselines.set(key, base.red ? 'suite is already red unmutated'
                : base.reportError || null);
        }
    }
    return baselines.get(key);
}

/** Apply one lie, run its suites, restore, and judge. Never leaves the tree dirty. */
function probe(m) {
    const setupError = baselineError(m.suites);
    if (setupError) return classify({ setupError, expected: m.expect });

    const path = resolve(ROOT, m.file);
    const original = readFileSync(path, 'utf8');
    const restore = () => writeFileSync(path, original);
    process.once('SIGINT', restore);
    try {
        writeFileSync(path, mutate(m, original));
    } catch (err) {
        restore();
        return classify({ setupError: String(err.message || err), expected: m.expect });
    }
    let run;
    try {
        run = runSuites(m.suites);
    } finally {
        restore();
    }
    return classify({ ...run, expected: m.expect });
}

// ── the self-test: prove the harness cannot false-positive ─────────────────

/**
 * The audit's own bug, made unrepeatable. Each case is a run that IS red and must still read as a
 * hole. The third is the real one — it spawns vitest against a file that is not there, exactly as
 * the original false-positive did, and requires the answer to be "hole".
 */
function selfTest() {
    const cases = [];

    // 1. a suite that does not exist — the original false-positive, end to end
    const ghost = {
        id: 'selftest/missing-suite', guarantee: 'a missing suite is never a bite',
        file: 'src/curator/StatusPair.jsx',
        find: 'className={`cur-badge cur-badge--epistemic cur-badge--${epistemic}`}',
        replace: 'className={"cur-badge cur-badge--epistemic"}',
        suites: ['src/curator/thisSuiteWasDeleted.dom.test.jsx'],
        expect: 'any guard at all',
    };
    cases.push(['a deleted suite', probe(ghost)]);

    // 2. a real, passing suite where the named guard does not exist — a RENAMED test. The suite
    //    genuinely goes red; the guarantee is still unguarded, because what died was not the guard.
    const real = MUTATIONS.find((m) => m.id === 'curator/status-class-dropped');
    cases.push(['a renamed guard',
        probe({ ...real, id: 'selftest/renamed-guard', expect: 'a test by a name nobody uses' })]);

    // 3. a mutation whose anchor is gone — the component moved on and the lie no longer applies
    cases.push(['a stale anchor',
        probe({ ...real, id: 'selftest/stale-anchor', find: 'this text is not in the file' })]);

    let bad = 0;
    for (const [name, verdict] of cases) {
        const ok = verdict.verdict !== BITTEN;
        if (!ok) bad += 1;
        process.stdout.write(`${ok ? 'HOLD   ' : 'BROKEN '} self-test · ${name}\n`
            + `         reads: ${verdict.verdict} — ${verdict.why}\n`);
    }
    if (bad) {
        process.stdout.write(`\n${bad} self-test(s) BROKEN — the harness can report a bite where `
            + 'there is none. Nothing below can be trusted.\n');
        return false;
    }
    process.stdout.write(`\n${cases.length}/${cases.length} self-tests hold — a red run that is `
        + 'not evidence reads as a hole.\n\n');
    return true;
}

// ── main ───────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const wantSelfTest = args.includes('--self-test') || args.includes('--all');
const onlySelfTest = args.includes('--self-test') && !args.includes('--all');
const filter = args.find((a) => !a.startsWith('--')) || '';

if (wantSelfTest && !selfTest()) process.exit(2);
if (onlySelfTest) process.exit(0);

const selected = MUTATIONS.filter((m) => m.id.includes(filter));
if (!selected.length) {
    process.stdout.write(`no mutation matches "${filter}"\n`);
    process.exit(2);
}

const holes = [];
for (const m of selected) {
    const verdict = probe(m);
    const bitten = verdict.verdict === BITTEN;
    if (!bitten) holes.push({ m, verdict });
    process.stdout.write(`${bitten ? 'BITES  ' : 'HOLE   '} ${m.id}\n         ${m.guarantee}\n`);
    process.stdout.write(`         ${bitten ? '↳' : '!'} ${verdict.why}\n`);
    for (const other of (verdict.incidental || []).slice(0, 2)) {
        process.stdout.write(`         · also broke: ${other}\n`);
    }
}

process.stdout.write(`\n${selected.length - holes.length}/${selected.length} guarantees proven to `
    + 'fail when broken\n');

if (holes.length) {
    process.stdout.write('\nUNGUARDED — a lie the suite would ship:\n');
    for (const { m, verdict } of holes) {
        process.stdout.write(`  · ${m.id} — ${m.guarantee}\n    ${verdict.why}\n`);
    }
    process.stdout.write('\nA guard that cannot be made to fail is not a guard. Either the guard '
        + 'is missing, or\nthe mutation no longer describes a real lie — fix whichever it is.\n');
}
process.exit(holes.length ? 1 : 0);
