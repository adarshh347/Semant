import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';

import { writerService } from './writerService';
import { writerExtensions } from './schema/writerExtensions';
import { docToBlockText, hasRunnableContent } from './schema/writerDoc';
import { exportManuscriptText, toManuscriptBlocks } from './schema/manuscriptExport';
import { WriterActionsContext } from './views/WriterActions';
import './WriterEditor.css';

/**
 * Semant Writer · W2 — the literary editor.
 *
 * A VIEW OVER THE LEDGER, NOT A WRITER TO IT. Every judgement this surface appears to make
 * is actually W1's: `writerService.run` parses and renders, `writerService.accept` is the
 * one gate into canon, the ontology wall lives in `render.py`. Nothing here produces prose
 * and nothing here writes to a scene. If a future change adds a code path in this file that
 * commits text, that is the second door the W2 directive forbids — the canon has one owner.
 *
 * WHAT THIS FILE IS RESPONSIBLE FOR, and it is only this: turning the document into the
 * block text W1 already parses, putting the results back into the document as the right
 * kind of node, and making the difference between staging, proposal and canon impossible to
 * miss. The invariants are guaranteed by the schema (`manuscriptExport`), not by this file's
 * good behaviour.
 */

/** Split rendered prose into paragraph nodes, keeping the two tiers of the cadence.
 *
 *  A blank line is the OUTER tier (a beat break → a new paragraph); a single newline is the
 *  INNER tier (a line turn inside the beat → a `hardBreak`). Getting this right at Accept is
 *  what makes accepted prose sit in the manuscript with the same rhythm the author sees in
 *  the card, rather than collapsing into uniform blocks.
 */
function proseToParagraphs(text, attrs) {
  return String(text || '')
    .split(/\n{2,}/)
    .map((beat) => beat.trim())
    .filter(Boolean)
    .map((beat) => {
      const content = [];
      beat.split('\n').forEach((line, i) => {
        if (i > 0) content.push({ type: 'hardBreak' });
        if (line) content.push({ type: 'text', text: line });
      });
      return { type: 'paragraph', attrs, content };
    });
}

