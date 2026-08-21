/**
 * INQUIRY WORKBENCH — the image citation index.
 *
 * These are the rules the sidebar renders, asserted where they can be asserted without a DOM. The
 * two that would be invisible in a screenshot are the two with the most tests: that a citation is
 * only ever a link a producer declared, and that resolution is keyed on `post_id` rather than on
 * the field misleadingly named `image_ref`.
 */
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
    imageCatalogue, citationIndex, resolveRef, danglingRefs, uncitedImages,
    inspectorTarget, countCitations, CITATION_SURFACES, SURFACE_FIELD,
} from './imageInspector.js';
import { normalizeSession } from './inquiryContract.js';
import {
    dissolvedFixture, completedFixture, otherDomainFixture, danglingImageFixture,
} from './inquiryFixtures.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));

const load = (f) => normalizeSession(f);
const entry = (session, id) => imageCatalogue(session).find((e) => e.post_id === id);

// ── the catalogue ───────────────────────────────────────────────────────────

describe('the catalogue', () => {
    it('carries every image the run was handed, in the order it was handed them', () => {
        const cat = imageCatalogue(load(dissolvedFixture()));
        expect(cat.map((e) => e.post_id)).toEqual(['post_altes_front', 'post_altes_rotunda']);
    });

    it('is ordered by the run, not by citation count', () => {
        // The rotunda is cited far less than the front and still comes second, because that is
        // the order the run received them in. Sorting by count would move the least-cited image —
        // the interesting one — to wherever the arithmetic put it.
        const cat = imageCatalogue(load(dissolvedFixture()));
        expect(cat[0].citation_count).toBeGreaterThan(cat[1].citation_count);
        expect(cat.map((e) => e.post_id)).toEqual(['post_altes_front', 'post_altes_rotunda']);
    });

    it('joins the posts row onto the catalogue rather than picking one of them', () => {
        // `graph.image_refs` is what the theorist was HANDED; `posts` is what was actually READ,
        // and only the latter carries the fingerprint. A catalogue built from either alone would
        // drop one of those two facts.
        const e = entry(load(dissolvedFixture()), 'post_altes_front');
        expect(e.image_url).toBe('/fixtures/altes-front.jpg');
        expect(e.readable).toBe(true);
        expect(e.in_posts).toBe(true);
        expect(e.fingerprint).toHaveLength(64);
    });

    it('leaves readability null when no post record declared it', () => {
        // NOT `true`. `otherDomainFixture` sends an image with no posts row at all, and a
        // catalogue that defaulted to readable would report a read that nothing recorded.
        const e = entry(load(otherDomainFixture()), 'post_weld_a');
        expect(e.readable).toBe(null);
        expect(e.in_posts).toBe(false);
    });

    it('returns nothing for a null session rather than throwing', () => {
        expect(imageCatalogue(null)).toEqual([]);
    });
});

// ── citations are read, never inferred ──────────────────────────────────────

describe('citations are read, never inferred', () => {
    it('reads all four declared surfaces', () => {
        const cited = entry(load(dissolvedFixture()), 'post_altes_front').citations;
        expect(Object.keys(cited).sort()).toEqual([...CITATION_SURFACES].sort());
        expect({
            reading_blocks: cited.reading_blocks.map((c) => c.id),
            source_units: cited.source_units.map((c) => c.id),
            atoms: cited.atoms.map((c) => c.id),
            claims: cited.claims.map((c) => c.id).length,
        }).toEqual({
            reading_blocks: ['rdb_1', 'rdb_2', 'rdb_3'],
            source_units: ['su_3', 'su_4', 'su_5'],
            atoms: ['atm_1', 'atm_2', 'atm_3'],
            claims: 4,
        });
    });

    it('never walks an atom to its source units to invent a scope', () => {
        // `atm_2` hangs off `su_1` and `su_2`, and BOTH of those cite no image at all. Its own
        // declared `image_scope` is the front — so a traversal-derived answer and the declared one
        // differ, and this asserts the declared one wins. Were the derivation ever added, `atm_2`
        // would acquire whatever its parents cite and this test would go red.
        const session = load(dissolvedFixture());
        const atom = session.graph.semantic_atoms.find((a) => a.atom_id === 'atm_2');
        const parents = session.graph.source_units
            .filter((u) => atom.source_unit_ids.includes(u.source_unit_id));

        expect(parents.map((u) => u.source_unit_id)).toEqual(['su_1', 'su_2']);
        expect(parents.flatMap((u) => u.image_refs)).toEqual([]);
        expect(atom.image_scope).toEqual(['post_altes_front']);

        // The index carries the atom under its own declaration and under nothing else.
        const front = entry(session, 'post_altes_front').citations.atoms.map((c) => c.id);
        expect(front).toContain('atm_2');
    });

    it('reads each surface from the field that surface actually uses', () => {
        // Blocks and units say `image_refs`; atoms and claims say `image_scope`. One module
        // reading both spellings is the reason a rename upstream shows up here as a zero rather
        // than as a crash.
        expect(SURFACE_FIELD).toEqual({
            reading_blocks: 'image_refs',
            source_units: 'image_refs',
            atoms: 'image_scope',
            claims: 'image_scope',
        });
        const g = load(dissolvedFixture()).graph;
        expect(g.reading.blocks[0]).toHaveProperty('image_refs');
        expect(g.source_units[2]).toHaveProperty('image_refs');
        expect(g.semantic_atoms[0]).toHaveProperty('image_scope');
        expect(g.claims[0]).toHaveProperty('image_scope');
    });

    it('carries the citing object\'s text, so the panel quotes rather than counts', () => {
        const cited = entry(load(dissolvedFixture()), 'post_altes_rotunda').citations;
        expect(cited.reading_blocks.map((c) => c.id)).toEqual(['rdb_2']);
        expect(cited.reading_blocks[0].text).toContain('rotunda is a centre');
        expect(cited.source_units.map((c) => c.id)).toEqual(['su_5']);
    });

    it('counts a multi-image citation against each image it names', () => {
        const session = load(dissolvedFixture());
        const front = entry(session, 'post_altes_front').citations.reading_blocks.map((c) => c.id);
        const rot = entry(session, 'post_altes_rotunda').citations.reading_blocks.map((c) => c.id);
        expect(front).toContain('rdb_2');
        expect(rot).toContain('rdb_2');
    });

    it('counts nothing twice within one surface', () => {
        const cited = entry(load(dissolvedFixture()), 'post_altes_front').citations;
        for (const surface of CITATION_SURFACES) {
            const ids = cited[surface].map((c) => c.id);
            expect(new Set(ids).size).toBe(ids.length);
        }
    });
});

