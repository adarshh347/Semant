# Front-of-house v2 — home polish · landing back · archive browse modes

**Mode:** design + plan. No app code. Owner: app-shell session. Plum v1.3.

---

## 1. Make the Home feel classy
**The honest lever is craft, not a component library** (and the "classy" OSS kits — Aceternity/Magic UI — are Tailwind-locked, so reference-only). The biggest wins are content + detail, then a little motion:

**Craft moves (no dep):**
- **Real imagery on the tiles.** The flat look is mostly placeholder rects. "Continue in Chiasm", "Archive mosaic", and "Read" should show **real image crops** (Cloudinary), and "Parts you recently noticed" should show the **percept crop clipped to its region** (SVG clipPath) — instant richness + on-brand.
- **Type hierarchy.** Bigger Fraunces tile titles, tighter leading, muted supporting text — the taste-spec type roles, applied harder.
- **One hero moment.** A single confident editorial line + the ◈ signature, lots of air; let one tile (Continue) dominate.
- **Depth restraint.** Flat cards, hairline borders, one accent/tile — already the rule; enforce it.

**OSS that genuinely helps (all MIT, no Tailwind):**
| Need | Pick | Note |
|---|---|---|
| Tasteful micro-interactions (hover-lift, reveal-on-load, layout) | **Motion** (ex-framer-motion) | the one real polish dep; reduced-motion safe |
| Smooth route/state transitions | **View Transitions API** (native) | cross-fades between Home↔Archive↔Chiasm; no dep |
| Animated stat numbers ("7 readings") | **@number-flow/react** (or CountUp) | the "This week" tile counts up |
| Icons, refined | **Lucide** (have it) / Phosphor | consistent stroke weight |
| Real crops / blur-up | **Cloudinary** transforms | already in |

Rule stays: motion explains/reveals, never decorates; `prefers-reduced-motion` → static.

## 2. Bring the motive landing back
Phase 3 moved the motive landing to `/welcome` and made `/` the dashboard — so the beautiful See·Read·Write page lost its front-door spot. **Restore it as the entry, with the dashboard one step in:**
- **`/` = the motive landing** (first impression, the classy editorial page) with a clear **"Enter" CTA → `/home`**.
- **`/home` = the bento dashboard** (the app home once you're in); the nav "Home" points here.
- (When auth exists later: first-visit → landing, returning → dashboard. For now, the landing is the door, the dashboard is the room.)
This gives you both — the motive page as the pitch, the dashboard as the workspace — without one eating the other.

## 3. Archive — multiple ways in (not just infinite scroll)
Offer a **view switch** in the archive; each mode suits a different intent:
| Mode | For | How |
|---|---|---|
| **Scroll** (default) | browse recent, linear | the infinite justified grid you have |
| **Jump / timeline** | reach *old* images fast | a **date/scrollbar scrubber** (a thin rail with month/year markers) + jump-to; maps scroll position → a date, so you fling to 2023 instantly. Pairs with `useInfiniteQuery` (fetch around the jumped offset) |
| **Wall (fisheye)** | see *thousands at once*, playful | a dense grid of tiny thumbs where **the area under the pointer magnifies** (macOS-Dock-style): scale each tile by its distance to the cursor via a CSS transform on `pointermove` (throttled). Optionally **pan a spatial 2D canvas** (map-style) instead of scrolling |
| **Grid** | uniform, scan-heavy | a plain square grid toggle |

**Techniques / OSS:**
- Fisheye magnification = a **light custom build** (pointer-distance → transform scale; no dominant drop-in lib). References: js-image-zoom, Magnifier.js, "spatial grid image explorer" (pannable canvas). Keep thumbs tiny + virtualized so thousands stay cheap.
- The timeline scrubber = custom (a rail synced to the query offset) — cheap, high-value for "access the old ones fast."
- All modes reuse the same `useInfiniteQuery` data + virtualization; only the layout differs.

## Recommended order
1. **Landing back** (`/` = motive, `/home` = dashboard) — small, restores the pitch.
2. **Home craft pass** — real crops on tiles + type + Motion micro-interactions + number-flow stats.
3. **Archive Jump/timeline** — the practical "reach old ones fast" win.
4. **Archive Wall (fisheye)** — the creative browse mode (its own phase; most custom).

## Questions
1. `/` = landing + `/home` = dashboard (my rec), or dashboard at `/` with landing at `/welcome` kept?
2. Wall mode: **fisheye-on-hover** (Dock feel) vs **pannable spatial map** vs both as sub-toggles?
3. Add **Motion** as the one polish dep? (I recommend yes — it's the classiness multiplier.)
