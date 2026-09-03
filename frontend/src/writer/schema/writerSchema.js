import { Node, mergeAttributes } from '@tiptap/core';
import { TextSelection } from '@tiptap/pm/state';
import Paragraph from '@tiptap/extension-paragraph';

/**
 * Semant Writer · W2 — the four node types.
 *
 * The schema is where the invariants stop being cosmetic. Each node declares, in its own
 * definition, whether it reaches the page (`manuscriptExport`), and `manuscriptExport.js`
 * reads that off the NodeSpec. Default is FALSE, so the guarantee is fail-closed.
 *
 *   1. `paragraph` (extended)   committed prose. The ONLY node that exports. Carries
 *                              `provenance` so an accepted span can answer "what wrote
 *                              this?" (I4), and `hardBreak` gives the two-tier cadence.
 *   2. `orchestration`          the `//` layer — the author's private reasoning. NEVER
 *                              exports (I6).
 *   3. `directive`             the `/` layer — an inline operator chip. Notation, not
 *                              prose; never exports.
 *   4. `quarantinedPassage`     an unaccepted render. NEVER exports until Accept turns it
 *                              into `paragraph` nodes (I1).
 *
 * WHY THE REFUSAL IS A STATE OF `quarantinedPassage` AND NOT A FIFTH NODE. The directive
 * specifies four node types, and a refusal genuinely IS what §3.4 describes — "an
 * unaccepted render". It just happens to be one that produced a reason instead of prose.
 * Modelling it as `status: 'refused'` keeps the two outcomes of one render call in one
 * node, which is also what makes "a refusal never leaves prose behind" true by
 * construction rather than by agreement between two node types. The card LOOKS entirely
 * different (see QuarantineCard) — that is a view concern, and it is the one place where
 * the visual difference genuinely is cosmetic.
 */

/** The `//` orchestration vocabulary, mirroring `dsl.ORCHESTRATION_KEYS`. */
export const ORCHESTRATION_KEYS = ['goal', 'arc', 'priority', 'avoid', 'voice'];

// ── 1. committed prose ───────────────────────────────────────────────────────

export const ManuscriptParagraph = Paragraph.extend({
  name: 'paragraph',

  // The one node that reaches the page.
  manuscriptExport: true,

  addAttributes() {
    return {
      ...this.parent?.(),
      // I4 — provenance survives the commit. Set when a span arrived by Accept; null when
      // the author typed it. `null` is meaningful: it means a human wrote this directly.
      //
      // `keepOnSplit: false` is load-bearing, not tidiness. ProseMirror copies a
      // textblock's attrs when Enter splits it, so pressing Enter at the end of an
      // accepted passage handed the NEW, empty paragraph the old one's provenance and
      // block id. Everything the author then typed themselves would export as
      // `origin: user_confirmed`, carrying operators that never touched it — provenance
      // asserting the model wrote the author's own sentence, which is exactly the
      // fabrication I4 exists to prevent. A split starts clean.
      provenance: {
        default: null,
        keepOnSplit: false,
        parseHTML: (el) => {
          const raw = el.getAttribute('data-provenance');
          if (!raw) return null;
          try {
            return JSON.parse(raw);
          } catch {
            return null;
          }
        },
        renderHTML: (attrs) =>
          attrs.provenance ? { 'data-provenance': JSON.stringify(attrs.provenance) } : {},
      },
      // Ledger block id, so an accepted span keeps pointing at the block it became.
      // Not inherited on split, for the same reason as `provenance` above — two
      // paragraphs claiming to be the same ledger block is a lie about the canon.
      blockId: {
        default: null,
        keepOnSplit: false,
        parseHTML: (el) => el.getAttribute('data-block-id'),
        renderHTML: (attrs) => (attrs.blockId ? { 'data-block-id': attrs.blockId } : {}),
      },
      // W8 — which passage lineage this span belongs to, and which version of it is on
      // the page. THE PARAGRAPH IS THE CURRENT POINTER: it holds exactly one version, so
      // a superseded version has no route into the export.
      //
      // `keepOnSplit: false` for the same reason as the two above, and it matters more
      // here rather than less. A split that carried the lineage would leave two paragraphs
      // both claiming to be version N of one passage, and accepting a revision would move
      // a pointer that two different pieces of prose believed they were.
      lineageId: {
        default: null,
        keepOnSplit: false,
        parseHTML: (el) => el.getAttribute('data-lineage-id'),
        renderHTML: (attrs) => (attrs.lineageId ? { 'data-lineage-id': attrs.lineageId } : {}),
      },
      version: {
        default: null,
        keepOnSplit: false,
        parseHTML: (el) => {
          const raw = el.getAttribute('data-version');
          return raw ? Number(raw) : null;
        },
        renderHTML: (attrs) => (attrs.version ? { 'data-version': String(attrs.version) } : {}),
      },
    };
  },
});

