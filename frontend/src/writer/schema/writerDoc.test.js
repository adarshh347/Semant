import { describe, it, expect } from 'vitest';
import { getSchema } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';

import { WRITER_NODES } from './writerSchema';
import { ManuscriptExport } from './manuscriptExport';
import { classifyLine, docToBlockText, hasRunnableContent } from './writerDoc';

/**
 * Semant Writer · W2 — the bridge to the W1 DSL.
 *
 * The point of these tests is that the surface does not become a second parser. What the
 * editor sends to `studio.run_block` must be text the EXISTING `dsl.parse_block` reads the
 * same way, with orchestration scope (which is positional) intact.
 */

const schema = getSchema([
  StarterKit.configure({ paragraph: false }),
  ManuscriptExport,
  ...WRITER_NODES,
]);

const doc = (content) => schema.nodeFromJSON({ type: 'doc', content });
const orch = (key, value, known = true) => ({ type: 'orchestration', attrs: { key, value, known } });
const directive = (operators, argument = '') => ({
  type: 'directive',
  attrs: { operators, argument, versions: null },
});

describe('classifyLine — typed notation', () => {
  it('reads a `//` note as orchestration', () => {
    expect(classifyLine('// goal: she arrives')).toEqual({
      node: 'orchestration',
      attrs: { key: 'goal', value: 'she arrives', known: true },
    });
  });

  it('marks an unknown key inert rather than dropping it', () => {
    const out = classifyLine('// mood: gentle');
    expect(out.attrs.key).toBe('mood');
    expect(out.attrs.known).toBe(false);
  });

  it('keeps a bare `//` note off the page even with no key', () => {
    const out = classifyLine('// just thinking aloud');
    expect(out.node).toBe('orchestration');
    expect(out.attrs.known).toBe(false);
  });

  it('reads a `/` line as a directive, with the operator stack and argument', () => {
    expect(classifyLine('/ threshold + interiority(the door)')).toEqual({
      node: 'directive',
      attrs: { operators: ['threshold', 'interiority'], argument: 'the door', versions: null },
    });
  });

  it('never reads `//` as a directive — the wall, at the point of entry', () => {
    expect(classifyLine('// avoid: threshold').node).toBe('orchestration');
  });

  it('leaves prose alone, including prose containing a URL', () => {
    expect(classifyLine('She read it at http://example.com/threshold.')).toBeNull();
    expect(classifyLine('The latch gave.')).toBeNull();
  });
});

describe('docToBlockText — the document as a W1 block', () => {
  it('serializes orchestration and directives in document order', () => {
    const text = docToBlockText(doc([
      orch('goal', 'she arrives at the door'),
      orch('voice', 'close third, past tense'),
      { type: 'paragraph', content: [directive(['threshold'], 'the door')] },
      { type: 'paragraph', content: [directive(['threshold', 'interiority'])] },
    ]));

    expect(text).toBe(
      '// goal: she arrives at the door\n'
      + '// voice: close third, past tense\n'
      + '/ threshold(the door)\n'
      + '/ threshold + interiority',
    );
  });

  it('preserves position, because orchestration scope is positional', () => {
    // A note AFTER a directive must not appear before it — that would re-stage the block.
    const text = docToBlockText(doc([
      { type: 'paragraph', content: [directive(['alpha'])] },
      orch('voice', 'first person'),
      { type: 'paragraph', content: [directive(['beta'])] },
    ]));
    expect(text.split('\n')).toEqual(['/ alpha', '// voice: first person', '/ beta']);
  });

  it('keeps prose and directives apart when they share a paragraph', () => {
    const text = docToBlockText(doc([
      {
        type: 'paragraph',
        content: [
          { type: 'text', text: 'She waited. ' },
          directive(['threshold']),
          { type: 'text', text: ' Then the hall.' },
        ],
      },
    ]));
    expect(text.split('\n')).toEqual(['She waited.', '/ threshold', 'Then the hall.']);
  });

  it('does NOT feed an unaccepted render back in as input', () => {
    // Uncommitted prose conditioning the next render would let the model treat something
    // the author never accepted as if it were canon.
    const text = docToBlockText(doc([
      { type: 'paragraph', content: [directive(['threshold'])] },
      {
        type: 'quarantinedPassage',
        attrs: { passageId: 'psg_1', status: 'quarantined', text: 'UNACCEPTED PROSE' },
      },
    ]));
    expect(text).not.toContain('UNACCEPTED PROSE');
    expect(text).toBe('/ threshold');
  });
});

describe('hasRunnableContent', () => {
  it('is false for prose alone and true once a directive exists', () => {
    expect(hasRunnableContent(doc([{ type: 'paragraph', content: [{ type: 'text', text: 'hi' }] }])))
      .toBe(false);
    expect(hasRunnableContent(doc([orch('goal', 'x')]))).toBe(false);
    expect(hasRunnableContent(doc([{ type: 'paragraph', content: [directive(['threshold'])] }])))
      .toBe(true);
  });
});
