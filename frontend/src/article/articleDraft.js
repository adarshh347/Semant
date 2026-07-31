/**
 * CIRCUIT-003 M4 — the perceptual article, as data the renderer can walk.
 *
 * The backend resolver (`article_resolver.py`) joins each of M3's citations to the geometry that
 * was actually produced for it. This module is the client half: it turns that payload into the
 * ordered blocks a document is made of, and it decides what the reader is TOLD.
 *
 * PURE. No React, no fetch, no DOM. Every judgement about what an article admits to lives here,
 * where it can be tested without rendering anything.
 *
 * THE ONE RULE WORTH RESTATING. M3 wrote two channels nothing had ever rendered:
 * `uncited_mentions` (a paragraph naming an image it does not cite) and `relevance_flags` (a
 * percept the composer itself said does not bear on the claim). M3 flagged, in its own final
 * report, that if M4 did not surface them the reader would never see the honest defect even
 * though the data was right there. `sectionDefects()` is the answer to that, and the renderer is
 * not permitted to drop it — a defect channel that exists in the payload and not on the page is
 * indistinguishable, to a reader, from no defect at all.
 */

// The five-way key, in reporting order. Mirrors M6/M5's vocabulary exactly; the words carry the
// meaning and the hue is decoration, so a greyscale screenshot still reads.
export const EPISTEMIC_LEGEND = [
    { status: 'visible', label: 'visible', hint: 'an extent present in the picture' },
    { status: 'measured', label: 'measured', hint: 'computed from the image signal' },
    { status: 'interpretive', label: 'interpretive', hint: 'a reading about the image' },
    { status: 'sourced', label: 'sourced', hint: 'from outside the image, with a citation' },
    { status: 'uncertain', label: 'uncertain', hint: 'the producer will not vouch for a kind' },
];

export const FUNCTION_LABEL = {
    support: 'supports',
    complicate: 'complicates',
    challenge: 'challenges',
};

export const FUNCTION_HINT = {
    support: 'evidence the claim rests on',
    complicate: 'holds, while making the claim harder to state simply',
    challenge: 'would tell against the claim if it came back strong',
};

/** The resolved-citation map, keyed by step_id. Tolerant of a missing payload. */
export const resolvedMap = (article) => (article && article.resolved) || {};

/** M3's draft, verbatim. The resolver carries it through unedited and so do we. */
export const draftOf = (article) => (article && article.draft) || {};

/**
 * One section's citations, each joined to its resolution.
 *
 * A citation whose resolution is missing is NOT dropped — it becomes an entry with
 * `status: 'unproduced'`, because a citation that vanishes between the composer and the page is a
 * sentence that has quietly stopped resting on anything.
 */
export function sectionCitations(section, article) {
    const resolved = resolvedMap(article);
    return (section?.citations || []).map((c) => {
        const r = resolved[c.step_id];
        return {
            ...c,
            status: r?.status || 'unproduced',
            geometry: r?.geometry || null,
            geometryKind: r?.geometry_kind || '',
            imageRef: r?.image_ref || c.image_ref || '',
            imageTitle: r?.image_title || c.image_title || '',
            label: r?.label || '',
            detail: r?.detail || '',
            candidates: r?.candidates || [],
            drawable: Boolean(r?.drawable),
            reopen: r?.reopen || null,
        };
    });
}

/**
 * Everything a section is admitting about itself. THE HONEST-DEFECT CHANNEL.
 *
 * Four kinds, each a different failure and each worded as itself:
 *   relevance   — the composer said this percept does not bear on the claim (M2's flagged limit,
 *                 surfaced in the document rather than narrated over)
 *   uncited     — the prose names an image the section does not cite
 *   unresolved  — a citation the resolver could not join, or refused to (ambiguity)
 *   caveat      — M3's own qualification, carried verbatim
 */
export function sectionDefects(section, article) {
    const out = [];
    // M3 records a relevance mismatch TWICE by design: structured in `relevance_flags`, and
    // again as prose in `caveats` (which is what the composer prompt is given). Rendering both
    // shows the reader the same admission twice in slightly different words, which reads as two
    // separate problems. The structured one wins; the prose restatement is suppressed below.
    const restated = new Set();
    for (const flag of section?.relevance_flags || []) {
        out.push({
            kind: 'relevance',
            title: `${flag.actuator} does not bear on this claim`,
            detail: flag.why || '',
        });
        restated.add(`${flag.actuator} does not bear on this claim: ${flag.why || ''}`.trim());
    }
    for (const image of section?.uncited_mentions || []) {
        out.push({
            kind: 'uncited',
            title: 'names an image this section does not cite',
            detail: image,
        });
    }
    for (const c of sectionCitations(section, article)) {
        if (c.status === 'ambiguous') {
            out.push({
                kind: 'unresolved',
                title: `${c.actuator}: which percept this cites cannot be settled`,
                detail: c.detail,
            });
        } else if (c.status === 'unproduced') {
            out.push({
                kind: 'unresolved',
                title: `${c.actuator}: no produced percept to show`,
                detail: c.detail,
            });
        }
    }
    for (const caveat of section?.caveats || []) {
        if (restated.has(String(caveat).trim())) continue;   // already shown, structured
        out.push({ kind: 'caveat', title: caveat, detail: '' });
    }
    return out;
}

/** Every defect in the article, so the document can carry a count where a reader lands on it. */
export function articleDefects(article) {
    const draft = draftOf(article);
    return (draft.sections || []).flatMap((s) =>
        sectionDefects(s, article).map((d) => ({ ...d, claim_id: s.claim_id })));
}

/**
 * The ordered blocks of the document.
 *
 * Order is the argument: opening, the body in the order the claims were bound, the
 * counter-reading, then what could not be carried. The qualifications come LAST and are never
 * interleaved among the sections — a limit placed beside a finding reads as a finding with a
 * footnote, and these are not findings.
 */
export function articleBlocks(article) {
    const draft = draftOf(article);
    const blocks = [];
    if (draft.thesis_prose || draft.thesis) {
        blocks.push({ type: 'opening', thesis: draft.thesis, prose: draft.thesis_prose || '' });
    }
    for (const section of draft.sections || []) {
        blocks.push({ type: 'section', section });
    }
    if (draft.counter_reading) {
        blocks.push({ type: 'counter', counter: draft.counter_reading });
    }
    if ((draft.qualifications || []).length) {
        blocks.push({ type: 'qualifications', items: draft.qualifications });
    }
    if ((draft.uncomposed || []).length) {
        blocks.push({ type: 'uncomposed', items: draft.uncomposed });
    }
    return blocks;
}

/**
 * The reopen target for a citation: which post to open, and what to find in it.
 *
 * Returns null when the citation never resolved — a link that opened the right post and could not
 * show the percept would teach a reader that the article's links are decorative.
 */
export function reopenTarget(citation) {
    if (!citation || !citation.reopen || !citation.reopen.post_id) return null;
    const { post_id, source_ref, step_id } = citation.reopen;
    const params = new URLSearchParams();
    if (source_ref) params.set('percept', source_ref);
    if (step_id) params.set('step', step_id);
    const query = params.toString();
    return { postId: post_id, href: `/posts/${post_id}${query ? `?${query}` : ''}` };
}

/** Is this article safe to describe as complete? Mirrors M3's own answer; never softened. */
export const isComplete = (article) => Boolean(draftOf(article).complete);

/** Always false. M4 DISPLAYS the quarantined draft; it has no commit path. */
export const isCommitted = (article) => Boolean(draftOf(article).committed);
