/**
 * Semant Writer · W2 — the bridge between the editor document and the W1 DSL.
 *
 * W2 does NOT re-implement the parser. `backend/services/writer/dsl.py` owns what a block
 * means; this module only turns the editor's node tree back into the block text that
 * `studio.run_block` already knows how to read, so the surface and the headless loop are
 * running the same code on the same input.
 *
 * The editor holds as STRUCTURE what the DSL holds as SYNTAX: an `orchestration` node is a
 * `//` line, a `directive` chip is a `/` line. Serializing back to text is therefore
 * lossless in the direction that matters — everything the backend needs to parse survives,
 * and the node attrs were themselves produced from that syntax in the first place.
 */

/** One orchestration node → its `//` line. */
function orchestrationLine(node) {
  return `// ${node.attrs.key}: ${node.attrs.value}`;
}

/** One directive node → its `/` line, operator stack and argument intact. */
function directiveLine(node) {
  const names = (node.attrs.operators || []).join(' + ');
  const arg = node.attrs.argument ? `(${node.attrs.argument})` : '';
  return `/ ${names}${arg}`;
}

/**
 * The editor document → the block text `studio.run_block` parses.
 *
 * Document order is preserved exactly, because the DSL's orchestration scope is
 * POSITIONAL: a `//` note conditions the directives that follow it, and reordering here
 * would silently re-stage the author's block. See `dsl.parse_block`'s scope rule.
 *
 * Quarantined passages are NOT serialized. They are render OUTPUT, not input; feeding an
 * unaccepted render back in as prose would let uncommitted text condition the next render
 * as if the author had accepted it.
 */
export function docToBlockText(doc) {
  const lines = [];
  if (!doc) return '';

  doc.forEach((node) => {
    if (node.type.name === 'orchestration') {
      lines.push(orchestrationLine(node));
      return;
    }
    if (node.type.name === 'quarantinedPassage') return;

    if (node.isTextblock) {
      // A paragraph may mix prose and directive chips. Emit each in document order, with
      // directives on their own lines — that is what the DSL requires, and the author sees
      // the chip sitting inline regardless.
      let buffer = '';
      const flush = () => {
        if (buffer.trim()) lines.push(buffer.trim());
        buffer = '';
      };
      node.forEach((child) => {
        if (child.type.name === 'directive') {
          flush();
          lines.push(directiveLine(child));
        } else if (child.type.name === 'hardBreak') {
          flush();
        } else if (child.isText) {
          buffer += child.text;
        }
      });
      flush();
    }
  });

  return lines.join('\n');
}

/** Does this block hold anything the loop could act on? Guards an empty Render call. */
export function hasRunnableContent(doc) {
  let found = false;
  doc?.descendants((node) => {
    if (node.type.name === 'directive') {
      found = true;
      return false;
    }
    return true;
  });
  return found;
}

// ── the notation the author types ────────────────────────────────────────────
// These mirror `dsl.py`'s regexes. They are matched here ONLY to decide when a typed line
// becomes a first-class node; the backend re-parses the serialized text and remains the
// authority on what a block means.

const ORCH_RE = /^\/\/\s*([A-Za-z_][\w-]*)\s*:\s*(.*)$/;
const BARE_ORCH_RE = /^\/\/\s*(.*)$/;
const DIRECTIVE_RE = /^\/(?!\/)\s*(.+)$/;
const OPERATOR_RE = /^([A-Za-z][\w-]*)\s*(?:\(([^)]*)\))?$/;

export const ORCHESTRATION_KEYS = ['goal', 'arc', 'priority', 'avoid', 'voice'];

/**
 * A typed line → the node it should become, or null if it is prose.
 *
 * `//` is tested BEFORE `/` — the negative lookahead in DIRECTIVE_RE says the same thing
 * twice on purpose. That ordering is the `/` ÷ `//` wall at the point of entry, and it is
 * the reason a staging note can never be read as a render instruction.
 */
export function classifyLine(text) {
  const line = (text || '').trim();
  if (!line) return null;

  if (line.startsWith('//')) {
    const m = ORCH_RE.exec(line);
    if (m) {
      const key = m[1].toLowerCase();
      return {
        node: 'orchestration',
        attrs: { key, value: m[2].trim(), known: ORCHESTRATION_KEYS.includes(key) },
      };
    }
    const bare = BARE_ORCH_RE.exec(line);
    // A `//` note with no `key: value` still must not reach the page, so it becomes an
    // orchestration node with no key — retained, inert, and invisible to the manuscript.
    return { node: 'orchestration', attrs: { key: '', value: (bare?.[1] || '').trim(), known: false } };
  }

  const d = DIRECTIVE_RE.exec(line);
  if (d) {
    const operators = [];
    let argument = '';
    for (const part of d[1].split('+')) {
      const m = OPERATOR_RE.exec(part.trim());
      if (!m) return null; // unreadable notation stays prose rather than becoming a wrong chip
      operators.push(m[1]);
      if (m[2]) argument = m[2].trim();
    }
    if (!operators.length) return null;
    return { node: 'directive', attrs: { operators, argument, versions: null } };
  }

  return null;
}
