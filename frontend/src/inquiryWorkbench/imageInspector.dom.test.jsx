/**
 * INQUIRY WORKBENCH — the image sidebar, on screen.
 *
 * The selector tests prove what the index says. These prove the surface does not soften it: that
 * a zero is printed, that an unresolvable reference opens a panel saying so rather than doing
 * nothing, that the picture never arrives without the sentence saying nothing was checked against
 * it, and that a chip outside a provider is not a control.
 */
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import InquiryWorkbenchPage from './InquiryWorkbenchPage.jsx';
import { createMockInquiryClient } from './inquiryClient.js';
import { createMockCorpusClient } from '../inquiryCorpus/corpusClient.js';
import ArtifactLedger from './ArtifactLedger.jsx';
import {
    ImageInspector, ImageInspectorProvider, ImageRef, ImageAbsences,
} from './ImageInspector.jsx';
import { normalizeSession } from './inquiryContract.js';
import {
    dissolvedFixture, danglingImageFixture, otherDomainFixture, FIXTURE_CORPUS,
} from './inquiryFixtures.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));

let container;
let root;

beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
});

afterEach(async () => {
    await act(async () => { root.unmount(); });
    container.remove();
    vi.restoreAllMocks();
});

const text = () => container.textContent || '';
const $ = (sel) => container.querySelector(sel);
const $$ = (sel) => [...container.querySelectorAll(sel)];
const click = async (el) => { await act(async () => { el.click(); }); };
const load = (f) => normalizeSession(f);

const panel = () => $('[data-image-inspector]');
const surface = (name) => $(`[data-surface="${name}"]`);

/** The sidebar alone — the resolution states should not need a click to reach. */
async function mountPanel(fixture, refId) {
    const session = load(fixture);
    await act(async () => {
        root.render(<ImageInspector session={session} refId={refId} onClose={() => {}} />);
    });
    return session;
}

/** The ledger inside a provider — the click path. */
async function mountLedger(fixture) {
    const session = load(fixture);
    await act(async () => {
        root.render(
            <ImageInspectorProvider session={session}>
                <ArtifactLedger session={session} />
            </ImageInspectorProvider>,
        );
    });
    return session;
}

// ── the click path ──────────────────────────────────────────────────────────

