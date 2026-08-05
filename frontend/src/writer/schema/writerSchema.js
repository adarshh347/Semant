import { Node, mergeAttributes } from '@tiptap/core';
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
export const WRITER_NODES = [ManuscriptParagraph, Orchestration, Directive, QuarantinedPassage];
