import React from 'react';

/**
 * MiniMarkdown — a deliberately small, dependency-free renderer for the Semant
 * Field Notes. It handles exactly the subset those articles use: YAML
 * front-matter (stripped), #/##/### headings, `---` rules, `>` blockquotes,
 * `- ` unordered lists, paragraphs, and inline **bold**, *italic*, `code`.
 *
 * It is intentionally not a general markdown engine — the input is our own,
 * simple, and trusted, so no HTML injection path exists (no dangerouslySetHTML).
 */

// ── inline: **bold**, `code`, *italic* → React nodes ─────────────────────────
function renderInline(text, keyBase) {
  // 1) split out `code` spans first so ** or * inside them stay literal.
  const codeParts = text.split(/(`[^`]+`)/g);
  const nodes = [];
  codeParts.forEach((part, i) => {
    if (/^`[^`]+`$/.test(part)) {
      nodes.push(<code key={`${keyBase}-c${i}`}>{part.slice(1, -1)}</code>);
      return;
    }
    // 2) bold, then 3) italic on the remaining plain text.
    const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
    boldParts.forEach((bp, j) => {
      if (/^\*\*[^*]+\*\*$/.test(bp)) {
        nodes.push(<strong key={`${keyBase}-b${i}-${j}`}>{bp.slice(2, -2)}</strong>);
        return;
      }
      const italicParts = bp.split(/(\*[^*]+\*)/g);
      italicParts.forEach((ip, k) => {
        if (/^\*[^*]+\*$/.test(ip)) {
          nodes.push(<em key={`${keyBase}-i${i}-${j}-${k}`}>{ip.slice(1, -1)}</em>);
        } else if (ip) {
          nodes.push(<React.Fragment key={`${keyBase}-t${i}-${j}-${k}`}>{ip}</React.Fragment>);
        }
      });
    });
  });
  return nodes;
}

// ── strip YAML front-matter (--- … ---) at the top of the file ───────────────
function stripFrontMatter(src) {
  if (!src.startsWith('---')) return src;
  const end = src.indexOf('\n---', 3);
  if (end === -1) return src;
  return src.slice(src.indexOf('\n', end + 1) + 1);
}

// ── block parser ─────────────────────────────────────────────────────────────
export default function MiniMarkdown({ source = '', className = '' }) {
  const lines = stripFrontMatter(source).replace(/\r\n/g, '\n').split('\n');
  const blocks = [];
  let para = [];
  let list = [];
  let quote = [];

  const flushPara = () => {
    if (para.length) {
      const key = `p${blocks.length}`;
      blocks.push(<p key={key}>{renderInline(para.join(' '), key)}</p>);
      para = [];
    }
  };
  const flushList = () => {
    if (list.length) {
      const key = `ul${blocks.length}`;
      blocks.push(
        <ul key={key}>
          {list.map((item, i) => (
            <li key={`${key}-${i}`}>{renderInline(item, `${key}-${i}`)}</li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  const flushQuote = () => {
    if (quote.length) {
      const key = `q${blocks.length}`;
      blocks.push(
        <blockquote key={key}>{renderInline(quote.join(' '), key)}</blockquote>,
      );
      quote = [];
    }
  };
  const flushAll = () => { flushPara(); flushList(); flushQuote(); };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) { flushAll(); continue; }

    if (/^#{1,3}\s/.test(line)) {
      flushAll();
      const level = line.match(/^(#{1,3})/)[1].length;
      const text = line.replace(/^#{1,3}\s/, '');
      const key = `h${blocks.length}`;
      const Tag = `h${level + 1 <= 6 ? level + 1 : 6}`; // # → h2, ## → h3, ### → h4 (page owns h1)
      blocks.push(<Tag key={key}>{renderInline(text, key)}</Tag>);
    } else if (/^---+$/.test(line.trim())) {
      flushAll();
      blocks.push(<hr key={`hr${blocks.length}`} />);
    } else if (/^>\s?/.test(line)) {
      flushPara(); flushList();
      quote.push(line.replace(/^>\s?/, ''));
    } else if (/^[-*]\s+/.test(line)) {
      flushPara(); flushQuote();
      list.push(line.replace(/^[-*]\s+/, ''));
    } else {
      flushList(); flushQuote();
      para.push(line.trim());
    }
  }
  flushAll();

  return <div className={`mini-markdown ${className}`}>{blocks}</div>;
}
