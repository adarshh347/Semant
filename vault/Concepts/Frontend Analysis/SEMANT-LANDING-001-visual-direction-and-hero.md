# SEMANT-LANDING-001 — Visual direction & the "Great Arrival" cinematic hero (spec)

**Status:** design spec (for the frontend pass). No code this round.
**Scope:** the doodle design language for the perception-engineering landing + the full cinematic hero choreography, with SVG/CSS build notes, tokens, asset prompts, and the avoid-list.
**Relationship to current design language:** extends *Paper + Plum* v1.3's discipline (type-led, restrained, one interactive accent) but shifts the register from warm daylight paper to **deep twilight** for the marketing surface. The product UI keeps Paper + Plum; this is the front-door.

---

## 1. The feeling (one paragraph)
A quiet twilight. Enormous negative space. A single small figure near the lower edge, looking up. From the upper-right, an immense hand-drawn meteor arrives — a scribbled luminous head trailing threads that separate into cyan, violet, coral, gold, white. The arrival is at once violent and delicate, drawn with human, uneven, pressure-sensitive lines, as if someone astonished sketched the sky the moment it happened. It should read as **a sophisticated doodle that is almost animation** — not clip-art, not corporate vector, not a film still. The emotional arc: *arrival → astonishment → connection → fragmentation → memory → afterimage.* That arc is also Semant's thesis — a captivation, marked, threaded into meaning, and remembered.

## 2. Doodle language (the mark vocabulary)
Every drawn element is built from these strokes; nothing is a smooth corporate path:
- **Delicate ink lines** — thin, confident, slightly wavering; the primary contour language.
- **Graphite construction marks** — faint straight guide-lines, ticks, light hatching; the "engineering" undertone (perception *engineering*).
- **Wax-crayon / dry-pastel texture** — grainy fills used sparingly inside the meteor head and tail.
- **Translucent fluorescent scribbles** — the tail threads: loose, luminous, overlapping, low-opacity.
- **Restrained luminous grain** — a whole-scene film grain / noise at very low opacity for atmosphere.
- **Human pressure variance** — stroke width breathes along its length (thick→thin), never uniform.
Micro-labels are **handwritten**, tiny, sparse — e.g. a faint "the arrival", "a thread", "the afterimage" beside elements, echoing the product's own marks. Never crowd them.

## 3. Palette (tokens)
Twilight base, luminous accents, one red thread. Proposed CSS variables (marketing scope):
```
--sky-midnight:   #0B1026;   /* deep base, top of sky            */
--sky-indigo:     #171A3A;   /* mid sky                          */
--sky-nearblack:  #05060F;   /* lower sky / vignette             */
--ink-white:      #F6F7FF;   /* brilliant white — headline, star core */
--glow-cyan:      #46E8FF;   /* electric cyan thread             */
--glow-ultra:     #7A5Cff;   /* ultraviolet thread               */
--glow-coral:     #FF6E9C;   /* coral-pink thread                */
--glow-gold:      #FFD98A;   /* pale gold thread / figure rim    */
--accent-red:     #FF3B3B;   /* THE single red thread — used once, tiny */
--graphite:       #9AA0C3;   /* construction marks, micro-labels, at low opacity */
```
Discipline: the sky is 2–3 of the deep tones as a soft vertical gradient; the luminous colours appear **only** in the meteor + threads; **`--accent-red` appears exactly once** (a single ribbon thread on the figure or one thread in the tail) as the eye's secret anchor. Body text = `--ink-white` at ~85%; micro-labels = `--graphite` at ~55%.

