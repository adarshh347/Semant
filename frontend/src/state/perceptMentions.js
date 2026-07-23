/**
 * Percept + Mention — the product-layer relationship model for Chiasm (assembly
 * Phase 1). Pure helpers; the shared store (`regionStore`) wires them into state.
 *
 * LOCKED shape (percept-model-digest):
 *   Percept  — the *attention* object built around a Region (the visual ground).
 *              `{ id, regionId, label, note, lens, actor }`. NOT a DB table yet —
 *              a thin client composition. v1 rule: one creator percept per region
 *              per post (unique regionId + actor).
 *   Mention  — the region↔block join (many-to-many). `{ id, perceptId, regionId,
 *              blockId, inlineContentId, form: 'inline'|'block', relationType,
 *              actor }`. `inlineContentId` distinguishes several refs in one block.
 *
 * `Region.block_id` / `Highlight.block_id` stay the PRIMARY attachment for
 * back-compat; Mentions are the real join layered on top. `blockIdsForRegion`
 * unions both so highlighting degrades gracefully instead of vanishing.
 *
 * Provenance chain stays distinct: Region.actor → Percept.actor → Mention.actor
 * → TextBlock.origin.
 */

export const RELATION_DEFAULT = 'cites';

// ── Percept ────────────────────────────────────────────────────────────────
// Deterministic id → one creator percept per region per post, idempotent upsert.
export function perceptId(regionId, actor = 'creator') {
  return `pct_${actor}_${regionId}`;
}

export function makePercept(region, { actor = 'creator' } = {}) {
  return {
    id: perceptId(region.id, actor),
    regionId: region.id,
    label: region.label || 'part',
    note: region.user_note || '',
    lens: null,
    actor,
  };
}

export function upsertPercept(percepts, percept) {
  const i = percepts.findIndex((p) => p.id === percept.id);
  if (i < 0) return [...percepts, percept];
  const next = [...percepts];
  next[i] = { ...next[i], ...percept };
  return next;
}

export function perceptForRegion(percepts, regionId, actor = 'creator') {
  return percepts.find((p) => p.regionId === regionId && p.actor === actor) || null;
}

// ── Expression Percept (Differential v1) ────────────────────────────────────
// A durable act of noticing, grounded in one or more Grounds. A NEW kind beside
// the attention percepts above: `pctx_` ids, no per-ground uniqueness — the
// cardinality is many-to-many-to-many (Percept↔Ground↔Mention). The old
// one-creator-percept-per-region rule stays untouched for back-compat.

let pctxSeq = 0;

export function makeExpressionPercept({
  id = null,
  expression = '',
  ground_ids = [],
  properties = [],
  actor = 'creator',
  created_at = null,
  // CIRCUIT-001 P1C — { [ground_id]: role }. What each cited ground DOES for
  // this reading. Optional: omitted entirely when nothing is named, so a percept
  // written before roles existed is byte-identical to one whose roles were
  // cleared. Never written to post.grounds — see differential/groundRoles.js.
  ground_roles = null,
} = {}) {
  return {
    id: id || `pctx_${Date.now().toString(36)}_${(pctxSeq++).toString(36)}`,
    kind: 'expression',
    expression,
    ground_ids: [...ground_ids],
    properties: [...properties],
    ...(ground_roles && Object.keys(ground_roles).length ? { ground_roles: { ...ground_roles } } : {}),
    actor,
    created_at: created_at || new Date().toISOString(),
  };
}

export function isExpressionPercept(p) {
  return !!p && (p.kind === 'expression' || String(p.id || '').startsWith('pctx_'));
}

/** Every expression Percept grounded (in part) in this Ground. Many-per-ground. */
export function perceptsForGround(percepts, groundId) {
  return (percepts || []).filter(
    (p) => isExpressionPercept(p) && (p.ground_ids || []).includes(groundId),
  );
}

// ── Mention ──────────────────────────────────────────────────────────────────
// Deterministic id from the edge it records → addMention is naturally idempotent
// (re-inserting the same chip doesn't duplicate the link).
export function mentionId({ perceptId: pid, regionId, markId, blockId, inlineContentId, form = 'block' }) {
  // Grammar unchanged (`men_<subject>_<block>_<slot>`); a mark chip simply names the
  // mark as its subject when it cites neither a percept nor a region (CIRCUIT-001 P3-A).
  return `men_${pid || markId || regionId || 'x'}_${blockId || 'x'}_${inlineContentId || form}`;
}

export function makeMention({
  perceptId: pid = null,
  regionId = null,
  // CIRCUIT-001 P3-A — a mark chip cites a visual_mark directly. The edge carries
  // the `vm_` id so click→recall can perform it. Optional: a percept/region mention
  // leaves it null and is byte-identical to before.
  markId = null,
  blockId,
  inlineContentId = null,
  form = 'block',
  relationType = RELATION_DEFAULT,
  actor = 'human',
  refKind = null,
  label = null,
  // An id carried by the markup wins over a derived one. Deriving is right when
  // a chip is BEING made; when one is being READ BACK, the chip already has an
  // identity and re-deriving it invents a second name for the same edge.
  id = null,
}) {
  return {
    id: id || mentionId({ perceptId: pid, regionId, markId, blockId, inlineContentId, form }),
    perceptId: pid,
    regionId,
    markId,
    blockId,
    inlineContentId,
    form,
    relationType,
    actor,
    refKind,
    label,
  };
}

