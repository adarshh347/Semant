import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { EditorContent, useEditor } from '@tiptap/react';

import { writerService } from './writerService';
import { writerExtensions } from './schema/writerExtensions';
import {
  directivesInDoc,
  docToBlockText,
  hasRunnableContent,
  pendingDirectiveIndices,
} from './schema/writerDoc';
import { exportManuscriptText, toManuscriptBlocks } from './schema/manuscriptExport';
import { WriterActionsContext } from './views/WriterActions';
import RevisionPanel from './revision/RevisionPanel';
import RecallPanel from './recall/RecallPanel';
import CitedSpans from './recall/CitedSpans';
import RegisterPanel from './registers/RegisterPanel';
import DepthView from './registers/DepthView';
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
  // W8 — the lineage the author is revising, or null. Opening this panel changes nothing;
  // it is a view onto what a committed span was declared under, plus its history.
  const [revising, setRevising] = useState(null);
  // W9 — the recall panel, and the committed passages the author has marked as
  // grounding for the next render. Empty unless they put something here: there is no
  // auto-citation, and the server refuses anything that is not committed canon.
  const [recalling, setRecalling] = useState(false);
  const [cited, setCited] = useState([]);
  // W10 — the author's ladder, and the manuscript read along it. Both are views:
  // opening either writes nothing, and the depth view makes no model call at all.
  const [panel, setPanel] = useState('');

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

  /**
   * BLOCK SCOPE (W3 §1). By default this renders only the directives that are still
   * PENDING — the ones whose render the author has not accepted. `{ all: true }` is the
   * explicit re-run-everything action, and `{ only: [i] }` re-renders one satisfied
   * directive on request.
   *
   * The whole block text always goes to the server regardless: `//` scope is positional,
   * so sending a filtered block would re-stage every directive after the gap.
   */
  const run = async ({ all = false, only = null } = {}) => {
    if (!editor || busy) return;
    const doc = editor.state.doc;
    const text = docToBlockText(doc);
    if (!hasRunnableContent(doc)) {
      setError('Nothing to render — a block needs at least one `/` directive.');
      return;
    }

    const onlyDirectives = all ? null : (only ?? pendingDirectiveIndices(doc));
    if (onlyDirectives && onlyDirectives.length === 0) {
      setError('Every directive here is already accepted. Re-render one from its span, '
        + 'or use Render all.');
      return;
    }

    setBusy(true);
    setError('');
    setStatus('Rendering…');
    try {
      const out = await writerService.run(projectId, {
        text, manuscriptId, sceneId, onlyDirectives,
        // Only the identity travels — the server re-reads the prose from the ledger, so a
        // stale copy held in this component can never become what the render rested on.
        cited: cited.map((c) => ({ lineage_id: c.lineage_id, version: c.version })),
      });
      const results = out.results ?? [];
      insertResults(results);
      const refused = results.filter((r) => r.status === 'refused').length;
      const skipped = results.filter((r) => r.status === 'skipped').length;
      const rendered = results.length - refused - skipped;
      setStatus(
        `${rendered} rendered, ${refused} refused`
        + (skipped ? `, ${skipped} already accepted` : '')
        + ' — nothing committed.',
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

    const directives = directivesInDoc(editor.state.doc);

    // A skipped directive produced nothing to place — it is reported so the author can
    // see it was already satisfied, not so a card appears for it.
    const placements = results
      .filter((r) => r.status !== 'skipped')
      .map((result) => {
        const d = directives[result.directive_index];
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
              directiveIndex: result.directive_index ?? null,
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
        // W8 — a committed span is version 1 of a lineage from the moment it lands, so the
        // first thing the author revises already has a history to append to.
        lineageId: result?.lineage_id ?? null,
        version: result?.lineage_id ? 1 : null,
      });

      // Mark the directive satisfied BEFORE the card is replaced, so the position lookup
      // is against the document the caller measured. A satisfied directive is skipped by
      // the next Render (W3 §1) — the author finished it.
      const directives = directivesInDoc(editor.state.doc);
      const source = directives[node.attrs.directiveIndex];

      const chain = editor.chain().focus(null, { scrollIntoView: false });
      if (source) {
        chain.command(({ tr }) => {
          tr.setNodeMarkup(source.pos, undefined, {
            ...source.node.attrs,
            satisfiedBy: passageId,
          });
          return true;
        });
      }
      chain.insertContentAt({ from: pos, to: pos + node.nodeSize }, paragraphs).run();

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

  // W7 — the alignment reading. Read-only: it returns diagnostics and this component does
  // nothing with them but show them. There is no path from a flag to an edit here, and
  // adding one would make the reading a rewriter.
  const onReadAlignment = useCallback(
    async ({ text, provenance, passageId }) => writerService.readAlignment(projectId, {
      text, provenance, passageId, sceneId, manuscriptId,
    }),
    [projectId, sceneId, manuscriptId],
  );

  const onDecideFlag = useCallback(
    async (readingId, flagId, state) => writerService.decideFlag(readingId, flagId, state),
    [],
  );

  // ── W8: revising a committed span ─────────────────────────────────────────
  //
  // The re-render goes through `run` — the SAME call the Render button makes. There is no
  // revise-and-render service method, deliberately: a second render path is where a "make
  // it better" instruction would eventually be added with no first-render caller to object.

  const onPrepareRevision = useCallback(
    async (scene, blockId) => writerService.prepareRevision(projectId, scene, blockId),
    [projectId],
  );

  const onRevisionRender = useCallback(
    async (text) => writerService.run(projectId, {
      text, manuscriptId, sceneId, quarantine: true,
    }),
    [projectId, manuscriptId, sceneId],
  );

  const onAcceptRevision = useCallback(
    async ({ passageId, lineageId, sceneId: scene, blockId, inResponseTo }) => {
      // The gate runs first, as it does for a first Accept: if this throws, the document is
      // untouched and the manuscript still says what it said.
      const result = await writerService.acceptRevision(projectId, {
        passageId, lineageId, sceneId: scene, blockId, inResponseTo,
      });

      // Move the POINTER in the document: replace the paragraph's text and bump its version.
      // The prior version is not here to lose — it is in the ledger's version history, and
      // this surface has no way to reach in and change it.
      const { state } = editor;
      let target = null;
      state.doc.descendants((node, pos) => {
        if (node.type.name === 'paragraph' && node.attrs.blockId === blockId) {
          target = { node, pos };
          return false;
        }
        return true;
      });
      if (target) {
        const replacement = proseToParagraphs(result.version.text, {
          ...target.node.attrs,
          version: result.version.version,
          lineageId,
        });
        editor
          .chain()
          .focus(null, { scrollIntoView: false })
          .insertContentAt(
            { from: target.pos, to: target.pos + target.node.nodeSize }, replacement,
          )
          .run();
      }
      setStatus(
        `v${result.version.version} is now current. v${result.version.version - 1} is kept.`,
      );
      return result;
    },
    [editor, projectId],
  );

  // ── W9: recall & cite ─────────────────────────────────────────────────────
  //
  // Recall is READ-ONLY. It returns the author's own committed sentences and this component
  // does nothing with them but show them and let the author mark one as grounding. There is
  // deliberately no "insert this into the manuscript" path here: copying prior prose into
  // the book would be the model deciding to repeat the author.

  const onRecall = useCallback(
    async ({ query, includeHistorical }) =>
      writerService.recall(projectId, { query, includeHistorical }),
    [projectId],
  );

  const onCite = useCallback((span) => {
    setCited((current) => (
      current.some((c) => c.lineage_id === span.lineage_id && c.version === span.version)
        ? current
        : [...current, span]
    ));
    setStatus('The next render will be asked to stay consistent with that passage.');
  }, []);

  const onUncite = useCallback((span) => {
    setCited((current) => current.filter(
      (c) => !(c.lineage_id === span.lineage_id && c.version === span.version),
    ));
  }, []);

  // ── W10: the author's layers ──────────────────────────────────────────────

  const onLoadRegisters = useCallback(
    async () => writerService.registers(projectId), [projectId]);
  const onRegisterTemplate = useCallback(
    async () => writerService.registerTemplate(), []);
  const onDeclareRegisters = useCallback(
    async (registers) => writerService.declareRegisters(projectId, registers),
    [projectId]);
  const onLoadDepth = useCallback(
    async () => writerService.depth(projectId), [projectId]);

  const onDismissRevision = useCallback(
    async (passageId) => {
      await writerService.dismiss(passageId);
      setStatus('Kept the version you had.');
    },
    [],
  );

  const onInspectOperator = useCallback(
    (name) => setInspecting(operators.find((o) => o.name === name) || { name, missing: true }),
    [operators],
  );

  // Re-rendering a directive the author already accepted is an EXPLICIT action (W3 §1),
  // never something the default Render does on its own.
  const onRerenderDirective = useCallback(
    (index) => run({ only: [index] }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [editor, projectId, manuscriptId, sceneId, busy],
  );

  const actions = useMemo(
    () => ({
      onAccept, onDismiss, onCreateOperator, onInspectOperator, onRerenderDirective,
      onReadAlignment, onDecideFlag, operators,
    }),
    [onAccept, onDismiss, onCreateOperator, onInspectOperator, onRerenderDirective,
     onReadAlignment, onDecideFlag, operators],
  );

  return (
    <WriterActionsContext.Provider value={actions}>
      <div className={`writer-editor${focusMode ? ' writer-editor--focus' : ''}`}>
        <div className="writer-editor__bar">
          <button
            type="button"
            onClick={() => run()}
            disabled={busy}
            data-testid="render-button"
            title="Render the directives you have not accepted yet"
          >
            {busy ? 'Rendering…' : 'Render'}
          </button>
          <button
            type="button"
            onClick={() => run({ all: true })}
            disabled={busy}
            data-testid="render-all-button"
            title="Re-render every directive in the block, including ones you accepted"
          >
            Render all
          </button>
          <button
            type="button"
            onClick={() => {
              const { $from } = editor.state.selection;
              const paragraph = $from.node($from.depth);
              const { lineageId, blockId } = paragraph?.attrs || {};
              if (!lineageId || !blockId) {
                setStatus('Put the caret in a committed passage to revise it.');
                return;
              }
              setRevising({ lineageId, blockId });
            }}
            disabled={busy}
            data-testid="revise-button"
            title="Change what you declared and render this passage again"
          >
            Revise
          </button>
          <button
            type="button"
            onClick={() => setPanel((p) => (p === 'registers' ? '' : 'registers'))}
            aria-pressed={panel === 'registers'}
            data-testid="registers-toggle"
            title="Name the layers you work in"
          >
            Layers
          </button>
          <button
            type="button"
            onClick={() => setPanel((p) => (p === 'depth' ? '' : 'depth'))}
            aria-pressed={panel === 'depth'}
            data-testid="depth-toggle"
            title="Read your manuscript by the layers you named"
          >
            Depth
          </button>
          <button
            type="button"
            onClick={() => setRecalling((r) => !r)}
            aria-pressed={recalling}
            data-testid="recall-toggle"
            title="Search what you have already committed"
          >
            Recall
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

        {panel === 'registers' && (
          <RegisterPanel
            onLoad={onLoadRegisters}
            onDeclare={onDeclareRegisters}
            onLoadTemplate={onRegisterTemplate}
            onClose={() => setPanel('')}
          />
        )}

        {panel === 'depth' && (
          <DepthView onLoad={onLoadDepth} onClose={() => setPanel('')} />
        )}

        <CitedSpans cited={cited} onUncite={onUncite} />

        {recalling && (
          <RecallPanel
            onRecall={onRecall}
            cited={cited}
            onCite={onCite}
            onUncite={onUncite}
            onClose={() => setRecalling(false)}
          />
        )}

        <div className="writer-editor__page">
          <EditorContent editor={editor} />
        </div>

        {revising && (
          <RevisionPanel
            key={`${revising.lineageId}:${revising.blockId}`}
            lineageId={revising.lineageId}
            blockId={revising.blockId}
            sceneId={sceneId}
            onPrepare={onPrepareRevision}
            onRender={onRevisionRender}
            onAcceptRevision={onAcceptRevision}
            onDismiss={onDismissRevision}
            onClose={() => setRevising(null)}
          />
        )}

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