## 4. Typography
- **Headline:** editorial serif — **Fraunces** (already in the app), large, tight leading, optical size high; one word or phrase may go *italic* for emphasis (never colour for emphasis).
- **Body / subhead:** a humanist sans (Inter / the app's existing sans), generous line-height, max ~62ch.
- **Micro-labels:** a handwriting face (e.g. Caveat) or hand-lettered SVG paths, tiny, `--graphite`.
- **CTAs:** the app's ink-pill for primary; ghost/underline for secondary + tertiary.

## 5. Layout of the hero
Full viewport (min-height 100svh). A single composition with a **quiet zone** reserved lower-left / lower-center for headline + CTAs, so the meteor's business stays upper-right and the sky's emptiness carries the rest.
- Meteor enters from **upper-right** (~85% x, ~5% y) travelling toward center-left.
- Figure sits **lower edge**, ~8–12% of viewport height, silhouette, off-center (≈ 38% x) so it looks *up and across* at the arrival.
- Headline block occupies the calm lower-left third; CTAs beneath it.
- Everything else is sky + a few faint graphite guide-ticks.

## 6. THE CINEMATIC SEQUENCE — "The Great Arrival"
A ~9–12s choreographed loop-then-settle (plays once on load; a gentle idle drift after). Six movements matched to the emotional arc. Timings are targets for the frontend pass.

**M1 · Arrival (0–2.0s).** Sky fades up from black. A single luminous point appears upper-right and draws its **entry stroke** — an ink line lengthening toward center as if the meteor is being sketched in real time (SVG `stroke-dashoffset` from full→0). Faint graphite guide-line precedes it by a beat (the "construction" under the gesture).

**M2 · Astonishment (2.0–3.5s).** The star **head** blooms: a scribbled wax-crayon core (`--ink-white` center → `--glow-gold` edge) with a soft radial glow. The figure at the lower edge lifts its head (a 2–3° silhouette rotation) and its ribbon catches wind (a single `--accent-red` thread, the only red). A hush: the sky darkens ~5% around the glow (vignette breath).

**M3 · Connection (3.5–5.5s).** A thin luminous line reaches from the meteor toward the figure — *the gaze/address*, the moment of captivation. It does not touch; it holds an **écart** (a gap). This is the thesis rendered: seeing as a relation across a distance, not a grab. Micro-label "the arrival" fades in near the head at low opacity.

**M4 · Fragmentation (5.5–7.5s).** The tail **separates into threads** — cyan, violet, coral, gold, white — each a translucent fluorescent scribble peeling off on its own slightly different path (staggered `stroke-dashoffset`, 120ms apart). Violent-yet-delicate: the threads overshoot and settle. A couple of threads throw off tiny **marks** (short ticks) — the doodle equivalent of the image decomposing into parts.

**M5 · Memory (7.5–9.5s).** Motion calms. The threads' motion eases to near-still; their glow lowers to a resting luminosity. One thread curves back toward the figure and becomes a small **kept mark** beside it — the captivation *remembered as a mark*. Micro-label "the afterimage" fades in.

**M6 · Afterimage (9.5s → idle).** Everything settles into a quiet composed still: the star at rest, threads faint, figure lowered slightly, headline fully legible. Idle state = a very slow drift (threads breathe ±1px, grain shimmers) — barely alive, never busy.

**Reduced motion:** under `prefers-reduced-motion: reduce`, skip M1–M5 entirely and render **M6, the composed afterimage still**, immediately. The static frame is designed to be the strongest single image, so the fallback loses nothing essential (same rule the current landing already follows with `useReveal`).

## 7. Build notes (frontend pass)
- **Technique:** hand-authored **inline SVG** for the meteor, threads, figure, and micro-labels (so strokes are real vector doodles with `stroke-linecap:round`, variable width via `stroke-width` + a few duplicated offset paths for pressure feel). Sky = CSS gradient layers. Grain = a tiled SVG `feTurbulence` noise at ~4% opacity, or a small PNG. Glow = SVG `feGaussianBlur` + `mix-blend-mode: screen`.
- **Animation:** prefer **CSS keyframes + SVG `stroke-dashoffset`** for the draw-on strokes and transforms; reserve JS only for sequencing (a small timeline that toggles classes per movement). No heavy animation library needed; if one is wanted, a tiny timeline (e.g. `motion`/GSAP) is justified only if it stays under budget. Keep it GPU-friendly (`transform`/`opacity` only; avoid animating filters continuously — bake the glow, animate opacity).
- **Performance:** total hero SVG < ~40KB; grain tile cached; pause the idle loop when the hero scrolls out of view (IntersectionObserver, like the existing reveal). Ship a static poster frame (M6) as the SSR/first-paint image so there's never an empty sky.
- **Responsive:** on narrow screens, shrink the meteor's travel, move the headline above the figure, keep the arc legible; never let threads cross the headline text.
- **Accessibility:** the hero is decorative → `role="img"` with an `aria-label` ("A small figure watches a hand-drawn meteor arrive across a twilight sky"); all copy lives in real text nodes over the SVG, never baked into it.

## 8. Reusable doodle system beyond the hero
The section cards reuse the language quietly: each **Engine/Workbench card** carries one tiny single-weight ink motif (a mark, a field swatch of grain, a trace line, a thread) in `--graphite` with at most one luminous accent — echoing the current landing's "one motif per card" discipline, retinted for twilight. The feature-article grid cards each get a distinct 1-glyph doodle (grammar = bracketed tokens; marks = a boxed region with a back-arrow; orchestration = a frozen packet; manuscript = a underlined line with a chip; rehearsal = a score/tick row; perception-engineering = the meteor-in-miniature).

## 9. Asset prompt (for a later image/gen or illustrator pass, if hand-SVG is deferred)
> A sophisticated minimalist **doodle**, hand-drawn with delicate uneven ink lines, faint graphite construction marks, and grainy wax-crayon texture. A deep twilight sky (midnight navy to near-black, soft vertical gradient), enormous negative space. Near the lower edge, a **small attentive figure** (8–12% of frame height) seen as a simple silhouette, hair and coat and a single thin **red ribbon** caught in wind, looking up and to the right. From the upper-right, an **enormous hand-drawn meteor**: a luminous scribbled star-head (white core, pale-gold edge) trailing a tail that **separates into distinct threads of electric cyan, ultraviolet, coral-pink, gold, and white** — translucent fluorescent scribbles, violent yet delicate. A thin luminous line reaches from the meteor toward the figure but **does not touch it** (a held gap). Restrained luminous film grain over everything. Tiny handwritten micro-labels. **No** anime, no realistic portrait, no photographic space, no glossy 3D, no emoji stars, no crowded constellations. Editorial, quiet, luminous, human-drawn.

## 10. Avoid-list (hard)
Anime screenshots · realistic portraits · generic space photography · glossy 3D renders · childish emoji stars · stock illustrations · literal imitation of any existing film · crowded constellations · unreadable decoration · more than one red element · smooth corporate vector paths · animating so much the copy can't be read.

---

*This spec is complete enough to build the hero and the card system in the frontend pass without further art direction; the sequence timings and tokens are the contract.*