describe('opening a reference', () => {
    it('opens nothing until something is clicked', async () => {
        await mountLedger(dissolvedFixture());
        expect(panel()).toBe(null);
    });

    it('opens the sidebar from the posts row', async () => {
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="posts"] .iw-expand'));
        await click($('[data-image-ref="post_altes_front"]'));
        expect(panel().dataset.imageInspector).toBe('post_altes_front');
    });

    it('opens it from a `rests on` reference inside a provenance panel', async () => {
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="reading_blocks"] .iw-expand'));
        await click($('[data-why-for="rdb_2"]'));
        const chip = $('[data-why-open="rdb_2"] [data-image-ref="post_altes_rotunda"]');
        expect(chip).not.toBe(null);
        await click(chip);
        expect(panel().dataset.imageInspector).toBe('post_altes_rotunda');
    });

    it('says on the chip itself which reference is open', async () => {
        // The panel can be scrolled out of view. Without this the chip is the only thing on
        // screen that could say it, and it said nothing.
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="posts"] .iw-expand'));
        const front = () => $('button[data-image-ref="post_altes_front"]');
        expect(front().getAttribute('aria-pressed')).toBe('false');
        await click(front());
        expect(front().getAttribute('aria-pressed')).toBe('true');
    });

    it('closes when the open reference is clicked again', async () => {
        // It carries `aria-pressed`, so it says it is a toggle. A control that says that and then
        // does not un-press has told a screen reader something untrue about the next click.
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="posts"] .iw-expand'));
        const chip = () => $('button[data-image-ref="post_altes_front"]');
        await click(chip());
        expect(panel()).not.toBe(null);
        expect(chip().getAttribute('title')).toContain('Close');
        await click(chip());
        expect(panel()).toBe(null);
        expect(chip().getAttribute('aria-pressed')).toBe('false');
    });

    it('switches to another reference without closing', async () => {
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="posts"] .iw-expand'));
        await click($('button[data-image-ref="post_altes_front"]'));
        await click($('button[data-image-ref="post_altes_rotunda"]'));
        expect($$('[data-image-inspector]')).toHaveLength(1);
        expect(panel().dataset.imageInspector).toBe('post_altes_rotunda');
    });

    it('closes on the close button and on Escape', async () => {
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="posts"] .iw-expand'));
        await click($('button[data-image-ref="post_altes_front"]'));

        await click($('[data-inspector-close="true"]'));
        expect(panel()).toBe(null);

        await click($('button[data-image-ref="post_altes_front"]'));
        await act(async () => {
            document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
        });
        expect(panel()).toBe(null);
    });

    it('gives focus to the panel and hands it back to the chip', async () => {
        // A sidebar that takes focus and drops it on the body leaves a keyboard reader at the top
        // of the document, several panels from the chip they were reading.
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="posts"] .iw-expand'));
        const chip = $('button[data-image-ref="post_altes_front"]');
        chip.focus();
        await click(chip);
        expect(document.activeElement).toBe(panel());

        await click($('[data-inspector-close="true"]'));
        expect(document.activeElement).toBe($('button[data-image-ref="post_altes_front"]'));
    });

    it('is not a modal: no backdrop, and the workbench behind it stays operable', async () => {
        // The argument being checked is on the other side of the screen. A backdrop would be the
        // visual claim that looking at the picture means leaving the reasoning.
        await mountLedger(dissolvedFixture());
        await click($('[data-artifact="posts"] .iw-expand'));
        await click($('button[data-image-ref="post_altes_front"]'));

        expect(panel().getAttribute('aria-modal')).toBe(null);
        expect($('.iw-backdrop, [data-backdrop]')).toBe(null);

        // A control behind the sidebar still works while it is open.
        await click($('[data-artifact="claims"] .iw-expand'));
        expect($('[data-artifact="claims"] [data-ledger-claim]')).not.toBe(null);
        expect(panel()).not.toBe(null);
    });
});

// ── a chip with nothing behind it ───────────────────────────────────────────

describe('a reference outside a provider', () => {
    it('is a plain token, not a control', async () => {
        // NOT a disabled button — a disabled button is still a button to a screen reader, and
        // this is not a control that happens to be unavailable.
        await act(async () => { root.render(<ImageRef refId="post_x" />); });
        expect($('button')).toBe(null);
        expect($('.iw-imgref.is-inert')).not.toBe(null);
        expect(text()).toContain('post_x');
    });

    it('lets a panel that carries references mount on its own', async () => {
        // Half the components with image references are mounted directly in their own tests. A
        // chip that threw there would make the provider a hidden requirement of every panel.
        const session = load(dissolvedFixture());
        await act(async () => { root.render(<ArtifactLedger session={session} />); });
        await click($('[data-artifact="posts"] .iw-expand'));
        expect(text()).toContain('post_altes_front');
        expect($('button[data-image-ref]')).toBe(null);
    });
});

// ── what the sidebar says ───────────────────────────────────────────────────

