import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import WriterEditor from './WriterEditor';
import { writerService } from './writerService';
import { exportManuscriptText, toManuscriptBlocks } from './schema/manuscriptExport';

/**
 * Semant Writer · W2 — the invariants AT THE SURFACE, and the §7 gate.
 *
 * `schema/manuscriptExport.test.js` pins the document model. This pins the view over it,
 * because a surface can reintroduce exactly what the loop forbids: auto-accepting, swallowing
 * a refusal into a spinner, or letting orchestration onto the page.
 *
 * The W1 loop is stubbed at `writerService` — this suite is about what the EDITOR does with a
 * render outcome, not about rendering (W1's backend suite and the live proof own that). What
 * is NOT stubbed is the schema: every export assertion runs through the real serializer.
 */

const OPERATORS = [
  { id: 'op_1', name: 'threshold', version: 1, definition: 'a crossing noticed late' },
  { id: 'op_2', name: 'interiority', version: 2, definition: 'what the body knows first' },
];

const LEAK_TOKEN = 'ZEBRAFISH-ORCHESTRATION-TOKEN';
const AVOID_TOKEN = 'PELICAN-AVOID-TOKEN';

const RENDERED = {
  line: 4,
  directive_index: 0,
  directive: '/ threshold',
  operators: ['threshold'],
  orchestration: { goal: LEAK_TOKEN, avoid: AVOID_TOKEN },
  status: 'ok',
  text: 'The latch gave before she had decided to push it.\nShe waited.',
  refusal: '',
  provenance: {
    operators: [{ name: 'threshold', version: 1 }],
    intents: [{ key: 'goal', value: LEAK_TOKEN }],
    model: 'openai/gpt-oss-120b',
  },
  diagnostics: [],
  passage_id: 'psg_1',
};

const REFUSED = {
  line: 5,
  directive_index: 0,
  directive: '/ threshold',
  operators: ['threshold'],
  orchestration: { voice: 'like Tolstoy' },
  status: 'refused',
  text: '',
  refusal:
    '`// voice: like Tolstoy` names something whose meaning lives in my priors, not in '
    + 'your ontology. I cannot check it against your book.\n\n'
    + '    #create tolstoy_voice: <the qualities, in your words>\n',
  provenance: {},
  diagnostics: [],
  passage_id: null,
};

let container, root, editor, exported;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
  editor = null;
  exported = '';
  vi.spyOn(writerService, 'listOperators').mockResolvedValue(OPERATORS);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function mount(props = {}) {
  await act(async () => {
    root.render(
      <WriterEditor
        projectId="ms_1"
        manuscriptId="ms_1"
        sceneId="sc_1"
        onExportChange={(t) => { exported = t; }}
        onEditorReady={(e) => { editor = e; }}
        {...props}
      />,
    );
  });
}

/** Seed the document directly — typed notation is covered by `writerDoc.test.js`. */
async function seed(content) {
  await act(async () => {
    editor.commands.setContent({ type: 'doc', content });
  });
}

const orch = (key, value) => ({ type: 'orchestration', attrs: { key, value, known: true } });
const directiveNode = (operators, argument = '') => ({
  type: 'paragraph',
  content: [{ type: 'directive', attrs: { operators, argument, versions: null } }],
});

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const allByTestId = (id) => [...container.querySelectorAll(`[data-testid="${id}"]`)];
const buttonWithText = (text) =>
  [...container.querySelectorAll('button')].find((b) => b.textContent.trim() === text);

/** The document's export, through the real serializer. */
const exportNow = () => exportManuscriptText(editor.state.doc);

async function renderBlock(results) {
  vi.spyOn(writerService, 'run').mockResolvedValue({ results, proposals: [], diagnostics: [] });
  await act(async () => { byTestId('render-button').click(); });
}

// ══ the surface exists ═══════════════════════════════════════════════════════

