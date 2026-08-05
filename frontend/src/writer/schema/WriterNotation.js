import { Extension } from '@tiptap/core';
import { classifyLine } from './writerDoc';

/**
 * Semant Writer · W2 — typed notation becomes a first-class node.
 *
 * The author types `// goal: she arrives at the door` and presses Enter; the line stops
 * being characters and becomes an `orchestration` node. Same for `/ threshold` → a
 * directive chip.
 *
 * WHY ON ENTER AND NOT AS AN INPUT RULE. A TipTap input rule fires on every keystroke that
 * completes its regex, which for `// goal: <anything>` means it would convert the moment
 * the author typed the colon and then fight them for the rest of the sentence. Converting
 * on Enter lets a line be edited as text right up until the author finishes it, which is
 * how writing actually goes.
 *
 * Shift+Enter is deliberately NOT intercepted: it is the soft break — the inner tier of the
 * cadence — and StarterKit's `hardBreak` already owns it.
 *
 * The conversion is exposed as a COMMAND rather than living inside the key handler, so it
 * can be driven directly in tests with the caret anywhere in the document. That seam exists
 * because of a real bug: see the note in `convertNotationLine`.
 */
export const WriterNotation = Extension.create({
  name: 'writerNotation',

  addCommands() {
    return {
      /**
       * Turn the line the caret sits on into the node it describes. Returns false — so
       * the caller falls through to the default Enter — when the line is ordinary prose.
       */
      convertNotationLine:
        () =>
        // `chain` is the INJECTED chain, which shares this command's transaction.
        // `editor.chain()` would start a competing one and ProseMirror rejects the result
        // as a mismatched transaction the moment the caller has already moved the caret.
        ({ chain, state }) => {
          const { $from, empty } = state.selection;

          // Only transform when the caret sits in a plain textblock the author has been
          // typing into. A selection spanning content is an edit, not a line being finished.
          if (!empty || !$from.parent.isTextblock) return false;
          if ($from.parent.type.name !== 'paragraph') return false;

          const classified = classifyLine($from.parent.textContent);
          if (!classified) return false;

          // The whole paragraph NODE, boundaries included, so the replacement is one
          // block-level swap rather than an edit of inline content followed by a
          // structural command.
          const from = $from.before();
          const to = $from.after();

          // Both branches are the same shape on purpose: replace the finished line with
          // [the node it became, a fresh paragraph to keep typing in].
          //
          // WHY NOT `createParagraphNear()` AFTER AN INLINE INSERT. A TipTap chain is
          // atomic — if any command in it returns false, NOTHING is dispatched. An earlier
          // version ended with `createParagraphNear()`, which succeeds when the line is the
          // last node in the document and fails when it is not. On failure the whole chain
          // rolled back: the conversion silently did not happen and the default Enter split
          // the line instead, leaving `/ interiority` sitting in the manuscript as plain
          // text that merely LOOKED like a directive. It was invisible for as long as every
          // test typed at the end of the document. Nothing here can partially apply.
          const replacement = classified.node === 'orchestration'
            ? { type: 'orchestration', attrs: classified.attrs }
            : { type: 'paragraph', content: [{ type: 'directive', attrs: classified.attrs }] };

          return chain()
            .focus(null, { scrollIntoView: false })
            .insertContentAt({ from, to }, [replacement, { type: 'paragraph' }])
            .run();
        },
    };
  },

  addKeyboardShortcuts() {
    return {
      Enter: () => this.editor.commands.convertNotationLine(),
    };
  },
});

export default WriterNotation;
