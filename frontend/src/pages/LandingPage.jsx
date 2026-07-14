import React from 'react';
import { Link } from 'react-router-dom';
import editorialImage from '../assets/background.jpeg';
import './LandingPage.css';

/**
 * Semant landing — the motive-based front page (Pass 2 · Phase 2a, refit to the
 * Semant design language v1.1).
 *
 * Built around one act: See · Read · Write. Editorial, type-led, restrained.
 * Two image registers, used strictly (design-language §4 / §7):
 *   • Hero = register-1, the *real editorial image* carrying only our thin
 *     terracotta region overlay on a few parts — the product's own truth.
 *   • Spine = register-2, one *muted-pastel card* per panel holding a hand-drawn
 *     thick-black-line motif that dissects an image into parts + a 1-line reading.
 * Colour discipline: warm paper + one terracotta *interactive* accent + the
 * pastel diagram cards; nothing else. Primary action is the ink pill; emphasis
 * is italic Fraunces, never colour.
 *
 * Phase 2a is fully static. [data-reveal] marks Phase 2b's reveal targets, and
 * this static state IS the prefers-reduced-motion fallback 2b degrades to.
 */

// Hero region overlay — 2–3 thin terracotta boxes on garment parts (register-1).
const HERO_REGIONS = [
  { label: 'the neckline', top: '26%', left: '46%', width: '20%', height: '13%' },
  { label: 'the drape', top: '52%', left: '38%', width: '26%', height: '20%' },
  { label: 'the patterned hem', top: '74%', left: '34%', width: '30%', height: '15%' },
];

/* ── Hand-drawn diagram motifs (thick single-weight black line + one terracotta
   accent). Fixed dark stroke via --diagram-ink so they stay black-on-pastel in
   dark mode. One motif per pastel card. ─────────────────────────────────────── */

function SeeMotif() {
  // A garment dissected into parts — two ink markers, one terracotta (the pick).
  return (
    <svg className="motif" viewBox="0 0 240 180" role="img" aria-label="A garment decomposed into parts.">
      <g fill="none" stroke="var(--diagram-ink)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <path d="M96 44 q24 -14 48 0 l16 26 -14 9 v70 q-26 10 -52 0 v-70 l-14 -9 z" />
        <path d="M120 40 v14" />
      </g>
      <circle cx="120" cy="118" r="13" fill="none" stroke="var(--diagram-ink)" strokeWidth="3" />
      <circle cx="150" cy="150" r="11" fill="none" stroke="var(--diagram-ink)" strokeWidth="3" />
      {/* the picked part — the one accent */}
      <circle cx="120" cy="47" r="15" fill="none" stroke="var(--accent)" strokeWidth="3.5" />
    </svg>
  );
}

function ReadMotif() {
  // A part, read: a lens over a swatch + a written reading line.
  return (
    <svg className="motif" viewBox="0 0 240 180" role="img" aria-label="A felt reading of a part.">
      <g fill="none" stroke="var(--diagram-ink)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <rect x="40" y="52" width="78" height="78" rx="8" />
        <path d="M52 74 q14 -10 28 0 t28 0" />
        <path d="M52 92 q14 -10 28 0 t28 0" />
        <path d="M52 110 q14 -10 28 0 t28 0" />
        <line x1="150" y1="132" x2="176" y2="158" />
      </g>
      {/* the lens ring — the one accent */}
      <circle cx="132" cy="112" r="26" fill="none" stroke="var(--accent)" strokeWidth="3.5" />
    </svg>
  );
}

function WriteMotif() {
  // Words from parts: a page of lines with one picked word marked.
  return (
    <svg className="motif" viewBox="0 0 240 180" role="img" aria-label="A paragraph grounded in the picked parts.">
      <g fill="none" stroke="var(--diagram-ink)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <rect x="52" y="34" width="112" height="128" rx="8" />
        <line x1="70" y1="66" x2="146" y2="66" />
        <line x1="70" y1="88" x2="146" y2="88" />
        <line x1="70" y1="110" x2="120" y2="110" />
        <line x1="70" y1="132" x2="146" y2="132" />
      </g>
      {/* the picked word, carried into the prose — the one accent */}
      <rect x="126" y="102" width="38" height="16" rx="5" fill="none" stroke="var(--accent)" strokeWidth="3.5" />
    </svg>
  );
}

