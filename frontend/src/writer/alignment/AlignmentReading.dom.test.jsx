import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import AlignmentReading from './AlignmentReading';

/**
 * Semant Writer · W7 — the reading, on screen.
 *
 * The backend drops any flag that cannot cite a declared element. This pins the surface's
 * half of the same discipline: that the citation is SHOWN (a flag whose grounding were
 * hidden reads exactly like generic craft advice), that there is NO REWRITE AFFORDANCE
 * anywhere, and that silence renders as an honest result rather than an empty container.
 */

const FLAG = (over = {}) => ({
  id: 'flg_1',
  element: 'intent:avoid',
  element_kind: 'intent',
  operator: null,
  operator_version: null,
  declared: 'melodrama',
  span: 'Her heart shattered into a thousand pieces',
  divergence: 'this is the melodrama you said to avoid',
  state: 'open',
  ...over,
});

const READING = (over = {}) => ({
  id: 'rdg_1',
  status: 'flagged',
  detail: '',
  model: 'openai/gpt-oss-120b',
  measured_against: [
    { id: 'intent:avoid', declared: 'melodrama' },
    { id: 'operator:restraint:intent', declared: 'say less than the moment wants' },
  ],
  flags: [FLAG()],
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

async function mount(props) {
  await act(async () => { root.render(<AlignmentReading {...props} />); });
}

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const allByTestId = (id) => [...container.querySelectorAll(`[data-testid="${id}"]`)];
const buttonLabels = () =>
  [...container.querySelectorAll('button')].map((b) => b.textContent.trim().toLowerCase());

describe('a flag shows what it rests on', () => {
  it('names the declared element and quotes the author own words', async () => {
    await mount({ reading: READING() });
    const cited = byTestId('flag-element').textContent;
    expect(cited).toContain('// avoid');
    expect(cited).toContain('melodrama');
  });

  it('frames an operator intent as what the author said it should DO', async () => {
    await mount({
      reading: READING({
        flags: [FLAG({
          element: 'operator:restraint:intent',
          element_kind: 'operator_intent',
          operator: 'restraint',
          operator_version: 2,
          declared: 'say less than the moment wants',
        })],
      }),
    });
    const cited = byTestId('flag-element').textContent;
    expect(cited).toContain('/restraint should do');
    expect(cited).toContain('say less than the moment wants');
    expect(cited).toContain('v2');
  });

  it('frames a negative example as what the author said it is NOT', async () => {
    await mount({
      reading: READING({
        flags: [FLAG({
          element: 'operator:restraint:not:0',
          element_kind: 'operator_negative_example',
          operator: 'restraint',
          declared: 'Her heart shattered into a thousand pieces.',
        })],
      }),
    });
    expect(byTestId('flag-element').textContent).toContain('is NOT');
  });

  it('shows the quoted span from the prose', async () => {
    await mount({ reading: READING() });
    expect(container.textContent).toContain('Her heart shattered into a thousand pieces');
  });
});

describe('there is no rewrite anywhere', () => {
  it('offers no fix, rewrite, apply or replace affordance', async () => {
    await mount({ reading: READING() });
    const labels = buttonLabels().join(' ');
    for (const forbidden of ['fix', 'rewrite', 'apply', 'replace', 'correct', 'improve']) {
      expect(labels).not.toContain(forbidden);
    }
  });

  it('says the forward action is the author re-rendering it themselves', async () => {
    await mount({ reading: READING() });
    expect(container.textContent).toContain('re-render it yourself');
  });

  it('offers only a judgement on each flag', async () => {
    await mount({ reading: READING() });
    expect(byTestId('flag-acted')).not.toBeNull();
    expect(byTestId('flag-dismissed')).not.toBeNull();
  });
});

describe('silence renders as a result', () => {
  it('says aligned in as many words', async () => {
    await mount({ reading: READING({ status: 'aligned', flags: [] }) });
    expect(byTestId('reading-aligned').textContent).toContain('nothing here diverges');
    expect(byTestId('reading-flag')).toBeNull();
  });

  it('says there was little declared intent, rather than inventing advice', async () => {
    await mount({
      reading: READING({
        status: 'thin', flags: [],
        detail: 'Little declared intent to check against: this passage’s operators say '
          + 'what they are but not what they should do.',
      }),
    });
    expect(byTestId('reading-thin').textContent).toContain('Little declared intent');
    expect(byTestId('reading-flag')).toBeNull();
  });

  it('says an unprovenanced span is not its to critique', async () => {
    await mount({
      reading: READING({
        status: 'no_provenance', flags: [],
        detail: 'You wrote this yourself — there is no declared standard to read it against.',
      }),
    });
    expect(byTestId('reading-no-provenance').textContent).toContain('no declared standard');
  });

  it('does NOT report a failed reading as aligned', async () => {
    // could-not-look and looked-and-found-nothing are different answers
    await mount({
      reading: READING({ status: 'unavailable', flags: [], detail: 'GROQ_API_KEY is not configured' }),
    });
    expect(byTestId('reading-unavailable')).not.toBeNull();
    expect(byTestId('reading-aligned')).toBeNull();
  });
});

describe('the reading is itself auditable on screen', () => {
  it('can show what it measured against, and which model read it', async () => {
    await mount({ reading: READING() });
    expect(byTestId('measured-elements')).toBeNull();
    await act(async () => { byTestId('show-measured').click(); });

    const measured = byTestId('measured-elements').textContent;
    expect(measured).toContain('intent:avoid');
    expect(measured).toContain('operator:restraint:intent');
    expect(measured).toContain('openai/gpt-oss-120b');
  });
});

describe('deciding a flag', () => {
  it('reports the author judgement without applying anything', async () => {
    const onDecide = vi.fn().mockResolvedValue(undefined);
    await mount({ reading: READING(), onDecide });
    await act(async () => { byTestId('flag-acted').click(); });
    expect(onDecide).toHaveBeenCalledWith('flg_1', 'acted');
  });

  it('shows a decided flag as decided, with no further action', async () => {
    await mount({ reading: READING({ flags: [FLAG({ state: 'dismissed' })] }) });
    expect(byTestId('flag-decided').textContent).toContain('dismissed');
    expect(byTestId('flag-acted')).toBeNull();
    expect(byTestId('flag-dismissed')).toBeNull();
  });

  it('counts the divergences', async () => {
    await mount({
      reading: READING({ flags: [FLAG(), FLAG({ id: 'flg_2' })] }),
    });
    expect(byTestId('reading-count').textContent).toContain('2 divergences');
    expect(allByTestId('reading-flag')).toHaveLength(2);
  });
});
