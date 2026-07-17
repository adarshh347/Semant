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
} = {}) {
  return {
    id: id || `pctx_${Date.now().toString(36)}_${(pctxSeq++).toString(36)}`,
    kind: 'expression',
    expression,
    ground_ids: [...ground_ids],
    properties: [...properties],
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
export function mentionId({ perceptId: pid, regionId, blockId, inlineContentId, form = 'block' }) {
  return `men_${pid || regionId || 'x'}_${blockId || 'x'}_${inlineContentId || form}`;
}

export function makeMention({
  perceptId: pid = null,
  regionId = null,
  blockId,
  inlineContentId = null,
  form = 'block',
  relationType = RELATION_DEFAULT,
  actor = 'human',
}) {
  return {
    id: mentionId({ perceptId: pid, regionId, blockId, inlineContentId, form }),
    perceptId: pid,
    regionId,
    blockId,
    inlineContentId,
    form,
    relationType,
    actor,
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
export function mentionsFromBlocks(textBlocks = []) {
  const re = /data-region-ids="([^"]*)"/g;
  const out = [];
  for (const b of textBlocks || []) {
    const html = b.content || '';
    let m;
    while ((m = re.exec(html)) !== null) {
      for (const rid of m[1].split(',').filter(Boolean)) {
        out.push(makeMention({ regionId: rid, blockId: b.id, form: 'inline', relationType: 'cites', actor: 'human' }));
      }
    }
  }
  // Dedupe by id (a block citing the same region twice → one edge).
  const seen = new Map();
  for (const men of out) seen.set(men.id, men);
  return [...seen.values()];
}
