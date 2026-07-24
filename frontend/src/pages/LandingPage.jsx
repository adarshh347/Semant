import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FIELD_NOTES, CATEGORY_LABEL, STATUS_LABEL } from '../content/fieldNotes';
import './LandingPage.css';

/**
 * Semant landing — the perception-engineering front door (SEMANT-LANDING-002).
 *
 * Replaces the earlier fashion-first "See · Read · Write" motive page with the
 * broader identity: Semant as a perception engineering environment — the Engine
 * (action grammar, orchestration session, marks, provenance) + the Workbench
 * (Differential, Manuscript, instruments, recall).
 *
 * Copy is drawn from vault/Writing/Semant Field Notes/00-landing-page.md and the
 * six field notes; visual direction from vault/Concepts/Frontend Analysis/
 * SEMANT-LANDING-001-visual-direction-and-hero.md ("The Great Arrival").
 *
 * Honesty: `built` states shipped mechanisms; `emerging`/`horizon` mark what the
 * workbench is growing toward. Nothing claims live model dispatch, agents, or
 * persistent memory as shipped.
 *
 * Motion: the hero's cinematic sequence and the [data-reveal] rise both run only
 * under prefers-reduced-motion:no-preference. The static composed state IS the
 * reduced-motion fallback — the hero SVG is authored to read as its own
 * afterimage still when nothing animates.
 */

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll('.perc-landing [data-reveal]');
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

const StatusChip = ({ status }) => (
  <span className={`perc-chip perc-chip--${status}`}>{STATUS_LABEL[status] || status}</span>
);

/* ── The Great Arrival — hand-authored SVG doodle hero ───────────────────────
   Authored so that WITHOUT animation it already reads as the composed
   afterimage still (M6). CSS adds the draw-on / arrival motion on top. */
function GreatArrival() {
  return (
    <svg
      className="arrival"
      viewBox="0 0 1200 760"
      preserveAspectRatio="xMidYMid slice"
      role="img"
      aria-label="A small figure at the lower edge watches an enormous hand-drawn meteor arrive across a twilight sky, its tail threading into cyan, violet, coral and gold."
    >
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0.3" y2="1">
          <stop offset="0" stopColor="#0B1026" />
          <stop offset="0.55" stopColor="#171A3A" />
          <stop offset="1" stopColor="#05060F" />
        </linearGradient>
        <radialGradient id="starGlow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#F6F7FF" stopOpacity="0.95" />
          <stop offset="0.4" stopColor="#FFD98A" stopOpacity="0.55" />
          <stop offset="1" stopColor="#FFD98A" stopOpacity="0" />
        </radialGradient>
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="7" />
        </filter>
      </defs>

      {/* sky + luminous grain */}
      <rect x="0" y="0" width="1200" height="760" fill="url(#sky)" />
      <rect x="0" y="0" width="1200" height="760" fill="#fff" opacity="0.035" filter="url(#grain)" />

      {/* faint graphite construction ticks — the engineering under the gesture */}
      <g className="arrival-guides" stroke="#9AA0C3" strokeWidth="1" opacity="0.16" fill="none">
        <path d="M980 70 L560 360" strokeDasharray="3 9" />
        <path d="M1040 150 L980 70" strokeDasharray="3 9" />
        <circle cx="980" cy="70" r="34" strokeDasharray="2 8" />
      </g>

      {/* the tail — threads separating into cyan / violet / coral / gold / white */}
      <g className="arrival-tail" fill="none" strokeLinecap="round">
        <path className="thread t1" d="M968 78 C 900 150, 820 210, 690 300" stroke="#46E8FF" strokeWidth="3" />
        <path className="thread t2" d="M966 84 C 890 168, 800 236, 650 336" stroke="#7A5CFF" strokeWidth="2.5" />
        <path className="thread t3" d="M972 74 C 918 132, 852 190, 726 276" stroke="#FF6E9C" strokeWidth="2.5" />
        <path className="thread t4" d="M964 90 C 878 182, 792 250, 636 356" stroke="#FFD98A" strokeWidth="2" />
        <path className="thread t5" d="M970 80 C 904 156, 828 220, 700 312" stroke="#F6F7FF" strokeWidth="1.6" />
        {/* one small red thread — the single red in the whole page */}
        <path className="thread t-red" d="M966 86 C 894 150, 610 300, 540 372" stroke="#FF3B3B" strokeWidth="1.4" opacity="0.85" />
      </g>

      {/* the star head */}
      <g className="arrival-head">
        <circle cx="980" cy="70" r="66" fill="url(#starGlow)" filter="url(#soft)" />
        <path
          className="head-scribble"
          d="M980 40 C 998 54, 1006 66, 998 82 C 1014 78, 1020 92, 1008 104 C 1000 118, 984 118, 972 108 C 958 120, 944 110, 950 94 C 938 92, 940 74, 956 72 C 958 54, 968 44, 980 40 Z"
          fill="none" stroke="#F6F7FF" strokeWidth="2.2" strokeLinejoin="round"
        />
        <circle cx="980" cy="72" r="7" fill="#F6F7FF" />
      </g>

      {/* connection — reaches toward the figure but holds a gap (the écart) */}
      <path className="arrival-connect" d="M956 108 C 820 250, 660 360, 556 452" fill="none"
        stroke="#46E8FF" strokeWidth="1.4" strokeDasharray="2 10" opacity="0.7" />

      {/* the figure — a small attentive silhouette at the lower edge */}
      <g className="arrival-figure" transform="translate(512 560)">
        <path d="M18 120 C 12 86, 10 60, 20 34 C 24 20, 34 10, 46 12 C 58 14, 62 26, 60 40
                 C 58 60, 60 92, 56 122 C 44 130, 30 130, 18 120 Z"
              fill="#05060F" stroke="#171A3A" strokeWidth="1" />
        <circle cx="40" cy="8" r="11" fill="#05060F" stroke="#171A3A" strokeWidth="1" />
        {/* the single red ribbon, caught in wind */}
        <path className="figure-ribbon" d="M52 26 C 78 30, 96 22, 120 30" fill="none"
              stroke="#FF3B3B" strokeWidth="2" strokeLinecap="round" />
        {/* the kept mark beside the figure — captivation, remembered */}
        <circle className="figure-mark" cx="112" cy="96" r="5" fill="none" stroke="#FFD98A" strokeWidth="1.6" />
      </g>

      {/* restrained handwritten micro-labels */}
      <text className="arrival-label l1" x="1010" y="60" fill="#9AA0C3">the arrival</text>
      <text className="arrival-label l2" x="600" y="512" fill="#9AA0C3">the afterimage</text>
    </svg>
  );
}