describe('WriterEditor — the surface', () => {
  it('mounts a prose surface with render and focus affordances', async () => {
    await mount();
    expect(byTestId('writer-prose')).not.toBeNull();
    expect(byTestId('render-button')).not.toBeNull();
    expect(byTestId('focus-toggle')).not.toBeNull();
  });

  it('focus mode is a real toggle', async () => {
    await mount();
    expect(container.querySelector('.writer-editor--focus')).toBeNull();
    await act(async () => { byTestId('focus-toggle').click(); });
    expect(container.querySelector('.writer-editor--focus')).not.toBeNull();
    expect(byTestId('focus-toggle').getAttribute('aria-pressed')).toBe('true');
  });

  it('will not call the loop for a block with no directive', async () => {
    const run = vi.spyOn(writerService, 'run');
    await mount();
    await act(async () => { byTestId('render-button').click(); });
    expect(run).not.toHaveBeenCalled();
    expect(byTestId('editor-error').textContent).toContain('needs at least one');
  });

  it('sends the block to the EXISTING loop as DSL text, not as a parsed structure', async () => {
    await mount();
    await seed([orch('goal', 'she arrives'), directiveNode(['threshold'], 'the door')]);
    await renderBlock([]);
    expect(writerService.run).toHaveBeenCalledWith('ms_1', {
      text: '// goal: she arrives\n/ threshold(the door)',
      manuscriptId: 'ms_1',
      sceneId: 'sc_1',
      onlyDirectives: [0],
    });
  });
});

// ══ W3 §1 — block scope at the surface ══════════════════════════════════════

describe('block scope', () => {
  const RENDERED_AT = (i, passageId) => ({
    ...RENDERED, directive_index: i, passage_id: passageId,
  });

  it('the default Render asks only for directives that are not yet accepted', async () => {
    vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();
    await seed([directiveNode(['threshold']), directiveNode(['interiority'])]);

    await renderBlock([RENDERED_AT(0, 'psg_1'), RENDERED_AT(1, 'psg_2')]);
    expect(writerService.run.mock.calls[0][1].onlyDirectives).toEqual([0, 1]);

    // accept the FIRST card only
    await act(async () => { allByTestId('accept-button')[0].click(); });

    await renderBlock([RENDERED_AT(1, 'psg_3')]);
    // the accepted directive is not asked for again
    expect(writerService.run.mock.calls.at(-1)[1].onlyDirectives).toEqual([1]);
  });

  it('a skipped result produces no card', async () => {
    await mount();
    await seed([directiveNode(['threshold']), directiveNode(['interiority'])]);
    await renderBlock([
      { ...RENDERED, directive_index: 0, status: 'skipped', text: '', passage_id: null },
      RENDERED_AT(1, 'psg_2'),
    ]);
    expect(allByTestId('quarantine-card')).toHaveLength(1);
    expect(byTestId('editor-status').textContent).toContain('already accepted');
  });

  it('Render all re-runs the whole block, satisfied directives included', async () => {
    vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED_AT(0, 'psg_1')]);
    await act(async () => { byTestId('accept-button').click(); });

    vi.spyOn(writerService, 'run').mockResolvedValue({ results: [], proposals: [], diagnostics: [] });
    await act(async () => { byTestId('render-all-button').click(); });
    // null means "the whole block" — the explicit re-run-everything action
    expect(writerService.run.mock.calls.at(-1)[1].onlyDirectives).toBeNull();
  });

  it('a satisfied directive offers an explicit re-render, and nothing re-renders on its own',
    async () => {
      vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
      await mount();
      await seed([directiveNode(['threshold'])]);
      await renderBlock([RENDERED_AT(0, 'psg_1')]);

      expect(byTestId('rerender-button')).toBeNull();   // pending: nothing to re-render
      await act(async () => { byTestId('accept-button').click(); });
      expect(byTestId('rerender-button')).not.toBeNull();

      vi.spyOn(writerService, 'run').mockResolvedValue({ results: [], proposals: [], diagnostics: [] });
      await act(async () => { byTestId('rerender-button').click(); });
      expect(writerService.run.mock.calls.at(-1)[1].onlyDirectives).toEqual([0]);
    });

  it('says so rather than rendering when every directive is already accepted', async () => {
    vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED_AT(0, 'psg_1')]);
    await act(async () => { byTestId('accept-button').click(); });

    const runs = writerService.run.mock.calls.length;
    await act(async () => { byTestId('render-button').click(); });
    expect(writerService.run.mock.calls.length).toBe(runs);   // no pointless call
    expect(byTestId('editor-error').textContent).toContain('already accepted');
  });
});