describe('the picture and its record', () => {
    it('shows the image, whether it was read, and the fingerprint', async () => {
        await mountPanel(dissolvedFixture(), 'post_altes_front');
        expect($('.iw-inspector-image img').getAttribute('src'))
            .toBe('/fixtures/altes-front.jpg');
        expect($('[data-readable="true"]').textContent).toContain('the run fetched and read it');
        expect(text()).toContain('fingerprint');
    });

    it('says a url was never carried rather than drawing a broken image', async () => {
        // "no url was carried" and "the fetch failed" draw the same browser placeholder and send
        // you to opposite repairs.
        const f = dissolvedFixture();
        f.graph.image_refs[0].image_url = '';
        await mountPanel(f, 'post_altes_front');
        expect($('.iw-inspector-image img')).toBe(null);
        expect($('[data-no-url="true"]').textContent).toContain('nothing to fetch');
    });

    it('distinguishes unread from unrecorded', async () => {
        const unread = dissolvedFixture();
        unread.posts[0].readable = false;
        await mountPanel(unread, 'post_altes_front');
        expect($('[data-readable="false"]').textContent)
            .toContain('written without it');

        await act(async () => { root.unmount(); });
        root = createRoot(container);

        // No posts row at all — nobody declared it, which is not a record saying it was read.
        await mountPanel(otherDomainFixture(), 'post_weld_a');
        expect($('[data-readable="null"]').textContent).toContain('not recorded');
    });

    it('names an image the read ledger never accounted for', async () => {
        const f = dissolvedFixture();
        f.posts = f.posts.filter((p) => p.post_id !== 'post_altes_front');
        await mountPanel(f, 'post_altes_front');
        expect($('[data-not-in-posts="true"]').textContent)
            .toContain('inconsistency upstream');
    });
});

describe('what rests on it', () => {
    it('prints every surface with its count', async () => {
        await mountPanel(dissolvedFixture(), 'post_altes_front');
        expect({
            reading_blocks: surface('reading_blocks').dataset.count,
            source_units: surface('source_units').dataset.count,
            atoms: surface('atoms').dataset.count,
            claims: surface('claims').dataset.count,
        }).toEqual({ reading_blocks: '3', source_units: '3', atoms: '3', claims: '4' });
        expect(panel().dataset.citationCount).toBe('13');
    });

    it('quotes the citing objects rather than only counting them', async () => {
        await mountPanel(dissolvedFixture(), 'post_altes_rotunda');
        expect($('[data-cite-id="rdb_2"]').textContent).toContain('rotunda is a centre');
    });

    it('prints a zero surface as a zero, never as an absence', async () => {
        // "no atom names this picture" and "the atoms have not arrived yet" are the two states
        // this whole workbench exists to keep apart.
        await mountPanel(dissolvedFixture(), 'post_altes_rotunda');
        expect(surface('atoms').dataset.count).toBe('0');
        expect(surface('atoms').className).toContain('is-empty');
        expect(surface('atoms').textContent).toContain('semantic atoms');
    });

    it('says once, where the picture and the claims meet, that nothing was checked', async () => {
        // The most persuasive layout on this surface, one caption away from a lie.
        await mountPanel(dissolvedFixture(), 'post_altes_front');
        const caveat = $('[data-caveat="not-verified"]');
        expect(caveat.textContent).toContain('Nothing below was checked against these pixels');
        expect($$('[data-caveat="not-verified"]')).toHaveLength(1);
    });
});

// ── the two absences, on screen ─────────────────────────────────────────────

describe('an image nothing cited', () => {
    it('says so instead of showing four empty surfaces', async () => {
        await mountPanel(danglingImageFixture(), 'post_altes_rotunda');
        expect(panel().dataset.citationCount).toBe('0');
        expect($('[data-uncited="true"]').textContent)
            .toContain('produced no recorded thought');
    });

    it('does not say so on an image that simply has few citations', async () => {
        await mountPanel(dissolvedFixture(), 'post_altes_rotunda');
        expect($('[data-uncited="true"]')).toBe(null);
    });
});