function Hero() {
  return (
    <header className="perc-hero">
      <div className="perc-hero-art"><GreatArrival /></div>
      <div className="perc-hero-copy">
        <p className="perc-eyebrow">Perception engineering</p>
        <h1 className="perc-hero-title">Turn visual captivation into structured action.</h1>
        <p className="perc-hero-sub">
          Semant is a perception engineering workbench — where images become fields,
          marks become citations, writing recalls what it rests on, and models
          propose actions without silently becoming authority.
        </p>
        <div className="perc-cta-row">
          <Link className="perc-btn perc-btn--primary" to="/home">Explore the Workbench</Link>
          <Link className="perc-btn perc-btn--ghost" to="/notes/perceptual-action-grammar">Read the Technical Notes</Link>
          <Link className="perc-btn perc-btn--link" to="/notes">View Research Horizons →</Link>
        </div>
      </div>
    </header>
  );
}

const VERBS = [
  { k: 'Notice', d: 'Say, in plain words, what caught you. Semant turns it into suggested acts — it never claims it saw what you saw.' },
  { k: 'Mark', d: 'Put a field, a trace, or a region on the image: the fall of light, an axis, a drape, a gaze.' },
  { k: 'Compose', d: 'Gather marks into a percept — a reading, not a list. “The arch, held against the shadow.”' },
  { k: 'Cite', d: 'Write a passage that points at the exact marks it rests on. The citation is real, not decorative.' },
  { k: 'Recall', d: 'Replay a percept: the image steps back, its evidence performs in turn, the reading breathes.' },
  { k: 'Challenge', d: 'Argue with a percept from the image itself. Only a person may author a challenge — never a model.' },
  { k: 'Orchestrate', d: 'Freeze the whole working context into one inspectable session a model could be asked to read.' },
];