export default function WriterEditor({
  projectId,
  manuscriptId = '',
  sceneId = '',
  initialContent = null,
  onExportChange = null,
  // Handed the TipTap instance once it exists. A seam for a parent that needs to seed or
  // read the document (the W2 gate test drives the editor through this rather than
  // reaching into component internals).
  onEditorReady = null,
}) {
  const [operators, setOperators] = useState([]);
  const [inspecting, setInspecting] = useState(null);
  const [focusMode, setFocusMode] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const editor = useEditor({
    extensions: useMemo(() => writerExtensions(), []),
    content: initialContent ?? { type: 'doc', content: [{ type: 'paragraph' }] },
    editorProps: {
      attributes: {
        class: 'writer-prose',
        'data-testid': 'writer-prose',
        spellcheck: 'false',
      },
    },
  });

  const loadOperators = useCallback(async () => {
    if (!projectId) return;
    try {
      setOperators(await writerService.listOperators(projectId));
    } catch (e) {
      setError(e.message);
    }
  }, [projectId]);

  useEffect(() => { loadOperators(); }, [loadOperators]);

  useEffect(() => {
    if (editor && onEditorReady) onEditorReady(editor);
  }, [editor, onEditorReady]);

  // The export is derived from the document, so any consumer (and the gate test) reads the
  // same serializer the manuscript would.
  useEffect(() => {
    if (!editor || !onExportChange) return undefined;
    const emit = () => onExportChange(exportManuscriptText(editor.state.doc));
    emit();
    editor.on('update', emit);
    return () => { editor.off('update', emit); };
  }, [editor, onExportChange]);

  // ── Render: hand the block to W1, put the outcomes back inline ─────────────

  const run = async () => {
    if (!editor || busy) return;
    const text = docToBlockText(editor.state.doc);
    if (!hasRunnableContent(editor.state.doc)) {
      setError('Nothing to render — a block needs at least one `/` directive.');
      return;
    }
    setBusy(true);
    setError('');
    setStatus('Rendering…');
    try {
      const out = await writerService.run(projectId, { text, manuscriptId, sceneId });
      insertResults(out.results ?? []);
      const refused = (out.results ?? []).filter((r) => r.status === 'refused').length;
      setStatus(
        `${(out.results ?? []).length - refused} rendered, ${refused} refused — nothing committed.`,
      );
    } catch (e) {
      setError(e.message);
      setStatus('');
    } finally {
      setBusy(false);
    }
  };

  /**
   * Place each outcome directly after the block holding the directive that produced it.
   *
   * `run_block` returns results in directive order and this walks directives in document
   * order, so the pairing is positional and 1:1. Inserted back-to-front so that an earlier
   * insertion cannot shift a later position out from under us.
   */
  const insertResults = (results) => {
    if (!editor || !results.length) return;

    const directives = [];
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'directive') directives.push({ node, pos });
      return true;
    });

    const placements = results.map((result, i) => {
      const d = directives[i];
      const after = d
        ? editor.state.doc.resolve(d.pos).after(1)
        : editor.state.doc.content.size;
      return { after, result };
    });

    placements
      .sort((a, b) => b.after - a.after)
      .forEach(({ after, result }) => {
        editor
          .chain()
          .insertContentAt(after, {
            type: 'quarantinedPassage',
            attrs: {
              passageId: result.passage_id,
              status: result.status === 'ok' ? 'quarantined' : result.status,
              text: result.text || '',
              refusal: result.refusal || '',
              provenance: result.provenance || null,
              orchestration: result.orchestration || null,
              diagnostics: result.diagnostics || [],
              directive: result.directive || '',
            },
          })
          .run();
      });
  };

  // ── Accept: the W1 gate first, the document second ─────────────────────────

  const onAccept = useCallback(
    async (passageId, pos, node) => {
      // The gate runs BEFORE the document changes. If Accept throws (a leak caught at the
      // door, a missing scene, an already-decided passage) the card stays exactly as it is
      // and the manuscript never moved.
      const result = await writerService.accept(passageId, sceneId);

      const provenance = { ...(node.attrs.provenance || {}), passageId };
      const paragraphs = proseToParagraphs(node.attrs.text, {
        provenance,
        blockId: result?.block_id ?? null,
      });

      editor
        .chain()
        .focus(null, { scrollIntoView: false })
        .insertContentAt({ from: pos, to: pos + node.nodeSize }, paragraphs)
        .run();

      setStatus('Accepted into the manuscript.');
    },
    [editor, sceneId],
  );

  const onDismiss = useCallback(
    async (passageId, pos, node) => {
      await writerService.dismiss(passageId);
      // I3 at the surface: the node goes, and it leaves nothing behind — no placeholder,
      // no struck-through prose, no trace in the export (which never held it anyway).
      editor
        .chain()
        .focus(null, { scrollIntoView: false })
        .deleteRange({ from: pos, to: pos + node.nodeSize })
        .run();
      setStatus('Dismissed.');
    },
    [editor],
  );

  const onCreateOperator = useCallback(
    async (name, definition) => {
      await writerService.createOperator(projectId, { name, definition });
      await loadOperators();
      setStatus(`Operator \`${name}\` is yours now — invoke it with / ${name}`);
    },
    [projectId, loadOperators],
  );

  const onInspectOperator = useCallback(
    (name) => setInspecting(operators.find((o) => o.name === name) || { name, missing: true }),
    [operators],
  );

  const actions = useMemo(
    () => ({ onAccept, onDismiss, onCreateOperator, onInspectOperator, operators }),
    [onAccept, onDismiss, onCreateOperator, onInspectOperator, operators],
  );

  return (
    <WriterActionsContext.Provider value={actions}>
      <div className={`writer-editor${focusMode ? ' writer-editor--focus' : ''}`}>
        <div className="writer-editor__bar">
          <button type="button" onClick={run} disabled={busy} data-testid="render-button">
            {busy ? 'Rendering…' : 'Render'}
          </button>
          <button
            type="button"
            onClick={() => setFocusMode((f) => !f)}
            aria-pressed={focusMode}
            data-testid="focus-toggle"
          >
            Focus
          </button>
          <span className="writer-editor__status" data-testid="editor-status">{status}</span>
          {error && <span className="writer-editor__error" data-testid="editor-error">{error}</span>}
        </div>

        <div className="writer-editor__page">
          <EditorContent editor={editor} />
        </div>

        {inspecting && (
          <aside className="writer-inspector" data-testid="operator-inspector">
            <header>
              <code>/{inspecting.name}</code>
              {!inspecting.missing && <span>v{inspecting.version}</span>}
              <button type="button" onClick={() => setInspecting(null)}>Close</button>
            </header>
            {inspecting.missing ? (
              <p>Not defined in this project yet — a directive naming it will refuse.</p>
            ) : (
              <>
                <p className="writer-inspector__definition">{inspecting.definition}</p>
                {inspecting.rendering_intent && (
                  <p className="writer-inspector__intent">{inspecting.rendering_intent}</p>
                )}
                {(inspecting.examples || []).map((ex) => (
                  <p key={ex} className="writer-inspector__example">{ex}</p>
                ))}
                {(inspecting.negative_examples || []).map((ex) => (
                  <p key={ex} className="writer-inspector__negative">not this: {ex}</p>
                ))}
              </>
            )}
          </aside>
        )}
      </div>
    </WriterActionsContext.Provider>
  );
}

export { proseToParagraphs, toManuscriptBlocks, exportManuscriptText };
