import { Extension, getExtensionField, callOrReturn } from '@tiptap/core';

/**
 * Semant Writer · W2 — the manuscript-export rule, declared ON THE SCHEMA.
 *
 * This is invariants I1 and I6 made STRUCTURAL. W1 enforced them at the render boundary
 * (`dsl.strip_orchestration`) and again at the Accept gate (`passages.accept` refuses a
 * leaking passage). W2 moves the guarantee up to the document model, where the editor
 * actually holds `//` orchestration and uncommitted renders as live nodes sitting inches
 * from committed prose.
 *
 * WHY A SCHEMA FIELD AND NOT A LIST IN THE SERIALIZER. A serializer that knows the names
 * of the nodes it must skip is a guard that silently rots: add a fifth node type in W3 and
 * it exports by default, because nobody remembered to add it to the deny-list. Declaring
 * the rule as a NodeSpec field inverts that — `manuscriptExport` defaults to FALSE, so a
 * node type is excluded from the manuscript unless its own definition opts in. A future
 * node that forgets to declare is silently *safe* rather than silently leaking.
 *
 * That is the whole design: FAIL CLOSED. The only nodes that reach the page are the ones
 * that said, in their own definition, that they are prose.
 *
 * Read `backend/services/writer/docs/GROUNDING.md` for why this matters more than it looks:
 * orchestration is the author's private reasoning, and if it reached the canon it would be
 * un-authored text in a manuscript whose whole claim is that the author wrote it.
 */
export const ManuscriptExport = Extension.create({
  name: 'manuscriptExport',

  // Propagate a `manuscriptExport` field from each node's definition onto its ProseMirror
  // NodeSpec, so `node.type.spec.manuscriptExport` is readable without an editor instance
  // (which is what lets the export test run headlessly in CI).
  extendNodeSchema(extension) {
    const context = {
      name: extension.name,
      options: extension.options,
      storage: extension.storage,
    };
    return {
      manuscriptExport:
        callOrReturn(getExtensionField(extension, 'manuscriptExport', context)) ?? false,
    };
  },
});

/** Does this node type reach the page? Fail-closed: anything undeclared is a no. */
export function exportsToManuscript(nodeType) {
  return nodeType?.spec?.manuscriptExport === true;
}

/**
 * Inline content of one prose node → HTML, preserving the two-tier cadence.
 *
 * A `hardBreak` is the SOFT break — a line turn inside a single beat — and it survives as
 * `<br>`. The paragraph boundary is the other tier and is carried by the block itself.
 * Both round-trip through the ledger's `{id,type,content(HTML),color,origin}` contract.
 *
 * Inline nodes that are not prose (a `/` directive chip) are skipped by the same
 * fail-closed rule as blocks — a chip is notation, and notation is not the page.
 */
function inlineToHTML(node) {
  let html = '';
  node.forEach((child) => {
    if (child.isText) {
      html += escapeHTML(child.text);
    } else if (child.type.name === 'hardBreak') {
      html += '<br>';
    } else if (exportsToManuscript(child.type)) {
      html += escapeHTML(child.textContent);
    }
    // else: notation. Deliberately dropped — see the fail-closed note above.
  });
  return html;
}

function escapeHTML(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/**
 * The document → the ledger's text_blocks. THE one serializer for the manuscript.
 *
 * Returns `[{ id, type, content, color, origin, provenance }]` — the same block shape
 * `blockConvert.js` and `manuscript_service.update_scene` already speak, so accepted prose
 * lands in canon through the existing contract rather than a parallel one.
 *
 * Nodes whose type does not declare `manuscriptExport: true` are absent from the result.
 * Not emptied, not commented out — ABSENT. There is no representation of orchestration or
 * of an unaccepted render anywhere in this output.
 */
export function toManuscriptBlocks(doc) {
  const blocks = [];
  if (!doc) return blocks;

  doc.forEach((node) => {
    if (!exportsToManuscript(node.type)) return;
    const content = inlineToHTML(node);
    blocks.push({
      id: node.attrs?.blockId || undefined,
      type: 'paragraph',
      content: content ? `<p>${content}</p>` : '',
      color: null,
      // `user_confirmed` when it came from an accepted render (the model proposed, the
      // author accepted — `routers/posts.py`'s vocabulary); `human` when the author typed
      // it. Never `model_suggested`: that means still-quarantined, and nothing quarantined
      // is in this list by construction.
      origin: node.attrs?.provenance ? 'user_confirmed' : 'human',
      provenance: node.attrs?.provenance || null,
      // W8 — the block IS the current pointer, so it carries which lineage and which
      // version it is showing. Exactly one version travels with a block, which is why
      // "export is current versions only" needs no filter: there is no second one here
      // to leave out.
      lineage_id: node.attrs?.lineageId || undefined,
      version: node.attrs?.version || undefined,
    });
  });

  return blocks;
}

/**
 * The ledger's text_blocks → an editor document. The inverse of `toManuscriptBlocks`.
 *
 * Opening the editor on a scene has to show the committed prose WITH ITS CADENCE — a
 * `<br>` comes back as the inner tier (a soft break inside the beat), a separate block as
 * the outer tier. Round-tripping that is what makes the two tiers real rather than a
 * display trick that survives only until reload.
 *
 * Only prose comes back, because only prose was ever stored: there is no orchestration and
 * no uncommitted render in the ledger to reconstruct. The `//` layer is working state, and
 * it lives and dies with the session by design (invariant 3, the two memories).
 */
export function manuscriptBlocksToDoc(blocks) {
  const content = (blocks || [])
    .map((block) => {
      const html = String(block.content ?? '');
      const inner = html.replace(/^<p>/i, '').replace(/<\/p>$/i, '');
      const nodes = [];
      inner.split(/<br\s*\/?>/i).forEach((line, i) => {
        if (i > 0) nodes.push({ type: 'hardBreak' });
        const text = line
          .replace(/<[^>]+>/g, '')
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/&amp;/g, '&');
        if (text) nodes.push({ type: 'text', text });
      });
      return {
        type: 'paragraph',
        attrs: {
          provenance: block.provenance ?? null,
          blockId: block.id ?? null,
          lineageId: block.lineage_id ?? null,
          version: block.version ?? null,
        },
        content: nodes,
      };
    })
    .filter((node) => node.content.length > 0);

  // An empty scene still needs somewhere for the caret to land.
  return { type: 'doc', content: content.length ? content : [{ type: 'paragraph' }] };
}

/**
 * The document → plain text, as the exported manuscript reads.
 *
 * This is what the mandatory I6 CI assertion runs against: put a distinctive token in a
 * `//goal`, render, Accept, export, and the token must be absent.
 */
export function exportManuscriptText(doc) {
  return toManuscriptBlocks(doc)
    .map((b) =>
      b.content
        .replace(/<br\s*\/?>/g, '\n')
        .replace(/<[^>]+>/g, '')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&amp;/g, '&'),
    )
    .filter((t) => t.trim())
    .join('\n\n');
}