function WhatSemantDoes() {
  return (
    <section className="perc-section" data-reveal>
      <p className="perc-kicker">What Semant does</p>
      <h2 className="perc-h2">Seven verbs, one surface.</h2>
      <p className="perc-lede">
        Something catches your eye. Today that moment goes into a caption a model wrote,
        or a rectangle you drew. Semant gives it somewhere better to go — acts you can
        inspect, edit, and take back.
      </p>
      <div className="perc-verbs">
        {VERBS.map((v) => (
          <div className="perc-verb" key={v.k}>
            <h3>{v.k}</h3>
            <p>{v.d}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

const WORKBENCH = [
  { t: 'Differential', s: 'built', d: 'The image-side perception workshop. You say what caught you; it offers acts; your hand places the geometry. Marks become grounds, grounds become percepts.' },
  { t: 'Manuscript', s: 'emerging', d: 'The writing-side multimodal field. A sentence can be asked what it cites — and answer honestly, including “nothing.” No green ticks.' },
  { t: 'Atlas & Codex', s: 'horizon', d: 'Comparative and time surfaces — percepts held together across many images and across time. Being explored.' },
];
const ENGINE = [
  { t: 'Perceptual Action Grammar', s: 'built', d: 'A closed vocabulary of perceptual acts. Every proposal is validated; an invalid one is refused, not “mostly kept.”' },
  { t: 'Attunement Planner', s: 'built', d: 'Turns what caught you into suggested acts, carrying the words it keyed on. It reads “gaze” and offers to mark one — it never claims it saw one.' },
  { t: 'Visual Marks', s: 'built', d: 'A renderer-independent truth. A drawn line is a view of a mark, never the other way around.' },
  { t: 'Suggestion Quarantine', s: 'built', d: 'Accepting a model suggestion mints a new mark pointing back at it — an approval can never be laundered into your own decision.' },
  { t: 'Orchestration Session', s: 'emerging', d: 'Freezes the whole ask into one inspectable request that can refuse an invalid one without spending anything.' },
  { t: 'Provenance & Recall', s: 'built', d: 'Every mark can say what it is; a percept can re-perform itself from the writing that mentions it.' },
];

function WorkbenchEngine() {
  return (
    <section className="perc-section" data-reveal>
      <div className="perc-split">
        <div>
          <p className="perc-kicker">The Workbench</p>
          <h2 className="perc-h2">Where seeing is performed.</h2>
          <div className="perc-cards">
            {WORKBENCH.map((c) => (
              <div className="perc-card" key={c.t}>
                <div className="perc-card-head"><h3>{c.t}</h3><StatusChip status={c.s} /></div>
                <p>{c.d}</p>
              </div>
            ))}
          </div>
        </div>
        <div>
          <p className="perc-kicker">The Engine</p>
          <h2 className="perc-h2">A small, strict engine.</h2>
          <div className="perc-cards">
            {ENGINE.map((c) => (
              <div className="perc-card" key={c.t}>
                <div className="perc-card-head"><h3>{c.t}</h3><StatusChip status={c.s} /></div>
                <p>{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

const AUDIENCE = [
  ['Fashion designers', 'Build a moodboard-with-reasoning: mark why a garment works, part by part.'],
  ['Filmmakers & directors', 'Read a frame’s gaze, axis, and light as marks; keep a shot’s reasoning, not just a screenshot.'],
  ['Writers', 'Compose passages that genuinely rest on what you saw — and can prove it.'],
  ['Artists', 'Treat an image as an instrument: fields, traces, negative space, rhythm — the felt parts, named.'],
  ['Researchers', 'Accumulate percepts and their evidence into something inspectable and comparable.'],
  ['Curators', 'Turn a stream of captivation into a structured, citable body of looking.'],
  ['Architects & designers', 'Mark axes, thresholds, and recession; read how an image builds its space.'],
  ['AI builders & agents', 'A grammar and a session that let models act on seeing without becoming its authority.'],
];

function AudienceCards() {
  return (
    <section className="perc-section" data-reveal>
      <p className="perc-kicker">Who it is for</p>
      <h2 className="perc-h2">Anyone whose work begins in being caught by an image.</h2>
      <div className="perc-audience">
        {AUDIENCE.map(([t, d]) => (
          <div className="perc-aud" key={t}><h3>{t}</h3><p>{d}</p></div>
        ))}
      </div>
    </section>
  );
}

function PerceptionEngineering() {
  return (
    <section className="perc-band" data-reveal>
      <p className="perc-kicker perc-kicker--light">Perception engineering</p>
      <p className="perc-claim">
        Agentic engineering gave language models a grammar of software actions —
        and with a human in the loop, they could <em>do</em> software work.
        Seeing never got that layer.
      </p>
      <p className="perc-claim perc-claim--accent">
        Perception engineering gives humans, models, and agents access to <em>situated seeing</em> —
        with a provenance for every mark, a session that can refuse a bad request, and a hard
        line between a suggestion and evidence.
      </p>
    </section>
  );
}

const PHIL = [
  ['Embodied cognition', 'Perception is something you do — so the core unit is an act, not a label.'],
  ['Phenomenology (Merleau-Ponty)', 'Seeing happens across a gap — so a percept holds a reading against its evidence, never collapsing into it.'],
  ['Gestalt figure-ground', 'Meaning lives in what isn’t there — so negative space is a field you can mark.'],
  ['Gaze studies', 'Where a look goes is data — so gaze and address are traces you can draw and cite.'],
  ['Architecture of perception', 'Light, surface, threshold, recession build a felt space — so they are field roles, not afterthoughts.'],
  ['Assemblage (Deleuze / DeLanda)', 'A reading is parts held in relation — so relations are their own marks.'],
];

function ResearchPhilosophy() {
  return (
    <section className="perc-section" data-reveal>
      <p className="perc-kicker">Research &amp; philosophy</p>
      <h2 className="perc-h2">Each idea earns its place by becoming a capability.</h2>
      <div className="perc-phil">
        {PHIL.map(([t, d]) => (
          <div className="perc-phil-row" key={t}>
            <h3>{t}</h3><p>{d}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function FeatureArticles() {
  return (
    <section className="perc-section" data-reveal>
      <p className="perc-kicker">Feature notes</p>
      <h2 className="perc-h2">The view from altitude has depth beneath it.</h2>
      <div className="perc-notes-grid">
        {FIELD_NOTES.map((n) => (
          <Link className="perc-note-card" to={`/notes/${n.slug}`} key={n.slug}>
            <div className="perc-card-head">
              <span className="perc-note-cat">{CATEGORY_LABEL[n.category]}</span>
              <StatusChip status={n.status} />
            </div>
            <h3>{n.title}</h3>
            <p>{n.summary}</p>
            <span className="perc-note-more">Read the note →</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

const FORMS = [
  ['Web workbench', 'built', 'The Differential and the Manuscript, in the browser.'],
  ['Desktop studio', 'horizon', 'A perception cockpit: a coding studio crossed with an orchestration workspace.'],
  ['CLI', 'horizon', 'The grammar and the session for technical users and automation — scriptable, inspectable.'],
  ['Phone', 'horizon', 'Everyday capture: catch an image, mark what caught you, let the reading grow later.'],
  ['Agent engine / API', 'horizon', 'The same grammar offered to agents — acting on seeing through the same guardrails a person does.'],
];

function ProductForms() {
  return (
    <section className="perc-section" data-reveal>
      <p className="perc-kicker">Product forms</p>
      <h2 className="perc-h2">One workbench, several doors.</h2>
      <div className="perc-forms">
        {FORMS.map(([t, s, d]) => (
          <div className="perc-form" key={t}>
            <div className="perc-card-head"><h3>{t}</h3><StatusChip status={s} /></div>
            <p>{d}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function FooterAfterimage() {
  return (
    <footer className="perc-after" data-reveal>
      <p className="perc-after-lede">
        Most tools want to tell you what an image <em>is</em>. Semant is building something
        quieter: an interface where perception can be marked, questioned, remembered, and
        returned — where the thing that caught you becomes an instrument you can think with.
      </p>
      <p className="perc-after-line">Semant — where images become instruments for thought.</p>
      <div className="perc-cta-row perc-cta-row--center">
        <Link className="perc-btn perc-btn--primary" to="/home">Explore the Workbench</Link>
        <Link className="perc-btn perc-btn--ghost" to="/notes">Read the Field Notes</Link>
      </div>
    </footer>
  );
}

export default function LandingPage() {
  useReveal();
  return (
    <div className="perc-landing">
      <Hero />
      <WhatSemantDoes />
      <WorkbenchEngine />
      <AudienceCards />
      <PerceptionEngineering />
      <ResearchPhilosophy />
      <FeatureArticles />
      <ProductForms />
      <FooterAfterimage />
    </div>
  );
}
