// CIRCUIT-001 P2B — the attunement planner.
//
// Takes what caught a curator — free text — and proposes Perceptual Actions.
//
// **There is no model here.** This is a deterministic, lexicon-driven proposer: it reads
// the prompt for the vocabulary of looking (gaze, light, shadow, fold, axis, rhythm,
// material, recession, comparison, writing) and emits structured, refusable proposals.
//
// Why deterministic first, and why this ordering is the point:
//
//   The grammar and the execution pathways have to exist and be trustworthy BEFORE anything
//   generative is allowed near them. A planner that hallucinates a `field_role` is caught by
//   `validateAction` and dropped; a planner that produced free prose would have nothing to
//   be caught by. Swapping this module for a model call later changes the SOURCE of the
//   proposals and nothing else — every proposal still passes the same validators, still
//   arrives as `model_suggested`, still requires the curator to accept it.
//
// **The planner is not truth.** It does not detect a gaze; it notices that the curator said
// "gaze", and offers a way to mark one. Everything it emits carries `provenance.matched` —
// the actual words it keyed on — so the card can say *you said "gaze"* rather than implying
// Semant saw one. UI copy must read "Suggested acts", never "Detected".

// ── HARNESS-001A: WHERE THE CUES NOW LIVE ────────────────────────────────────
//
// The cue vocabulary moved OUT of this file into `contracts/attunement-lexicon.v1.json`,
// because a second runtime now reads it: the backend inquiry mind frames a prompt from the
// same cues. Two lexicons would be two systems that both claim to know what "fold" means,
// and they would disagree within a week.
//
// THE PLANNING STAYED. Which acts a cue proposes, how a label is built, what is suppressed
// when the post already has regions, the side-hint window — all still here, all exported
// under exactly the names they were.
//
// The contract carries blocks this planner deliberately does NOT read (`inquiry_cues`,
// `demand_cues`, `output_cues`, `corpus_terms`, `known_unresolved`): those are about the
// shape of a QUESTION over a corpus, and this planner proposes marks on ONE image. Reading
// them here would change what the panel suggests, and the sculpture fixture is the pin that
// says it must not.
import LEXICON_CONTRACT from '../contracts/attunement-lexicon.v1.json';
import {
    normalizeAction, validateActionList, actionId,
} from './perceptualActions';

export const LEXICON_SCHEMA_VERSION = LEXICON_CONTRACT.schema_version;

/**
 * The lexicon. Each entry: the cues that fire it, and the acts it proposes.
 *
 * Cues are matched as whole-ish words against a lowercased prompt, longest first, so
 * "shoulder" cannot be swallowed by a shorter overlapping cue. Every entry is small,
 * inspectable, and deliberately conservative: over-proposing is not free — a panel of
 * fourteen cards is a panel nobody reads.
 */
export const LEXICON = LEXICON_CONTRACT.lexicon;

/**
 * Writing intents, kept separate: every cue here must name an OUTPUT the curator wants, not
 * a quality they are describing.
 *
 * `aesthetic` was in this list and is deliberately not: the sculpture fixture opens *"The
 * aesthetic is in the gaze…"*, which describes the image and asks for nothing. A cue that
 * fires on a common descriptive noun makes the panel offer to write an essay every time
 * somebody says what they are looking at.
 */
export const WRITING_CUES = LEXICON_CONTRACT.writing_cues;

const norm = (s) => String(s || '').toLowerCase();

const escapeRe = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Does a whole-word cue appear? `\bcue\b`, and only for cues the contract lists under
 * `word_cues`.
 *
 * Substring matching is right for the prefix cues the lexicon depends on — 'illuminat' has to
 * catch 'illuminated' and 'illumination'. It is wrong for a short cue that lives inside
 * unrelated words: 'lit' fires inside "sensuality", 'gather' inside "together", 'arm' inside
 * "warm". Each of those makes a card say *you said "lit"* to somebody who said "sensuality",
 * which is the one thing a planner that attributes everything to the prompt must never do.
 */
const wordCuePresent = (t, cue) => new RegExp(`\\b${escapeRe(norm(cue))}\\b`).test(t);

/** Which cues actually appear, longest-first so a longer phrase wins its substring. */
function matchCues(text, cues, wordCues = []) {
    const t = norm(text);
    return [...cues.filter((c) => t.includes(c)),
            ...wordCues.filter((c) => wordCuePresent(t, c))]
        .sort((a, b) => b.length - a.length)
        .filter((c, _i, kept) => !kept.some((other) => other !== c && other.includes(c)));
}

/** Every lexicon entry the prompt fires, in lexicon order (stable output). */
export function detectCues(prompt) {
    const hits = [];
    for (const entry of LEXICON) {
        const matched = matchCues(prompt, entry.cues, entry.word_cues || []);
        if (matched.length) hits.push({ key: entry.key, matched, proposes: entry.proposes });
    }
    return hits;
}

