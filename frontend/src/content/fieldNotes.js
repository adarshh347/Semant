// Semant Field Notes — the six feature articles behind the landing page.
// Bodies are the canonical vault essays, imported verbatim as raw markdown
// (Vite `?raw`) and rendered by <MiniMarkdown/>. Metadata is kept here so the
// landing feature-grid and the article pages share one source of truth.
//
// Status vocabulary (SEMANT-LANDING-001): built · emerging · horizon.

import note01 from './field-notes/01-perceptual-action-grammar.md?raw';
import note02 from './field-notes/02-visual-marks-that-can-be-cited.md?raw';
import note03 from './field-notes/03-orchestration-session.md?raw';
import note04 from './field-notes/04-manuscript-as-multimodal-field.md?raw';
import note05 from './field-notes/05-rehearsal-instead-of-benchmarking.md?raw';
import note06 from './field-notes/06-perception-engineering.md?raw';

export const FIELD_NOTES = [
  {
    slug: 'perceptual-action-grammar',
    title: 'The Perceptual Action Grammar',
    category: 'technical',
    status: 'built',
    summary:
      'A closed vocabulary of the things a curator might do next in an image — so a suggestion arrives as a structured, inspectable, refusable act, not prose or a silent change.',
    body: note01,
  },
  {
    slug: 'visual-marks-that-can-be-cited',
    title: 'Visual Marks That Can Be Cited',
    category: 'technical',
    status: 'built',
    summary:
      'A renderer-independent truth for everything drawn on an image, and a quarantine that stops model suggestions from laundering themselves into evidence.',
    body: note02,
  },
  {
    slug: 'orchestration-session',
    title: 'The Orchestration Session',
    category: 'technical',
    status: 'emerging',
    summary:
      'A pure assembler that freezes the whole working context into one inspectable request that can be refused before anything is spent. Nothing is dispatched — deliberately.',
    body: note03,
  },
  {
    slug: 'manuscript-as-multimodal-field',
    title: 'Manuscript as a Multimodal Field',
    category: 'philosophy',
    status: 'emerging',
    summary:
      'Writing that can be asked what it cites and answer honestly — including “nothing” and “not assessed” — with no green ticks and no fake scores.',
    body: note04,
  },
  {
    slug: 'rehearsal-instead-of-benchmarking',
    title: 'Rehearsal Instead of Benchmarking',
    category: 'research',
    status: 'emerging',
    summary:
      'Situated seeing can’t be scored on a leaderboard. Semant rehearses it — scored runs over real fixtures, a manifest refused before it’s spent.',
    body: note05,
  },
  {
    slug: 'perception-engineering',
    title: 'Perception Engineering',
    category: 'hybrid',
    status: 'horizon',
    summary:
      'Agentic engineering gave language models a grammar of software actions. Perception engineering is the missing layer that gives humans, models, and agents access to situated seeing.',
    body: note06,
  },
];

export const noteBySlug = (slug) => FIELD_NOTES.find((n) => n.slug === slug) || null;

export const CATEGORY_LABEL = {
  technical: 'Technical',
  philosophy: 'Philosophy',
  research: 'Research horizon',
  hybrid: 'Manifesto',
};

export const STATUS_LABEL = {
  built: 'Built',
  emerging: 'Emerging',
  horizon: 'Horizon',
};
