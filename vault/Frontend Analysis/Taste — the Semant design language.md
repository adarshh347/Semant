# Taste — the Semant design language

> Living reference. The **rules that turn our tokens into elegance** (classy, calm, non-messy). Check/​update this as the look evolves. Related: [[Frontend beyond visuals - the orchestrator's lens]], [[Purpose Structure Surface]].
> **North star:** Anthropic's *Claude for teachers* page — big serif, warm paper, muted body, ONE terracotta accent, a hand-drawn illustration, one black pill CTA, oceans of whitespace.
> **The key realisation:** our tokens *already* target this look (Fraunces + warm paper + terracotta + ink). The slop isn't the palette — it's the **application**: too many elements, weak hierarchy, cramped air, the display serif never used big, no illustration. This doc codifies the application rules. **Craft = restraint.**

**Status:** v1 · 2026-07-14 · applies to: landing (Pass 2), then all surfaces. Changelog at the bottom.

---

## 0. Decode of the reference (why it feels elegant)
| What the eye sees | The architectural cause | Our lever |
|---|---|---|
| Calm, expensive, uncluttered | **whitespace + one idea per screen**; few elements, huge margins | `--space-16/24` section padding; cut elements |
| "Editorial", literary | **big serif display**, tight leading + tracking, ink-black | `--font-display` (Fraunces) at `--fs-display`, `--tracking-tight` |
| Warm, human, not techy | **warm paper base + one warm accent**, no gradients | `--bg`/`--surface` + `--accent` (terracotta), nothing else |
| Personality without noise | **one hand-drawn illustration**, organic line | Open-Doodles-style line art (see §4) |
| Clear next step | **a single, high-contrast CTA** (black pill) | one `--ink` pill; secondary = text link |
| Never busy | **strong hierarchy**: 1 display, 1 muted body, 1 eyebrow | the type roles in §2 |

Rule of thumb: **if a screen has more than ~5 distinct visual elements, it's drifting to slop.** Remove before you style.

---

## 1. Colour dynamics
Discipline over palette. The base is warm-neutral; **terracotta is a spice, not a sauce.**

| Role | Token | Light hex | Rule |
|---|---|---|---|
| Page base | `--bg` | `#FBF9F5` | the paper; almost everything sits on this |
| Raised surface | `--surface` / `--surface-2` | `#FFFFFF` / `#F4F1EA` | cards/panels; use sparingly, prefer flat-on-paper |
| Display ink | `--ink` | `#1A1814` | headlines only; max contrast |
| Body ink | `--ink-muted` | `#6F6A61` | **all body copy is muted, not black** — this is the elegance tell |
| Subtle | `--ink-subtle` | `#9C968B` | eyebrows, captions, meta |
| Hairline | `--line` / `--line-strong` | `#E7E2D8` | borders are hairline, rare (border-grammar) |
| **The accent** | `--accent` / `--accent-deep` | `#C4533A` / `#A53F2A` | **ONE per view**: the CTA, or the illustration, or a single mark — not all three |
| Accent wash | `--accent-soft` | `#F7E8E2` | a whole-section tint at most; never many chips |
| Primary action | `--ink` (pill) | `#1A1814` | black pill like the reference; accent is the *secondary* colour, not the button |

Colour theory notes:
- **60 / 30 / 10** here = paper / ink-text / (accent + surfaces). Accent stays near 10%, ideally less.
- **Contrast is hierarchy:** display = full ink; body = muted; meta = subtle. Never body-copy in pure black (reads cheap/heavy).
- **Kill on sight** (slop signals, already on the Track-D kill-list): gradients (except the one defined `--accent-gradient`, used almost never), neon, glow shadows, glassmorphism, >1 accent hue, coloured text for emphasis (use weight/size instead).
- Dark mode ("Ink"): same rules, inverted; accent stays the single warm note against dark paper.

---

## 2. Typography (the biggest elegance lever)
Three roles, held strictly. Most "AI slop" is one font at one size everywhere; elegance is **contrast of size + weight + colour**.

| Role | Family | Size | Weight | Tracking | Colour | Leading |
|---|---|---|---|---|---|---|
| **Display** (hero H1) | `--font-display` Fraunces | `--fs-display` (2.75–4.5rem) | 500–600 | `--tracking-tight` (−0.02em) | `--ink` | **tight** ~1.05 |
| Section head (H2) | `--font-display` | `--fs-h1`/`--fs-h2` | 500 | tight | `--ink` | ~1.1 |
| **Eyebrow / kicker** | `--font-sans` Inter | `--fs-caption` (0.75rem) | 600 | `--tracking-wide` (+0.08em), UPPERCASE | `--ink-subtle` | — |
| **Body** | `--font-sans` Inter | `--fs-body-lg` (1.125rem) | 400 | normal | `--ink-muted` | **1.6** |
| Small / meta | `--font-sans` | `--fs-small` | 400–500 | normal | `--ink-subtle` | 1.5 |
| Data / code accent | `--font-mono` Spline Sans Mono | `--fs-small` | 400 | normal | `--ink-muted` | — |

Rules:
- **Display must be BIG** — the reference headline is ~72px. Timidly-sized serif is the #1 reason our current hero reads flat. Use `--fs-display`, tight leading, let it wrap to 2 lines.
- **Measure:** body max-width **60–68ch** (~34rem). Never full-width paragraphs.
- **One display, one body, one eyebrow per section.** Emphasis = *italic Fraunces* (we loaded the italic axis) or weight — **not** colour, **not** ALL-CAPS body.
- Pairing: Fraunces (display, warm serif) × Inter (UI/body) is exactly the reference pairing — keep it; don't introduce a third face.

---

## 3. Layout & spacing (whitespace is the material)
| Lever | Rule |
|---|---|
| **Section rhythm** | vertical padding `--space-16`→`--space-24` (4–6rem+). Air is the product. |
| **Asymmetry** | hero = text left (≈55%), illustration/image right — like the reference. Avoid dead-centered everything. |
| **One idea per screen** | each scroll section makes *one* point (eyebrow + head + ≤2 sentences + at most one visual). |
| **Alignment** | everything hangs off a left text-column edge; the illustration is the only right-side object. |
| **Density** | generous. If it feels full, delete an element before shrinking spacing. |
| **Borders** | hairline, rare (border-grammar): only panes, the header rule, a focused surface earn a line. |
| **Radii** | `--radius-md/lg` on the few cards; the CTA is a `--radius-pill`. Consistent, not mixed. |
| **Elevation** | mostly flat-on-paper; `--shadow-sm/md` only where something truly lifts. No shadow soup. |

Non-messy = **fewer things, more space, one clear path for the eye** (eyebrow → display → one line → CTA).

---

## 4. Imagery & illustration (where the "taste" sources are)
The reference's warmth comes from **one hand-drawn line illustration** (apple + book) in the accent colour — not stock photos, not 3D, not gradient blobs.

**Two image registers for Semant:**
1. **The real editorial image** (fashion/art) — Semant's actual subject. Treat it with restraint: generous frame, no heavy furniture, our thin region overlays as the only markup. The image *is* the beauty; don't decorate it.
2. **Hand-drawn line illustration** — for the landing/empty/marketing surfaces, in the Open-Doodles register (organic single-weight line + one terracotta fill).

**Open-source sources (verify licence at use):**
| Source | Style | Licence | Use |
|---|---|---|---|
| **Open Doodles** (Pablo Stanley) | loose hand-drawn objects/scenes | **CC0** | closest match to the reference; recolour line to `--ink`, fill to `--accent` |
| **Open Peeps** | sketchy people, mix-and-match | **CC0** | figures for the See·Read·Write panels |
| **unDraw** | minimalist SVG, recolourable | permissive (catch-free) | on-the-fly recolour to our accent hex |
| **Blush** | curated collections | free plan (some attribution) | if a specific set fits; check per-collection |
| Custom / generated line art | our own | ours | a bespoke "reading an image, part by part" motif — the strongest long-term |

Rules: **one illustration per view**, single line weight, `--ink` stroke + one `--accent` fill, sitting in whitespace. No multi-colour vector scenes, no isometric 3D, no emoji, no photographic stock.

---

## 5. Motion (subtle, meaningful)
| Rule | Detail |
|---|---|
| **Purpose only** | motion explains a state change or reveals on scroll; never decorative loops. |
| **Easing** | the one defined curve `--ease` (`cubic-bezier(.22,1,.36,1)`) everywhere. |
| **Duration** | 150–320ms for UI; scroll reveals ~400–600ms. Nothing bouncy/springy-overshoot. |
| **Distance** | rise 8–16px + fade; small. Big slides read cheap. |
| **Scroll storytelling** | See→Read→Write = a scrubbed sequence (GSAP), calm, tied to scroll position. |
| **Respect** | `prefers-reduced-motion` → everything falls back to the static state. |
| Stack | **Motion** (UI/reveals) + **GSAP ScrollTrigger** (scroll demo). No Tailwind-locked effect libs. |

---

## 6. The slop checklist (fail = fix before shipping)
- [ ] Display serif is **big** (`--fs-display`), not timid.
- [ ] Body is `--ink-muted`, measure ≤ ~66ch.
- [ ] **≤1 accent** use per view; primary CTA is the ink pill.
- [ ] Section padding ≥ `--space-16`; the screen breathes.
- [ ] ≤ ~5 distinct elements per section; one idea each.
- [ ] One hand-drawn illustration max; no stock/3D/gradient-blob/emoji.
- [ ] Hairline borders only where earned; no shadow soup, no glass, no neon.
- [ ] Motion subtle, `--ease`, reduced-motion fallback present.
- [ ] Type roles: exactly one display + one body + one eyebrow per section.
- [ ] Nothing centred-by-default; deliberate asymmetry + left text-column.

---

## Changelog (keep this living)
- **v1 · 2026-07-14** — created from the *Claude for teachers* reference + our token audit. Applies to landing Pass 2; extend to Atelier/Loom/feed as they're built.
- _next_ — add per-surface notes (Atelier pane, Loom, feed cards) once designed; capture any token changes here.

---

## 7. Anthropic-site study (d.1) — the next level of minimalism
Decoded from the Anthropic **announcement** pages. This is a *quieter, more confident* register than the teachers page — worth stealing wholesale for our explanatory + editorial surfaces.

| What the eye sees | Architectural cause | Our move |
|---|---|---|
| Serene, almost empty | **centered, single-column announcement**; enormous top whitespace; one headline, one date, one image | use for Read articles, About, changelog, any "statement" page |
| Confident headline | **big bold serif**, near-black, tight leading, centered, 2 lines max | our `--font-display` at `--fs-display`, weight 600, centered variant |
| Tiny loud label | **bold UPPERCASE eyebrow** ("Announcements"), small, ink (not muted) | eyebrow variant: `--fs-caption`, 700, `--tracking-wide`, `--ink` |
| Signature illustration | **a muted-pastel rounded card holding a hand-drawn thick-black-line motif** (globe/objects) — flat, naive, warm | **new illustration register** — see §4 update below |
| Unique "brand" feel in a tiny detail | **a custom peach text-selection highlight** | add a `::selection` token — see §1 update |
| Restraint everywhere | **no shadows, no gradients, flat pastel panels, one line weight** | matches our kill-list; go flatter still |

**The big lesson:** their personality lives in **two cheap, high-signal details** — the *hand-drawn diagram on a pastel card*, and the *peach selection colour*. Neither costs performance; both read as taste. We adopt both.

### 1-update · Colour — add the muted-pastel set + the selection highlight
Anthropic pairs the warm-paper base with a small family of **muted, chalky pastels** used *only as illustration-card backgrounds* (never as text/UI colour):
| Pastel (card bg only) | ~hex | Use |
|---|---|---|
| Sage | `#C6D4C6` | diagram card background |
| Clay/peach | `#EAC7B4` | diagram card background |
| Sky | `#C4D2DD` | diagram card background |
| Wheat | `#E7D9B8` | diagram card background |
- **Rule:** pastels are **backgrounds for hand-drawn diagrams only** — one per card, never on text, buttons, or more than one card in view at once. They're the "warm" without breaking the one-accent rule (terracotta stays the single *interactive* accent).
- **Selection highlight (adopt):** add `--highlight: #F2C9B6;` (soft terracotta-peach) and set `::selection { background: var(--highlight); color: var(--ink); }` site-wide. A unique selection colour is a free, high-taste signal.

### 4-update · Illustration — the pastel-card + hand-drawn-line register (preferred over doodles)
Replace the "generic Open-Doodles" idea for *concept/diagram* spots with Anthropic's register:
- a **flat rounded pastel card** (`--radius-lg`, one pastel bg, no shadow) containing **one hand-drawn, thick single-weight black line motif**.
- For Semant this is perfect for **"dissect an image into parts"** diagrams: a naive line drawing of a garment/figure with a few parts circled + a label line — literally the product's idea, in their style.
- Keep Open Doodles / unDraw (CC0) only for people/empty-state warmth; the **pastel-card hand-drawn diagram is the house diagram style** for See·Read·Write and explainer sections.
- Diagrams should **dissect into short analysis** (their pattern): the drawing + a 1-line reading beside it, not a decorative blob.

---

## 8. Immediate site fixes (d.1) — nav mark, hero image, colour
Concrete corrections to the current build (from the d.1 screenshots of our own landing):

1. **Nav logo mark** — the little dot/symbol beside "Semant" (`.nav-logo-mark`) doesn't fit. Anthropic just sets the **wordmark itself** as the logo (`ANTHROP\C`, no separate icon). **Do the same: drop the dot; set "Semant" in `--font-display`** as the wordmark, one weight, tight tracking. If a mark is ever wanted, it must be a **bespoke on-concept glyph** (a reading/seeing/framed-part mark), never a generic dot/asterisk.
2. **Hero image** — retire `leg-palm.jpg` **and** strip the leftover neon toolbar buttons (Brainstorm/Save/Split→Save/Save-all — the killed BoundingBoxEditor pills) that are pasted over it. Replace with **register-1**: a real editorial image (fashion/art) carrying **only our thin terracotta region overlay** on 2–3 parts — the product's own truth as the hero visual. (Concept diagrams elsewhere use the §4 pastel-card style.)
3. **Colour — be creative but elegant:** base stays warm paper + one terracotta interactive accent; add the muted-pastel cards (§1-update) for diagrams and the peach `::selection`. That's the whole "creative" surface — restraint is the elegance.

---

## Changelog (keep this living)
- **v1 · 2026-07-14** — created from the *Claude for teachers* reference + token audit.
- **v1.1 · 2026-07-14 (d.1)** — added the Anthropic-site study: muted-pastel illustration cards, hand-drawn black-line diagram register, the peach `::selection` highlight, centered-announcement layout, and the immediate nav-mark / hero-image / colour fixes.
- _next_ — per-surface notes (Atelier pane, Loom, feed cards) as they're built.

---

## 9. Semant identity — LOCKED: **Paper + Ultramarine** (the un-Anthropic palette)
**Why:** our old tokens (warm cream + terracotta + serif) *were* Anthropic's palette. We keep the *principles* (minimalism, whitespace, one accent, muted diagram cards, unique selection, hand-drawn line art) but **own the surface**: a warm paper base against a **cool electric ultramarine** accent — warm/cool tension Anthropic doesn't have. **This supersedes every terracotta value in §1 and §7.**

### The signature idea
**Ultramarine = the colour of attention.** It's the accent *and* the colour of our **region-overlay marks** — the thin annotation lines/labels that are Semant's own, un-copyable visual language. Lean on those marks as the brand motif instead of borrowed hand-drawn globes.

### Palette (replaces the accent + pastel rows)
| Role | Token | Value | Note |
|---|---|---|---|
| Page base | `--bg` | `#FAF8F3` | keep the warm paper (invites; contrasts the cool accent) |
| Ink | `--ink` | `#14140F` | display + max contrast |
| Body ink | `--ink-muted` | `#66625A` | all body copy |
| **Accent (the one)** | `--accent` | `#2733CC` | ultramarine — CTAs' *secondary*, links, emphasis, **region marks** |
| Accent deep (hover) | `--accent-deep` | `#1B24A6` | |
| Accent wash | `--accent-soft` | `#E7E9F9` | at most one section tint |
| Accent ink | `--accent-ink` | `#FFFFFF` | text on ultramarine |
| Primary action | `--ink` pill | `#14140F` | black pill stays the primary; ultramarine is the *accent*, not the button |
| **Selection** | `--highlight` | `#DADEF6` | pale-blue `::selection` (our version of the peach detail) |

**Cool diagram-card pastels** (replace the warm sage/clay set — those read Anthropic):
| Card bg | ~hex |
|---|---|
| Sky | `#C9D6E6` |
| Stone | `#DBD8D0` |
| Blue-grey | `#CCD3DE` |
| Pale ultramarine | `#DCE0F5` |

### Type (optional divergence)
Keep **Fraunces** for now (loaded, works). If we want a sharper break from Anthropic's chunky serif later, shift the display to a **higher-contrast editorial serif** (e.g. Newsreader / Spectral / Playfair) — flagged, not required. The ultramarine accent + cool cards + blue selection already carry most of the divergence.

### Scope note (Foundation change)
Swapping `--accent` terracotta→ultramarine in `index.css` **re-skins the whole app** (accent is token-driven). Do it as a deliberate token change and spot-check the main screens (landing, gallery, a post/Atelier), not just the landing.

## Changelog
- **v1 · 2026-07-14** — from the *Claude for teachers* reference + token audit.
- **v1.1 · 2026-07-14 (d.1)** — Anthropic-site study: pastel diagram cards, peach `::selection`, nav/hero fixes.
- **v1.2 · 2026-07-14 (originality)** — **LOCKED identity: Paper + Ultramarine.** Supersedes terracotta; accent + region-marks = ultramarine; cool diagram cards; pale-blue selection; Fraunces kept (serif-swap optional). The region-overlay marks are the signature motif.