// ══ typed notation becomes a node — ANYWHERE in the document ════════════════

describe('notation conversion', () => {
  /** Put the caret at the end of the paragraph whose text matches, then convert. */
  async function convertLineContaining(fragment) {
    let pos = null;
    editor.state.doc.descendants((node, p) => {
      if (node.type.name === 'paragraph' && node.textContent.includes(fragment)) {
        pos = p + node.nodeSize - 1;
        return false;
      }
      return true;
    });
    await act(async () => {
      editor.commands.setTextSelection(pos);
      editor.commands.convertNotationLine();
    });
  }

  const typedLine = (text) => ({ type: 'paragraph', content: [{ type: 'text', text }] });

  it('converts a `/` line that is the LAST node', async () => {
    await mount();
    await seed([typedLine('/ threshold')]);
    await convertLineContaining('/ threshold');
    expect(byTestId('directive-chip')).not.toBeNull();
  });

  it('converts a `/` line in the MIDDLE of the document', async () => {
    // REGRESSION. The first implementation ended its chain with `createParagraphNear()`,
    // which fails when the line is not last — and because a TipTap chain is atomic, the
    // whole conversion silently rolled back and Enter split the line instead, leaving
    // `/ interiority` in the manuscript as plain text that only looked like a directive.
    // Every test typed at the end of the document, so nothing caught it.
    await mount();
    await seed([
      typedLine('/ interiority'),
      { type: 'paragraph', content: [{ type: 'text', text: 'The hallway fell away.' }] },
    ]);
    await convertLineContaining('/ interiority');

    expect(byTestId('directive-chip')).not.toBeNull();
    // and the line is GONE as text — not merely joined by a chip
    expect(JSON.stringify(editor.getJSON())).not.toContain('/ interiority');
    // the prose after it is untouched
    expect(exportNow()).toContain('The hallway fell away.');
  });

  it('converts a `//` line in the middle of the document', async () => {
    await mount();
    await seed([
      typedLine('// goal: she arrives'),
      { type: 'paragraph', content: [{ type: 'text', text: 'The hallway fell away.' }] },
    ]);
    await convertLineContaining('// goal');

    expect(byTestId('orchestration-node')).not.toBeNull();
    expect(exportNow()).not.toContain('she arrives');
    expect(exportNow()).toContain('The hallway fell away.');
  });

  it('leaves ordinary prose alone, so Enter still breaks a paragraph', async () => {
    await mount();
    await seed([typedLine('She waited by the door.')]);
    let handled;
    await act(async () => {
      editor.commands.setTextSelection(editor.state.doc.content.size - 1);
      handled = editor.commands.convertNotationLine();
    });
    expect(handled).toBe(false);          // falls through to the default Enter
    expect(byTestId('directive-chip')).toBeNull();
    expect(exportNow()).toContain('She waited by the door.');
  });

  it('does not convert a line where notation ran into prose', async () => {
    // `/ interiorityThe hallway…` is not a directive, and guessing that it was one would
    // silently drop the author's sentence.
    await mount();
    await seed([typedLine('/ interiorityThe hallway fell away.')]);
    let handled;
    await act(async () => {
      editor.commands.setTextSelection(editor.state.doc.content.size - 1);
      handled = editor.commands.convertNotationLine();
    });
    expect(handled).toBe(false);
    expect(byTestId('directive-chip')).toBeNull();
  });
});

// ══ the `/` ÷ `//` distinction, visible ══════════════════════════════════════

