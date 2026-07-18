// Sequences — the archive's real grain.
//
// A reel split into frames, or a carousel saved in one go, lands as a burst of
// posts created seconds apart. The archive is ordered newest→oldest by _id, and
// a MongoDB ObjectId carries its creation time in its first 4 bytes, so we can
// recover those bursts client-side with no backend call.
//
// SEAM: `architecture-lab/feature-source-groups.md` specs a real `source_group`
// ({group_id, group_type, sequence_index, t_ms}) owned by the vision-pipeline
// thread. When it lands, `groupKey()` should prefer `post.source_group.group_id`
// and this timestamp heuristic becomes the fallback for pre-backfill posts.
// Nothing else in the UI needs to change.

const BURST_GAP_MS = 90 * 1000; // > 90s apart ⇒ a different upload session

export function objectIdDate(id) {
  if (typeof id !== 'string' || id.length < 8) return null;
  const secs = parseInt(id.slice(0, 8), 16);
  return Number.isFinite(secs) ? new Date(secs * 1000) : null;
}

// The identity of the group a post belongs to, once the pipeline stamps one.
export function groupKey(post) {
  return post?.source_group?.group_id ?? null;
}

// A human label for the kind of sequence we're looking at.
function labelFor(group) {
  const type = group.items[0]?.source_group?.group_type;
  const n = group.items.length;
  if (type === 'reel' || type === 'video') return `Sequence · ${n} frames`;
  if (type === 'carousel') return `Carousel · ${n} slides`;
  if (n === 1) return 'Single';
  // Pre-source_group: an upload burst IS the sequence we can honestly claim.
  return `Sequence · ${n} frames`;
}

/**
 * Split an ordered (newest→oldest) post list into sequences.
 * Prefers a real `source_group.group_id`; falls back to an upload-time burst.
 * Returns [{ key, label, at, items }].
 */
export function groupIntoSequences(posts) {
  const out = [];
  let current = null;
  let lastTs = null;

  for (const post of posts) {
    const gid = groupKey(post);
    const ts = objectIdDate(post.id)?.getTime() ?? null;

    const startsNew =
      !current ||
      (gid != null
        ? gid !== current.gid
        : current.gid != null || lastTs == null || ts == null || Math.abs(lastTs - ts) > BURST_GAP_MS);

    if (startsNew) {
      current = { key: gid ?? `burst:${post.id}`, gid, at: ts, items: [post] };
      out.push(current);
    } else {
      current.items.push(post);
    }
    lastTs = ts;
  }

  return out.map((g) => ({ key: g.key, at: g.at, items: g.items, label: labelFor(g) }));
}