// ── 2. the `//` layer ────────────────────────────────────────────────────────

export const Orchestration = Node.create({
  name: 'orchestration',
  group: 'block',
  atom: true,
  selectable: true,
  draggable: false,

  // I6, structurally. This is the guard — the quiet styling is only a courtesy to the eye.
  manuscriptExport: false,

  addAttributes() {
    return {
      key: { default: 'goal' },
      value: { default: '' },
      // An unrecognised key is RETAINED but inert, exactly as `dsl.parse_block` does: the
      // author's words are never dropped on the floor, they simply condition nothing.
      known: { default: true },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-writer-orchestration]' }];
  },

  renderHTML({ HTMLAttributes, node }) {
    // NOTE: this is the EDITOR's DOM, not the manuscript. The manuscript serializer never
    // calls renderHTML — it reads `manuscriptExport` and skips this node entirely.
    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-writer-orchestration': node.attrs.key,
        class: 'writer-node-orchestration',
      }),
      `// ${node.attrs.key}: ${node.attrs.value}`,
    ];
  },
});

// ── 3. the `/` layer ─────────────────────────────────────────────────────────

export const Directive = Node.create({
  name: 'directive',
  group: 'inline',
  inline: true,
  atom: true,
  selectable: true,

  manuscriptExport: false,

  addAttributes() {
    return {
      // The operator stack: `/ threshold + interiority` is ONE directive naming two.
      operators: { default: [] },
      argument: { default: '' },
      // Resolved from the registry for display (`name v1`); null until looked up.
      versions: { default: null },
      // BLOCK SCOPE (W3 §1). The passage id whose Accept satisfied this directive, or
      // null while it is still pending. A satisfied directive is skipped by the default
      // Render: re-rendering it would propose a second passage for prose that is already
      // canon. Cleared by nothing — the author re-runs a satisfied directive explicitly.
      satisfiedBy: { default: null, keepOnSplit: false },
    };
  },

  parseHTML() {
    return [{ tag: 'span[data-writer-directive]' }];
  },

  renderHTML({ HTMLAttributes, node }) {
    const names = (node.attrs.operators || []).join(' + ');
    const arg = node.attrs.argument ? `(${node.attrs.argument})` : '';
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-writer-directive': names,
        class: 'writer-node-directive',
      }),
      `/${names}${arg}`,
    ];
  },
});

// ── 4. the unaccepted render ─────────────────────────────────────────────────

export const QuarantinedPassage = Node.create({
  name: 'quarantinedPassage',
  group: 'block',
  atom: true,
  selectable: true,

  // I1, structurally. `committed=false` content cannot reach the manuscript, and the way
  // it BECOMES committed is not a flag flip here — Accept replaces this node with
  // `paragraph` nodes after the W1 gate has written to canon.
  manuscriptExport: false,

  addAttributes() {
    return {
      passageId: { default: null },
      // 'quarantined' | 'refused' | 'unavailable' — the render outcome. See the note at
      // the top of this file for why a refusal lives here.
      status: { default: 'quarantined' },
      text: { default: '' },
      refusal: { default: '' },
      provenance: { default: null },
      orchestration: { default: null },
      diagnostics: { default: [] },
      directive: { default: '' },
      // Which directive produced this, so Accept can mark that directive satisfied
      // (W3 §1). Index in document order, matching `run_block`'s `directive_index`.
      directiveIndex: { default: null },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-writer-quarantine]' }];
  },

  renderHTML({ HTMLAttributes, node }) {
    return [
      'div',
      mergeAttributes(HTMLAttributes, {
        'data-writer-quarantine': node.attrs.status,
        class: 'writer-node-quarantine',
      }),
      // Deliberately NOT the prose. Even in the editor's fallback DOM (used when no node
      // view is mounted), an unaccepted render does not render as plain text that a copy,
      // a paste or a `innerText` scrape could mistake for manuscript.
      node.attrs.status === 'refused' ? 'refused render' : 'quarantined render',
    ];
  },
});

