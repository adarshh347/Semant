import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import RevisionCard from './RevisionCard';
import PassageGenealogy from './PassageGenealogy';
import DeclarationDiff from './DeclarationDiff';

/**
 * Semant Writer · W8 — revision at the surface (gate step 8).
 *
 * The backend cannot mutate a version and cannot put a polish instruction in a prompt. This
 * pins the surface's half of the same discipline, which is mostly a set of ABSENCES: no
 * "improve", no "try again but better", no restore-this-version button. A surface can
 * reintroduce exactly what the loop forbids, and here it would do it by being helpful.
 */

const DIFF = (over = {}) => ({
  operators_added: [],
  operators_removed: [],
  operators_reversioned: [],
  intents_added: [],
  intents_removed: [],
  intents_changed: [],
  ...over,
});

const VERSION = (over = {}) => ({
  id: 'ver_1',
  version: 1,
  text: 'The latch gave before she had decided to push it.',
  revised_from: '',
  declaration_diff: DIFF(),
  in_response_to: {},
  loop_outcome: null,
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

// ══ the declaration diff — the WHY ══════════════════════════════════════════

describe('the declaration diff', () => {
  it('names what the author changed in their own terms', async () => {
    await mount(<DeclarationDiff diff={DIFF({
      operators_added: ['threshold'],
      intents_changed: [{ key: 'avoid', from: 'melodrama', to: 'summary' }],
    })} />);

    const text = byTestId('declaration-diff').textContent;
    expect(text).toContain('/threshold');
    expect(text).toContain('// avoid');
    expect(text).toContain('melodrama');
    expect(text).toContain('summary');
  });

  it('reports a re-versioned operator as an edit, not a swap', async () => {
    await mount(<DeclarationDiff diff={DIFF({
      operators_reversioned: [{ name: 'restraint', from: 1, to: 2 }],
    })} />);

    const text = byTestId('declaration-diff').textContent;
    expect(text).toContain('v1 → v2');
    expect(text).toContain('you edited the operator itself');
  });

  it('says plainly when nothing declared changed', async () => {
    // Silence here would read as a component that failed to load.
    await mount(<DeclarationDiff diff={DIFF()} />);
    expect(byTestId('declaration-diff-empty').textContent)
      .toContain('Nothing you declared changed');
  });
});

// ══ the revise card ════════════════════════════════════════════════════════

describe('the revision card', () => {
  const PROPOSAL = { id: 'psg_2', text: 'The latch gave. She did not go in.' };

  const card = (over = {}) => (
    <RevisionCard
      lineageId="lin_1"
      currentVersion={1}
      currentText="The latch gave before she had decided to push it."
      proposal={PROPOSAL}
      diff={DIFF({ intents_added: ['goal'] })}
      onAccept={vi.fn()}
      onDismiss={vi.fn()}
      {...over}
    />
  );

  it('shows the declaration diff and both versions', async () => {
    await mount(card());
    expect(byTestId('declaration-diff').textContent).toContain('// goal');
    expect(byTestId('revision-current-text').textContent).toContain('had decided to push it');
    expect(byTestId('revision-proposed-text').textContent).toContain('She did not go in');
  });

  it('says the manuscript has not changed', async () => {
    await mount(card());
    expect(byTestId('revision-not-applied').textContent).toContain('Nothing has changed');
    expect(byTestId('revision-not-applied').textContent).toContain('still what the book says');
  });

  it('offers no way to improve, polish or retry', async () => {
    // The absence IS the feature. Each of these hands the model a standard the author
    // never declared.
    await mount(card());
    const labels = buttonLabels();
    for (const forbidden of ['improve', 'polish', 'tighten', 'better', 'enhance',
      'try again', 'regenerate', 'rewrite', 'fix']) {
      expect(labels.some((l) => l.includes(forbidden))).toBe(false);
    }
    expect(labels).toHaveLength(2);
  });

  it('accepting names it as the next version, not as a replacement', async () => {
    const onAccept = vi.fn().mockResolvedValue(undefined);
    await mount(card({ onAccept }));

    expect(byTestId('revision-accept').textContent).toContain('Make this v2');
    expect(byTestId('revision-dismiss').textContent).toContain('Keep v1');
    expect(container.textContent).toContain('it does not overwrite');

    await act(async () => { byTestId('revision-accept').click(); });
    expect(onAccept).toHaveBeenCalledWith(expect.objectContaining({
      passageId: 'psg_2', lineageId: 'lin_1',
    }));
  });

  it('dismissing keeps the current version', async () => {
    const onDismiss = vi.fn().mockResolvedValue(undefined);
    await mount(card({ onDismiss }));
    await act(async () => { byTestId('revision-dismiss').click(); });
    expect(onDismiss).toHaveBeenCalledWith('psg_2');
  });

  it('surfaces a refused accept instead of swallowing it', async () => {
    const onAccept = vi.fn().mockRejectedValue(new Error('a decision is made once'));
    await mount(card({ onAccept }));
    await act(async () => { byTestId('revision-accept').click(); });
    expect(container.querySelector('.writer-revision__error').textContent)
      .toContain('a decision is made once');
  });

  it('shows which alignment flag it answers, when it answers one', async () => {
    await mount(card({ answering: { flag_id: 'flg_1', element: 'intent:avoid' } }));
    expect(byTestId('revision-answering').textContent).toContain('intent:avoid');
  });
});

// ══ the genealogy ══════════════════════════════════════════════════════════

describe('the genealogy view', () => {
  const HISTORY = [
    VERSION(),
    VERSION({
      id: 'ver_2',
      version: 2,
      text: 'The latch gave. She did not go in.',
      revised_from: 'lin_1@v1',
      declaration_diff: DIFF({ intents_added: ['goal'] }),
    }),
  ];

  it('lists every version, oldest first, marking the current one', async () => {
    await mount(<PassageGenealogy versions={HISTORY} currentVersion={2} />);
    const numbers = allByTestId('version-number').map((n) => n.textContent);
    expect(numbers).toEqual(['v1', 'v2']);
    expect(byTestId('version-current').textContent).toContain('current');
    expect(container.textContent).toContain('superseded — kept');
  });

  it('leads each version with what changed, not with the prose', async () => {
    await mount(<PassageGenealogy versions={HISTORY} currentVersion={2} />);
    expect(byTestId('declaration-diff').textContent).toContain('// goal');
    expect(byTestId('version-parent').textContent).toContain('lin_1@v1');
    // the prose is behind a disclosure — it is the consequence, not the explanation
    expect(byTestId('version-text')).toBeNull();
  });

  it('offers no restore, revert or delete', async () => {
    // Restoring would move the pointer with no authoring act behind it.
    await mount(<PassageGenealogy versions={HISTORY} currentVersion={2} />);
    const labels = buttonLabels();
    for (const forbidden of ['restore', 'revert', 'roll back', 'undo', 'delete', 'remove']) {
      expect(labels.some((l) => l.includes(forbidden))).toBe(false);
    }
    expect(container.textContent).toContain('declare it again and render');
  });

  it('a version can be read but not edited', async () => {
    await mount(<PassageGenealogy versions={HISTORY} currentVersion={2} />);
    await act(async () => { allByTestId('version-peek')[0].click(); });
    expect(byTestId('version-text').textContent).toContain('had decided to push it');
    expect(container.querySelector('textarea')).toBeNull();
    expect(container.querySelector('[contenteditable="true"]')).toBeNull();
  });

  it('shows a cleared divergence', async () => {
    await mount(<PassageGenealogy versions={[HISTORY[0], VERSION({
      id: 'ver_2',
      version: 2,
      revised_from: 'lin_1@v1',
      in_response_to: { flag_id: 'flg_1', element: 'intent:avoid' },
      loop_outcome: { outcome: 'cleared', element: 'intent:avoid' },
    })]} currentVersion={2} />);

    expect(byTestId('version-flag-link').textContent).toContain('intent:avoid');
    expect(byTestId('version-loop-outcome').textContent).toContain('cleared');
  });

  it('shows a divergence that SURVIVED the revision just as plainly', async () => {
    // A loop that displayed only its successes would teach the author that revision
    // always works.
    await mount(<PassageGenealogy versions={[HISTORY[0], VERSION({
      id: 'ver_2',
      version: 2,
      revised_from: 'lin_1@v1',
      in_response_to: { flag_id: 'flg_1', element: 'intent:avoid' },
      loop_outcome: { outcome: 'still_present', element: 'intent:avoid' },
    })]} currentVersion={2} />);

    expect(byTestId('version-loop-outcome').textContent)
      .toContain('still there afterwards');
  });

  it('renders nothing at all when there is no history', async () => {
    await mount(<PassageGenealogy versions={[]} />);
    expect(byTestId('genealogy')).toBeNull();
  });
});