describe('a reference naming a picture the session does not carry', () => {
    it('opens a panel saying exactly that, with its citers', async () => {
        await mountPanel(danglingImageFixture(), 'post_altes_missing');
        expect(panel().dataset.resolved).toBe('false');
        expect($('[data-unresolved="post_altes_missing"]').textContent)
            .toContain('does not carry');
        expect($('[data-cite-id="su_9"]')).not.toBe(null);
        expect($('[data-cite-id="atm_9"]')).not.toBe(null);
    });

    it('shows no image record for it, because there is none', async () => {
        await mountPanel(danglingImageFixture(), 'post_altes_missing');
        expect($('.iw-inspector-image')).toBe(null);
        expect(text()).not.toContain('fingerprint');
    });

    it('distinguishes a dangling reference from one nothing cites at all', async () => {
        await mountPanel(dissolvedFixture(), 'post_nobody_mentions');
        expect(panel().dataset.resolved).toBe('false');
        expect(text()).toContain('Nothing cites it either');
    });
});

describe('the absences panel', () => {
    it('names both, with the objects responsible', async () => {
        const session = load(danglingImageFixture());
        await act(async () => {
            root.render(
                <ImageInspectorProvider session={session}>
                    <ImageAbsences session={session} />
                </ImageInspectorProvider>,
            );
        });
        expect($('[data-absence="uncited"]').dataset.count).toBe('1');
        expect($('[data-uncited-post="post_altes_rotunda"]')).not.toBe(null);
        expect($('[data-absence="dangling"]').dataset.count).toBe('1');
        expect($('[data-dangling-ref="post_altes_missing"]').textContent)
            .toContain('cited by su_9, atm_9');
    });

    it('renders nothing at all when everything lines up', async () => {
        const session = load(dissolvedFixture());
        await act(async () => { root.render(<ImageAbsences session={session} />); });
        expect(text()).toBe('');
    });
});

// ── the whole page ──────────────────────────────────────────────────────────

const CORPUS_PAGES = [{
    posts: FIXTURE_CORPUS.map((c) => ({
        id: c.post_id,
        photo_url: c.image_url,
        text_blocks: [{ content: c.title }],
        region_annotations: [],
    })),
    total_pages: 1,
    current_page: 1,
}];

