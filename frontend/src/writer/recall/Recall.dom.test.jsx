import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import RecallPanel from './RecallPanel';
import CitedSpans from './CitedSpans';

/**
 * Semant Writer · W9 — recall at the surface (gate step 8).
 *
 * The backend cannot summarise, because it cannot call a model. This pins the surface's
 * half of the same rule, which is where the violation would actually arrive if it did:
 * a keyword highlight inserted into the author's sentence, a line clamp that adds an
 * ellipsis they did not write, a helpful "you might mean…" filling an empty result, or an
 * "insert into manuscript" button that copies prior prose into the book.
 */

const COLD_ROOM = 'The room had gone cold in the night. She did not light the fire.';
const CADENCED = 'She waited.\nThe latch gave.\n\nShe did not go in.';

const SPAN = (over = {}) => ({
  lineage_id: 'lin_1',
  version: 1,
  passage_id: 'psg_1',
  text: COLD_ROOM,
  score: 3.2,
  provenance: {},
  location: { scene_title: 'The kitchen', chapter_title: 'Chapter one', block_id: 'blk_1' },
  ...over,
});

const RESULT = (over = {}) => ({
  query: 'cold room',
  spans: [SPAN()],
  searched: 12,
  empty_reason: '',
  ...over,
});

let container, root;

beforeEach(() => {
  container = document.createElement('div');
  document.body.appendChild(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root.unmount());
  container.remove();
  vi.restoreAllMocks();
});

async function mount(element) {
  await act(async () => { root.render(element); });
}

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const allByTestId = (id) => [...container.querySelectorAll(`[data-testid="${id}"]`)];
const buttonLabels = () =>
  [...container.querySelectorAll('button')].map((b) => b.textContent.trim().toLowerCase());

