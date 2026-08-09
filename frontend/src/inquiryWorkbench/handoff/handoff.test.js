/**
 * INQUIRY WORKBENCH — the Lane D handoff, kept honest.
 *
 * A consumed-field inventory is a document whose ordinary fate is to be right on the day it is
 * written and wrong a week later, at which point it is worse than nothing: Lane D would be
 * generating a payload against a list that no longer describes the reader. So the list is checked
 * rather than promised.
 *
 * Two directions, and the first is the one that matters:
 *
 *   1. every field a normaliser READS must be named in the inventory — so adding a field to the
 *      contract and forgetting the document fails here rather than in Lane D's integration;
 *   2. the canonical JSON must be exactly what `canonicalFixture()` produces — so the file Lane D
 *      diffs its backend against cannot drift from the fixture the tests use.
 */
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { canonicalFixture } from '../inquiryFixtures.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const LANE = path.resolve(HERE, '..');

const inventory = () => fs.readFileSync(path.join(HERE, 'CONSUMED-FIELDS.md'), 'utf8');
const canonicalJson = () =>
    fs.readFileSync(path.join(HERE, 'canonical-session.json'), 'utf8');

/**
 * Every payload key the contract reads.
 *
 * Derived from the source rather than maintained by hand: the normalisers all reach into their
 * argument as `v.<key>` or `raw.<key>`, so scanning for that is a complete and mechanical account
 * of what this surface consumes. A hand-kept list here would have exactly the staleness problem
 * the inventory has, one layer down.
 */
function readFields() {
    const src = fs.readFileSync(path.join(LANE, 'inquiryContract.js'), 'utf8');
    const found = new Set();
    for (const m of src.matchAll(/\b(?:v|raw)\.([a-z_][a-z_0-9]*)\b/g)) found.add(m[1]);
    return [...found].sort();
}

describe('the consumed-field inventory', () => {
    it('names every field the normalisers read', () => {
        const doc = inventory();
        // `foo`, `foo[]`, `graph.foo` or `graph.foo[]` — brackets mark an array and a dotted
        // prefix says where the field sits. Both are notation; neither is a different field, and a
        // guard that could not read them would be worked around rather than satisfied.
        const named = (f) => new RegExp(
            `\`(?:[A-Za-z_.]+\\.)?${f.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:\\[\\])?\``)
            .test(doc);
        const missing = readFields().filter((f) => !named(f));
        expect(missing).toEqual([]);
    });

    it('reads a non-trivial number of fields, so the check above cannot pass vacuously', () => {
        // If the scan ever stops matching — a refactor renaming `v` to something else — the
        // assertion above would go green against an empty list and prove nothing.
        const fields = readFields();
        expect(fields.length).toBeGreaterThan(80);
        for (const f of ['usable_as_evidence', 'execution_mode', 'revision', 'attempted']) {
            expect(fields).toContain(f);
        }
    });

    it('states the rules Lane D has to satisfy, not just the field names', () => {
        const doc = inventory();
        for (const rule of [
            /byte-identical/i,
            /capped at `interpretive`/i,
            /minted once per decision and reused on every retry/i,
            /never defaulted true/i,
            /separates `empty` from `unavailable`/i,
            /only source of a `measured` or `visible` badge/i,
        ]) {
            expect([String(rule), rule.test(doc)]).toEqual([String(rule), true]);
        }
    });
});

describe('the canonical session', () => {
    it('is byte-identical to what canonicalFixture() produces', () => {
        expect(canonicalJson()).toBe(JSON.stringify(canonicalFixture(), null, 2) + '\n');
    });

    it('is a complete Phase-1 session: an answer, a simulated receipt, no evidence', () => {
        const s = JSON.parse(canonicalJson());
        expect(s.state).toBe('complete');
        expect(s.synthesis.sections.length).toBeGreaterThan(0);
        expect(s.graph.semantic_remainder.length).toBeGreaterThan(0);
        expect(s.capability_receipts).toHaveLength(1);
        expect(s.capability_receipts[0].execution_mode).toBe('fixture');
        // the shape of the phase: one simulation, and nothing that could be called evidence
        expect(s.evidence).toEqual([]);
    });

    it('names every fixture the inventory advertises', () => {
        const doc = inventory();
        // A table row promising a fixture that does not exist would send Lane D looking for it.
        const promised = [...doc.matchAll(/^\| `(\w+Fixture)` \|/gm)].map((m) => m[1]);
        expect(promised.length).toBeGreaterThan(10);
        const src = fs.readFileSync(path.join(LANE, 'inquiryFixtures.js'), 'utf8');
        for (const name of promised) {
            expect([name, src.includes(`export function ${name}(`)]).toEqual([name, true]);
        }
    });
});