/** Mount the real page and drive the real entry form to a started session. */
async function startPage(fixture) {
    const client = createMockInquiryClient({ script: [fixture] });
    await act(async () => {
        root.render(
            <InquiryWorkbenchPage
                client={client}
                corpusClient={createMockCorpusClient({ pages: CORPUS_PAGES })}
            />,
        );
    });
    const box = $('.iw-prompt');
    await act(async () => {
        Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
            .set.call(box, 'why is this centred?');
        box.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await click($('.ic-tile'));
    await click($('.iw-start'));
    await act(async () => {});
}

describe('on the page', () => {
    it('makes the header thumbnails openable', async () => {
        // The thumbnails were the one place a person could already SEE the pictures and the one
        // place they could do nothing with them.
        await startPage(dissolvedFixture());
        const thumb = $('.iw-session-images button[data-image-ref="post_altes_front"]');
        expect(thumb).not.toBe(null);
        expect(thumb.querySelector('img')).not.toBe(null);
        await click(thumb);
        expect(panel().dataset.imageInspector).toBe('post_altes_front');
    });

    it('shows both absences without a single chip being clicked', async () => {
        // The point of the absences being a panel rather than sidebar content.
        await startPage(danglingImageFixture());
        expect($('.iw-image-absences')).not.toBe(null);
        expect($('[data-uncited-post="post_altes_rotunda"]')).not.toBe(null);
        expect($('[data-dangling-ref="post_altes_missing"]')).not.toBe(null);
        expect(panel()).toBe(null);
    });

    it('renders no absences panel on a session whose references line up', async () => {
        await startPage(dissolvedFixture());
        expect($('.iw-image-absences')).toBe(null);
    });

    it('drops the sidebar when the person starts a different inquiry', async () => {
        // The provider wraps the session view only. Spanning the entry screen too would leave a
        // sidebar pointing at a picture from an inquiry no longer on screen.
        await startPage(dissolvedFixture());
        await click($('.iw-session-images button[data-image-ref="post_altes_front"]'));
        expect(panel()).not.toBe(null);
        await click($('.iw-again'));
        expect(panel()).toBe(null);
        expect($('.iw-prompt')).not.toBe(null);
    });

    it('keeps the sidebar open when the session streams an update', async () => {
        // The session is watched. A stage landing three more claims about this image should ADD
        // them, not close the panel out from under someone.
        const before = load(dissolvedFixture());
        const Harness = ({ session }) => (
            <ImageInspectorProvider session={session}>
                <ArtifactLedger session={session} />
            </ImageInspectorProvider>
        );
        await act(async () => { root.render(<Harness session={before} />); });
        await click($('[data-artifact="posts"] .iw-expand'));
        await click($('button[data-image-ref="post_altes_front"]'));
        const was = Number(panel().dataset.citationCount);

        const grown = dissolvedFixture();
        grown.graph.claims.push({
            claim_id: 'clm_new', text: 'a later pass added this',
            claim_kind: 'pattern_or_sequence', status: 'proposed',
            image_scope: ['post_altes_front'], author: 'model',
        });
        await act(async () => { root.render(<Harness session={load(grown)} />); });

        expect(panel().dataset.imageInspector).toBe('post_altes_front');
        expect(Number(panel().dataset.citationCount)).toBe(was + 1);
        expect($('[data-cite-id="clm_new"]')).not.toBe(null);
    });
});

// ── generality ──────────────────────────────────────────────────────────────

describe('generality', () => {
    it('traverses a session from another domain with no branch', async () => {
        await mountPanel(otherDomainFixture(), 'post_weld_a');
        expect(panel().dataset.resolved).toBe('true');
        expect(Number(surface('claims').dataset.count)).toBeGreaterThan(0);
        expect(surface('reading_blocks').dataset.count).toBe('0');
    });

    it('names no topic in the component or its stylesheet rules', () => {
        const src = fs.readFileSync(path.join(HERE, 'ImageInspector.jsx'), 'utf8');
        for (const topic of ['altes', 'museum', 'rotunda', 'weld', 'buddha', 'sculpture', 'fold']) {
            expect([topic, new RegExp(`\\b${topic}s?\\b`, 'i').test(src)]).toEqual([topic, false]);
        }
    });
});

// ── the stylesheet carries none of the meaning ──────────────────────────────

describe('the stylesheet carries none of the meaning', () => {
    const css = () => fs.readFileSync(path.join(HERE, 'inquiryWorkbench.css'), 'utf8');
    const rule = (selector) => {
        const m = css().match(new RegExp(`\\${selector}\\s*\\{([^}]*)\\}`));
        return m ? m[1].replace(/\s+/g, ' ').trim() : null;
    };

    it('gives the inert chip no cursor and no underline, rather than a paler one', () => {
        // An `is-inert` styled as a dimmer button would read as a control that is unavailable.
        expect(rule('.iw-imgref.is-inert')).toContain('cursor: auto');
        expect(rule('.iw-imgref.is-inert')).toContain('border-bottom: 0');
    });

    it('does not let the sidebar acquire a backdrop or a scroll lock', () => {
        expect(css()).not.toMatch(/\.iw-inspector[^{]*\{[^}]*position:\s*fixed[^}]*\}[\s\S]{0,40}backdrop/);
        expect(rule('.iw-inspector')).not.toContain('overflow: hidden');
    });

    it('keeps an empty surface visible', async () => {
        // The ledger's rule, and for the ledger's reason: the count IS the information.
        expect(rule('.iw-inspector-surface.is-empty')).toContain('border-style: dashed');
        expect(rule('.iw-inspector-surface.is-empty')).not.toContain('display: none');
    });

    it('uses editorial tokens and no hard-coded colour', () => {
        const section = css().slice(css().indexOf('/* ── the image inspector'));
        expect(section).not.toMatch(/#[0-9a-f]{3,8}\b/i);
        expect(section).toMatch(/var\(--/);
    });
});
