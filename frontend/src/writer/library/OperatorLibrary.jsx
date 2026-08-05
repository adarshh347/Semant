import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { writerService } from '../writerService';
import './OperatorLibrary.css';

/**
 * Semant Writer · W5 — the portable ontology, on screen.
 *
 * The author's language above any one book: promote what you defined here, import what you
 * defined elsewhere, publish improvements up, pull newer versions down.
 *
 * THE ONE THING THIS SURFACE MUST NOT IMPLY. An import is a LINKED COPY, not a live link.
 * Editing an imported operator here changes neither the library nor any other book, and the
 * panel says so in as many words — because a surface that made the library look like shared
 * state would set the author up to expect exactly the spooky action W5 was designed to
 * refuse. Each row shows the copy's own version beside the library version it came from, so
 * "mine, taken from v2" is visible rather than inferred.
 *
 * NO ROUTE TO THE CANON. Promote, import, publish and pull are ontology operations. This
 * component has no accept, no scene, no block — same discipline as the W3 graph and the W4
 * suggestion feed.
 */
export default function OperatorLibrary({ projectId, author, onChanged = null, onClose = null }) {
  const [entries, setEntries] = useState([]);
  const [operators, setOperators] = useState([]);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    try {
      const [lib, ops] = await Promise.all([
        author ? writerService.library(author) : Promise.resolve({ entries: [] }),
        writerService.listOperators(projectId),
      ]);
      setEntries(lib.entries ?? []);
      setOperators(ops ?? []);
      setError('');
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [projectId, author]);

  useEffect(() => { load(); }, [load]);

  const act = async (label, fn, message) => {
    setBusy(label);
    setError('');
    try {
      await fn();
      setStatus(message);
      await load();
      if (onChanged) onChanged();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  };

  const inProject = useMemo(
    () => Object.fromEntries(operators.map((o) => [o.name, o])), [operators],
  );
  const inLibrary = useMemo(
    () => Object.fromEntries(entries.map((e) => [e.name, e])), [entries],
  );

  // Every name the author can act on, from either side.
  const rows = useMemo(() => {
    const names = [...new Set([...Object.keys(inProject), ...Object.keys(inLibrary)])].sort();
    return names.map((name) => {
      const project = inProject[name] ?? null;
      const entry = inLibrary[name] ?? null;
      const ref = project?.library_ref ?? null;
      return {
        name,
        project,
        entry,
        ref,
        // A newer library version exists than the one this copy was taken from. Available,
        // never applied — it waits for the author to pull it.
        behind: Boolean(entry && ref && entry.version > ref.version),
      };
    });
  }, [inProject, inLibrary]);

  if (!author) {
    return (
      <section className="writer-library" data-testid="operator-library">
        <header className="writer-library__bar"><strong>Your library</strong>
          {onClose && <button type="button" onClick={onClose}>Close</button>}
        </header>
        <p className="writer-library__empty" data-testid="library-no-author">
          This manuscript has not said whose it is. A library is one author&rsquo;s language —
          set the manuscript&rsquo;s author and it will appear here.
        </p>
      </section>
    );
  }

  return (
    <section className="writer-library" data-testid="operator-library">
      <header className="writer-library__bar">
        <strong>Your library</strong>
        <span className="writer-library__author">{author}</span>
        <span className="writer-library__help">
          carried between your books — an import is a copy, so editing it here changes
          nothing anywhere else
        </span>
        {onClose && <button type="button" onClick={onClose}>Close</button>}
      </header>

      {error && <p className="writer-library__error" data-testid="library-error">{error}</p>}
      {status && !error && <p className="writer-library__status">{status}</p>}
      {loading && <p className="writer-library__empty">Loading…</p>}

      {!loading && rows.length === 0 && (
        <p className="writer-library__empty" data-testid="library-empty">
          Nothing yet. Promote an operator you want to use in another book and it will live
          here.
        </p>
      )}

      <ul className="writer-library__rows">
        {rows.map((row) => (
          <li key={row.name} className="writer-library__row" data-testid="library-row">
            <div className="writer-library__id">
              <code>/{row.name}</code>
              {row.project && (
                <span className="writer-library__badge" title="this project's copy">
                  here v{row.project.version}
                </span>
              )}
              {row.entry && (
                <span className="writer-library__badge writer-library__badge--lib"
                      title="the library version">
                  library v{row.entry.version}
                </span>
              )}
              {row.ref && (
                <span className="writer-library__from" data-testid="library-lineage">
                  taken from v{row.ref.version}
                </span>
              )}
              {row.behind && (
                <span className="writer-library__behind" data-testid="library-behind">
                  a newer version is available
                </span>
              )}
            </div>

            <div className="writer-library__actions">
              {row.project && !row.entry && (
                <button
                  type="button"
                  data-testid="promote-button"
                  disabled={Boolean(busy)}
                  onClick={() => act(row.name,
                    () => writerService.promoteToLibrary(projectId, author, row.name),
                    `/${row.name} is in your library`)}
                >
                  Promote
                </button>
              )}
              {row.entry && !row.project && (
                <button
                  type="button"
                  data-testid="import-button"
                  disabled={Boolean(busy)}
                  onClick={() => act(row.name,
                    () => writerService.importFromLibrary(projectId, author, row.name),
                    `/${row.name} is in this book now — your copy, to edit as you like`)}
                >
                  Import
                </button>
              )}
              {row.project && row.entry && (
                <button
                  type="button"
                  data-testid="publish-button"
                  disabled={Boolean(busy)}
                  onClick={() => act(row.name,
                    () => writerService.publishToLibrary(projectId, author, row.name),
                    `/${row.name} published — your other books keep what they have until you pull`)}
                >
                  Publish
                </button>
              )}
              {row.behind && (
                <button
                  type="button"
                  data-testid="pull-button"
                  disabled={Boolean(busy)}
                  onClick={() => act(row.name,
                    () => writerService.pullFromLibrary(projectId, author, row.name),
                    `/${row.name} updated from the library`)}
                >
                  Pull
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