/** The manuscript mode the prompt asks for, or null. Most specific wins over 'description'. */
export function detectWritingMode(prompt) {
    for (const w of WRITING_CUES) {
        if (matchCues(prompt, w.cues, w.word_cues || []).length) return w.mode;
    }
    return null;
}

// ── side hints ───────────────────────────────────────────────────────────────
// "the left face", "the shadowed right side" — a spatial hint the curator can see on the
// card, so a proposal points somewhere rather than floating. It is a HINT and nothing else:
// no geometry is derived from it, and it never becomes a box.

const SIDES = LEXICON_CONTRACT.sides;
const SIDE_WINDOW = LEXICON_CONTRACT.matching.side_window;

/** The side words nearest a cue, as a plain phrase, or ''. */
export function sideHintFor(prompt, cue) {
    const t = norm(prompt);
    const at = t.indexOf(norm(cue));
    if (at < 0) return '';
    // A local window either side of the cue: near enough to be about it.
    const window = t.slice(Math.max(0, at - SIDE_WINDOW),
                           Math.min(t.length, at + norm(cue).length + SIDE_WINDOW));
    const found = SIDES.filter((s) => s.cues.some((c) => window.includes(c))).map((s) => s.key);
    return found.length ? found.join(' / ') : '';
}

// ── the planner ──────────────────────────────────────────────────────────────

const FIELD_COLOUR = LEXICON_CONTRACT.field_colours;

