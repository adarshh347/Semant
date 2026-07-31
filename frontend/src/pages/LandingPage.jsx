import React from 'react';
import NearArrival from '../components/scene/NearArrival.jsx';
// Playfair Display — the landing's display serif, self-hosted and subset to
// latin (it only ever appears at display sizes). Landing-only, so it rides in
// the landing's lazy chunk rather than the app-wide bundle. Weights used: 400
// (normal + italic) and 500 (normal).
import '@fontsource/playfair-display/latin-400.css';
import '@fontsource/playfair-display/latin-400-italic.css';
import '@fontsource/playfair-display/latin-500.css';
import './LandingPage.css';

// Verb glyphs are INLINED as components — as <img> their scoped
// `#g-verb-*:hover .gest` gestures could never fire (an <img> is a black box to
// host hover). Everything else stays a fixed URL asset.
import { ReactComponent as VerbNotice } from '@/assets/glyphs/15-verb-notice.svg';
import { ReactComponent as VerbMark } from '@/assets/glyphs/16-verb-mark.svg';
import { ReactComponent as VerbCompose } from '@/assets/glyphs/17-verb-compose.svg';
import { ReactComponent as VerbCite } from '@/assets/glyphs/18-verb-cite.svg';
import { ReactComponent as VerbRecall } from '@/assets/glyphs/19-verb-recall.svg';
import { ReactComponent as VerbChallenge } from '@/assets/glyphs/20-verb-challenge.svg';
import { ReactComponent as VerbOrchestrate } from '@/assets/glyphs/21-verb-orchestrate.svg';

// Fixed glyph + diagram URLs (favicon-harsh mode) for everything shown as
// <img>/<object>: no host CSS reaches them, and none needs to.
const GLYPH_URLS = import.meta.glob('../assets/glyphs/*.svg', { query: '?url', import: 'default', eager: true });
const DIAGRAM_URLS = import.meta.glob('../assets/diagrams/*.svg', { query: '?url', import: 'default', eager: true });
const g = (file) => GLYPH_URLS[`../assets/glyphs/${file}`];
const d = (file) => DIAGRAM_URLS[`../assets/diagrams/${file}`];

// One hue per section, stated three ways (wash · eyebrow tick · strip dots).
// Enforced HERE, in one place, via the `--sec` custom property.
function Section({ id, hue, className = '', style, children }) {
  return (
    <section id={id} className={className} style={{ '--sec': `var(--${hue})`, ...style }}>
      {children}
    </section>
  );
}

// A hand-drawn wobble rule between bands (verbatim paths from the source).
function Rule({ base, accent }) {
  return (
    <div className="wrap">
      <svg className="rule" viewBox="0 0 1000 12" preserveAspectRatio="none">
        <path d={base} />
        <path className="a" d={accent} />
      </svg>
    </div>
  );
}

