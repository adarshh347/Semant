import { describe, it, expect, beforeEach } from 'vitest';
import {
    planFromPrompt, detectCues, detectWritingMode, sideHintFor,
    quickAction, QUICK_CHIPS, SCULPTURE_FIXTURE, LEXICON,
} from './attunementPlanner';
import { validateAction, _resetActionIds, ACTION_TYPES } from './perceptualActions';

/**
 * CIRCUIT-001 P2B — the planner.
 *
 * What is pinned: that the lexicon fires on the vocabulary of looking, that everything it
 * emits is a VALID action (so a lexicon bug becomes a dropped proposal, never a malformed
 * card), and that it proposes rather than asserts.
 *
 * What is deliberately NOT pinned: the exact card count for an arbitrary prompt. The
 * lexicon is meant to grow; a test asserting "exactly 6 acts" would make every new cue a
 * test failure and teach the next author to stop adding cues.
 */

const plan = (p, ctx = {}) => planFromPrompt(p, { now: 0, ...ctx });
const typesIn = (r) => r.actions.map((a) => a.type);
const rolesIn = (r, type, key) =>
    r.actions.filter((a) => a.type === type).map((a) => a.payload[key]);

beforeEach(() => { _resetActionIds(); });

// ── cue detection ────────────────────────────────────────────────────────────

describe('the lexicon fires on the vocabulary of looking', () => {
    const fires = (prompt, key) => detectCues(prompt).some((c) => c.key === key);

    it('gaze / looking / eyes / address', () => {
        expect(fires('the gaze she points toward', 'gaze')).toBe(true);
        expect(fires('her eyes', 'gaze')).toBe(true);
        expect(fires('a direct address to the viewer', 'gaze')).toBe(true);
        expect(fires('the stone is cold', 'gaze')).toBe(false);
    });

    it('light / illumination / glow', () => {
        expect(fires('extreme lighting on the left', 'light')).toBe(true);
        expect(fires('an illuminated edge', 'light')).toBe(true);
        expect(fires('it glows', 'light')).toBe(true);
    });

    it('shadow / darkness / the dark side', () => {
        expect(fires('against the shadowed right side', 'shadow')).toBe(true);
        expect(fires('darkness pools below', 'shadow')).toBe(true);
    });

    it('fold / shoulder / drapery', () => {
        expect(fires('the shoulder-level folding architecture', 'fold')).toBe(true);
        expect(fires('heavy drapery', 'fold')).toBe(true);
    });

    it('architecture / structure / axis', () => {
        expect(fires('the folding architecture', 'architecture')).toBe(true);
        expect(fires('a structural axis', 'architecture')).toBe(true);
    });

    it('comparison and kinship', () => {
        expect(fires('it echoes the motif in the other panel', 'comparison')).toBe(true);
        expect(fires('a kinship with the earlier figure', 'comparison')).toBe(true);
    });

    it('an empty or wordless prompt fires nothing', () => {
        expect(detectCues('')).toEqual([]);
        expect(detectCues('   ')).toEqual([]);
        expect(detectCues('asdfgh qwerty')).toEqual([]);
    });

    it('every lexicon entry proposes something the grammar knows', () => {
        for (const entry of LEXICON) {
            expect(entry.cues.length, entry.key).toBeGreaterThan(0);
            for (const p of entry.proposes) {
                expect(p, entry.key).toMatch(/^(field|trace|connect):[a-z_]+$/);
            }
        }
    });
});

describe('writing intent is read separately from the image', () => {
    it('names a kind of writing when the prompt asks for one', () => {
        expect(detectWritingMode('write a critique of this')).toBe('art_critique');
        expect(detectWritingMode('a philosophical note')).toBe('philosophical_note');
        expect(detectWritingMode('a youtube script')).toBe('youtube_script');
        expect(detectWritingMode('some questions to ask myself')).toBe('question_list');
        expect(detectWritingMode('describe what is here')).toBe('description');
    });

    it('returns null when no writing was asked for', () => {
        expect(detectWritingMode('the gaze and the light')).toBe(null);
    });
});

describe('side hints point a proposal somewhere without inventing geometry', () => {
    it('reads the side words near the cue', () => {
        expect(sideHintFor('extreme lighting on the left face', 'lighting')).toContain('left');
        expect(sideHintFor('against the shadowed right side', 'shadowed')).toContain('right');
    });
    it('is empty when nothing local says where', () => {
        expect(sideHintFor('the material is stone', 'material')).toBe('');
        expect(sideHintFor('anything', 'not-present')).toBe('');
    });
});

// ── the fixture ──────────────────────────────────────────────────────────────

