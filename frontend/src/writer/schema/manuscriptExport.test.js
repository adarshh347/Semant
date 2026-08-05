import { describe, it, expect } from 'vitest';
import { getSchema } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';

import { WRITER_NODES } from './writerSchema';
import {
  ManuscriptExport,
  exportsToManuscript,
  toManuscriptBlocks,
  exportManuscriptText,
} from './manuscriptExport';

/**
 * Semant Writer · W2 — the export rule, at the document model.
 *
 * THIS FILE IS THE MANDATORY CI GUARD (W2 directive §4, I6). It is deliberately headless:
 * `getSchema()` builds the real schema with no DOM and no editor, so the guarantee is
 * tested against the document MODEL rather than against what a mounted component happened
 * to render. A UI test can pass while the model leaks; this cannot.
 *
 * What it pins:
 *   I6 — `//` orchestration never reaches the manuscript export;
 *   I1 — an unaccepted render never reaches it either;
 *   and the property that makes both durable: the rule is FAIL-CLOSED, so a node type that
 *   never declares `manuscriptExport` is excluded rather than included.
 */

const schema = getSchema([
  StarterKit.configure({ paragraph: false }),
  ManuscriptExport,
  ...WRITER_NODES,
]);

const doc = (content) => schema.nodeFromJSON({ type: 'doc', content });
const para = (text, attrs = {}) => ({
  type: 'paragraph',
  attrs,
  content: text ? [{ type: 'text', text }] : [],
});

const LEAK_TOKEN = 'ZEBRAFISH-ORCHESTRATION-TOKEN';
const UNACCEPTED = 'PROSE-THAT-WAS-NEVER-ACCEPTED';

describe('the manuscript export rule', () => {
  it('declares the rule on the schema, defaulting to false', () => {
    expect(exportsToManuscript(schema.nodes.paragraph)).toBe(true);
    expect(exportsToManuscript(schema.nodes.orchestration)).toBe(false);
    expect(exportsToManuscript(schema.nodes.directive)).toBe(false);
    expect(exportsToManuscript(schema.nodes.quarantinedPassage)).toBe(false);
  });

  it('is FAIL-CLOSED — a node that never declared the field does not export', () => {
    // `heading` comes from StarterKit and knows nothing about this module. It must be
    // excluded by DEFAULT, not by anyone remembering to add it to a deny-list. This is the
    // property that keeps the guarantee true when W3 adds nodes.
    expect(schema.nodes.heading.spec.manuscriptExport).toBe(false);
    expect(exportsToManuscript(schema.nodes.heading)).toBe(false);
    expect(exportsToManuscript(undefined)).toBe(false);
  });

  // ── I6 ──────────────────────────────────────────────────────────────────
  it('I6 — orchestration text is absent from the export', () => {
    const d = doc([
      { type: 'orchestration', attrs: { key: 'goal', value: LEAK_TOKEN, known: true } },
      { type: 'orchestration', attrs: { key: 'avoid', value: `${LEAK_TOKEN}-AVOID`, known: true } },
      para('She crossed before she had decided to.'),
    ]);

    const text = exportManuscriptText(d);
    expect(text).not.toContain(LEAK_TOKEN);
    expect(text).toContain('She crossed before she had decided to.');

    // and not merely absent from the text — absent from the BLOCKS, in every field
    expect(JSON.stringify(toManuscriptBlocks(d))).not.toContain(LEAK_TOKEN);
  });

  it('I6 — a `//` note with no key still cannot reach the page', () => {
    const d = doc([
      { type: 'orchestration', attrs: { key: '', value: LEAK_TOKEN, known: false } },
      para('The latch gave.'),
    ]);
    expect(exportManuscriptText(d)).not.toContain(LEAK_TOKEN);
  });

  // ── I1 ──────────────────────────────────────────────────────────────────
  it('I1 — an unaccepted render is absent from the export', () => {
    const d = doc([
      para('Committed prose.'),
      {
        type: 'quarantinedPassage',
        attrs: { passageId: 'psg_1', status: 'quarantined', text: UNACCEPTED },
      },
    ]);

    const text = exportManuscriptText(d);
    expect(text).not.toContain(UNACCEPTED);
    expect(text).toBe('Committed prose.');
    expect(toManuscriptBlocks(d)).toHaveLength(1);
  });

  it('I1 — a refusal leaves no prose in the export either', () => {
    const d = doc([
      {
        type: 'quarantinedPassage',
        attrs: {
          passageId: null,
          status: 'refused',
          text: '',
          refusal: `cannot render: ${UNACCEPTED}`,
        },
      },
    ]);
    expect(exportManuscriptText(d)).toBe('');
    expect(toManuscriptBlocks(d)).toHaveLength(0);
  });

  // ── directives are notation, not prose ──────────────────────────────────
  it('an inline directive chip does not print into the prose', () => {
    const d = doc([
      {
        type: 'paragraph',
        content: [
          { type: 'text', text: 'She waited. ' },
          { type: 'directive', attrs: { operators: ['threshold'], argument: 'the door' } },
          { type: 'text', text: ' Then she moved.' },
        ],
      },
    ]);
    const text = exportManuscriptText(d);
    expect(text).toContain('She waited.');
    expect(text).toContain('Then she moved.');
    expect(text).not.toContain('threshold');
    expect(text).not.toContain('/');
  });

  // ── the two-tier cadence round-trips ────────────────────────────────────
  it('the two tiers of the cadence survive into the ledger blocks', () => {
    const d = doc([
      {
        type: 'paragraph',
        content: [
          { type: 'text', text: 'The latch gave.' },
          { type: 'hardBreak' },
          { type: 'text', text: 'She waited.' },
        ],
      },
      para('A beat later, the hall.'),
    ]);

    const blocks = toManuscriptBlocks(d);
    // inner tier — a soft break inside one beat
    expect(blocks[0].content).toBe('<p>The latch gave.<br>She waited.</p>');
    // outer tier — a separate block
    expect(blocks).toHaveLength(2);
    expect(blocks[1].content).toBe('<p>A beat later, the hall.</p>');
  });

  // ── I4 ──────────────────────────────────────────────────────────────────
  it('I4 — an accepted span carries its provenance into the block', () => {
    const provenance = {
      operators: [{ name: 'threshold', version: 1 }],
      intents: [{ key: 'goal', value: 'cross it' }],
      passageId: 'psg_1',
    };
    const d = doc([para('Across it before she knew.', { provenance, blockId: 'blk_1' })]);

    const [block] = toManuscriptBlocks(d);
    expect(block.provenance.operators[0]).toEqual({ name: 'threshold', version: 1 });
    expect(block.provenance.passageId).toBe('psg_1');
    expect(block.id).toBe('blk_1');
    // the model proposed, the author accepted — never `model_suggested`, which means
    // still quarantined, and nothing quarantined is in this list by construction
    expect(block.origin).toBe('user_confirmed');
  });

  it('prose the author typed themselves is `human`, not `user_confirmed`', () => {
    const [block] = toManuscriptBlocks(doc([para('She had been standing there an hour.')]));
    expect(block.origin).toBe('human');
    expect(block.provenance).toBeNull();
  });

  it('escapes HTML so prose cannot inject markup into the ledger', () => {
    const [block] = toManuscriptBlocks(doc([para('a < b & c > d')]));
    expect(block.content).toBe('<p>a &lt; b &amp; c &gt; d</p>');
  });
});
