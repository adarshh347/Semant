/**
 * INQUIRY WORKBENCH — what rests on one picture.
 *
 * Every image reference in this surface is currently an inert string. `WhyHere` prints
 * `from: post_7f21`, the source-unit row prints the same token, and the header renders a
 * thumbnail that does nothing. A reader who wants the obvious thing — *which picture is that, and
 * what did the run actually say about it?* — has to match an id by eye across four panels.
 *
 * These are the selectors behind the fix. They are pure functions of a normalised session, they
 * hold no state, and they are separated from the sidebar deliberately: the interesting content of
 * this lane is the RESOLUTION RULES below, and rules that live inside a component are rules nobody
 * can test without a DOM.
 *
 * ## Citations are read, never inferred
 *
 * Four objects declare which images they rest on, and all four say so in a field the producer
 * wrote:
 *
 * ```text
 * reading.blocks[].image_refs      the theorist naming what it looked at
 * source_units[].image_refs        the dissector carrying that forward
 * semantic_atoms[].image_scope     the atom's own declared scope
 * claims[].image_scope             the claim's own declared scope
 * ```
 *
 * It is tempting to add a fifth, derived one — an atom hangs off source units, and those units
 * cite images, so the atom "obviously" rests on them too. This module does not do that, and the
 * refusal is the point. A derived citation would put a link on the screen that no producer
 * declared, under a panel whose entire promise is that it shows what the run recorded. The
 * sixth instance in this tree of the same discipline: the availability of a path is not the
 * assertion of one.
 *
 * ## post_id is the key; `image_ref` is a URL
 *
 * This one is a live trap. The catalogue entry has BOTH fields:
 *
 * ```text
 * graph.image_refs[] = { post_id, title, image_ref, image_url }
 * ```
 *
 * and the name `image_ref` makes it look like the thing a citation string would match. It is not.
 * The backend builds the catalogue in `corpus.image_refs_for`, where `image_ref` is the post's
 * URL, and it builds citations in `capability.py` as `post_id` and nothing else. `backendParity`
 * already asserts the consequence — `img.image_url === img.image_ref` on a real payload.
 *
 * So resolution is keyed on `post_id`, with `image_ref` accepted only as a fallback for a producer
 * that spelled it the other way. Keyed the other way round, this panel would resolve every
 * citation in the fixtures (whose `imgref_…` values are invented) and none at all in production.
 *
 * ## A reference to a picture the session does not carry is a state, not a blank
 *
 * `danglingRefs` exists because the alternative is worse than useless. If a source unit cites
 * `post_9` and the catalogue has no `post_9`, the honest render is *this names an image the
 * session does not carry* — an upstream defect, shown. A component that quietly dropped the
 * unresolvable chip would make that defect invisible at exactly the surface built to expose it.
 */

/** Every citation surface, in the order the chain produces them. */
export const CITATION_SURFACES = ['reading_blocks', 'source_units', 'atoms', 'claims'];

export const SURFACE_LABEL = {
    reading_blocks: 'reading blocks',
    source_units: 'source units',
    atoms: 'semantic atoms',
    claims: 'claims',
};

/** Where each surface's declared scope lives, named so the tests can assert the field. */
export const SURFACE_FIELD = {
    reading_blocks: 'image_refs',
    source_units: 'image_refs',
    atoms: 'image_scope',
    claims: 'image_scope',
};

const list = (v) => (Array.isArray(v) ? v : []);

/**
 * The posts row, keyed by id.
 *
 * `posts` is what was actually READ — it carries the fingerprint and the `readable: false` state —
 * while `graph.image_refs` is what the theorist was HANDED. They are usually the same set and are
 * emphatically not the same fact, so the catalogue joins them rather than picking one.
 */
function postsById(session) {
    const by = new Map();
    for (const p of list(session?.posts)) {
        if (p?.post_id) by.set(p.post_id, p);
    }
    return by;
}

/**
 * Every image this session carries, each with what rests on it.
 *
 * Ordered by `graph.image_refs` — the order the run was given them in — and NOT by citation count.
 * Sorting by "most cited" would put the surface's own arithmetic ahead of the run's own sequence,
 * and an image nothing cites would sink to the bottom exactly when it is the interesting one.
 */
export function imageCatalogue(session) {
    if (!session) return [];
    const posts = postsById(session);
    const cited = citationIndex(session);

    return list(session.graph?.image_refs).map((img) => {
        const post = posts.get(img.post_id) || null;
        const citations = cited.get(img.post_id) || emptyCitations();
        return {
            post_id: img.post_id,
            title: img.title,
            image_url: img.image_url,
            image_ref: img.image_ref,
            // Straight off the post record, never defaulted to `true`. `null` means nobody
            // declared it, which is a different thing from a post declared readable.
            readable: post ? post.readable : null,
            fingerprint: post ? post.fingerprint : '',
            note: post ? post.note : '',
            // `false` where the post row simply does not mention this image — the theorist was
            // handed something the read ledger never accounted for.
            in_posts: Boolean(post),
            citations,
            citation_count: countCitations(citations),
        };
    });
}