// ── post_id is the key ──────────────────────────────────────────────────────

describe('resolution is keyed on post_id', () => {
    it('resolves a citation string, which is a post id', () => {
        const session = load(dissolvedFixture());
        expect(resolveRef(session, 'post_altes_front').title)
            .toBe('Altes Museum, Lustgarten front');
    });

    it('accepts image_ref only as a fallback', () => {
        const session = load(dissolvedFixture());
        expect(resolveRef(session, 'imgref_altes_rotunda').post_id).toBe('post_altes_rotunda');
    });

    it('prefers a post_id match over an image_ref match', () => {
        // The pathological payload: one image's `image_ref` collides with another's `post_id`.
        // Whichever way it is keyed, one of the two chips opens the wrong picture — so the
        // precedence is fixed and asserted rather than left to `find` order.
        const f = dissolvedFixture();
        f.graph.image_refs = [
            { post_id: 'B', title: 'the one whose image_ref collides', image_ref: 'A', image_url: '/b.jpg' },
            { post_id: 'A', title: 'the one whose post_id is A', image_url: '/a.jpg' },
        ];
        expect(resolveRef(load(f), 'A').title).toBe('the one whose post_id is A');
    });

    it('refuses a near miss', () => {
        // No prefix stripping, no case folding, no suffix match. A fuzzy resolve would show a
        // person one picture while the run reasoned about another.
        const session = load(dissolvedFixture());
        for (const near of ['POST_ALTES_FRONT', 'altes_front', 'post_altes_front ', 'post_altes']) {
            expect([near, resolveRef(session, near)]).toEqual([near, null]);
        }
    });

    it('resolves nothing for an empty ref', () => {
        expect(resolveRef(load(dissolvedFixture()), '')).toBe(null);
        expect(resolveRef(load(dissolvedFixture()), null)).toBe(null);
    });

    it('holds the production spelling, where image_ref is a URL', () => {
        // `corpus.image_refs_for` sets `image_ref` to the post's url, and `backendParity` asserts
        // `image_url === image_ref` on a real payload. Keyed on `image_ref` this panel would
        // resolve every fixture and nothing in production, so the production shape is tested
        // directly rather than only through fixtures that spell it `imgref_…`.
        const f = dissolvedFixture();
        for (const img of f.graph.image_refs) img.image_ref = img.image_url;
        const session = load(f);
        expect(resolveRef(session, 'post_altes_front').image_url).toBe('/fixtures/altes-front.jpg');
        expect(entry(session, 'post_altes_front').citation_count).toBeGreaterThan(0);
    });
});

// ── the two absences ────────────────────────────────────────────────────────

describe('a reference to a picture the session does not carry', () => {
    it('is reported with its citers rather than dropped', () => {
        const dangling = danglingRefs(load(danglingImageFixture()));
        expect(dangling.map((d) => d.ref)).toEqual(['post_altes_missing']);
        expect(dangling[0].citations.source_units.map((c) => c.id)).toEqual(['su_9']);
        expect(dangling[0].citation_count).toBe(2);
    });

    it('is empty on a session whose every reference resolves', () => {
        expect(danglingRefs(load(dissolvedFixture()))).toEqual([]);
    });

    it('does not become a catalogue entry', () => {
        // The catalogue is what the session CARRIES. A dangling ref is a defect to report, not an
        // image to add — inventing an entry for it would make the upstream bug look like content.
        const cat = imageCatalogue(load(danglingImageFixture()));
        expect(cat.map((e) => e.post_id)).not.toContain('post_altes_missing');
    });
});

