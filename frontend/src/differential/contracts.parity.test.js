// HARNESS-001A — the frontend half of the cross-language parity gate.
//
// The Perceptual Action Grammar and the attunement lexicon are now DATA read by two runtimes.
// Data read by two runtimes drifts unless something fails when it does. These are the things
// that fail.
//
// FOUR CHECKS, and each one is here because of a specific way this could go quietly wrong:
//
//  1. THE MIRROR IS THE CANONICAL FILE. `frontend/src/contracts/*.json` exists only because the
//     Vercel project uploads `frontend/` as its deployment source, so the bundle cannot import
//     from the repo root. A copy that nothing pins is a second contract with a head start.
//
//  2. THE JS READS THE VERSION AND THE CLOSED SETS FROM THE CONTRACT. Asserted against the file
//     rather than against a literal here, so a set edited in one place and not the other fails.
//
//  3. EVERY ACT THE BACKEND FRAMER PROPOSED VALIDATES IN THE JS VALIDATOR. Read from the
//     committed backend fixture. This is the check that has no substitute: the whole claim of
//     the lane is that the two runtimes enforce ONE grammar, and this is the only place a
//     Python-built object meets the JavaScript law.
//
//  4. THE JS PLANNER'S OWN OUTPUT IS COMMITTED FOR THE BACKEND TO VALIDATE. The mirror image of
//     (3), written here because only vitest can import the planner's extensionless ESM. A drift
//     in the planner fails HERE, and the backend then validates the same committed acts.
//
// Nothing in this file is a mock. The validator, the planner and the fixtures are the real ones.

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import GRAMMAR from '../contracts/perceptual-action-grammar.v1.json';
import LEXICON_CONTRACT from '../contracts/attunement-lexicon.v1.json';
import {
    ACTION_TYPES, TARGETS, SOURCES, STATUSES, GEOMETRY_MODES, GRAMMAR_SCHEMA_VERSION,
    validateAction, FIELD_ROLE_KEYS,
} from './perceptualActions';
import { LEXICON, WRITING_CUES, SCULPTURE_FIXTURE, LEXICON_SCHEMA_VERSION, planFromPrompt }
    from './attunementPlanner';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, '../../..');
const CANONICAL = path.join(REPO_ROOT, 'contracts');
const MIRROR = path.resolve(HERE, '../contracts');

// Written by this file, read by `test_inquiry_contracts.py`. Regenerate an intentional change
// with UPDATE_PARITY_FIXTURES=1 npx vitest run src/differential/contracts.parity.test.js
const JS_PLANNER_FIXTURE = path.join(CANONICAL, 'fixtures', 'js-planner-sculpture.actions.json');

const read = (p) => fs.readFileSync(p, 'utf8');

describe('the shared contracts — one law, two runtimes', () => {
    it('the frontend mirror is byte-identical to the canonical contract', () => {
        for (const name of ['perceptual-action-grammar.v1.json', 'attunement-lexicon.v1.json']) {
            expect(read(path.join(MIRROR, name)),
                   `${name} has drifted from contracts/${name} — run `
                   + 'python scripts/contracts_sync.py')
                .toBe(read(path.join(CANONICAL, name)));
        }
    });

    it('the grammar module reads its closed sets from the contract, not from literals', () => {
        expect(GRAMMAR_SCHEMA_VERSION).toBe('perceptual-action-grammar.v1');
        expect(ACTION_TYPES).toEqual(GRAMMAR.closed_sets.action_types);
        expect(TARGETS).toEqual(GRAMMAR.closed_sets.targets);
        expect(SOURCES).toEqual(GRAMMAR.closed_sets.sources);
        expect(STATUSES).toEqual(GRAMMAR.closed_sets.statuses);
        expect(GEOMETRY_MODES).toEqual(GRAMMAR.closed_sets.geometry_modes);
        expect(FIELD_ROLE_KEYS).toEqual(GRAMMAR.vocabularies.field_roles.map((r) => r.key));
    });

    it('the planner reads its cues from the contract, not from literals', () => {
        expect(LEXICON_SCHEMA_VERSION).toBe('attunement-lexicon.v1');
        expect(LEXICON).toBe(LEXICON_CONTRACT.lexicon);
        expect(WRITING_CUES).toBe(LEXICON_CONTRACT.writing_cues);
        expect(SCULPTURE_FIXTURE).toBe(LEXICON_CONTRACT.fixtures.sculpture);
    });

    it('the contract declares the two laws that are not about shape', () => {
        const ids = GRAMMAR.laws.map((l) => l.id);
        expect(ids).toContain('model-may-not-author-challenge');
        expect(ids).toContain('nothing-is-dispatched');
        expect(GRAMMAR.model_forbidden_actions).toContain('challenge_percept');
        expect(GRAMMAR.never_applies).toContain('ask_model_reading');
    });
});

