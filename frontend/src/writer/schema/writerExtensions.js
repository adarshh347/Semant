import StarterKit from '@tiptap/starter-kit';
import Placeholder from '@tiptap/extension-placeholder';
import { ReactNodeViewRenderer } from '@tiptap/react';

import { ManuscriptExport } from './manuscriptExport';
import { Directive, ManuscriptParagraph, Orchestration, QuarantinedPassage } from './writerSchema';
import { WriterNotation } from './WriterNotation';
import OrchestrationView from '../views/OrchestrationView';
import DirectiveChip from '../views/DirectiveChip';
import QuarantineCard from '../views/QuarantineCard';

/**
 * Semant Writer · W2 — the editor's extension set.
 *
 * Node VIEWS are attached here rather than in `writerSchema.js` on purpose: the schema
 * module must stay free of React so the export guarantee can be tested headlessly, with
 * `getSchema()` and no DOM. The invariant lives in the schema; the pixels live here.
 */
export function writerExtensions({ placeholder } = {}) {
  return [
    StarterKit.configure({
      // Our paragraph carries `provenance`/`blockId` and declares `manuscriptExport`.
      paragraph: false,
      // A literary surface is prose, not a document editor: no headings, no lists, no
      // code blocks, no rules. Their absence is part of the register (and, because the
      // export rule is fail-closed, any of them that reappeared would be excluded from
      // the manuscript until it declared otherwise).
      heading: false,
      bulletList: false,
      orderedList: false,
      listItem: false,
      codeBlock: false,
      horizontalRule: false,
      blockquote: false,
    }),
    Placeholder.configure({
      placeholder:
        placeholder ??
        'Write. Or stage a passage:  // goal: …  then  / operator',
    }),
    ManuscriptExport,
    ManuscriptParagraph,
    Orchestration.extend({
      addNodeView: () => ReactNodeViewRenderer(OrchestrationView),
    }),
    Directive.extend({
      addNodeView: () => ReactNodeViewRenderer(DirectiveChip),
    }),
    QuarantinedPassage.extend({
      addNodeView: () => ReactNodeViewRenderer(QuarantineCard),
    }),
    WriterNotation,
  ];
}

export default writerExtensions;
