# Semant — Execution Model & New Directions

> How "always-on" work actually happens, the 7-item map, and 12 further
> directions beyond the breadth list. Drafted 2026-06-18.

## A. How "running in the background" really works

Claude (me) runs only during an active turn. There is **no autonomous
hours-long unattended loop**. The effect of "always analyzing, always in queue,
taking feedback" is produced by three cooperating parts:

1. **Backend worker (yours, on Render).** A queue (Mongo collection or Redis) +
   a long-running consumer process that: pulls images → calls Groq →
   stores suggestions → re-reads feedback on the next pass. Runs 24/7,
   independent of me. *This is the real item-3 engine.* I architect + scaffold it.
2. **Scheduled tasks (mine).** Periodic unattended runs (e.g. hourly) that kick
   the pipeline, summarise what's new, and notify you. The "notify me at steps"
   mechanism.
3. **Live artifact dashboard.** A persistent HTML panel you reopen anytime; it
   re-fetches current state. The "present it so I don't have to decode it"
   surface. = item 7.

Division of labor: **I am architect + driver + presenter; the continuous engine
lives in your backend.**

## B. The 7 items, mapped

| # | Item | Mechanism | Lift |
|---|---|---|---|
| 1 | Direction MCQ (what writing you want) | Aletheia prompt + small UI | light |
| 2 | Anatomy button → clickable regions → comment→conversation | segmentation model (SAM-class) in backend + overlay UI | heavy |
| 3 | Always-on research pipeline | backend worker + queue (the 24/7 engine) | heaviest |
| 4 | Semantic embeddings | Atlas Vector Search; foundational | medium |
| 5 | +2 motive articles; item-3 articles in own section | content + frontend | light |
| 6 | Instagram id/description detection | IG oEmbed / Graph API, NOT scraping (ToS) | medium |
| 7 | Live project panel | artifact dashboard | medium |

Suggested order: **7 (panel, makes all else legible) → 4 (embeddings, foundation)
→ 1 (quick win) → 3 (the engine) → 2 / 5 / 6.**

## C. Twelve further directions (beyond the breadth list)

Grouped. Your list was *horizontal* (more features). These add *depth* —
memory, theory, and modes of attention.

### Depth & memory
1. **Aesthetic fingerprint.** Longitudinal self-portrait: what recurs in what
   enchants you (motifs, colour, theme) — a mirror of taste built over months.
2. **Constellation / Atlas view.** Arrange saved images by *affinity*
   (embedding-projected), not chronology; browse by resonance. Model: Aby
   Warburg's **Bilderatlas Mnemosyne** — panels of images clustered by
   recurring emotional gestures ("pathos formulae"). Detect your own pathos
   formulae across the archive. https://brooklynrail.org/2021/02/art_books/Aby-Warburgs-Bilderatlas-Mnemosyne/
3. **Temporal return.** Saved images resurface recontextualised: "you saved
   this 6 months ago — does it still pierce you?" Memory as living, not storage.
4. **Mood / Stimmung search.** Query the archive by atmosphere ("images that feel
   like dusk grief") rather than tags. (Needs embeddings, item 4.)

### Theory-lenses
5. **Erotics mode (Sontag).** A deliberate counter-mode to the interpretive
   lenses: no decoding, pure sensuous attention to the surface, slow reveal.
   "In place of a hermeneutics we need an erotics of art." Keeps the tool from
   over-explaining and killing the image. https://en.wikipedia.org/wiki/Against_Interpretation
6. **Transgression lens (Bataille).** Detect where an image crosses a limit /
   taboo and *why that crossing produces charge* — "the taboo holds the
   transgression in shape." A rigorous frame for your eroticism/transgression
   interest. https://www.thecollector.com/georges-batailles-erotism-religion-death/
7. **Genealogy / afterlife of images (Warburg, Didi-Huberman).** Trace an
   image's ancestors: this pose quotes a Madonna, this light is Caravaggio. A
   visual citation graph — the *Nachleben* (survival) of forms.
8. **Intersubjective gap.** Show how another viewer's lenses read the same image;
   the difference between two gazes is itself a disclosure.

### Modes of attention
9. **Question-only / epoché mode.** An Aletheia that *only* asks ever-sharper
   questions and never answers — phenomenological bracketing of assumptions.
10. **Counter-algorithm / serendipity engine.** Surface images *unlike* what the
    feed pushes; cultivate friction and surprise. Enchantment needs the
    unexpected (Bennett).
11. **The unseen / outside the frame.** Speculate or reconstruct what lies beyond
    the edges; the before/after of the "decisive moment."
12. **Cross-modal translation.** Render an image as a soundscape, colour-field, or
    haptic pattern — disclosure through another sense.

## D. References added this round
- Aby Warburg, *Bilderatlas Mnemosyne* — https://brooklynrail.org/2021/02/art_books/Aby-Warburgs-Bilderatlas-Mnemosyne/
  · overview https://medium.com/@aurora.wiemer/mnemosyne-atlas-by-aby-warburg-87c4c06c6be1
- Susan Sontag, *Against Interpretation* ("erotics of art") — https://en.wikipedia.org/wiki/Against_Interpretation
- Georges Bataille, *Erotism: Death and Sensuality* — https://www.thecollector.com/georges-batailles-erotism-religion-death/
  · taboo/transgression https://epochemagazine.org/76/transgressing-the-taboo-a-comparative-analysis-of-batailles-and-freuds-theoretical-approaches/
