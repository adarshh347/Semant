/**
 * ATLAS L1 — the pure half of curation: what a walk IS, and what a save owes the server.
 *
 * A CORPUS IS A SEQUENCE, NOT A SET. Everything here preserves that and nothing here sorts. The
 * picker numbers a selection in click order because the order somebody picks in IS the walk they
 * are describing — an alphabetised or date-sorted list would be a folder, and M1 is explicit that
 * "a corpus that cannot say why the stair follows the colonnade is a folder".
 *
 * THE NOTE IS PART OF THE ARGUMENT. Each image carries the curator's reason for its place. It is
 * optional — a walk you have not yet explained is still a walk — but it is the field the argument
 * planner is later handed as `why this sequence`, so it is offered at curation time rather than
 * bolted on afterwards.
 *
 * Everything is a function of its arguments: no fetch, no clock.
 */

/** How many images one walk may hold. Mirrors the backend's cap so the surface can say so first. */
export const MAX_IMAGES = 60;

/** A selection (post ids in click order) → what `POST /corpora` takes. */
export function imagesFrom(selected, notes = {}) {
    return (selected || [])
        .filter(Boolean)
        .map((postId) => ({ post_id: String(postId), note: String(notes[postId] || '').trim() }));
}

/**
 * Toggle one image in the selection, KEEPING click order.
 *
 * Re-picking an image removes it rather than moving it to the end: a curator un-picking the third
 * image of five expects four, not a reshuffle. Order changes are their own gesture (`move`).
 */
export function toggle(selected, postId) {
    const list = selected || [];
    return list.includes(postId) ? list.filter((p) => p !== postId) : [...list, postId];
}

/** Move one image within the walk. Cannot add or drop — membership is a different gesture. */
export function move(selected, postId, delta) {
    const list = [...(selected || [])];
    const from = list.indexOf(postId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= list.length) return list;
    const [item] = list.splice(from, 1);
    list.splice(to, 0, item);
    return list;
}

/**
 * Why this walk cannot be saved yet, in words — or '' when it can.
 *
 * Returned as a sentence rather than a boolean so the surface can SAY the reason instead of
 * presenting a dead button and leaving the curator to guess which rule they broke.
 */
export function saveBlocker(selected, title) {
    const n = (selected || []).length;
    if (!n) return 'Pick the images, in the order you walk them.';
    if (!String(title || '').trim()) return 'Give the walk a name — you will want to find it again.';
    if (n > MAX_IMAGES) return `A walk holds at most ${MAX_IMAGES} images; this one has ${n}.`;
    return '';
}

/** One line per saved walk, for the list a curator reopens from. Counts, never adjectives. */
export function corpusSummary(corpus) {
    const images = corpus?.images || [];
    const noted = images.filter((i) => (i.note || '').trim()).length;
    return {
        id: corpus?.id,
        title: corpus?.title || corpus?.id || '',
        count: images.length,
        // Said separately because an unexplained walk is still a walk — this is a prompt, not a
        // reproach, and folding it into the count would make it read as a defect.
        noted,
        why: corpus?.why || '',
    };
}

/** The hydrated view's images → rows a curation list can draw, order preserved. */
export function walkRows(view) {
    return (view?.images || []).map((i) => ({
        postId: String(i.post_id),
        position: Number(i.position ?? 0),
        note: i.note || '',
        readable: i.readable !== false,
        imageRef: i.image_ref || '',
        title: i.title || '',
        committed: Number(i.committed || 0),
        // An image that could not be read STAYS in the walk and says why. "This image has no
        // percepts" and "this image could not be loaded" are different facts about a corpus.
        unreadableReason: i.unreadable_reason || '',
    }));
}