describe('the sculpture fixture', () => {
    // The prompt this planner was built against, kept beside the planner so it cannot drift.
    const result = () => plan(SCULPTURE_FIXTURE, { hasParts: false });

    it('proposes a gaze trace', () => {
        expect(rolesIn(result(), 'trace_direction', 'trace_role')).toContain('gaze_address');
    });

    it('proposes a light field and a shadow field, distinctly', () => {
        const fields = rolesIn(result(), 'brush_field', 'field_role');
        expect(fields).toContain('light_field');
        expect(fields).toContain('shadow_field');
    });

    it('proposes marking the shoulder-level fold', () => {
        expect(rolesIn(result(), 'brush_field', 'field_role')).toContain('fold');
    });

    it('proposes an architectural axis', () => {
        expect(rolesIn(result(), 'trace_direction', 'trace_role')).toContain('architectural_axis');
    });

    it('proposes finding parts, because this post has none', () => {
        expect(typesIn(result())).toContain('find_parts');
    });

    it('proposes composing a percept, seeded with the curator\'s OWN words', () => {
        // The planner has no business writing the noticing. It carries the sentence to the
        // place where it becomes one; the wording stays the curator's.
        const compose = result().actions.find((a) => a.type === 'compose_percept');
        expect(compose).toBeTruthy();
        expect(compose.payload.draft_text).toBe(SCULPTURE_FIXTURE);
    });

    it('offers a counter-reading, and never as a model\'s idea', () => {
        const ch = result().actions.find((a) => a.type === 'challenge_percept');
        expect(ch).toBeTruthy();
        expect(ch.source).not.toBe('model_suggested');
    });

    it('does NOT propose a manuscript, because the prompt never asked to write', () => {
        expect(typesIn(result())).not.toContain('start_manuscript');
        // …and does once it is asked.
        expect(typesIn(plan(`${SCULPTURE_FIXTURE} Write a critique.`))).toContain('start_manuscript');
    });

    it('every proposal is valid, and nothing was silently dropped', () => {
        const r = result();
        for (const a of r.actions) expect(validateAction(a).valid, a.type).toBe(true);
        expect(r.rejected).toEqual([]);
    });

    it('carries the words it keyed on, so a card can say why', () => {
        const light = result().actions.find((a) => a.payload.field_role === 'light_field');
        expect(light.provenance.planner).toBe('attunement/lexicon-v1');
        expect(light.provenance.matched.join(' ')).toMatch(/light/);
        expect(light.payload.reason).toContain('you said');
    });

    it('a proposal points somewhere when the prompt said where', () => {
        const shadow = result().actions.find((a) => a.payload.field_role === 'shadow_field');
        expect(shadow.payload.target_hint).toContain('right');
    });

    it('is deterministic — the same prompt plans the same acts', () => {
        _resetActionIds();
        const a = plan(SCULPTURE_FIXTURE);
        _resetActionIds();
        const b = plan(SCULPTURE_FIXTURE);
        expect(a.actions).toEqual(b.actions);
    });
});

// ── behaviour around the fixture ─────────────────────────────────────────────

describe('the planner proposes rather than asserts', () => {
    it('emits nothing at all for an empty prompt', () => {
        expect(plan('').actions).toEqual([]);
        expect(plan('   ').actions).toEqual([]);
    });

    it('emits nothing for a prompt with no vocabulary it knows', () => {
        // Silence is the honest output. Inventing acts for words it does not understand is
        // how a proposer starts pretending to see.
        expect(plan('asdf qwerty zxcv', { hasParts: true }).actions).toEqual([]);
    });

    it('suppresses find_parts when the image already has parts', () => {
        expect(typesIn(plan(SCULPTURE_FIXTURE, { hasParts: true }))).not.toContain('find_parts');
        expect(typesIn(plan(SCULPTURE_FIXTURE, { hasParts: false }))).toContain('find_parts');
    });

    it('carries the post\'s way of looking into find_parts', () => {
        const fp = plan('the gaze', { hasParts: false, wayOfLooking: 'architecture' })
            .actions.find((a) => a.type === 'find_parts');
        expect(fp.payload.way_of_looking).toBe('architecture');
    });

    it('every image mark it proposes requires the curator to draw it', () => {
        // The planner never produces geometry. Not "does not yet" — never: it has no access
        // to the image at all.
        const marks = plan(SCULPTURE_FIXTURE).actions
            .filter((a) => ['brush_field', 'trace_direction'].includes(a.type));
        expect(marks.length).toBeGreaterThan(0);
        for (const m of marks) {
            expect(m.payload.geometry_mode).not.toBe('polygon');
            expect(m.warnings.join(' ')).toContain('Needs a mark from you');
        }
    });

    it('proposals arrive as proposed, never pre-applied', () => {
        for (const a of plan(SCULPTURE_FIXTURE).actions) expect(a.status).toBe('proposed');
    });
});

// ── quick chips ──────────────────────────────────────────────────────────────

describe('quick chips give every entry without typing', () => {
    it('each published chip builds a valid action', () => {
        for (const chip of QUICK_CHIPS) {
            const a = quickAction(chip.key, { now: 0 });
            expect(a, chip.key).toBeTruthy();
            expect(validateAction(a).valid, chip.key).toBe(true);
            expect(ACTION_TYPES).toContain(a.type);
        }
    });

    it('a chip is the user\'s own act, not the system\'s suggestion', () => {
        expect(quickAction('brush_light', { now: 0 }).source).toBe('user');
    });

    it('an unknown chip returns null rather than something plausible', () => {
        expect(quickAction('summon', { now: 0 })).toBe(null);
    });
});
