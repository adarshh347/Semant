// CIRCUIT-001 P2 — the Seeing Console: pure derivation and curator-facing copy.
//
// All of the console's vocabulary, mapping and status derivation lives here so it is
// unit-testable in the default (node, no-DOM) harness and the JSX stays thin. That is the
// same discipline visionActivity.js already keeps for the activity rail.
//
// THE RULE THIS MODULE EXISTS TO HOLD (P1 spec Part E):
//
//     Operation names are WIRE IDENTITY. Labels are curator-facing and may be rewritten
//     freely. The two must never be conflated.
//
// So `dissect` stays the operation id everywhere on the wire — route, payload, telemetry
// stage ids, `vision_runs.operation` — and the curator never reads that word. Every key
// exported below is the value the backend already expects; only the labels are new.

import { OPERATIONS, OPERATION_LABEL, deriveEntry } from './visionActivity';

// ── the operation, and its curator-facing name ────────────────────────────────
// FIND_PARTS_OPERATION is the wire id. It is exported so a test can assert the console
// still speaks to the same endpoint it always did, and so nothing has to hard-code it twice.
export const FIND_PARTS_OPERATION = 'dissect';

export const FIND_PARTS_LABEL = 'Find parts';
export const FIND_PARTS_BUSY = 'Looking…';
export const FIND_PARTS_TITLE = 'Find visual material you can turn into grounds and percepts.';

// The empty state. It invites perceptual work rather than naming the machine operation:
// what the curator gets is material for grounds and percepts, not "the image's anatomy".
export const EMPTY_TITLE = 'Nothing found here yet.';
export const EMPTY_BODY = 'Find parts to begin composing grounds and percepts.';

// The busy line over the stage. Present tense, no machine vocabulary.
export const LOOKING_CAPTION = 'Looking through the image…';

// The failure line. States what did not happen; never a cause it cannot know.
export const FIND_PARTS_FAILED = 'Couldn’t look through the image — is the backend running?';

// ── ways of looking ──────────────────────────────────────────────────────────
// A mode of ATTENTION, not a model profile. Each `key` is exactly the domain-profile
// specialist the backend already accepts; only the labels changed. `general` is the base
// pass — always on, never a choice — which is why it carries `base: true` and is excluded
// from the toggle set rather than rendered as a disabled button pretending to be one.
export const WAYS_OF_LOOKING = [
  {
    key: 'general',
    base: true,
    label: 'Ordinary looking',
    hint: 'Always on — the plain pass over whatever is there.',
  },
  {
    key: 'fashion',
    label: 'Fashion & body',
    hint: 'Attend to garments, drape and the worn body.',
  },
  {
    key: 'architecture',
    label: 'Built space',
    hint: 'Attend to structure, surface and the made environment.',
  },
  {
    key: 'painting',
    label: 'Painting & surface',
    hint: 'Attend to the picture plane — mark, ground, facture.',
  },
];

export const BASE_WAY = WAYS_OF_LOOKING.find((w) => w.base);
export const SPECIALIST_WAYS = WAYS_OF_LOOKING.filter((w) => !w.base);
export const WAY_KEYS = WAYS_OF_LOOKING.map((w) => w.key);
export const wayLabel = (k) => WAYS_OF_LOOKING.find((w) => w.key === k)?.label || k;

/** Which ways this post is currently looking through. Mirrors ProfileControl's default. */
export function chosenWays(profile) {
  const chosen = profile && Array.isArray(profile.chosen) ? profile.chosen : null;
  return chosen && chosen.length ? chosen : ['general'];
}

/**
 * Next `chosen` array to PATCH when a specialist way is toggled.
 *
 * `general` is stripped because the service re-adds it first; sending it back would let a
 * curator's toggle decide the base pass, which is not theirs to decide. Identical semantics
 * to the control this replaces — the wire behaviour must not move with the label.
 */
export function toggleWay(chosen, key) {
  const cur = Array.isArray(chosen) ? chosen : [];
  const next = cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key];
  return next.filter((k) => k !== 'general');
}

