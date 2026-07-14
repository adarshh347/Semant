import React from 'react';
import { Link } from 'react-router-dom';
import legPalmImage from '../assets/leg-palm.jpg';
import './LandingPage.css';

/**
 * Semant landing — the motive-based front page (Landing revamp, Pass 2 · Phase 2a).
 *
 * Built around one act: See · Read · Write. Editorial, type-led, honest copy — the
 * voice is lifted from `architecture-lab/landing-articles/01–03` with the product
 * word swapped to Semant. Phase 2a is fully static (no motion); the DOM is shaped
 * for Phase 2b to attach Motion reveals + a GSAP ScrollTrigger scrub to the
 * `.demo-*` nodes without restructuring. `data-reveal` marks 2b's reveal targets.
 */

// The three parts the demo "reads" — true to the actual image (a cast hand + forearm),
// so nothing on the page claims more than the picture shows.
const DEMO_PARTS = [
  { id: 'p1', label: 'the taut tendon', top: '34%', left: '58%' },
  { id: 'p2', label: 'the fall of light', top: '18%', left: '30%' },
  { id: 'p3', label: 'the loosening grip', top: '68%', left: '40%' },
];

export default function LandingPage() {
  return (
    <div className="landing">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <header className="landing-hero" data-reveal>
        <div className="landing-hero-copy">
          <span className="landing-kicker">See · Read · Write</span>
          <span className="landing-wordmark">Semant</span>
          <h1 className="landing-wedge">
            Every tool tells you <em>what’s</em> in an image.
            <br />
            Semant tells you <em>why it moves you</em> — part by part, in your own words.
          </h1>
          <p className="landing-lede">
            Close-reading for the age of the scroll. Not another place to save
            images — an instrument for seeing them.
          </p>
          <div className="landing-cta-row">
            <Link to="/gallery" className="landing-cta">
              Explore the Gallery <span className="landing-cta-arrow" aria-hidden>→</span>
            </Link>
            <a href="#see-read-write" className="landing-cta-secondary">
              See how it reads <span aria-hidden>↓</span>
            </a>
          </div>
        </div>

        <figure className="landing-hero-figure">
          <div className="landing-hero-frame">
            <img src={legPalmImage} alt="A cast of a hand and forearm, lit from the side." />
          </div>
          <figcaption className="landing-hero-vlabel">Reading, not tagging</figcaption>
        </figure>
      </header>

      {/* ── The problem ──────────────────────────────────────────────────── */}
      <section className="landing-section landing-problem" data-reveal>
        <span className="landing-kicker landing-kicker--accent">The problem</span>
        <h2 className="landing-h2">Saving is not seeing.</h2>
        <p className="landing-prose">
          We have never had more places to <em>save</em> an image — and never
          understood them less. A moodboard is an archive of your attention with
          the attention removed. It remembers <em>that</em> you stopped. It
          forgets <em>why</em> — and the why is the only part that matters.
        </p>
        <p className="landing-pullquote">Saving is a reflex. Seeing is a practice.</p>
      </section>

      {/* ── See · Read · Write — the spine ───────────────────────────────── */}
      <section id="see-read-write" className="landing-section landing-spine">
        <div className="landing-spine-head" data-reveal>
          <span className="landing-kicker landing-kicker--accent">The act</span>
          <h2 className="landing-h2">See · Read · Write</h2>
          <p className="landing-prose">
            One image, slowed down — decomposed into meaningful parts, read part
            by part, and written from. Here is the whole loop on a single frame.
          </p>
        </div>

        {/* SEE */}
        <article className="landing-panel" data-reveal>
          <div className="landing-panel-copy">
            <span className="landing-numeral">01</span>
            <h3 className="landing-h3">See — reading, not tagging.</h3>
            <p className="landing-prose">
              A tagger flattens the picture to a list: <em>hand, arm, 94%.</em>{' '}
              Semant decomposes it into the parts that carry the meaning — the
              taut tendon, the fall of light, the loosening grip.
            </p>
          </div>
          <figure className="landing-demo" aria-label="The image, decomposed into parts.">
            <div className="landing-demo-frame">
              <img src={legPalmImage} alt="The same cast, with three parts marked." />
              {DEMO_PARTS.map((p) => (
                <span
                  key={p.id}
                  className="landing-demo-part"
                  style={{ top: p.top, left: p.left }}
                >
                  <span className="landing-demo-dot" aria-hidden />
                  <span className="landing-demo-part-label">{p.label}</span>
                </span>
              ))}
            </div>
          </figure>
        </article>

        {/* READ */}
        <article className="landing-panel landing-panel--reverse" data-reveal>
          <div className="landing-panel-copy">
            <span className="landing-numeral">02</span>
            <h3 className="landing-h3">Read — a felt reading, part by part.</h3>
            <p className="landing-prose">
              Each part read through the lenses the image itself calls for — an
              interpretation you can disagree with, extend, and write from.
            </p>
          </div>
          <figure className="landing-reading" aria-label="A felt reading of a part.">
            <span className="landing-reading-tag">the loosening grip</span>
            <blockquote className="landing-reading-line">
              “The grip performs strength while the slack fingers quietly refuse
              it — control and its release held in the same hand.”
            </blockquote>
          </figure>
        </article>

        {/* WRITE */}
        <article className="landing-panel" data-reveal>
          <div className="landing-panel-copy">
            <span className="landing-numeral">03</span>
            <h3 className="landing-h3">Write — words that sound like you.</h3>
            <p className="landing-prose">
              It writes <em>with</em> you, not <em>for</em> you. The real visual
              detail is right there, grounded in the image and in your
              accumulating voice — no generic slop, no “✨ obsessed with this vibe ✨.”
            </p>
          </div>
          <figure className="landing-draft" aria-label="A paragraph assembled from the picked parts.">
            <div className="landing-draft-card">
              <p>
                The forearm holds a quiet argument: the{' '}
                <mark>taut tendon</mark> insists on effort while the{' '}
                <mark>loosening grip</mark> lets it go, and the{' '}
                <mark>fall of light</mark> down the wrist takes the side of
                release. Strength, caught in the act of forgetting itself.
              </p>
              <span className="landing-draft-origin">written with Semant · from your picks</span>
            </div>
          </figure>
        </article>
      </section>

      {/* ── The payoff ───────────────────────────────────────────────────── */}
      <section className="landing-section landing-payoff" data-reveal>
        <span className="landing-kicker landing-kicker--accent">The payoff</span>
        <h2 className="landing-h2">Your taste is your edge.</h2>
        <p className="landing-prose">
          When everyone can generate everything, the one thing that can’t be
          faked is a point of view. Do this a hundred times and a{' '}
          <em>portrait of your own eye</em> appears — the motifs you return to,
          the details you can’t stop noticing, your taste written down as
          language instead of scattered across boards you’ll never reopen.
        </p>
        <p className="landing-pullquote">Your taste, given back — not harvested.</p>
      </section>

      {/* ── Close ────────────────────────────────────────────────────────── */}
      <section className="landing-section landing-close" data-reveal>
        <h2 className="landing-h2 landing-close-line">
          Tagging tells you what you’re looking at.
          <br />
          Reading tells you what you’re <em>seeing</em>.
        </h2>
        <p className="landing-prose landing-close-sub">We only care about the second one.</p>
        <Link to="/gallery" className="landing-cta landing-cta--lg">
          Start seeing <span className="landing-cta-arrow" aria-hidden>→</span>
        </Link>
      </section>
    </div>
  );
}
