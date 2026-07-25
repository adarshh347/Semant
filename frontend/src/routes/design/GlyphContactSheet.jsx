import React from 'react';
import './GlyphContactSheet.css';

/**
 * Glyph contact sheet — dev-only checkpoint route (/_design/glyphs).
 *
 * A faithful React port of `frontend skills/glyph-contact-sheet.html`. Every
 * glyph is loaded as `<img src=…>` (the URL / `?url` svgr mode), exactly as the
 * source does, so this proves the *asset* layer migrated clean and independent
 * of host CSS. If this renders identically to the source file, everything after
 * it is layout work (per MIGRATION.md, "step 3 is the checkpoint that matters").
 */

// Resolve every glyph to its emitted URL. `?url` sidesteps svgr's component
// transform and gives vite's asset URL — the same "harshest" mode as the source.
const GLYPH_URLS = import.meta.glob('../../assets/glyphs/*.svg', {
  query: '?url', import: 'default', eager: true,
});
const url = (file) => GLYPH_URLS[`../../assets/glyphs/${file}`];

// A hand-drawn wobble rule, verbatim from the source (each has its own path).
function Rule({ base, accent }) {
  return (
    <svg className="rule" viewBox="0 0 1000 12" preserveAspectRatio="none">
      <path d={base} />
      <path className="a" d={accent} />
    </svg>
  );
}

function Card({ file, set, name, anch }) {
  return (
    <div className="card">
      <div className="row">
        <img className="i20" src={url(file)} alt="" />
        <img className="i32" src={url(file)} alt="" />
        <img className="i56" src={url(file)} alt="" />
      </div>
      <p className="set">{set}</p><h2>{name}</h2>
      <p className="anch">{anch}</p>
      <div className="path">glyphs/{file}</div>
    </div>
  );
}

const SUBSTRATE = [
  { file: '01-perceptual-state.svg', set: 'Substrate', name: 'Perceptual State', anch: 'a photographic print, dog-eared' },
  { file: '02-ground-ontology.svg', set: 'Substrate', name: 'Ground Ontology', anch: 'a specimen tray' },
  { file: '03-operation-grammar.svg', set: 'Substrate', name: 'Operation Grammar', anch: 'a hand stamp' },
  { file: '04-stateful-lineage.svg', set: 'Substrate', name: 'Stateful Lineage', anch: 'needle and thread' },
  { file: '05-epistemic-control.svg', set: 'Substrate', name: 'Epistemic Control', anch: 'a bell jar' },
  { file: '06-passage-execution.svg', set: 'Substrate', name: 'Passage Execution', anch: 'a manifest and a slot' },
];
const WORKBENCH = [
  { file: '07-differential.svg', set: 'Workbench', name: 'Differential', anch: 'a print under a loupe · uneven cuts, not boxes' },
  { file: '08-manuscript.svg', set: 'Workbench', name: 'Manuscript', anch: 'a page, a citation chip, a tether out of the text' },
  { file: '09-atlas.svg', set: 'Workbench', name: 'Atlas', anch: 'prints pegged on a wire · the same mark, held across' },
];
const FORMS = [
  { file: '10-form-web.svg', set: 'Form', name: 'Web', anch: 'a browser window with one tab' },
  { file: '11-form-desktop.svg', set: 'Form', name: 'Desktop', anch: 'an open laptop' },
  { file: '12-form-cli.svg', set: 'Form', name: 'CLI', anch: 'a terminal · the cursor is the mark' },
  { file: '13-form-phone.svg', set: 'Form', name: 'Phone', anch: 'a handset' },
  { file: '14-form-agent.svg', set: 'Form', name: 'Agent', anch: 'a plug entering a wall socket · no robot, no sparkle' },
];
const VERBS = [
  { file: '15-verb-notice.svg', set: 'Verb', name: 'Notice', anch: 'a circled thing in the margin' },
  { file: '16-verb-mark.svg', set: 'Verb', name: 'Mark', anch: 'a pen nib' },
  { file: '17-verb-compose.svg', set: 'Verb', name: 'Compose', anch: 'two torn scraps in register' },
  { file: '18-verb-cite.svg', set: 'Verb', name: 'Cite', anch: 'a tether from text back to print' },
  { file: '19-verb-recall.svg', set: 'Verb', name: 'Recall', anch: 'a card index' },
  { file: '20-verb-challenge.svg', set: 'Verb', name: 'Challenge', anch: 'two strokes crossing · neither erased' },
  { file: '21-verb-orchestrate.svg', set: 'Verb', name: 'Orchestrate', anch: 'a brace gathering three runs' },
];

const USING_CODE = `<!-- fixed, portable -->
<img src="glyphs/07-differential.svg" width="32" height="32" alt="">

<!-- inlined, tunable -->
<svg class="glyph"><use href="#g-differential"/></svg>

.glyph        { color: var(--ink); }        /* the ink line */
.glyph        { --tick:   #7B2D6B; }        /* the one plum, on the Semant tick */
.glyph        { --wash-o: 0.18; }           /* pigment planes */
.glyph        { --guide-o:0.16; }           /* graphite construction */

.card:hover   { --wash-o: 0.27; --guide-o: 0.28; }
.ink-only     { --wash-o: 0;    --tick: currentColor; }`;

