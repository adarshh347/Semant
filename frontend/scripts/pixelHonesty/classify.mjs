/**
 * WAVE4 — the audit's own honesty floor: when does a mutation count as BITTEN?
 *
 * The pixel-honesty audit found seven view tests that asserted nothing. It also found one in
 * itself: five `scene/*` mutations reported BITES against a suite that did not exist, because
 * vitest exited non-zero on the missing file and the runner read that as the guard firing. A
 * harness with that bug, wired into CI, passes green on a DELETED suite — the failure it hunts,
 * automated.
 *
 * So the decision is pulled out of the runner and made a pure function, for two reasons:
 *
 *   1. It can be unit-tested without spawning anything, so the false-positive is pinned by a test
 *      that runs in the ordinary suite rather than by a comment promising it was thought about.
 *   2. Every way a run can be red for the WRONG reason is enumerated here, in one place, where the
 *      list can be read and argued with.
 *
 * THE RULE. A mutation is bitten only when the specifically named guard ran and failed. Not "the
 * suite went red" — red is the cheap part, and almost anything produces it. A missing file, a
 * renamed suite, a syntax error from a clumsy mutation, a collection failure, an unrelated test
 * that happened to break: all red, none of them evidence that the guarantee is guarded.
 *
 * Everything that is not positive evidence is a HOLE. The asymmetry is deliberate — a harness that
 * guesses in its own favour is worse than no harness, because it is believed.
 */

export const BITTEN = 'bitten';
export const HOLE = 'hole';

/**
 * @param {object} r
 * @param {string|null} r.setupError   the suite was missing / already red / the anchor was absent
 * @param {boolean}     r.red          the mutated run exited non-zero
 * @param {string[]}    r.failed       full names of the tests that failed, from the run report
 * @param {string|null} r.reportError  the run report could not be read or made no sense
 * @param {string}      r.expected     the full name of the guard that must be the one to die
 */
export function classify({ setupError = null, red = false, failed = [],
                           reportError = null, expected = '' }) {
    // ── the ways a red run is not evidence ──────────────────────────────────
    if (setupError) return { verdict: HOLE, why: setupError };

    // A report we cannot read is not a result. Reading a parse failure as anything but a hole is
    // the original bug in a different costume.
    if (reportError) return { verdict: HOLE, why: reportError };

    if (!expected) {
        return { verdict: HOLE, why: 'the mutation names no guard, so no red could confirm it' };
    }

    if (!red) {
        return {
            verdict: HOLE,
            why: 'the suite stayed green with the guarantee broken — nothing guards it',
        };
    }

    // Red with nothing reported failing means the suite did not run: a missing file, a collection
    // error, a mutation that would not parse. This is the exact shape of the false-positive.
    if (!failed.length) {
        return {
            verdict: HOLE,
            why: 'red with no failed assertion — the suite crashed rather than a guard firing',
        };
    }

    if (!failed.includes(expected)) {
        return {
            verdict: HOLE,
            why: `red, but the named guard did not fire — "${expected}" is not among the `
                + `${failed.length} failure(s): ${failed.slice(0, 3).join(' | ')}`,
        };
    }

    return { verdict: BITTEN, why: `"${expected}" failed under the mutation`, incidental: failed.filter((f) => f !== expected) };
}

export const isBitten = (result) => classify(result).verdict === BITTEN;