describe('the backend framer meets the JavaScript grammar', () => {
    const framePath = path.join(REPO_ROOT, 'backend', 'tests', 'fixtures',
                                'inquiry_frame_fixture.json');
    const frame = JSON.parse(read(framePath));

    it('every act the Python framer proposed validates HERE, in the JS validator', () => {
        expect(frame.proposed_actions.length).toBeGreaterThan(0);
        for (const action of frame.proposed_actions) {
            const verdict = validateAction(action);
            expect(verdict.errors, `${action.type} was refused by the JS validator`).toEqual([]);
            expect(verdict.valid).toBe(true);
        }
    });

    it('and every one of them is still only proposed', () => {
        for (const action of frame.proposed_actions) {
            expect(action.status).toBe('proposed');
        }
    });

    it('the frame carries no geometry, no confidence and no region', () => {
        const serialised = JSON.stringify(frame);
        for (const forbidden of ['mask_rle', '"bbox"', '"region_id"', '"confidence"',
                                 '"polygon"', '"coordinates"']) {
            expect(serialised).not.toContain(forbidden);
        }
    });

    it('an unknown action type is refused by name rather than coerced', () => {
        // The same object the backend would refuse, judged here — so "fails closed" means the
        // same thing in both languages rather than two things with one name.
        const verdict = validateAction({ ...frame.proposed_actions[0], type: 'segment_folds' });
        expect(verdict.valid).toBe(false);
        expect(verdict.errors[0]).toContain('segment_folds');
    });
});

describe('the JS planner, committed for the backend to validate', () => {
    const planned = planFromPrompt(SCULPTURE_FIXTURE, { hasParts: false, now: 0 });

    it('proposes the ten acts the sculpture fixture has always produced', () => {
        expect(planned.rejected).toEqual([]);
        expect(planned.actions).toHaveLength(10);
    });

    it('is committed at contracts/fixtures/ for the Python validator to read', () => {
        const payload = `${JSON.stringify({
            note: 'Written by frontend/src/differential/contracts.parity.test.js. '
                + 'Read by backend/tests/test_inquiry_contracts.py, which validates every act '
                + 'below against the Python enforcement of the same grammar. '
                + 'Regenerate: UPDATE_PARITY_FIXTURES=1 npx vitest run '
                + 'src/differential/contracts.parity.test.js',
            prompt: SCULPTURE_FIXTURE,
            planner: 'attunement/lexicon-v1',
            grammar_version: GRAMMAR_SCHEMA_VERSION,
            lexicon_version: LEXICON_SCHEMA_VERSION,
            actions: planned.actions,
        }, null, 2)}\n`;

        if (process.env.UPDATE_PARITY_FIXTURES) {
            fs.mkdirSync(path.dirname(JS_PLANNER_FIXTURE), { recursive: true });
            fs.writeFileSync(JS_PLANNER_FIXTURE, payload, 'utf8');
        }
        expect(read(JS_PLANNER_FIXTURE),
               'the JS planner no longer produces the committed fixture — rerun with '
               + 'UPDATE_PARITY_FIXTURES=1 if the change was intended')
            .toBe(payload);
    });
});