const PANELS = [
  {
    n: '01',
    title: 'See — reading, not tagging.',
    line: 'A tagger flattens the picture to a list. Semant decomposes it into the parts that carry the meaning.',
    pastel: 'clay',
    motif: <SeeMotif />,
    reading: 'Not “a gown” — the neckline, the drape, the patterned hem.',
  },
  {
    n: '02',
    title: 'Read — a felt reading, part by part.',
    line: 'Each part read through the lenses the image itself calls for — an interpretation you can extend and write from.',
    pastel: 'sage',
    motif: <ReadMotif />,
    reading: '“The drape gives where the neckline holds — softness argued against restraint.”',
  },
  {
    n: '03',
    title: 'Write — words that could sound like you.',
    line: 'The aim: prose grounded in the parts you picked and your accumulating voice — not generic slop.',
    pastel: 'sky',
    motif: <WriteMotif />,
    reading: 'The picked part, carried into the sentence — in your own words.',
  },
];

export default function LandingPage() {
  return (
    <div className="landing">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <header className="landing-hero" data-reveal>
        <div className="landing-hero-copy">
          <span className="landing-eyebrow">See · Read · Write</span>
          <h1 className="landing-wedge">
            Every tool tells you <em>what’s</em> in an image. Semant tells you{' '}
            <em>why it moves you</em> — part by part, in your own words.
          </h1>
          <p className="landing-lede">
            Close-reading for the age of the scroll — an instrument for seeing
            images, not another place to save them.
          </p>
          <div className="landing-cta-row">
            <Link to="/gallery" className="landing-pill">
              Explore the Gallery <span aria-hidden>→</span>
            </Link>
            <a href="#see-read-write" className="landing-textlink">
              See how it reads <span aria-hidden>↓</span>
            </a>
          </div>
        </div>

        <figure className="landing-hero-figure">
          <div className="landing-hero-frame">
            <img src={editorialImage} alt="An editorial fashion figure in a patterned gown." />
            {HERO_REGIONS.map((r) => (
              <span
                key={r.label}
                className="landing-region"
                style={{ top: r.top, left: r.left, width: r.width, height: r.height }}
              >
                <span className="landing-region-label">{r.label}</span>
              </span>
            ))}
          </div>
        </figure>
      </header>

      {/* ── The problem ──────────────────────────────────────────────────── */}
      <section className="landing-section" data-reveal>
        <span className="landing-eyebrow">The problem</span>
        <h2 className="landing-h2">Saving is not seeing.</h2>
        <p className="landing-prose">
          We have never had more places to save an image — and never understood
          them less. A moodboard is an archive of your attention with the
          attention removed. It remembers <em>that</em> you stopped; it forgets
          <em> why</em> — and the why is the only part that matters.
        </p>
        <p className="landing-pullquote">Saving is a reflex. Seeing is a practice.</p>
      </section>

      {/* ── See · Read · Write — the spine ───────────────────────────────── */}
      <section id="see-read-write" className="landing-section landing-spine">
        <div className="landing-spine-head" data-reveal>
          <span className="landing-eyebrow">The act</span>
          <h2 className="landing-h2">See · Read · Write.</h2>
          <p className="landing-prose">
            One image, slowed down — decomposed into meaningful parts, read part
            by part, and written from.
          </p>
        </div>

        {PANELS.map((p, i) => (
          <article
            key={p.n}
            className={`landing-panel${i % 2 === 1 ? ' landing-panel--reverse' : ''}`}
            data-reveal
          >
            <div className="landing-panel-copy">
              <span className="landing-numeral">{p.n}</span>
              <h3 className="landing-h3">{p.title}</h3>
              <p className="landing-prose">{p.line}</p>
            </div>
            <figure className={`landing-card landing-card--${p.pastel}`}>
              {p.motif}
              <figcaption className="landing-card-reading">{p.reading}</figcaption>
            </figure>
          </article>
        ))}
      </section>

      {/* ── The payoff ───────────────────────────────────────────────────── */}
      <section className="landing-section" data-reveal>
        <span className="landing-eyebrow">The payoff</span>
        <h2 className="landing-h2">Your taste is your edge.</h2>
        <p className="landing-prose">
          When everyone can generate everything, the one thing that can’t be
          faked is a point of view. Do this a hundred times and a portrait of
          your own eye appears — the details you can’t stop noticing, your taste
          written down as language instead of scattered across boards you’ll
          never reopen.
        </p>
        <p className="landing-pullquote">Your taste, given back — not harvested.</p>
      </section>

      {/* ── Close (centered announcement register) ───────────────────────── */}
      <section className="landing-section landing-close" data-reveal>
        <h2 className="landing-h2 landing-close-line">
          Tagging tells you what you’re looking at. Reading tells you what
          you’re <em>seeing</em>.
        </h2>
        <p className="landing-prose landing-close-sub">We only care about the second one.</p>
        <Link to="/gallery" className="landing-pill landing-pill--lg">
          Start seeing <span aria-hidden>→</span>
        </Link>
      </section>
    </div>
  );
}