/** Auto proposed this profile and the curator has not overridden it. */
export const isAutoWay = (profile) => profile ? profile.user_overridden === false : false;

/**
 * The router's reason, or null.
 *
 * Live corpus data reaches us as `" · user override · user override"` — a string built by
 * appending to an empty seed and never cleaned. Rendering it verbatim shows the curator
 * punctuation and a stutter, so: split on the separator, drop blanks, drop consecutive
 * repeats, and return null rather than an empty shell. A reason we cannot state plainly is
 * one we should not state at all.
 */
export function wayReason(profile) {
  const raw = String((profile && profile.reason) || '');
  const parts = raw.split('·').map((s) => s.trim()).filter(Boolean);
  const deduped = parts.filter((p, i) => p !== parts[i - 1]);
  return deduped.length ? deduped.join(' · ') : null;
}

// ── grain (the subdivision vocabulary) ───────────────────────────────────────
// Keys are the `mode` values the detect route already accepts. Frozen; labels are not.
export const GRAINS = [
  { key: 'general', label: 'Whole parts' },
  { key: 'garment', label: 'Garments' },
  { key: 'body', label: 'Body' },
  { key: 'texture', label: 'Textures' },
  { key: 'material', label: 'Materials' },
  { key: 'composition', label: 'Composition' },
];
export const GRAIN_KEYS = GRAINS.map((g) => g.key);
export const grainLabel = (k) => GRAINS.find((g) => g.key === k)?.label || k;

// ── sources / capabilities ───────────────────────────────────────────────────
// Quiet status marks, never a curator decision. The role comes from the capability the
// backend itself reports, so this cannot drift from what the server can actually do.
export const CAPABILITY_ROLE = {
  segment: 'Segmentation',
  mask_refine: 'Refinement',
  fashion_parse: 'Garment reading',
  arch_parse: 'Structure reading',
  vlm: 'Model reading',
};

// Short display names for the passes we know. An unknown pass falls back to its own id
// rather than being hidden — a source we cannot name is still a source that ran.
export const SOURCE_LABEL = {
  yolo11n_seg: 'YOLO',
  segformer_b0_ade: 'SegFormer',
  sam21_hiera_tiny: 'SAM',
  fashionpedia_r50fpn: 'Fashionpedia',
  segformer_clothes: 'Garment parser',
};

export const SOURCE_STATE_LABEL = {
  ready: 'ready',
  deferred: 'deferred',
  unavailable: 'unavailable',
  unknown: 'not reported',
  unused: 'not used',
};

/**
 * The capability strip.
 *
 * Scheduled passes first (they are what the next look will use), then anything the server
 * reports that this way of looking does NOT schedule, marked `unused`.
 *
 * A pass with no capability record is `unknown` — **not** `ready`. The control this replaces
 * defaulted to `ready`, which asserted availability on the strength of a missing record; a
 * strip that invents readiness is worse than one that admits it does not know.
 */
export function sourceStrip(passes = [], caps = {}) {
  const scheduled = (Array.isArray(passes) ? passes : []).filter(Boolean);
  const seen = new Set(scheduled);
  const entry = (name, used) => {
    const cap = caps[name] || null;
    return {
      name,
      label: SOURCE_LABEL[name] || name,
      role: (cap && CAPABILITY_ROLE[cap.capability]) || null,
      state: used ? (cap && cap.state ? cap.state : 'unknown') : 'unused',
      stateLabel: SOURCE_STATE_LABEL[used ? (cap && cap.state ? cap.state : 'unknown') : 'unused']
        || (cap && cap.state) || 'unknown',
      detail: (cap && cap.reason) || '',
      used,
    };
  };
  const rest = Object.keys(caps || {}).filter((n) => !seen.has(n)).sort();
  return [...scheduled.map((n) => entry(n, true)), ...rest.map((n) => entry(n, false))];
}

/** Only the sources the next look will actually use. */
export const scheduledSources = (strip) => (strip || []).filter((s) => s.used);

