import React, { useState } from 'react';
import Manuscript from '../components/blocknote/Manuscript';
import { useTheme } from '../context/ThemeContext';
import './BlockNoteLab.css';

// Dev harness for the Manuscript editor (Editor Path B · Phase 2), at
// /lab/manuscript. Seeds a realistic story via the converter and shows the
// serialised text_blocks so the round-trip is eyeball-verifiable. Not linked.
const SAMPLE = [
  { id: 'block_h', type: 'h1', content: '<h1>The turned collar</h1>', origin: 'human', color: null },
  { id: 'block_p1', type: 'paragraph', content: '<p>The drape softens the <strong>severe</strong> shoulder.</p>', origin: 'human', color: null },
  { id: 'block_sut', type: 'paragraph', content: '<p>An <em>Aletheia</em> reading, drafted for you.</p>', origin: 'sutradhar', color: null },
  { id: 'block_wash', type: 'paragraph', content: '<p>A remembered line.</p>', origin: 'human', color: '#fef3c7' },
  { id: 'block_chip', type: 'paragraph', origin: 'human', color: null,
    content: '<p>The <span data-region-ref data-ref-kind="part" data-region-ids="reg_1" data-label="shoulder drape" class="ref-chip ref-chip--part">shoulder drape</span> carries the meaning.</p>' },
  { id: 'block_q', type: 'quote', content: '<blockquote>The moat stays ours.</blockquote>', origin: 'human', color: null },
];

export default function ManuscriptLab() {
  const { theme, toggleTheme } = useTheme();
  const [out, setOut] = useState([]);

  return (
    <div className="bnlab">
      <header className="bnlab-bar">
        <span className="bnlab-kicker">Manuscript · Editor Path B · Phase 2</span>
        <nav className="bnlab-actions">
          <button className="bnlab-btn" onClick={toggleTheme}>
            {theme === 'dark' ? '☾ dark' : '☀ light'} · toggle
          </button>
        </nav>
        <span className="bnlab-meta">seeded via blockConvert · ids preserved</span>
      </header>

      <div className="bnlab-canvas">
        <div className="bnlab-doc">
          <Manuscript initialBlocks={SAMPLE} onChange={setOut} />
        </div>
      </div>

      <pre
        data-testid="manuscript-serialized"
        style={{
          maxWidth: 720,
          margin: '0 auto 4rem',
          padding: '1rem',
          fontSize: 12,
          fontFamily: 'var(--font-mono)',
          color: 'var(--ink-muted)',
          background: 'var(--surface-2)',
          border: '1px solid var(--line)',
          borderRadius: 'var(--radius-md)',
          overflow: 'auto',
        }}
      >
        {out.length
          ? out.map((b) => `${b.id}  [${b.type}] origin=${b.origin} color=${b.color ?? '—'}  ${b.content}`).join('\n')
          : 'edit above — serialised text_blocks (via converter) appear here'}
      </pre>
    </div>
  );
}