describe('the two layers are distinct on screen', () => {
  it('renders `//` in the orchestration register and `/` as an operator chip', async () => {
    await mount();
    await seed([orch('goal', 'she arrives'), directiveNode(['threshold'])]);

    expect(byTestId('orchestration-node')).not.toBeNull();
    expect(byTestId('directive-chip')).not.toBeNull();
    // and they are not the same element type — one is a block, one sits inline
    expect(byTestId('orchestration-node').className).toContain('writer-orchestration');
    expect(byTestId('directive-chip').className).toContain('writer-directive');
  });

  it('an operator chip shows its version, and flags an undefined operator', async () => {
    await mount();
    await seed([directiveNode(['threshold']), directiveNode(['ekstasis'])]);

    const chips = allByTestId('directive-chip');
    expect(chips[0].textContent).toContain('threshold');
    expect(chips[0].textContent).toContain('v1');
    // an operator the author never defined says so before the render refuses
    expect(chips[1].textContent).toContain('undefined');
    expect(chips[1].className).toContain('writer-directive--undefined');
  });

  it('clicking a chip inspects the operator definition', async () => {
    await mount();
    await seed([directiveNode(['interiority'])]);
    await act(async () => {
      byTestId('directive-chip').querySelector('.writer-directive__op').click();
    });
    const inspector = byTestId('operator-inspector');
    expect(inspector.textContent).toContain('what the body knows first');
    expect(inspector.textContent).toContain('v2');
  });
});

// ══ I1 — propose / commit ════════════════════════════════════════════════════

describe('I1 — nothing enters the manuscript without Accept', () => {
  it('a render lands as a quarantined card and the export does not move', async () => {
    await mount();
    await seed([orch('goal', LEAK_TOKEN), directiveNode(['threshold'])]);
    const before = exportNow();

    await renderBlock([RENDERED]);

    expect(byTestId('quarantine-card')).not.toBeNull();
    expect(byTestId('quarantine-label').textContent).toBe('quarantined');
    expect(byTestId('quarantine-prose').textContent).toContain('The latch gave');

    // the proposal is on screen and NOT in the manuscript
    expect(exportNow()).toBe(before);
    expect(exportNow()).not.toContain('The latch gave');
  });

  it('Accept routes through the W1 gate before the document changes', async () => {
    const accept = vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED]);

    expect(accept).not.toHaveBeenCalled();          // no auto-commit
    await act(async () => { byTestId('accept-button').click(); });

    expect(accept).toHaveBeenCalledWith('psg_1', 'sc_1');
    expect(exportNow()).toContain('The latch gave before she had decided to push it.');
    expect(byTestId('quarantine-card')).toBeNull(); // the card became prose
  });

  it('a failed Accept leaves the card standing and the manuscript untouched', async () => {
    // e.g. the gate refusing a passage that would leak orchestration into canon
    vi.spyOn(writerService, 'accept').mockRejectedValue(
      new Error('refusing to commit: orchestration would reach the manuscript'),
    );
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED]);

    await act(async () => { byTestId('accept-button').click(); });

    expect(byTestId('quarantine-card')).not.toBeNull();
    expect(container.textContent).toContain('orchestration would reach the manuscript');
    expect(exportNow()).not.toContain('The latch gave');
  });

  it('accepted prose keeps the two-tier cadence', async () => {
    vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED]);
    await act(async () => { byTestId('accept-button').click(); });

    // the render's single newline is the INNER tier — a soft break inside one beat
    expect(exportNow()).toBe(
      'The latch gave before she had decided to push it.\nShe waited.',
    );
  });
});

// ══ I2 — refusal is an answer ════════════════════════════════════════════════

describe('I2 — a refusal is a result, with its reason', () => {
  it('renders a refusal card with the reason and NO prose card', async () => {
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([REFUSED]);

    const card = byTestId('refusal-card');
    expect(card).not.toBeNull();
    expect(byTestId('refusal-reason').textContent).toContain('lives in my priors');
    // never filler prose, never an empty result, never a spinner
    expect(byTestId('quarantine-card')).toBeNull();
    expect(byTestId('quarantine-prose')).toBeNull();
    expect(byTestId('accept-button')).toBeNull();
  });

  it('a refusal is not an error banner', async () => {
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([REFUSED]);
    expect(byTestId('editor-error')).toBeNull();
  });

  it('a style-by-reference refusal carries the #create on-ramp inline', async () => {
    const create = vi.spyOn(writerService, 'createOperator').mockResolvedValue({});
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([REFUSED]);

    const onramp = byTestId('create-onramp');
    expect(onramp).not.toBeNull();
    expect(onramp.textContent).toContain('tolstoy_voice');

    // the on-ramp is one action from the refusal, not a context switch
    await act(async () => { buttonWithText('Define tolstoy_voice in my own words').click(); });
    const textarea = container.querySelector('#define-tolstoy_voice');
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value',
      ).set;
      setter.call(textarea, 'a cold remove; the narrator knows less than the reader');
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => { buttonWithText('Define it').click(); });

    expect(create).toHaveBeenCalledWith('ms_1', {
      name: 'tolstoy_voice',
      definition: 'a cold remove; the narrator knows less than the reader',
    });
  });

  it('the refusal never contributes to the manuscript', async () => {
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([REFUSED]);
    expect(exportNow()).not.toContain('Tolstoy');
    expect(exportNow()).not.toContain('priors');
  });
});