describe('an image nothing cited', () => {
    it('is named, not left to be noticed as a gap', () => {
        const uncited = uncitedImages(load(danglingImageFixture()));
        expect(uncited.map((e) => e.post_id)).toEqual(['post_altes_rotunda']);
    });

    it('is none of them on a fully cited run', () => {
        expect(uncitedImages(load(dissolvedFixture()))).toEqual([]);
    });

    it('reports zero as a count rather than as an absent number', () => {
        const e = uncitedImages(load(danglingImageFixture()))[0];
        expect(e.citation_count).toBe(0);
        expect(countCitations(e.citations)).toBe(0);
    });
});

// ── what a chip opens ───────────────────────────────────────────────────────

describe('the inspector target', () => {
    it('is the resolved entry and its citations', () => {
        const t = inspectorTarget(load(dissolvedFixture()), 'post_altes_rotunda');
        expect([t.resolved, t.entry.title, t.citations.claims.length])
            .toEqual([true, 'Rotunda, interior', 1]);
    });

    it('is unresolved-with-citers for a dangling ref', () => {
        // The sidebar still opens, and what it says is that this reference names an image the
        // session does not carry — with the objects that cite it. A chip that did nothing would
        // hide the defect at the surface built to show it.
        const t = inspectorTarget(load(danglingImageFixture()), 'post_altes_missing');
        expect([t.resolved, t.entry, t.ref])
            .toEqual([false, null, 'post_altes_missing']);
        expect(t.citations.source_units.map((c) => c.id)).toEqual(['su_9']);
    });

    it('is unresolved-with-nothing for a ref no object cites', () => {
        const t = inspectorTarget(load(dissolvedFixture()), 'post_never_mentioned');
        expect([t.resolved, countCitations(t.citations)]).toEqual([false, 0]);
    });
});

// ── generality ──────────────────────────────────────────────────────────────

describe('generality', () => {
    it('reads a session from another domain with no branch', () => {
        // The board's generality gate. Nothing in this module knows what a building is, and the
        // micrograph session traverses the identical types.
        const session = load(otherDomainFixture());
        const cat = imageCatalogue(session);
        expect(cat.map((e) => e.post_id)).toEqual(['post_weld_a']);
        expect(cat[0].citations.claims.length).toBeGreaterThan(0);
        expect(cat[0].citations.reading_blocks).toEqual([]);
    });

    it('mentions no topic anywhere in the module', () => {
        // WHOLE WORDS. A substring scan flagged this module's own `case folding` as the rehearsal
        // topic `fold` — the same false positive a `requests.` scan hit in 002B — and a scan that
        // cries wolf gets narrowed until it catches nothing. The boundary keeps `folds` a topic
        // and `folding` a word.
        const src = fs.readFileSync(path.join(HERE, 'imageInspector.js'), 'utf8');
        for (const topic of ['altes', 'museum', 'rotunda', 'weld', 'buddha', 'sculpture', 'fold']) {
            const hit = new RegExp(`\\b${topic}s?\\b`, 'i').test(src);
            expect([topic, hit]).toEqual([topic, false]);
        }
    });

    it('and the scan can still see one', () => {
        // The negative control. Without it the assertion above passes just as happily against a
        // regex that matches nothing at all.
        const planted = 'the rotunda is a centre the facade never announces';
        const hits = ['altes', 'museum', 'rotunda', 'weld', 'buddha', 'sculpture', 'fold']
            .filter((t) => new RegExp(`\\b${t}s?\\b`, 'i').test(planted));
        expect(hits).toEqual(['rotunda']);
    });
});

// ── the index itself ────────────────────────────────────────────────────────

describe('the citation index', () => {
    it('is built once and keyed by ref', () => {
        const index = citationIndex(load(dissolvedFixture()));
        expect([...index.keys()].sort()).toEqual(['post_altes_front', 'post_altes_rotunda']);
    });

    it('skips an empty ref rather than keying on one', () => {
        const f = dissolvedFixture();
        f.graph.source_units[0].image_refs = ['', null, 'post_altes_front'];
        const index = citationIndex(load(f));
        expect([...index.keys()]).not.toContain('');
        expect(index.get('post_altes_front').source_units.map((c) => c.id)).toContain('su_1');
    });

    it('survives a graph missing every citation surface', () => {
        const index = citationIndex(normalizeSession({ session_id: 'x', graph: {} }));
        expect(index.size).toBe(0);
        expect(imageCatalogue(normalizeSession({ session_id: 'x', graph: {} }))).toEqual([]);
    });

    it('counts the completed fixture\'s claims against the images they name', () => {
        const cat = imageCatalogue(load(completedFixture()));
        const total = cat.reduce((n, e) => n + e.citations.claims.length, 0);
        // Every claim names at least one image, and two name both — so the sum over images
        // exceeds the claim count. That is the correct arithmetic for a per-image panel, and
        // asserting it here stops anyone "fixing" it into a de-duplicated total.
        expect(total).toBeGreaterThan(load(completedFixture()).graph.claims.length);
    });
});