function excerpt(prompt, max = 120) {
    const s = String(prompt || '').trim().replace(/\s+/g, ' ');
    return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/**
 * Plan a set of proposed actions from a captivation prompt.
 *
 * @param prompt  free text — what caught the curator
 * @param ctx.hasParts        whether the post already has regions (suppresses the
 *                            find_parts proposal when it would be noise)
 * @param ctx.wayOfLooking    the post's current profile, carried into find_parts
 * @param ctx.now             injected clock
 * @param ctx.idFn            injected id source, so tests are deterministic
 * @returns {{actions: object[], rejected: object[], cues: object[], prompt: string}}
 */
export function planFromPrompt(prompt, {
    hasParts = false, wayOfLooking = 'general', now = 0, idFn = actionId,
} = {}) {
    const text = String(prompt || '').trim();
    if (!text) return { actions: [], rejected: [], cues: [], prompt: '' };

    const cues = detectCues(text);
    const writingMode = detectWritingMode(text);
    const raw = [];
    const provenance = (key, matched) => ({
        planner: 'attunement/lexicon-v1',
        promptExcerpt: excerpt(text),
        matched,
        cue: key,
    });

    // 1 — find parts, but only when there is nothing there. Proposing segmentation over an
    //     already-dissected post is noise, and noise is how a panel stops being read.
    if (!hasParts) {
        raw.push({
            type: 'find_parts',
            source: 'system',
            intent: 'open the image into material you can cite',
            payload: {
                way_of_looking: wayOfLooking,
                reason: 'nothing has been found in this image yet',
            },
            provenance: provenance('bootstrap', []),
        });
    }

    // 2 — one act per fired cue, in lexicon order.
    for (const hit of cues) {
        for (const proposal of hit.proposes) {
            const [family, role] = proposal.split(':');
            const hint = sideHintFor(text, hit.matched[0]);
            if (family === 'field') {
                raw.push({
                    type: 'brush_field',
                    source: 'system',
                    intent: 'mark where this lives, in your own hand',
                    payload: {
                        field_role: role,
                        label: labelFromCue(hit, role, hint),
                        target_hint: hint,
                        geometry_mode: 'soft_field',
                        color: FIELD_COLOUR[role] || null,
                        softness: 0.8,
                        requires_refinement: true,
                        reason: `you said “${hit.matched[0]}”`,
                    },
                    provenance: provenance(hit.key, hit.matched),
                });
            } else if (family === 'trace') {
                raw.push({
                    type: 'trace_direction',
                    source: 'system',
                    intent: 'draw the direction, from and to',
                    payload: {
                        trace_role: role,
                        label: labelFromCue(hit, role, hint),
                        from_hint: hint || '',
                        to_hint: '',
                        geometry_mode: role === 'architectural_axis' ? 'vector' : 'curve',
                        requires_user_anchor: true,
                        reason: `you said “${hit.matched[0]}”`,
                    },
                    provenance: provenance(hit.key, hit.matched),
                });
            } else if (family === 'connect') {
                raw.push({
                    type: 'connect_marks',
                    source: 'system',
                    intent: 'tie two marks together and say how they bear on each other',
                    payload: {
                        relation_role: role,
                        label: '',
                        source_refs: [],
                        target_refs: [],
                        reason: `you said “${hit.matched[0]}”`,
                    },
                    provenance: provenance(hit.key, hit.matched),
                });
            }
        }
    }

    // 3 — a percept draft, seeded with the curator's own sentence.
    //     The draft text is THEIRS, not ours: the planner has no business writing the
    //     noticing, only carrying it to the place where it becomes one.
    if (cues.length) {
        raw.push({
            type: 'compose_percept',
            source: 'system',
            intent: 'say what you notice, and cite what it rests on',
            payload: {
                draft_text: text,
                intent: 'isolate',
                proposed_ground_refs: [],
                suggested_ground_roles: suggestRoles(cues),
                reason: 'your words, carried to where they become a noticing',
            },
            provenance: provenance('compose', cues.flatMap((c) => c.matched)),
        });
    }

    // 4 — writing, only when the prompt asked for it.
    if (writingMode) {
        raw.push({
            type: 'start_manuscript',
            source: 'system',
            intent: 'begin writing from what you have marked',
            payload: {
                mode: writingMode,
                draft: '',
                cited_percept_refs: [],
                insertion_mode: 'unsaved',
                reason: 'you named a kind of writing',
            },
            provenance: provenance('writing', [writingMode]),
        });
    }

    // 5 — the counter-reading. `source: 'system'` and never `model_suggested`: a model may
    //     not author a challenge, and `validateAction` refuses one that tries. Offering the
    //     ACT is fine — performing it is the curator's.
    if (cues.length >= 2) {
        raw.push({
            type: 'challenge_percept',
            source: 'system',
            intent: 'ask what would make this reading wrong',
            payload: {
                percept_ref: 'draft',
                challenge_type: 'alternative_reading',
                prompt: 'What else could account for this, and what would settle it?',
                reason: 'a reading with several parts has several ways to be wrong',
            },
            provenance: provenance('challenge', []),
        });
    }

    const normalized = raw.map((r) => normalizeAction(r, { now, idFn }));
    const { actions, rejected } = validateActionList(normalized.filter(Boolean));
    return {
        actions,
        // A proposal that failed to normalize is reported, not swallowed — a planner
        // silently dropping its own output is how a lexicon bug becomes invisible.
        rejected: [...rejected, ...normalized.map((n, i) => (n ? null : { index: i, errors: ['failed to normalize'], raw: raw[i] })).filter(Boolean)],
        cues,
        prompt: text,
    };
}

const LABEL_TEMPLATES = LEXICON_CONTRACT.labels;

function labelFromCue(hit, role, hint) {
    const base = hit.matched[0];
    const side = hint ? ` (${hint})` : '';
    const rule = LABEL_TEMPLATES[role] || LABEL_TEMPLATES.default;
    let out = String(rule.template).replace('{cue}', base).replace('{side}', side);
    // `the the gaze` — the one collapse the templates need, declared beside the template
    // that causes it rather than hidden in a conditional here.
    if (Array.isArray(rule.collapse)) out = out.replace(rule.collapse[0], rule.collapse[1]);
    return out;
}

/** Which ground roles the fired cues would plausibly want. Candidates, never assignments. */
function suggestRoles(cues) {
    const map = LEXICON_CONTRACT.ground_role_suggestions;
    const out = {};
    for (const c of cues) if (map[c.key]) out[c.key] = map[c.key];
    return out;
}

/**
 * The quick chips — deterministic single acts with no prompt at all, so a curator who does
 * not want to type still has every entry into the circuit.
 */
export function quickAction(kind, { now = 0, idFn = actionId, wayOfLooking = 'general' } = {}) {
    const specs = {
        map_gaze: {
            type: 'trace_direction', intent: 'draw where the look goes',
            payload: { trace_role: 'gaze_address', label: 'gaze', geometry_mode: 'curve', requires_user_anchor: true, reason: 'you asked to map a gaze' },
        },
        brush_light: {
            type: 'brush_field', intent: 'paint where the light lives',
            payload: { field_role: 'light_field', label: 'light', geometry_mode: 'soft_field', color: FIELD_COLOUR.light_field, softness: 0.8, reason: 'you asked to brush light' },
        },
        find_parts: {
            type: 'find_parts', intent: 'open the image into material you can cite',
            payload: { way_of_looking: wayOfLooking, reason: 'you asked to find parts' },
        },
        start_note: {
            type: 'start_manuscript', intent: 'begin writing',
            payload: { mode: 'description', insertion_mode: 'unsaved', reason: 'you asked to start a note' },
        },
        counter_reading: {
            type: 'challenge_percept', intent: 'ask what would make this wrong',
            payload: { percept_ref: 'draft', challenge_type: 'alternative_reading', prompt: 'What else could account for this?', reason: 'you asked for a counter-reading' },
        },
    };
    const s = specs[kind];
    if (!s) return null;
    return normalizeAction({ ...s, source: 'user' }, { now, idFn });
}

export const QUICK_CHIPS = [
    { key: 'map_gaze', label: 'Map gaze' },
    { key: 'brush_light', label: 'Brush light' },
    { key: 'find_parts', label: 'Find parts' },
    { key: 'start_note', label: 'Start note' },
    { key: 'counter_reading', label: 'Ask for counter-reading' },
];

/** The fixture this planner was built against. In the contract so BOTH runtimes plan the
 *  same sentence and a drift in either shows up as a changed fixture rather than as two
 *  planners quietly diverging on different inputs. */
export const SCULPTURE_FIXTURE = LEXICON_CONTRACT.fixtures.sculpture;