// ══ I3 — dismiss leaves no trace ═════════════════════════════════════════════

describe('I3 — dismissing costs the canon nothing', () => {
  it('removes the card and leaves nothing behind', async () => {
    const dismiss = vi.spyOn(writerService, 'dismiss').mockResolvedValue({});
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED]);

    await act(async () => { byTestId('dismiss-button').click(); });

    expect(dismiss).toHaveBeenCalledWith('psg_1');
    expect(byTestId('quarantine-card')).toBeNull();
    expect(exportNow()).not.toContain('The latch gave');
    // no placeholder, no struck-through remnant, nothing in the document at all
    expect(JSON.stringify(editor.getJSON())).not.toContain('The latch gave');
  });
});

// ══ I4 — provenance ══════════════════════════════════════════════════════════

describe('I4 — provenance is on the card and survives the commit', () => {
  it('the quarantined card shows operators with versions and the active intents', async () => {
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED]);

    const prov = byTestId('quarantine-provenance').textContent;
    expect(prov).toContain('threshold');
    expect(prov).toContain('v1');
    expect(prov).toContain('goal');
    expect(prov).toContain('openai/gpt-oss-120b');
  });

  it('a paragraph split off an accepted span does NOT inherit its provenance', async () => {
    // REGRESSION. ProseMirror copies attrs when Enter splits a textblock, so pressing
    // Enter at the end of an accepted passage gave the new empty paragraph the accepted
    // one's provenance and block id. Anything the author typed there would then export as
    // `user_confirmed`, crediting operators that never touched it.
    await mount();
    await seed([{
      type: 'paragraph',
      attrs: {
        provenance: { operators: [{ name: 'threshold', version: 1 }], passageId: 'psg_1' },
        blockId: 'blk_1',
      },
      content: [{ type: 'text', text: 'Across it before she knew.' }],
    }]);

    await act(async () => {
      editor.commands.setTextSelection(editor.state.doc.content.size - 1);
      editor.commands.splitBlock();
      editor.commands.insertContent('She had been standing there an hour.');
    });

    const paras = editor.getJSON().content;
    expect(paras[1].attrs.provenance).toBeNull();
    expect(paras[1].attrs.blockId).toBeNull();

    // and it exports as the author's own, not as an accepted render
    const blocks = toManuscriptBlocks(editor.state.doc);
    expect(blocks[0].origin).toBe('user_confirmed');
    expect(blocks[1].origin).toBe('human');
    expect(blocks[1].provenance).toBeNull();
  });

  it('an accepted span is still inspectable in the document', async () => {
    vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED]);
    await act(async () => { byTestId('accept-button').click(); });

    const committed = editor.getJSON().content.filter(
      (n) => n.type === 'paragraph' && n.attrs?.provenance,
    );
    expect(committed.length).toBeGreaterThan(0);
    expect(committed[0].attrs.provenance.operators[0]).toEqual({ name: 'threshold', version: 1 });
    expect(committed[0].attrs.provenance.passageId).toBe('psg_1');
    expect(committed[0].attrs.blockId).toBe('blk_9');
  });
});

// ══ I6 — the mandatory export-leak assertion, end to end ═════════════════════