export default function GlyphContactSheet() {
  return (
    <div className="pe-scope gcs">
      <div className="sheet">
        <div className="eyebrow mono"><span className="tk" /><span>Glyph library &nbsp;·&nbsp; nine files</span></div>
        <h1>Contact sheet</h1>
        <p className="lede">Each glyph is now a standalone file. Nothing on this page is inlined.</p>
        <p className="note">Every mark below is loaded with <code>&lt;img src="glyphs/…svg"&gt;</code>, which is the harshest way to use an SVG — no inherited colour, no cascade, no host CSS. If a glyph survives that, it will survive anywhere: a favicon, a README, a print sheet, a background-image, an OG card.</p>

        <Rule base="M2 7 C180 5.6 420 7.6 640 6.2 C800 5.2 900 7 998 5.8" accent="M498 2.4 C499 5.4 499.6 7.2 500.4 10" />

        <div className="eyebrow mono"><span className="tk" /><span>§5 — The Perceptual Substrate</span></div>
        <div className="grid">
          {SUBSTRATE.map((g) => <Card key={g.file} {...g} />)}
        </div>

        <Rule base="M2 6 C210 7.4 400 5.4 610 6.8 C790 8 900 5.8 998 7" accent="M320 2.4 C321.2 5.4 321.8 7.4 322.4 10.2" />

        <div className="eyebrow mono"><span className="tk" /><span>§4 — The Workbench &nbsp;·&nbsp; new</span></div>
        <p className="note">Three working surfaces, drawn to the same contract. The shared idea across the set: each is a place where evidence is kept attached to where it came from — under a loupe, beside a sentence, along a wire.</p>
        <div className="grid">
          {WORKBENCH.map((g) => <Card key={g.file} {...g} />)}
        </div>

        <Rule base="M2 6.8 C240 5.6 460 7.4 660 6 C820 5 910 6.8 998 6.2" accent="M712 2.6 C713 5.6 713.6 7.6 714.2 10.4" />

        <div className="eyebrow mono"><span className="tk" /><span>Product forms &nbsp;·&nbsp; the doors &nbsp;·&nbsp; new</span></div>
        <p className="note">One workbench, several doors. Each is a literal, nameable surface — a tab, a lid, a prompt, a handset, a socket — and each holds the same mark in the same place, at the same size, with the tick leaving at the same angle. The recipe is legible enough that a sixth door could be drawn by anyone who has seen these five.</p>
        <div className="grid">
          {FORMS.map((g) => <Card key={g.file} {...g} />)}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <p className="set">The recipe</p>
            <p className="anch" style={{ lineHeight: 1.9, margin: 0 }}>a nameable enclosure<br />+ one detail that names the platform<br />+ the mark, mid-left of the interior<br />+ the tick, leaving up-right at 45°<br />+ two planes, off-register<br />+ two graphite crop ticks</p>
          </div>
        </div>

        <Rule base="M2 6.2 C240 7.4 460 5.4 660 6.8 C820 8 910 6 998 6.6" accent="M212 2.6 C213 5.6 213.6 7.6 214.2 10.4" />

        <div className="eyebrow mono"><span className="tk" /><span>Verbs &nbsp;·&nbsp; dynamic micro-glyphs &nbsp;·&nbsp; new</span></div>
        <p className="note">Seven acts. Each carries one gesture written inside its own file, played once on hover or focus and then at rest — nothing loops, and <code>prefers-reduced-motion</code> is honoured in the asset rather than in the page. Shown here as files, so they sit still.</p>
        <div className="grid">
          {VERBS.map((g) => <Card key={g.file} {...g} />)}
          <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <p className="set">The gesture rule</p>
            <p className="anch" style={{ lineHeight: 1.9, margin: 0 }}>one gesture per verb<br />0.65–0.80s, played once<br />never a loop, never on load<br />the mark always lands last<br />reduced motion → the still</p>
          </div>
        </div>

        <Rule base="M2 7.2 C240 6 460 7.8 660 6.4 C820 5.4 910 7.2 998 6.6" accent="M604 2.6 C605 5.6 605.6 7.6 606.2 10.4" />

        <div className="eyebrow mono"><span className="tk" /><span>Using them</span></div>
        <p className="note">As a file, a glyph is fixed. Inlined into the page, it becomes tunable: three custom properties are exposed, and they inherit through <code>&lt;use&gt;</code>, so a hover state on a card can breathe the whole set at once.</p>

        <pre>{USING_CODE}</pre>

        <p className="note" style={{ marginTop: 26 }}>Filter ids are namespaced per file (<code>differential-bA</code>, <code>atlas-bB</code>) so any number of them can be inlined into one document without colliding.</p>
      </div>
    </div>
  );
}