/** True when something the next look depends on is not ready. Drives one quiet warning. */
export const hasBlockedSource = (strip) =>
  scheduledSources(strip).some((s) => s.state === 'unavailable');

// ── operation memory ─────────────────────────────────────────────────────────
// The console's trace panel is a projection of the LATEST recorded run per operation. It is
// not a live stage stream: there is no socket and no per-stage push, only `…/vision-runs/
// latest` re-read on a bounded timer while something is running. Every helper here is named
// so that nothing in the UI can imply otherwise.

/**
 * Derive one entry per instrumented operation, in a stable order.
 * `results` is the shape `useVisionActivity` returns: { op: { run, unreadable } }.
 */
export function memoryEntries(results = {}, { regionsById = {}, now = Date.now() } = {}) {
  return OPERATIONS.map((op) => {
    const r = results[op];
    return deriveEntry(op, r ? r.run : null, {
      regionsById, now, unreadable: !!(r && r.unreadable),
    });
  });
}

/** Epoch ms of the moment a run last reported, or null. Ordering only — never causality. */
export function entryTime(run) {
  if (!run) return null;
  const t = Date.parse(run.completed_at || run.updated_at || run.created_at || '');
  return Number.isNaN(t) ? null : t;
}

/**
 * The single most recently recorded operation, or null.
 *
 * Ordered by each run's own reported time. Two runs being adjacent in this ordering says
 * nothing about one having produced the other, and no copy derived from it may suggest so.
 */
export function latestEntry(entries = [], results = {}) {
  let best = null;
  let bestAt = -Infinity;
  for (const e of entries) {
    if (e.isEmpty || e.isUnreadable) continue;
    const at = entryTime(results[e.operation] ? results[e.operation].run : null);
    if (at === null) { if (!best) best = e; continue; }
    if (at > bestAt) { bestAt = at; best = e; }
  }
  return best;
}

/**
 * The collapsed one-line state of the whole memory panel.
 *
 * `unreadable` is kept distinct from `empty` at every level (P2.2R-B1): a failed read must
 * never render as "nothing recorded", because that is a claim about the corpus made on the
 * strength of a broken request.
 */
export function memorySummary(entries = []) {
  const recorded = entries.filter((e) => !e.isEmpty && !e.isUnreadable);
  const unreadable = entries.filter((e) => e.isUnreadable).length;
  if (entries.some((e) => e.isActive)) return { text: 'observing…', tone: 'active' };
  if (recorded.length) {
    return {
      text: `${recorded.length} recorded${unreadable ? ' · some unreadable' : ''}`,
      tone: unreadable ? 'warn' : 'ok',
    };
  }
  if (unreadable) return { text: 'couldn’t read activity', tone: 'unreadable' };
  return { text: 'nothing recorded yet', tone: 'muted' };
}

/**
 * What the memory panel is a record OF. Rendered verbatim so the scope of the claim travels
 * with the claim: these four operations are instrumented, and the other nine are not.
 */
export const MEMORY_SCOPE = `Records ${OPERATIONS.length} instrumented operations — not all vision activity.`;

/**
 * How the panel knows what it knows. Required by Gate 3G: if it does not stream, it must not
 * read as though it does.
 */
export const MEMORY_PROVENANCE = 'Latest recorded run per operation, re-read while one is running.';

// Curator-facing strings this module owns. The guard test asserts none of them says
// "dissect" — the rename is enforced by a key/exports check, not by reading the screen.
export const CONSOLE_COPY = [
  FIND_PARTS_LABEL, FIND_PARTS_BUSY, FIND_PARTS_TITLE,
  EMPTY_TITLE, EMPTY_BODY, LOOKING_CAPTION, FIND_PARTS_FAILED,
  MEMORY_SCOPE, MEMORY_PROVENANCE,
  ...WAYS_OF_LOOKING.map((w) => w.label), ...WAYS_OF_LOOKING.map((w) => w.hint),
  ...GRAINS.map((g) => g.label),
];

// Re-exported so a consumer never has to reach past this module into the wire vocabulary.
export { OPERATIONS, OPERATION_LABEL };
