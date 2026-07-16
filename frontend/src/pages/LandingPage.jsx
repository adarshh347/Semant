import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import editorialImage from '../assets/background.jpeg';
import './LandingPage.css';

// Phase 2b, finally: a restrained reveal on the [data-reveal] sections — rise
// 12px + fade on --ease, once, as each enters the viewport. CSS owns the look;
// under prefers-reduced-motion the transition never applies, so the static
// Phase-2a state IS the fallback, exactly as promised below.
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.landing [data-reveal]');
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('is-revealed');
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: '0px 0px -10% 0px' },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

/**
 * Semant landing — the motive-based front page, on the design language v1.3
 * (Paper + Plum), positioned per architecture-lab/responses/market-targets.md:
 * visual creators (fashion-first) articulating their taste, against moodboard
 * drift and AI slop. Copy drawn from the landing-articles (01 saving-is-not-
 * seeing · 02 your-taste-is-your-edge · 03 reading-not-tagging · 04 chiasm).
 *
 * Built around one act: See · Read · Write. Editorial, type-led, restrained.
 * Two image registers, used strictly (design-language §4 / §7):
 *   • Hero = register-1, the *real editorial image* carrying only our thin
 *     plum region overlay on a few parts — the product's own truth.
 *   • Spine = register-2, one *muted-pastel card* per panel holding a hand-drawn
 *     thick-black-line motif that dissects an image into parts + a 1-line reading.
 * Colour discipline: warm paper + one plum *interactive* accent + the pastel
 * diagram cards; nothing else. Primary action is the ink pill; emphasis is
 * italic Fraunces, never colour.
 *
 * [data-reveal] sections get the Phase 2b rise-and-fade (useReveal above);
 * the static markup IS the prefers-reduced-motion fallback.
 */

// Hero region overlay — 2–3 thin plum boxes on garment parts (register-1).
const HERO_REGIONS = [
  { label: 'the neckline', top: '26%', left: '46%', width: '20%', height: '13%' },
  { label: 'the drape', top: '52%', left: '38%', width: '26%', height: '20%' },
  { label: 'the patterned hem', top: '74%', left: '34%', width: '30%', height: '15%' },
];

/* ── Hand-drawn diagram motifs (thick single-weight black line + one plum
   accent). Fixed dark stroke via --diagram-ink so they stay black-on-pastel in
   dark mode. One motif per pastel card. ─────────────────────────────────────── */

function SeeMotif() {
  // A garment dissected into parts — two ink markers, one plum (the pick).
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
    pastel: 'mauve',
    motif: <SeeMotif />,
    reading: 'Not “a gown” — the neckline, the drape, the patterned hem.',
  },
  {
    n: '02',
    title: 'Read — a felt reading, part by part.',
    line: 'Each part read through the lenses the image itself calls for — an interpretation you can extend and write from.',
    pastel: 'stone',
    motif: <ReadMotif />,
    reading: '“The drape gives where the neckline holds — softness argued against restraint.”',
  },
  {
    n: '03',
    title: 'Write — words that could sound like you.',
    line: 'The aim: prose grounded in the parts you picked and your accumulating voice — not generic slop.',
    pastel: 'bluegrey',
    motif: <WriteMotif />,
    reading: 'The picked part, carried into the sentence — in your own words.',
  },
];

export default function LandingPage() {
  useReveal();
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
            <Link to="/home" className="landing-pill">
              Enter <span aria-hidden>→</span>
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
          Pinterest, Cosmos, Are.na, Savee, a thousand screenshots you will
          never open again — we have never had more places to <em>save</em> an
          image, and the reason you saved it evaporates the second you scroll
          on. A moodboard is an archive of your attention with the attention
          removed: it remembers <em>that</em> you stopped and forgets{' '}
          <em>why</em>. Designers call the result drift. It isn&rsquo;t a lack
          of inspiration. It&rsquo;s a lack of seeing.
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
          When everyone can generate everything, the specific way <em>you</em>{' '}
          see is the last unautomatable thing you own. Read a hundred images
          this way and a portrait of your own eye appears — the motifs you
          return to, the details you can&rsquo;t stop noticing — your taste
          written down as language instead of scattered across boards
          you&rsquo;ll never reopen. Then it writes <em>with</em> you, not{' '}
          <em>for</em> you: captions, lookbook lines, notes grounded in the real
          detail and in your accumulated voice. For stylists, creative
          directors, and anyone building an aesthetic in public — words that
          sound like the person who saw the thing.
        </p>
        <p className="landing-pullquote">Your taste, given back — not harvested.</p>
      </section>

      {/* ── The room — Chiasm (article 04) ───────────────────────────────── */}
      <section className="landing-section" data-reveal>
        <span className="landing-eyebrow">The room</span>
        <h2 className="landing-h2">Chiasm — the crossing.</h2>
        <p className="landing-prose">
          Most software keeps the image on one side and your words on the
          other, the detail that moved you stuck behind glass. Semant&rsquo;s
          workspace has two shores — the <em>Field</em>, where the image is
          taken apart by attention, and the <em>Manuscript</em>, where it
          becomes language — and the product is the crossing between them. The
          drape you mark travels into the sentence as a live thing: hover the
          word and the shape lights up on the image; write about it and the
          image remembers being written about.
        </p>
        <p className="landing-pullquote">
          Not a nicer editor — a medium where seeing and saying cross.
        </p>
      </section>

      {/* ── Close (centered announcement register) ───────────────────────── */}
      <section className="landing-section landing-close" data-reveal>
        <h2 className="landing-h2 landing-close-line">
          Tagging tells you what you’re looking at. Reading tells you what
          you’re <em>seeing</em>.
        </h2>
        <p className="landing-prose landing-close-sub">We only care about the second one.</p>
        <Link to="/home" className="landing-pill landing-pill--lg">
          Start seeing <span aria-hidden>→</span>
        </Link>
      </section>
    </div>
  );
}