function emptyCitations() {
    return { reading_blocks: [], source_units: [], atoms: [], claims: [] };
}

export function countCitations(citations) {
    return CITATION_SURFACES.reduce((n, k) => n + list(citations?.[k]).length, 0);
}

/**
 * One pass over the graph, building `post_id → citations`.
 *
 * Built once and shared rather than re-scanned per image: the catalogue is O(graph), not
 * O(images × graph), and more importantly every surface reads from ONE index, so a reference the
 * index cannot place is placed nowhere rather than in three of four panels.
 */
export function citationIndex(session) {
    const index = new Map();
    // ONE OBJECT DECLARING THE SAME IMAGE TWICE IS ONE CITATION. A producer that emitted
    // `image_refs: ['a', 'a']` would otherwise make this panel report two citing objects where
    // there is one — and the count is the first thing a reader trusts. Deduplicating on the
    // OBJECT is not inference: it is refusing to count a thing twice for being named twice.
    const seen = new Set();
    const add = (ref, surface, entry) => {
        const key = String(ref || '');
        if (!key) return;
        const once = `${key}\u0000${surface}\u0000${entry.id}`;
        if (seen.has(once)) return;
        seen.add(once);
        if (!index.has(key)) index.set(key, emptyCitations());
        index.get(key)[surface].push(entry);
    };

    const g = session?.graph || {};

    for (const b of list(g.reading?.blocks)) {
        for (const r of list(b.image_refs)) {
            add(r, 'reading_blocks', { id: b.block_id, kind: b.kind, text: b.text });
        }
    }
    for (const u of list(g.source_units)) {
        for (const r of list(u.image_refs)) {
            add(r, 'source_units', {
                id: u.source_unit_id,
                kind: u.source_type?.value || '',
                text: u.exact_quote,
            });
        }
    }
    for (const a of list(g.semantic_atoms)) {
        for (const r of list(a.image_scope)) {
            add(r, 'atoms', { id: a.atom_id, kind: a.unit_kind?.value || '', text: a.text });
        }
    }
    for (const c of list(g.claims)) {
        for (const r of list(c.image_scope)) {
            add(r, 'claims', {
                id: c.claim_id,
                kind: c.kind?.value || '',
                text: c.text,
                status: c.status || null,
            });
        }
    }
    return index;
}

/**
 * Resolve one reference string to a catalogue entry, or `null`.
 *
 * `post_id` first, `image_ref` second, and nothing else — no prefix stripping, no case folding, no
 * "ends with" match. A near-miss resolved by a fuzzy rule would show a person one picture while
 * the run reasoned about another, which is the single worst thing this panel could do.
 *
 * Takes a session OR an already-built catalogue, so a caller holding one does not rebuild it.
 */
export function resolveRef(session, ref) {
    const key = String(ref || '');
    if (!key) return null;
    const catalogue = Array.isArray(session) ? session : imageCatalogue(session);
    return catalogue.find((e) => e.post_id === key)
        || catalogue.find((e) => e.image_ref && e.image_ref === key)
        || null;
}

/**
 * Every reference cited by something that the catalogue cannot place.
 *
 * Returned with its citers, because "there is a dangling ref somewhere" is not actionable and
 * "`rdb_2` and `su_4` cite `post_9`, which this session does not carry" is.
 */
export function danglingRefs(session) {
    const catalogue = imageCatalogue(session);
    const known = new Set();
    for (const e of catalogue) {
        known.add(e.post_id);
        if (e.image_ref) known.add(e.image_ref);
    }
    const out = [];
    for (const [ref, citations] of citationIndex(session)) {
        if (known.has(ref)) continue;
        out.push({ ref, citations, citation_count: countCitations(citations) });
    }
    return out;
}

/**
 * Images the run was handed and nothing ever cited.
 *
 * The counterpart absence to `danglingRefs`, and the one a reader is more likely to care about: a
 * picture that went in and produced no recorded thought about it is either a theorist that skipped
 * it or a chain that lost the link, and both are worth seeing.
 */
export function uncitedImages(session) {
    return imageCatalogue(session).filter((e) => e.citation_count === 0);
}

/** The catalogue entry a chip should open, given whatever the surface had to hand. */
export function inspectorTarget(session, ref) {
    const catalogue = imageCatalogue(session);
    const entry = resolveRef(catalogue, ref);
    if (entry) return { ref: String(ref || ''), entry, resolved: true, citations: entry.citations };
    const dangling = danglingRefs(session).find((d) => d.ref === String(ref || ''));
    return {
        ref: String(ref || ''),
        entry: null,
        resolved: false,
        citations: dangling ? dangling.citations : emptyCitations(),
    };
}