/** The W2 node set, in the order the editor registers them. */
// ── 5. one committed passage, one identity ───────────────────────────────────

/**
 * ATLAS-WRITER-MASS-BUILD-001D — the node that carries a committed passage's IDENTITY.
 *
 * THE PROBLEM IT CLOSES. A render of several paragraphs used to become several `paragraph`
 * nodes, each stamped with the same `blockId`, `lineageId` and `version`. Canon held ONE
 * block; the editor held three nodes all claiming to be it. Accepting a revision replaced
 * the first match and left the others standing as orphans that still said "I am version 1".
 *
 * THE DECISION. One canonical block may contain internal paragraph structure, and the editor
 * represents it as ONE wrapper node whose children are plain paragraphs. The wrapper alone
 * carries `provenance`/`blockId`/`lineageId`/`version`; the paragraphs inside carry nothing.
 * Chosen over "one lineage per paragraph" because a revision is a fresh render of the whole
 * declared set — it may come back as one paragraph or four — and there is no honest way to
 * say which new paragraph is the descendant of which old one. A passage has a history; a
 * paragraph inside it does not.
 *
 * Export reads the wrapper as one block with `<p>…</p><p>…</p>` content, which is exactly
 * what `manuscript_service.block_paragraphs` reads back. `isolating` keeps the caret from
 * merging a human paragraph into the passage; Enter at its end steps OUT to a clean
 * paragraph (see `addKeyboardShortcuts`), so prose the author types after an accepted span
 * is theirs and not the render's.
 */
export const CommittedPassage = Node.create({
  name: 'committedPassage',
  group: 'block',
  content: 'paragraph+',
  defining: true,
  isolating: true,

  // The wrapper reaches the page — as ONE block.
  manuscriptExport: true,

  addAttributes() {
    return {
      provenance: {
        default: null,
        parseHTML: (el) => {
          const raw = el.getAttribute('data-provenance');
          if (!raw) return null;
          try { return JSON.parse(raw); } catch { return null; }
        },
        renderHTML: (attrs) =>
          attrs.provenance ? { 'data-provenance': JSON.stringify(attrs.provenance) } : {},
      },
      blockId: {
        default: null,
        parseHTML: (el) => el.getAttribute('data-block-id'),
        renderHTML: (attrs) => (attrs.blockId ? { 'data-block-id': attrs.blockId } : {}),
      },
      lineageId: {
        default: null,
        parseHTML: (el) => el.getAttribute('data-lineage-id'),
        renderHTML: (attrs) => (attrs.lineageId ? { 'data-lineage-id': attrs.lineageId } : {}),
      },
      version: {
        default: null,
        parseHTML: (el) => {
          const raw = el.getAttribute('data-version');
          return raw ? Number(raw) : null;
        },
        renderHTML: (attrs) => (attrs.version ? { 'data-version': String(attrs.version) } : {}),
      },
    };
  },

  parseHTML() {
    return [{ tag: 'div[data-writer-committed]' }];
  },

  renderHTML({ HTMLAttributes }) {
    return ['div', mergeAttributes(HTMLAttributes, {
      'data-writer-committed': '',
      class: 'writer-passage',
    }), 0];
  },

  addKeyboardShortcuts() {
    return {
      // Enter at the very end of a committed passage leaves it: a NEW plain paragraph after
      // the wrapper, with no identity. Inside the passage Enter behaves as usual (the
      // passage keeps its one identity however many paragraphs it holds).
      Enter: ({ editor }) => {
        const { $from, empty } = editor.state.selection;
        if (!empty) return false;
        let depth = $from.depth;
        while (depth > 0 && $from.node(depth).type.name !== this.name) depth -= 1;
        if (depth === 0) return false;
        const wrapper = $from.node(depth);
        const paragraph = $from.parent;
        const atEnd = $from.parentOffset === paragraph.content.size
          && wrapper.lastChild === paragraph;
        if (!atEnd) return false;
        const after = $from.after(depth);
        return editor.commands.command(({ tr, state }) => {
          tr.insert(after, state.schema.nodes.paragraph.create());
          tr.setSelection(TextSelection.create(tr.doc, after + 1));
          return true;
        });
      },
    };
  },
});

export const WRITER_NODES = [
  ManuscriptParagraph, Orchestration, Directive, QuarantinedPassage, CommittedPassage,
];