async function search(result, { query = 'cold room' } = {}) {
  const onRecall = vi.fn().mockResolvedValue(result);
  await mount(<RecallPanel onRecall={onRecall} onCite={vi.fn()} />);
  const input = byTestId('recall-query');
  await act(async () => {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
      .set.call(input, query);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
  await act(async () => { byTestId('recall-search').click(); });
  return onRecall;
}

// ══ THE VERBATIM RULE, at the surface ══════════════════════════════════════

describe('a recalled span is the author’s own words', () => {
  it('renders the stored text byte for byte', async () => {
    await search(RESULT());
    expect(byTestId('span-text').textContent).toBe(COLD_ROOM);
  });

  it('adds no ellipsis, no clamp, no truncation', async () => {
    const long = Array.from({ length: 40 },
      (_, n) => `She counted the ${n + 1}th stair and did not stop.`).join(' ');
    await search(RESULT({ spans: [SPAN({ text: long })] }));

    expect(byTestId('span-text').textContent).toBe(long);
    expect(byTestId('span-text').textContent).not.toContain('…');
  });

  it('keeps the cadence — line turns are meaning here, not formatting', async () => {
    await search(RESULT({ spans: [SPAN({ text: CADENCED })] }));
    expect(byTestId('span-text').textContent).toBe(CADENCED);
  });

  it('inserts no highlight markup into the author’s sentence', async () => {
    // A <mark> around the query terms is the surface editing the prose.
    await search(RESULT());
    const quote = byTestId('span-text');
    expect(quote.querySelector('mark')).toBeNull();
    expect(quote.querySelector('em')).toBeNull();
    expect(quote.querySelector('strong')).toBeNull();
    expect(quote.innerHTML).toBe(quote.textContent);
  });

  it('shows no summary line among the results', async () => {
    await search(RESULT());
    // Scoped to the RESULTS. The panel's header disclaims summarising in so many words,
    // and the rule is about what appears alongside the author's prose — not about whether
    // the word may be printed at all.
    const results = container.querySelector('.writer-recall__list').textContent.toLowerCase();
    for (const forbidden of ['you established', 'summary', 'in summary', 'so far you',
      'this suggests', 'overview', 'gist']) {
      expect(results).not.toContain(forbidden);
    }
    // and only the author's own sentence sits inside the quotation
    expect(byTestId('span-text').textContent).toBe(COLD_ROOM);
  });

  it('says where the span sits, without describing it', async () => {
    await search(RESULT());
    expect(byTestId('span-location').textContent).toContain('Chapter one');
    expect(byTestId('span-location').textContent).toContain('The kitchen');
    expect(byTestId('span-location').textContent).toContain('v1');
  });
});

// ══ empty is a result ══════════════════════════════════════════════════════

describe('an empty recall', () => {
  it('says so plainly and offers nothing in its place', async () => {
    await search(RESULT({
      spans: [], empty_reason: 'Nothing in your manuscript matches that.',
    }));

    expect(byTestId('recall-empty').textContent)
      .toContain('Nothing in your manuscript matches');
    expect(byTestId('recall-span')).toBeNull();
    const text = container.textContent.toLowerCase();
    for (const forbidden of ['you might', 'perhaps', 'did you mean', 'try instead',
      'suggestion']) {
      expect(text).not.toContain(forbidden);
    }
  });

  it('reports an empty manuscript as its own answer', async () => {
    await search(RESULT({
      spans: [], empty_reason: 'There is no committed prose in this manuscript yet.',
    }));
    expect(byTestId('recall-empty').textContent).toContain('no committed prose');
  });
});

// ══ citing is the author's act ═════════════════════════════════════════════

describe('citing', () => {
  it('marks a span as grounding for the next render', async () => {
    const onCite = vi.fn();
    const onRecall = vi.fn().mockResolvedValue(RESULT());
    await mount(<RecallPanel onRecall={onRecall} onCite={onCite} />);

    const input = byTestId('recall-query');
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
        .set.call(input, 'cold');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => { byTestId('recall-search').click(); });
    await act(async () => { byTestId('span-cite').click(); });

    expect(onCite).toHaveBeenCalledWith(expect.objectContaining({ lineage_id: 'lin_1' }));
  });

  it('shows an already-cited span as citable no more', async () => {
    const onRecall = vi.fn().mockResolvedValue(RESULT());
    await mount(
      <RecallPanel onRecall={onRecall} onCite={vi.fn()} onUncite={vi.fn()}
        cited={[{ lineage_id: 'lin_1', version: 1 }]} />,
    );
    const input = byTestId('recall-query');
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
        .set.call(input, 'cold');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => { byTestId('recall-search').click(); });

    expect(byTestId('span-uncite')).not.toBeNull();
    expect(byTestId('span-cite')).toBeNull();
  });

  it('offers NO way to insert prior prose into the manuscript', async () => {
    // Copying committed prose back into the book would be the model deciding to repeat
    // the author. The absence is the feature.
    await search(RESULT());
    const labels = buttonLabels();
    for (const forbidden of ['insert', 'paste', 'copy', 'add to manuscript', 'use this',
      'apply', 'accept']) {
      expect(labels.some((l) => l.includes(forbidden))).toBe(false);
    }
  });

  it('offers no summarise affordance', async () => {
    await search(RESULT());
    const labels = buttonLabels();
    for (const forbidden of ['summarise', 'summarize', 'summary', 'digest', 'catch me up',
      'what did i establish']) {
      expect(labels.some((l) => l.includes(forbidden))).toBe(false);
    }
  });

  it('passes the historical flag through only when asked', async () => {
    const onRecall = await search(RESULT());
    expect(onRecall).toHaveBeenCalledWith(
      expect.objectContaining({ includeHistorical: false }),
    );
  });

  it('surfaces a failed search instead of swallowing it', async () => {
    const onRecall = vi.fn().mockRejectedValue(new Error('recall is unavailable'));
    await mount(<RecallPanel onRecall={onRecall} />);
    const input = byTestId('recall-query');
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')
        .set.call(input, 'cold');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => { byTestId('recall-search').click(); });

    expect(byTestId('recall-error').textContent).toContain('recall is unavailable');
    expect(byTestId('recall-span')).toBeNull();
  });
});

// ══ the citation strip ═════════════════════════════════════════════════════

describe('the citation strip', () => {
  it('is absent until the author cites something', async () => {
    await mount(<CitedSpans cited={[]} />);
    expect(byTestId('cited-spans')).toBeNull();
  });

  it('names what the next render will stay consistent with', async () => {
    await mount(<CitedSpans cited={[SPAN(), SPAN({ lineage_id: 'lin_2', version: 3 })]} />);
    expect(byTestId('cited-spans').textContent).toContain('Staying consistent with 2');
    expect(allByTestId('cited-span')).toHaveLength(2);
    expect(allByTestId('cited-span')[0].textContent).toContain('The kitchen');
    expect(allByTestId('cited-span')[1].textContent).toContain('v3');
  });

  it('does not repeat the prose beside the composition surface', async () => {
    // Prose sitting inline here is one drag away from being pasted into the book.
    await mount(<CitedSpans cited={[SPAN()]} />);
    expect(byTestId('cited-spans').textContent).not.toContain(COLD_ROOM);
  });

  it('lets the author take a citation back', async () => {
    const onUncite = vi.fn();
    await mount(<CitedSpans cited={[SPAN()]} onUncite={onUncite} />);
    await act(async () => { byTestId('cited-remove').click(); });
    expect(onUncite).toHaveBeenCalledWith(expect.objectContaining({ lineage_id: 'lin_1' }));
  });
});
