// PERCEPTUAL-FORMS-001E — the bundled payloads are the committed payloads.
//
// `forms/fixtures/formPayloads.json` is a mirror inside `frontend/` of the nineteen files at
// `contracts/fixtures/perception-lab/forms/`. It exists because the deployed bundle cannot import
// from the repo root, and it is the kind of file that rots silently: nothing in the running
// application would misbehave if it fell a version behind — the lab would simply render an
// out-of-date payload with total confidence, which is worse.
//
// So this is the gate. It also regenerates:
//
//     UPDATE_FORM_FIXTURES=1 npx vitest run src/perceptionLab/forms/formFixtureDrift
//
// Compared as PARSED STRUCTURE rather than as bytes, deliberately. The canonical files are
// authored by a Python lane and `0.0` there is `0` here; a byte comparison would fail on
// formatting that means nothing and pass on nothing that a byte comparison uniquely catches.

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';

import { FORM_PAYLOADS, SCENARIOS, scenariosFor } from './fixtures/formFixtures';
import { PERCEPTUAL_FORMS, form } from '../contract/perceptionLabContract';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '../../../..');
const CANONICAL = path.join(REPO_ROOT, 'contracts', 'fixtures', 'perception-lab');
const BUNDLE = path.join(HERE, 'fixtures', 'formPayloads.json');

const read = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const MANIFEST = read(path.join(CANONICAL, 'manifest.json'));
const BY_FORM = MANIFEST.form_payloads.by_form;

describe('the bundled form payloads mirror the committed ones', () => {
    if (process.env.UPDATE_FORM_FIXTURES) {
        it('regenerates the bundle', () => {
            const out = {};
            for (const [key, entry] of Object.entries(BY_FORM)) {
                out[key] = read(path.join(CANONICAL, entry.file));
            }
            fs.writeFileSync(BUNDLE, `${JSON.stringify(out, null, 2)}\n`);
            expect(Object.keys(out)).toHaveLength(19);
        });
        return;
    }

    it('carries one payload per registered form, and no extras', () => {
        expect(Object.keys(FORM_PAYLOADS).sort()).toEqual([...PERCEPTUAL_FORMS].sort());
    });

    it.each(Object.keys(BY_FORM))('%s matches the committed file', (key) => {
        const canonical = read(path.join(CANONICAL, BY_FORM[key].file));
        expect(FORM_PAYLOADS[key],
            `${BY_FORM[key].file} has drifted from the bundle — run `
            + 'UPDATE_FORM_FIXTURES=1 npx vitest run src/perceptionLab/forms/formFixtureDrift')
            .toEqual(canonical);
    });

    it('each payload declares the variant the form registry names for it', () => {
        for (const key of PERCEPTUAL_FORMS) {
            expect(FORM_PAYLOADS[key].variant, key).toBe(form(key).payload_variant);
        }
    });
});

describe('the derived scenarios', () => {
    it('offers contract and empty for every form', () => {
        for (const key of PERCEPTUAL_FORMS) {
            expect(scenariosFor(key), key).toEqual(
                expect.arrayContaining(['contract', 'empty']));
        }
    });

    it('keeps the examination counter when it empties the collection', () => {
        // The `every_form_can_say_it_looked` law, at the fixture level. An empty scenario that
        // dropped `pairs_examined` alongside `relations` would be indistinguishable from a form
        // that never ran — which is exactly the confusion the counter exists to prevent.
        const pairs = SCENARIOS['topology.pair_relation'];
        expect(pairs.empty.relations).toEqual([]);
        expect(pairs.empty.pairs_examined).toBe(pairs.contract.pairs_examined);
        expect(pairs.empty.pairs_examined).toBeGreaterThan(0);

        const masks = SCENARIOS['extent.hard_mask'];
        expect(masks.empty.instances).toEqual([]);
        expect(masks.empty.searched).toBe(masks.contract.searched);
    });

    it('does not mutate the committed payload when it derives from it', () => {
        expect(SCENARIOS['extent.hard_mask'].contract.instances).toHaveLength(2);
        expect(FORM_PAYLOADS['extent.hard_mask'].instances).toHaveLength(2);
        expect(SCENARIOS['topology.adjacency_graph'].contract.edges).toHaveLength(3);
    });

    it('withholds a field by replacing its values with a ref, not by deleting the field', () => {
        // A deleted field reads as "this form has no field". A withheld one reads as "the field
        // exists, is measured, and is not on this page" — which is the true state and the one the
        // renderer must refuse against.
        const soft = SCENARIOS['extent.soft_field'].withheld;
        expect(soft.field).toBeTruthy();
        expect(soft.field.field_shape).toEqual([4, 4]);
        expect(soft.field.inline_values).toBeNull();
        expect(soft.field.data_ref.uri).toBe('semant://fields/withheld');
        expect(soft.field.calibration.state).toBe('calibrated');
    });

    it('generates dense scenarios with no randomness — twice is the same', () => {
        const a = JSON.stringify(SCENARIOS['topology.pair_relation'].dense);
        const b = JSON.stringify(SCENARIOS['topology.pair_relation'].dense);
        expect(a).toBe(b);
        expect(SCENARIOS['topology.pair_relation'].dense.relations).toHaveLength(18);
        expect(SCENARIOS['extent.hard_mask'].dense.instances).toHaveLength(18);
    });

    it('gives dense extent instances real decodable masks, not boxes standing in for them', () => {
        const withMasks = SCENARIOS['extent.hard_mask'].dense.instances
            .filter((i) => i.mask_rle);
        expect(withMasks.length).toBeGreaterThan(3);
        for (const i of withMasks) {
            expect(i.mask_rle.size).toEqual([8, 8]);
            expect(i.mask_rle.counts.reduce((x, y) => x + y, 0)).toBe(64);
        }
    });
});