export function addMention(mentions, mention) {
  const i = mentions.findIndex((m) => m.id === mention.id);
  if (i < 0) return [...mentions, mention];
  const next = [...mentions];
  next[i] = { ...next[i], ...mention };
  return next;
}

export function removeMentionsForBlock(mentions, blockId) {
  return mentions.filter((m) => m.blockId !== blockId);
}

export const mentionsForBlock = (mentions, blockId) => mentions.filter((m) => m.blockId === blockId);
export const mentionsForRegion = (mentions, regionId) => mentions.filter((m) => m.regionId === regionId);
export const mentionsForPercept = (mentions, pid) => mentions.filter((m) => m.perceptId === pid);
// CIRCUIT-001 P3-A — which blocks cite this mark (the mark analog of the above).
export const mentionsForMark = (mentions, markId) => mentions.filter((m) => m.markId === markId);

/**
 * Which blocks talk about this region? Union of Mention edges AND the primary
 * `Region.block_id` — so a block still lights up when a chip is deleted but the
 * block_id survives, and vice versa. Generalises the old block_id-only highlight.
 */
export function blockIdsForRegion(mentions, regions, regionId) {
  const ids = new Set();
  for (const m of mentions) if (m.regionId === regionId && m.blockId) ids.add(m.blockId);
  const region = (regions || []).find((r) => r.id === regionId);
  if (region?.block_id) ids.add(region.block_id);
  return ids;
}

/**
 * Reconstruct inline Mentions from stored block markup — every `data-region-ids`
 * a block's HTML carries becomes a mention edge. Lets existing stories (and the
 * read view) resolve region↔block links without a backend table, so no link is
 * lost migrating off Path A.
 */
const ATTR = (tag, name) => {
  const m = tag.match(new RegExp(`${name}="([^"]*)"`));
  return m ? m[1] : null;
};

export function mentionsFromBlocks(textBlocks = []) {
  // Match the whole chip element, not one attribute of it. The old regex read
  // `data-region-ids` alone, which is why every other attribute the chip
  // faithfully round-trips (percept id, mention id, ref kind, label) was
  // discarded on load — the information was never missing, only unread.
  const chipRe = /<[a-zA-Z]+[^>]*\bdata-region-ref\b[^>]*>/g;
  const out = [];
  for (const b of textBlocks || []) {
    const html = b.content || '';
    let m;
    while ((m = chipRe.exec(html)) !== null) {
      const tag = m[0];
      const perceptId = ATTR(tag, 'data-percept-id');
      const markId = ATTR(tag, 'data-mark-id');
      const storedId = ATTR(tag, 'data-mention-id');
      const refKind = ATTR(tag, 'data-inline-type') || ATTR(tag, 'data-ref-kind');
      const label = ATTR(tag, 'data-label');
      const regionIds = (ATTR(tag, 'data-region-ids') || '').split(',').filter(Boolean);
      const base = { blockId: b.id, form: 'inline', relationType: 'cites', actor: 'human', refKind, label };

      if (markId) {
        // A mark chip is ONE edge keyed on the mark. Its `data-region-ids` are the
        // mark's linked GROUND ids (carried for hover context), never region edges —
        // so, like a percept chip, it is not split per id.
        out.push(makeMention({
          ...base, markId, perceptId: perceptId || null, regionId: null, id: storedId || null,
        }));
        continue;
      }

      if (perceptId) {
        // ONE edge per chip, keyed on the percept. A `/percept` chip's
        // `data-region-ids` are GROUND ids, so splitting it per id would mint
        // region edges pointing at `gnd_…` — a set of "whatever was in that
        // attribute"↔block edges rather than region↔block edges.
        out.push(makeMention({
          ...base, perceptId, regionId: regionIds[0] || null, id: storedId || null,
        }));
        continue;
      }
      // No percept on the chip → the pre-existing shape: one region edge per id.
      // Kept verbatim so chips written before this change reconstruct exactly as
      // they always did.
      for (const rid of regionIds) out.push(makeMention({ ...base, regionId: rid }));
    }
  }
  // Dedupe by id (a block citing the same region twice → one edge).
  const seen = new Map();
  for (const men of out) seen.set(men.id, men);
  return [...seen.values()];
}

/**
 * Is this Percept carried by the writing? Answers the Circulation Thread's
 * "mentioned" link. Reports WHERE, never why — a block id is a location, not a
 * cause.
 */
export function blockIdsForPercept(mentions, perceptId) {
  const ids = new Set();
  for (const m of mentions || []) if (m.perceptId === perceptId && m.blockId) ids.add(m.blockId);
  return ids;
}