describe('I6 — `//` never reaches the manuscript', () => {
  it('THE GATE: stage, render, accept, export — the orchestration token is absent', async () => {
    vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();

    // 2. a block: two `//` lines, then a `/` directive
    await seed([
      orch('goal', LEAK_TOKEN),
      orch('avoid', AVOID_TOKEN),
      directiveNode(['threshold']),
    ]);
    expect(allByTestId('orchestration-node')).toHaveLength(2);

    // 3. render → quarantined card, nothing in the manuscript
    await renderBlock([RENDERED]);
    expect(byTestId('quarantine-card')).not.toBeNull();
    expect(exportNow()).toBe('');

    // 4. accept → prose flows in, and the staging does NOT
    await act(async () => { byTestId('accept-button').click(); });

    const text = exportNow();
    expect(text).toContain('The latch gave before she had decided to push it.');
    expect(text).not.toContain(LEAK_TOKEN);
    expect(text).not.toContain(AVOID_TOKEN);
    expect(text).not.toContain('//');
    expect(text).not.toContain('goal:');

    // the orchestration is still on screen for the author — it simply is not the page
    expect(allByTestId('orchestration-node')).toHaveLength(2);
    expect(container.textContent).toContain(LEAK_TOKEN);
  });

  it('a directive chip never prints into the manuscript either', async () => {
    vi.spyOn(writerService, 'accept').mockResolvedValue({ block_id: 'blk_9' });
    await mount();
    await seed([directiveNode(['threshold'], 'the door')]);
    await renderBlock([RENDERED]);
    await act(async () => { byTestId('accept-button').click(); });

    expect(exportNow()).not.toContain('threshold');
    expect(exportNow()).not.toContain('the door');
  });
});

// ══ W7 — the reading on a quarantined render ════════════════════════════════

describe('the alignment reading, offered before Accept', () => {
  const READING = (over = {}) => ({
    id: 'rdg_1',
    status: 'flagged',
    detail: '',
    model: 'openai/gpt-oss-120b',
    measured_against: [{ id: 'intent:avoid', declared: 'melodrama' }],
    flags: [{
      id: 'flg_1',
      element: 'intent:avoid',
      element_kind: 'intent',
      operator: null,
      operator_version: null,
      declared: 'melodrama',
      span: 'She waited.',
      divergence: 'this leans on the pause for feeling',
      state: 'open',
    }],
    ...over,
  });

  async function readOn(reading) {
    vi.spyOn(writerService, 'readAlignment').mockResolvedValue(reading);
    await mount();
    await seed([directiveNode(['threshold'])]);
    await renderBlock([RENDERED]);
    await act(async () => { byTestId('read-alignment').click(); });
  }

  it('reads the quarantined passage against its own provenance, and writes nothing', async () => {
    await readOn(READING());

    expect(writerService.readAlignment).toHaveBeenCalledWith('ms_1', expect.objectContaining({
      text: RENDERED.text,
      provenance: RENDERED.provenance,
      passageId: 'psg_1',
    }));
    expect(byTestId('reading-flag')).not.toBeNull();
    expect(byTestId('flag-element').textContent).toContain('melodrama');
    // still quarantined, still not canon
    expect(byTestId('quarantine-card')).not.toBeNull();
    expect(exportNow()).toBe('');
  });

  it('a refused decision is shown to the author rather than swallowed', async () => {
    // `decide` is once-only: a second one comes back 400. A rejection with no catch would
    // leave the flag reading as open with nothing said.
    await readOn(READING());
    vi.spyOn(writerService, 'decideFlag').mockRejectedValue(
      new Error('flag flg_1 is already dismissed — a decision is made once'),
    );

    await act(async () => { byTestId('flag-dismissed').click(); });

    expect(container.querySelector('.writer-card__error').textContent)
      .toContain('a decision is made once');
    expect(exportNow()).toBe('');
  });

  it('offers no way to apply a flag to the prose', async () => {
    await readOn(READING());
    const labels = [...container.querySelectorAll('button')]
      .map((b) => b.textContent.trim().toLowerCase());
    for (const forbidden of ['rewrite', 'fix', 'apply', 'replace', 'improve']) {
      expect(labels.some((l) => l.includes(forbidden))).toBe(false);
    }
  });
});
