import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import OperatorLibrary from './OperatorLibrary';
import { writerService } from '../writerService';

/**
 * Semant Writer · W5 — the library panel, mounted.
 *
 * The backend suite owns the semantics. This owns what the surface implies: that an import
 * reads as a COPY with its own version and a recorded lineage, that a newer library version
 * is shown as AVAILABLE rather than applied, and that this panel has no route to the canon.
 */

const AUTHOR = 'adarsh';

const LIBRARY = (entries) => ({ author: AUTHOR, entries });

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

async function mount({ entries = [], operators = [], author = AUTHOR } = {}) {
  vi.spyOn(writerService, 'library').mockResolvedValue(LIBRARY(entries));
  vi.spyOn(writerService, 'listOperators').mockResolvedValue(operators);
  await act(async () => {
    root.render(<OperatorLibrary projectId="ms_b" author={author} />);
  });
}

const byTestId = (id) => container.querySelector(`[data-testid="${id}"]`);
const allByTestId = (id) => [...container.querySelectorAll(`[data-testid="${id}"]`)];

describe('OperatorLibrary', () => {
  it('says so when the manuscript has not declared an author', async () => {
    await mount({ author: '' });
    expect(byTestId('library-no-author').textContent).toContain("one author");
  });

  it('offers Promote for something defined here but not in the library', async () => {
    await mount({ operators: [{ name: 'threshold', version: 2 }] });
    expect(byTestId('promote-button')).not.toBeNull();
    expect(byTestId('import-button')).toBeNull();
  });

  it('offers Import for something in the library but not here', async () => {
    await mount({ entries: [{ name: 'threshold', version: 1 }] });
    expect(byTestId('import-button')).not.toBeNull();
    expect(byTestId('promote-button')).toBeNull();
  });

  it('shows an imported copy as a COPY — its own version, and where it came from', async () => {
    await mount({
      entries: [{ name: 'threshold', version: 1 }],
      operators: [{ name: 'threshold', version: 3, library_ref: { version: 1 } }],
    });
    const row = byTestId('library-row').textContent;
    expect(row).toContain('here v3');            // this book's own version
    expect(row).toContain('library v1');
    expect(byTestId('library-lineage').textContent).toContain('taken from v1');
  });

  it('says a newer version is AVAILABLE, never that it was applied', async () => {
    await mount({
      entries: [{ name: 'threshold', version: 4 }],
      operators: [{ name: 'threshold', version: 1, library_ref: { version: 2 } }],
    });
    expect(byTestId('library-behind').textContent).toContain('available');
    expect(byTestId('pull-button')).not.toBeNull();
  });

  it('offers no Pull when the copy is already at the library version', async () => {
    await mount({
      entries: [{ name: 'threshold', version: 2 }],
      operators: [{ name: 'threshold', version: 5, library_ref: { version: 2 } }],
    });
    expect(byTestId('library-behind')).toBeNull();
    expect(byTestId('pull-button')).toBeNull();
  });

  it('promotes on the explicit action', async () => {
    const promote = vi.spyOn(writerService, 'promoteToLibrary').mockResolvedValue({});
    await mount({ operators: [{ name: 'threshold', version: 1 }] });
    await act(async () => { byTestId('promote-button').click(); });
    expect(promote).toHaveBeenCalledWith('ms_b', AUTHOR, 'threshold');
  });

  it('pulls only when asked', async () => {
    const pull = vi.spyOn(writerService, 'pullFromLibrary').mockResolvedValue({});
    await mount({
      entries: [{ name: 'threshold', version: 3 }],
      operators: [{ name: 'threshold', version: 1, library_ref: { version: 1 } }],
    });
    expect(pull).not.toHaveBeenCalled();
    await act(async () => { byTestId('pull-button').click(); });
    expect(pull).toHaveBeenCalledWith('ms_b', AUTHOR, 'threshold');
  });

  it('says plainly that an import is a copy', async () => {
    await mount({ entries: [{ name: 'threshold', version: 1 }] });
    expect(container.textContent).toContain('an import is a copy');
  });

  it('has no route to the canon', async () => {
    const accept = vi.spyOn(writerService, 'accept');
    const run = vi.spyOn(writerService, 'run');
    await mount({ operators: [{ name: 'threshold', version: 1 }] });
    expect(accept).not.toHaveBeenCalled();
    expect(run).not.toHaveBeenCalled();
  });

  it('surfaces a server refusal rather than swallowing it', async () => {
    vi.spyOn(writerService, 'promoteToLibrary')
      .mockRejectedValue(new Error('cannot promote `hush`: it refers to `threshold`'));
    await mount({ operators: [{ name: 'hush', version: 1 }] });
    await act(async () => { byTestId('promote-button').click(); });
    expect(byTestId('library-error').textContent).toContain('it refers to `threshold`');
  });
});