// The fixed drawing-sheet ground: stationary grain, margin guides, corner crop
// ticks and a few construction marks parked in the outer margins.
function PageGround() {
  return (
    <div className="bg" aria-hidden="true">
      <svg className="bg-grain" xmlns="http://www.w3.org/2000/svg">
        <filter id="pageGrain">
          <feTurbulence type="fractalNoise" baseFrequency="0.7" numOctaves="3" stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#pageGrain)" />
      </svg>
      <div className="bg-guides"><i /><i /></div>
      <span className="bg-crop tl" /><span className="bg-crop tr" />
      <span className="bg-crop bl" /><span className="bg-crop br" />

      <svg className="bg-mark" style={{ top: '16%', left: '2.2%' }} width="16" height="16" viewBox="0 0 16 16">
        <g fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round">
          <path d="M8 2 V14" /><path d="M2 8 H14" /></g>
      </svg>
      <svg className="bg-mark" style={{ top: '47%', right: '2.4%' }} width="14" height="14" viewBox="0 0 14 14">
        <g fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round">
          <path d="M3 3 L11 11" /><path d="M11 3 L3 11" /></g>
      </svg>
      <svg className="bg-mark" style={{ top: '72%', left: '2.6%' }} width="18" height="10" viewBox="0 0 18 10">
        <path d="M1 5 H17" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
      </svg>
      <svg className="bg-mark" style={{ top: '30%', right: '2%' }} width="10" height="14" viewBox="0 0 10 14">
        <path d="M5 1 V13" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeDasharray="2 3" />
      </svg>
      <svg className="bg-mark" style={{ top: '88%', right: '3%' }} width="14" height="14" viewBox="0 0 14 14">
        <circle cx="7" cy="7" r="2.2" fill="currentColor" />
      </svg>
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="pe-scope landing">
      <PageGround />

      {/* ══ §0 HERO ══ */}
      <Section id="top" hue="indigo" className="hero">
        <div className="wrap">
          <div className="heroText">
            <div className="eyebrow mono"><span className="tk" /><span>Perception engineering</span></div>
            <h1>Perception is not a prompt.</h1>
            <p className="lede" style={{ marginTop: 22 }}>It is something that arrives, catches, and reorganises attention.</p>
            <p className="tight">Semant is a workbench for turning what a model and a person see into marks that can be inspected, argued with, and returned to.</p>
            <div className="cta">
              <a className="pill" href="#workbench">Enter the Workbench →</a>
              <a className="ghost" href="#runtime">Read Thesis-001</a>
            </div>
          </div>
          <figure className="heroScene">
            <NearArrival />
          </figure>
        </div>
      </Section>

      <Rule base="M2 7 C180 5.6 420 7.6 640 6.2 C800 5.2 900 7 998 5.8" accent="M498 2.4 C499 5.4 499.6 7.2 500.4 10" />

      {/* ══ §1 PROBLEM ══ */}
      <Section id="problem" hue="mulberry">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§1 · Visual intelligence under pressure</span></div>
          <h2>Machine vision does not fail evenly.</h2>
          <p className="lede">It is most comfortable when seeing resolves to a nameable, bounded thing.</p>
          <p>Images also contain intervals, diffuse fields, fine parts, directional pressures, and relationships that do not coincide with object boundaries. These are often where creative inquiry actually begins.</p>

          <div className="cards c2" style={{ marginTop: 34 }}>
            <div className="panel">
              <div className="hd">A related grounding fault line</div>
              <div className="bars">
                <div className="bar"><span className="k">Area</span><span className="t"><i style={{ width: '88%', background: 'var(--indigo)' }} /></span></div>
                <div className="bar"><span className="k">Object</span><span className="t"><i style={{ width: '64%', background: 'var(--amethyst)' }} /></span></div>
                <div className="bar"><span className="k">Part</span><span className="t"><i style={{ width: '38%', background: 'var(--mulberry)' }} /></span></div>
                <div className="bar"><span className="k">Space</span><span className="t"><i style={{ width: '26%', background: 'var(--clay)' }} /></span></div>
              </div>
              <div className="axis"><span>Stronger grounding</span><span>Weaker</span></div>
              <p style={{ fontSize: 13, marginTop: 18 }}>Multi-level 3D grounding shows the same shape of failure: systems do substantially worse when the referent is unoccupied space or a fine-grained part rather than a comfortably bounded object. Shown qualitatively here.
                <a href="#" className="mono" style={{ color: 'var(--plum)', textDecoration: 'none', whiteSpace: 'nowrap' }}> Model tables → <span className="todo">todo</span></a></p>
            </div>
            <div className="panel">
              <div className="hd">What a painting may ask of us</div>
              <p style={{ fontSize: 13, marginBottom: 14 }}>Not only:</p>
              <p className="quote">“Which objects are present?”</p>
              <p style={{ fontSize: 13, margin: '18px 0 14px' }}>But:</p>
              <p className="quote">“Where does pressure gather?”<br />“What path carries the action?”<br />“Which interval holds the image?”</p>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', marginTop: 44 }}>
            <svg width="180" height="18" viewBox="0 0 180 18" aria-label="the unresolved gap">
              <g fill="none" stroke="#1E1A1C" strokeWidth="2" strokeLinecap="round" opacity=".5">
                <path d="M4 10.4 C20 9.4 44 10.6 68 9.6" /><path d="M112 10.2 C136 9.2 160 10.4 176 9.4" />
              </g>
            </svg>
          </div>
        </div>
      </Section>

      {/* ══ §2 EVIDENCE ══ */}
      <Section id="evidence" hue="clay" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§2 · An answer is not yet evidence</span></div>
          <div className="cards c2">
            <div className="panel">
              <div className="hd">Ordinary multimodal answer</div>
              <p className="flow">image → model → caption</p>
              <p className="quote" style={{ marginTop: 14 }}>“Movement rises toward the bright sky.”</p>
              <p style={{ fontSize: 13, marginTop: 16 }}>Where did that reading come from? What counters it? What can be revised?</p>
            </div>
            <div className="panel">
              <div className="hd">Semant trace</div>
              <p className="flow">image → inquiry → grounds<br />&nbsp;&nbsp;↳ local evidence<br />&nbsp;&nbsp;&nbsp;&nbsp;↳ supported percept</p>
              <p className="quote" style={{ marginTop: 14 }}>“Upward-right pull, supported by path_07 and field_12; countered by the lower cloud mass in relation_03.”</p>
            </div>
          </div>
          <p className="lede" style={{ marginTop: 30, maxWidth: '60ch' }}>Prose communicates the perception. Evidence keeps the seeing inspectable.</p>
        </div>
      </Section>

      <Rule base="M2 6 C210 7.4 400 5.4 610 6.8 C790 8 900 5.8 998 7" accent="M320 2.4 C321.2 5.4 321.8 7.4 322.4 10.2" />

      {/* ══ §3 VERBS ══ */}
      <Section id="verbs" hue="amethyst">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§3 · What Semant does</span>
            <a className="far mono" href="#" style={{ textDecoration: 'none' }}>Verb sheet →</a></div>
          <h2>Seven acts.</h2>
          <p className="tight">Each is a thing you can do to an image and to what has already been said about it.</p>

          <div className="cards c4" style={{ marginTop: 30 }}>
            <div className="card door"><VerbNotice className="g sm" /><span className="lbl">Notice</span><p>Something catches, before it has a name.</p></div>
            <div className="card door"><VerbMark className="g sm" /><span className="lbl">Mark</span><p>Put a deliberate trace where it caught.</p></div>
            <div className="card door"><VerbCompose className="g sm" /><span className="lbl">Compose</span><p>Bring separate evidence into one reading.</p></div>
            <div className="card door"><VerbCite className="g sm" /><span className="lbl">Cite</span><p>Keep the claim tied to what it came from.</p></div>
            <div className="card door"><VerbRecall className="g sm" /><span className="lbl">Recall</span><p>Find the mark again, later, elsewhere.</p></div>
            <div className="card door"><VerbChallenge className="g sm" /><span className="lbl">Challenge</span><p>Put a reading under pressure without deleting it.</p></div>
            <div className="card door"><VerbOrchestrate className="g sm" /><span className="lbl">Orchestrate</span><p>Run several attempts and compare what they leave.</p></div>
            <div className="card door" style={{ justifyContent: 'center' }}>
              <span className="lbl" style={{ color: 'var(--plum)' }}>Live</span>
              <p>These animate on hover. <a href="#" style={{ color: 'var(--plum)' }}>Open the verb sheet →</a></p>
            </div>
          </div>
        </div>
      </Section>

      {/* ══ §4 WORKBENCH ══ */}
      <Section id="workbench" hue="lilac">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§4 · The Workbench</span><span className="far mono">Working surfaces</span></div>
          <h2>Three surfaces, one state.</h2>
          <p className="tight">This is where Semant is a product rather than a thesis.</p>

          <div className="cards c3" style={{ marginTop: 30 }}>
            <div className="card">
              <img className="g" src={g('07-differential.svg')} alt="" />
              <h3>Differential</h3>
              <p className="claim">Dissect, brush, trace and relate visual evidence.</p>
              <p>Cuts that follow perception rather than the object boundary, and a rail of everything you have inspected.</p>
              <object className="mini" type="image/svg+xml" data={d('specimen-differential.svg')} aria-label="Differential specimen" />
              <div className="strip"><span className="d" style={{ background: 'var(--amethyst)' }} /><span>open field →</span></div>
            </div>
            <div className="card">
              <img className="g" src={g('08-manuscript.svg')} alt="" />
              <h3>Manuscript</h3>
              <p className="claim">Write with the evidence still attached to its visual origin.</p>
              <p>A citation is not a footnote here; it is a live tether back to the region it was drawn from.</p>
              <object className="mini" type="image/svg+xml" data={d('specimen-manuscript.svg')} aria-label="Manuscript specimen" />
              <div className="strip"><span className="d" style={{ background: 'var(--mulberry)' }} /><span>open writing →</span></div>
            </div>
            <div className="card">
              <img className="g" src={g('09-atlas.svg')} alt="" />
              <h3>Atlas</h3>
              <p className="claim">Hold percepts across images and across time.</p>
              <p>The same mark, found again in another picture, months later, without having been renamed.</p>
              <object className="mini" type="image/svg+xml" data={d('specimen-atlas.svg')} aria-label="Atlas specimen" />
              <div className="strip"><span className="d" style={{ background: 'var(--clay)' }} /><span>open atlas →</span></div>
            </div>
          </div>
        </div>
      </Section>

      <Rule base="M2 6.8 C240 5.6 460 7.4 660 6 C820 5 910 6.8 998 6.2" accent="M712 2.6 C713 5.6 713.6 7.6 714.2 10.4" />

      {/* ══ §5 SUBSTRATE ══ */}
      <Section id="substrate" hue="indigo">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§5 · The Perceptual Substrate</span><span className="far mono">Technical core</span></div>
          <h2>Six invariants.</h2>
          <p className="tight">The Workbench is held together by a small set of architectural invariants — each able to survive a change of implementation.</p>

          <div className="cards c3" style={{ marginTop: 30 }}>
            <div className="card">
              <img className="g" src={g('01-perceptual-state.svg')} alt="" />
              <h3>Perceptual State</h3>
              <p className="claim">Evidence has identity before it has a name.</p>
              <p>Something inside the picture can be pointed at, held, and changed — without losing the print it came from.</p>
              <img className="mini" src={d('mini-state-chain.svg')} alt="" />
              <div className="strip"><span className="d" style={{ background: 'var(--amethyst)' }} /><span>source → region → ground → percept → mention</span></div>
            </div>
            <div className="card">
              <img className="g" src={g('02-ground-ontology.svg')} alt="" />
              <h3>Ground Ontology</h3>
              <p className="claim">Not everything worth seeing is an object.</p>
              <p>A blot, a scatter, a stroke, a pairing — four kinds of evidence that will not fit the same drawer.</p>
              <img className="mini" src={d('mini-ground-types.svg')} alt="" />
              <div className="strip"><span className="d" style={{ background: 'var(--indigo)' }} /><span>region · field · path · boundary · relation · constellation</span></div>
            </div>
            <div className="card">
              <img className="g" src={g('03-operation-grammar.svg')} alt="" />
              <h3>Operation Grammar</h3>
              <p className="claim">Which acts are permitted, and on what.</p>
              <p>Preconditions, directed attention, tool selection — and a refusal when the evidence will not support the act.</p>
              <img className="mini" src={d('mini-fail-closed.svg')} alt="" />
              <div className="strip"><span className="d" style={{ background: 'var(--mulberry)' }} /><span>attune · select ground · operate · bind</span></div>
            </div>
            <div className="card">
              <img className="g" src={g('04-stateful-lineage.svg')} alt="" />
              <h3>Stateful Lineage</h3>
              <p className="claim">Identity survives the turn.</p>
              <p>A mark keeps its identity across crops, turns, models, manuscripts and comparisons.</p>
              <img className="mini" src={d('mini-lineage-turns.svg')} alt="" />
              <div className="strip"><span className="d" style={{ background: 'var(--clay)' }} /><span>origin → turn → turn → recall</span></div>
            </div>
            <div className="card">
              <img className="g" src={g('05-epistemic-control.svg')} alt="" />
              <h3>Epistemic Control</h3>
              <p className="claim">More than one reading may deserve to be kept.</p>
              <p>Uncertainty, counterevidence, quarantine, revision and human veto — disagreement held open, not resolved away.</p>
              <img className="mini" src={d('mini-two-readings.svg')} alt="" />
              <div className="strip"><span className="d" style={{ background: 'var(--lilac)' }} /><span>challenge · quarantine · revise · retain</span></div>
            </div>
            <div className="card">
              <img className="g" src={g('06-passage-execution.svg')} alt="" />
              <h3>Passage Execution</h3>
              <p className="claim">Every act runs through a bounded passage.</p>
              <p>Manifests, capability routing, actors and execution boundaries. An act that cannot be inspected does not run.</p>
              <img className="mini" src={d('mini-passage.svg')} alt="" />
              <div className="strip"><span className="d" style={{ background: 'var(--amethyst)' }} /><span>manifest · route · execute · replay</span></div>
            </div>
          </div>
        </div>
      </Section>

      {/* ══ §6 RUNTIME ══ */}
      <Section id="runtime" hue="amethyst">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§6 · The Perceptual Runtime</span></div>
          <p><span className="badge">Thesis-001 · architectural horizon</span></p>
          <h2 style={{ marginTop: 20 }}>The Runtime exists to keep the perceptual world open after inference.</h2>
          <p className="tight">A stateful execution environment for visual evidence. Humans, language models, vision-language models and specialist systems can inspect, transform, contest and reuse the same perceptual state without reducing it to a caption.</p>
          <p className="tight" style={{ fontSize: 13.5 }}>This is a thesis, not shipped infrastructure. The substrate above is what exists today; the Runtime is what it is being built toward.</p>

          <figure className="figure" style={{ margin: 0 }}>
            <object type="image/svg+xml" data={d('section-runtime.svg')} aria-label="The Perceptual Runtime" />
            <figcaption>Fig. 1 — four kinds of actor, one bounded runtime, one chain of state, three surfaces that read it</figcaption>
          </figure>
          <p style={{ marginTop: 22 }}><a className="ghost" href="#">Read Thesis-001 <span className="todo">todo</span></a></p>
        </div>
      </Section>

      {/* ══ §7 REHEARSAL ══ */}
      <Section id="rehearsal" hue="mulberry">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§7 · Rehearsal</span><span className="far mono">Research method</span></div>
          <h2>Rehearsal is how an architecture learns what it actually permits.</h2>
          <p className="tight">Semant compares operations, evidence, uncertainty and usefulness across runs — not only the fluency of their final answers. The important idea is not that one run won. It is that different runs leave different evidence, and more than one reading may deserve to be retained.</p>

          <figure className="figure" style={{ margin: 0 }}>
            <object type="image/svg+xml" data={d('section-rehearsal.svg')} aria-label="Rehearsal" />
            <figcaption>Fig. 2 — one inquiry, three runs, one quarantine, two retentions, and the challenge that revises the grammar</figcaption>
          </figure>

          <p className="mono" style={{ marginTop: 26, lineHeight: 2.2, color: 'rgba(30,26,28,.4)', maxWidth: 'none' }}>
            Geometric correctness &nbsp;·&nbsp; evidence coverage &nbsp;·&nbsp; operation choice &nbsp;·&nbsp; calibrated uncertainty<br />
            Cross-image recall &nbsp;·&nbsp; human usefulness &nbsp;·&nbsp; disagreement quality
          </p>
        </div>
      </Section>

      {/* ══ §8 PERCEPTION ENGINEERING ══ */}
      <Section id="pe" hue="plum">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§8 · Perception engineering</span></div>
          <h2>Seeing becomes engineerable when its operations can be directed, inspected, contested, rehearsed, and remembered.</h2>

          <figure className="figure" style={{ margin: 0 }}>
            <object type="image/svg+xml" data={d('section-perception-engineering.svg')} aria-label="Perception engineering" />
            <figcaption>Fig. 3 — hover to let the stroke arrive · one pass, then it rests</figcaption>
          </figure>
        </div>
      </Section>

      {/* ══ §9 QUESTIONS ══ */}
      <Section id="questions" hue="clay">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§9 · Open research questions</span></div>
          <div className="qs">
            <div className="q"><span className="n">01</span><span className="t">Can a system preserve one selected Ground across twenty turns?</span></div>
            <div className="q"><span className="n">02</span><span className="t">Can it recognise when the question concerns a Field rather than an object?</span></div>
            <div className="q"><span className="n">03</span><span className="t">Can it trace directional pressure without inventing a thing?</span></div>
            <div className="q"><span className="n">04</span><span className="t">Can it expose a useful disagreement with inspectable counterevidence?</span></div>
          </div>
          <p style={{ marginTop: 26 }}><a className="ghost" href="#">View the capability matrix <span className="todo">todo</span></a></p>
        </div>
      </Section>

      <Rule base="M2 7.2 C240 6 460 7.8 660 6.4 C820 5.4 910 7.2 998 6.6" accent="M604 2.6 C605 5.6 605.6 7.6 606.2 10.4" />

      {/* ══ §10 ARTICLES ══ */}
      <Section id="articles" hue="lilac">
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>§10 · Writing</span><span className="far mono">Six pieces</span></div>
          <h2>The long form.</h2>
          <p className="tight">Each article opens one of the doors above and goes further than the landing page can. Glyphs are reused from the library rather than invented per article — an article about grounds carries the tray.</p>

          <div className="artlist">
            <a className="art" href="#">
              <img src={g('02-ground-ontology.svg')} alt="" />
              <span className="n mono">01</span>
              <span className="body">
                <span className="t">The grounding fault line</span>
                <span className="s">Where multi-level grounding breaks down, what the published numbers actually say, and why the weak cases are the interesting ones.</span>
              </span>
              <span className="k mono">Research note <span className="todo">todo</span></span>
            </a>
            <a className="art" href="#">
              <img src={g('18-verb-cite.svg')} alt="" />
              <span className="n mono">02</span>
              <span className="body">
                <span className="t">An answer is not yet evidence</span>
                <span className="s">On the difference between a fluent caption and a reading you can take apart, and why the second is harder to fake.</span>
              </span>
              <span className="k mono">Essay <span className="todo">todo</span></span>
            </a>
            <a className="art" href="#">
              <img src={g('01-perceptual-state.svg')} alt="" />
              <span className="n mono">03</span>
              <span className="body">
                <span className="t">Addressing what has no name yet</span>
                <span className="s">Identity for visual evidence before anyone has decided what it is — and what breaks if you skip that step.</span>
              </span>
              <span className="k mono">Technical <span className="todo">todo</span></span>
            </a>
            <a className="art" href="#">
              <img src={g('05-epistemic-control.svg')} alt="" />
              <span className="n mono">04</span>
              <span className="body">
                <span className="t">Keeping the disagreement</span>
                <span className="s">Quarantine, counterevidence and human veto. Why a system that resolves every conflict is less useful than one that files them.</span>
              </span>
              <span className="k mono">Essay <span className="todo">todo</span></span>
            </a>
            <a className="art" href="#">
              <img src={g('21-verb-orchestrate.svg')} alt="" />
              <span className="n mono">05</span>
              <span className="body">
                <span className="t">Rehearsal</span>
                <span className="s">The evaluation design: what is compared across runs, what counts as a good disagreement, and where the method is still weak.</span>
              </span>
              <span className="k mono">Method <span className="todo">todo</span></span>
            </a>
            <a className="art" href="#">
              <img src={g('04-stateful-lineage.svg')} alt="" />
              <span className="n mono">06</span>
              <span className="body">
                <span className="t">Perception engineering</span>
                <span className="s">The argument for treating seeing as something with operations, boundaries and a memory — stated plainly, and its objections.</span>
              </span>
              <span className="k mono">Thesis <span className="todo">todo</span></span>
            </a>
          </div>
        </div>
      </Section>

      {/* ══ PHILOSOPHY ══ */}
      <Section id="philosophy" hue="plum" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>A position</span></div>
          <div className="creed">
            <p>A picture is not a list of the things inside it.</p>
            <p>Attention is an operation, and operations can be wrong.</p>
            <p>Evidence that cannot be pointed at is not evidence.</p>
            <p>The interesting readings are the contested ones.</p>
            <p>Nothing worth seeing should have to be seen only once.</p>
          </div>
        </div>
      </Section>

      {/* ══ AUDIENCES ══ */}
      <Section id="audiences" hue="amethyst" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>Who this is for</span></div>
          <div className="cards c4">
            <div className="card door"><img className="g sm" src={g('07-differential.svg')} alt="" /><span className="lbl">Art historians</span><p>Read a painting closely, and keep the reading attached to the canvas.</p></div>
            <div className="card door"><img className="g sm" src={g('02-ground-ontology.svg')} alt="" /><span className="lbl">Researchers</span><p>Probe where a model's grounding actually fails, with evidence you can re-open.</p></div>
            <div className="card door"><img className="g sm" src={g('08-manuscript.svg')} alt="" /><span className="lbl">Writers &amp; critics</span><p>Write from images without losing what the claim was drawn from.</p></div>
            <div className="card door"><img className="g sm" src={g('09-atlas.svg')} alt="" /><span className="lbl">Archives</span><p>Hold a perception across a collection, and find it again years later.</p></div>
          </div>
        </div>
      </Section>

      {/* ══ FORMS ══ */}
      <Section id="forms" hue="indigo" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="eyebrow mono"><span className="tk" /><span>Product forms</span><span className="far mono">One workbench, several doors</span></div>
          <div className="doors" style={{ marginTop: 20 }}>
            <div className="card door" style={{ flex: '1 1 150px' }}><img className="g sm" src={g('10-form-web.svg')} alt="" /><span className="lbl">Web</span></div>
            <div className="card door" style={{ flex: '1 1 150px' }}><img className="g sm" src={g('11-form-desktop.svg')} alt="" /><span className="lbl">Desktop</span></div>
            <div className="card door" style={{ flex: '1 1 150px' }}><img className="g sm" src={g('12-form-cli.svg')} alt="" /><span className="lbl">CLI</span></div>
            <div className="card door" style={{ flex: '1 1 150px' }}><img className="g sm" src={g('13-form-phone.svg')} alt="" /><span className="lbl">Phone</span></div>
            <div className="card door" style={{ flex: '1 1 150px' }}><img className="g sm" src={g('14-form-agent.svg')} alt="" /><span className="lbl">Agent</span></div>
          </div>
        </div>
      </Section>

      {/* ══ FOOTER ══ */}
      <footer>
        <div className="wrap after">
          <span className="line">A perception can pass. A kept mark lets it return.</span>
          <img src={g('19-verb-recall.svg')} width="26" height="26" alt="" />
        </div>
        <div className="wrap" style={{ marginTop: 26, display: 'flex', gap: 22, flexWrap: 'wrap' }}>
          <a className="mono" style={{ textDecoration: 'none' }} href="#">Glyph library →</a>
          <a className="mono" style={{ textDecoration: 'none' }} href="#">Verb sheet →</a>
          <a className="mono" style={{ textDecoration: 'none' }} href="#">Specimen 02 →</a>
        </div>
      </footer>
    </div>
  );
}
