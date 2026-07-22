import { describe, it, expect } from 'vitest';
import { mentionsFromBlocks } from './perceptMentions.js';

/**
 * The one test in this slice that needs a DOM, and it needs one for a real
 * reason: `mentionsFromBlocks` reads stored markup with a regex, but the markup
 * it will meet in production was SERIALISED BY A BROWSER, not written by hand.
 * A browser is free to reorder attributes, change quoting, and drop the space
 * before `>`. Testing the parser only against hand-written strings would prove
 * it works on the one shape I happened to type.
 *
 * So: build the chip as an element, let the DOM serialise it, and parse THAT.
 */
const chipEl = (attrs) => {
    const span = document.createElement('span');
    span.setAttribute('data-region-ref', '');
    for (const [k, v] of Object.entries(attrs)) span.setAttribute(k, v);
    span.textContent = 'the upper head';
    const p = document.createElement('p');
    p.appendChild(document.createTextNode('before '));
    p.appendChild(span);
    p.appendChild(document.createTextNode(' after'));
    return p.outerHTML;
};

describe('mention reconstruction survives real browser-serialised markup', () => {
    it('parses a percept chip the DOM produced, not one I hand-wrote', () => {
        const html = chipEl({
            'data-inline-type': 'percept',
            'data-ref-kind': 'percept',
            'data-region-ids': 'gnd_1,gnd_2',
            'data-percept-id': 'pctx_abc',
            'data-mention-id': 'men_pctx_abc_blk1_ic_1',
            'data-label': 'the upper head',
            class: 'ref-chip ref-chip--percept',
        });
        // Sanity: this really is DOM output, not a literal.
        expect(html).toContain('<span');
        expect(html).toContain('data-region-ref');

        const [men] = mentionsFromBlocks([{ id: 'blk1', content: html }]);
        expect(men.perceptId).toBe('pctx_abc');
        expect(men.id).toBe('men_pctx_abc_blk1_ic_1');
        expect(men.refKind).toBe('percept');
        expect(men.label).toBe('the upper head');
        expect(men.blockId).toBe('blk1');
    });

    it('is not confused by other spans, nested markup, or two chips in one block', () => {
        const decoy = '<span class="not-a-chip" data-label="decoy">x</span>';
        const html = decoy
            + chipEl({ 'data-region-ids': 'gnd_1', 'data-percept-id': 'pctx_a' })
            + '<strong>bold</strong>'
            + chipEl({ 'data-region-ids': 'gnd_2', 'data-percept-id': 'pctx_b' });
        const out = mentionsFromBlocks([{ id: 'blk1', content: html }]);
        expect(out.map((m) => m.perceptId)).toEqual(['pctx_a', 'pctx_b']);
    });

    it('back-compat: a DOM-serialised part chip still yields one edge per region', () => {
        const html = chipEl({ 'data-inline-type': 'part', 'data-region-ids': 'region_1,region_2' });
        const out = mentionsFromBlocks([{ id: 'blk1', content: html }]);
        expect(out.map((m) => m.regionId)).toEqual(['region_1', 'region_2']);
        expect(out.every((m) => m.perceptId === null)).toBe(true);
    });
});
