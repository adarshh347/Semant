# Lane 1 — Top chrome: findings

**Lens:** Purpose → Structure (Surface deferred). **Anchor (locked):** the @handle persona identity lives in the content meta-head (Lane 4). The topbar must **not** duplicate persona identity — this plan keeps it out of chrome entirely.

**Headline finding:** the "sibling constraint" that `border-layout-plan.md` §D marked as a **blocked P1** is *already unblocked*. Two hooks that reach the navbar from outside `<main>` already exist in the code:
- `App.jsx:13` puts `app-layout--fullscreen` on the **root** `.app-layout` for every `/posts/*` route — a route-aware class that wraps *both* the navbar and `<main>`, so `.app-layout--fullscreen .navbar { … }` is reachable CSS **today**.
- `PostDetailPage.jsx:586` toggles `post-detail-editing` on `document.body`, and `Navbar.css:104–123` already consumes it to fade/compact the navbar during editing.

So collapsing the global navbar on Drishya needs **no new state plumbing** — only new CSS rules keyed off a class that already renders. That reframes every "needs a hook" item below as reachable now.

---

## Current chrome inventory

Everything rendered above `.post-detail-split`, top to bottom, with duplicates flagged.

### Bar 1 — Global navbar (`NavBar.jsx`, same on every page)
| Control | Ref | Purpose | Note |
|---|---|---|---|
| Logo "Drishtikone" → `/` | `NavBar.jsx:10–13` | home / brand | goes to Landing, not Gallery |
| 9 nav links (Gallery, Highlights, Feed, Epics, Research, Personas, Unconceal, Anatomy, Motive) | `NavBar.jsx:15–25` | global wayfinding | on a focused image page these compete with the work |
| **ThemeToggle** | `NavBar.jsx:28` | theme | **DUPLICATE ①** |
| Upload CTA → `/gallery` | `NavBar.jsx:29–31` | primary global action | same destination as the topbar's back-link |
| container `.navbar` | `Navbar.css:13` | — | floating rounded pill, `--radius-xl`, backdrop blur |

Routes confirmed in `main.jsx:30–42`: all 9 links are real top-level routes; `/posts/:postId` (Drishya) is **not** in the nav — you reach it only from Gallery.

### Bar 2 — Post topbar (`PostDetailPage.jsx:644–678`, `.post-detail-topbar`)
| Control | Ref | Purpose | Note |
|---|---|---|---|
| Back-link "← Gallery" → `/gallery` | `:645–647` | leave the page | overlaps Upload CTA + logo as "get out" affordances |
| `.sutradhar-brand` ("Sutradhar / सूत्रधार · the thread-holder") | `:650–653` | editor-identity label | `position:absolute; left:50%; pointer-events:none` (`css:1452–1460`); **decorative center slot**, hidden < 820px (`css:1476`) |
| Unsaved pill (conditional `isDirty`) | `:656–659` | status | fine, status-only |
| **ThemeToggle** | `:661` | theme | **DUPLICATE ①** — same component as `NavBar.jsx:28` |
| AI Assistant (toggle `isChatOpen`) | `:662–668` | open the deep AI sidebar | primary-ish; toggles `.primary`/`.secondary` |
| Edit (only when `!isEditing`) | `:669–673` | enter edit mode | see trio analysis — likely redundant |
| Delete (danger) | `:674–676` | destroy the post | rare + destructive, sits permanently front-of-house |
| container `.post-detail-topbar` | `css:22–35` | — | full-width glass bar, `border-bottom`, `.compact` variant exists (`css:37–42`) |

### Persona line — inside content, NOT chrome (`PostDetailPage.jsx:746–759`, `.source-account-section`)
Full-width band: avatar + "From **@handle** · display_name" + "Open persona →". `css:379–402`. **Lane 4 has already locked this to the content meta-head** (decisions-log "Lane 4 answers" #1). Listed here only to confirm Lane 1 leaves it alone.

### Duplicates summary
- **ThemeToggle ×2** — `NavBar.jsx:28` and `PostDetailPage.jsx:661`.
- **"Leave to Gallery" ×3 senses** — logo→`/` (Landing), Upload→`/gallery`, back-link→`/gallery`. Not literal duplicates but three exits stacked in one viewport.
- Persona identity is **not** currently duplicated (only the content band renders it); the anchor's job is to keep it that way.

---

## Proposed structure (leanest arrangement)

One chrome zone, not two floating bars. The global navbar **recedes to a slim rail on `/posts/*`** (route-aware, using the existing `app-layout--fullscreen` hook) rather than merging — merging would drag 9 global links into the page's own bar. The post topbar keeps its own actions but sheds the duplicate toggle, the decorative center slot, and demotes the rare/secondary actions.

```
.app-layout--fullscreen                     (App.jsx — already route-aware)
├─ Navbar  → SLIM RAIL on /posts/*
│   ├─ logo → / (kept, compacted)
│   ├─ nav-links  → collapse into a single "☰ / Drishtikone ▾" menu (all 9 still reachable)
│   ├─ ThemeToggle          ← the ONE surviving toggle
│   └─ Upload CTA (kept — global new-work action)
│
└─ main--fullscreen
   └─ PostDetailPage (.editing-mode toggles body.post-detail-editing)
      ├─ .post-detail-topbar  → hairline strip, page-scoped only
      │   ├─ back-link "← Gallery"           (kept: the page's own exit)
      │   ├─ [Sutradhar brand → fold left, inline, no center slot]   (decorative; see Q)
      │   ├─ Unsaved pill (isDirty)          (kept, status)
      │   ├─ AI Assistant                    (kept — the one primary action)
      │   └─ "⋯" overflow  →  { Delete }      (rare/destructive moves in)
      │   (Edit removed as a button — Content pane becomes directly editable / pencil on its header)
      │
      └─ .post-detail-split …
```

Net: two bars still physically stack (Bar 1 slim rail + Bar 2 page strip), but each carries **one job** — Bar 1 = "where am I in the app + leave", Bar 2 = "act on *this* image". No control appears twice.

---

## Per-control decision table

| Control | Ref | Decision | New home | Reason (Purpose) |
|---|---|---|---|---|
| Navbar 9 links | `NavBar.jsx:15–25` | **collapse** on `/posts/*` | single menu/disclosure in the slim rail | none of the 9 serve reading/marking/writing/tracing *this* image; they're wayfinding, keep reachable but out of the way |
| Navbar ThemeToggle | `NavBar.jsx:28` | **keep** | slim rail | the survivor of the pair |
| Topbar ThemeToggle | `:661` | **remove** | — (delete the copy) | duplicate; theme is global chrome, belongs in Bar 1 |
| Navbar Upload CTA | `NavBar.jsx:29` | **keep** | slim rail | global "start new work"; distinct job from "leave this page" |
| Navbar logo | `NavBar.jsx:10` | **keep**, compact | slim rail | brand + home |
| Back-link "← Gallery" | `:645` | **keep** | topbar (left) | the page's own exit; nearest, most expected |
| Sutradhar brand (center) | `:650` / `css:1452` | **fold left / demote** | inline start of topbar, no dedicated center slot | decorative label (`pointer-events:none`), already hidden < 820px — it is not structural (see Q1) |
| Unsaved pill | `:656` | **keep** | topbar | status of *this* edit; correct place |
| **AI Assistant** | `:662` | **keep as the one primary** | topbar (right) | opens the deep conversational assistant — a Drishya-purpose action (writing help); the only button that should stay full-weight |
| **Edit** | `:669` | **remove as a standalone button** | Content pane becomes directly editable; if an explicit trigger is wanted, a pencil affordance on the **Content panel header** (`:717`) | Content is already block-editable; a top-level Edit button is a mode gate the panel can own. Reduces the strip from 3 buttons to 1 |
| **Delete** | `:674` | **move** | "⋯" overflow menu in the topbar | rare + destructive; front-of-house permanence is a mis-weighting, not a capability need |

Every capability remains reachable: theme (rail), all 9 links (menu), leave (back-link + Upload), AI (button), edit (direct/pencil), delete (overflow).

---

## Code-change surface (described, not written)

**None of this is in scope for this lane — it is the build map for a later narrow prompt.**

1. **Navbar slim-rail on `/posts/*` — CSS only, hook already exists.**
   `App.jsx:13` already emits `app-layout--fullscreen` on the root. Add rules `.app-layout--fullscreen .navbar { … }` (compact padding, links→menu) in `Navbar.css`. **No new state, no prop, no route logic** — the border-layout-plan §D "needs a state hook (P1)" is already satisfied by this class. *This is the correction to the plan's assumption.*
   - The "9 links → one menu" collapse needs a small JSX change in `NavBar.jsx` (a disclosure/menu component + open state), but it can render the same `<NavLink>`s conditionally; no routing change.

2. **Drop the duplicate ThemeToggle.**
   Delete `<ThemeToggle />` at `PostDetailPage.jsx:661` and its import if unused elsewhere (it's used only here in this file — verify). Bar 1's copy survives.

3. **Delete → overflow menu.**
   In `.post-detail-actions` (`:655–677`), replace the always-on Delete button with a "⋯" trigger opening a small menu holding Delete (reuse `handleDelete`). Pattern already exists in the repo — `RichTextBlock.jsx:112–171` is a working `MoreHorizontal` overflow menu with outside-click/Escape close; lift/copy that shape.

4. **Edit button removal / pencil-on-header.**
   Remove the `!isEditing && <button … startEditing>` at `:669–673`. Either (a) make the Content pane enter edit on focus/click, or (b) add a pencil affordance to the Content `.panel-header` (`:717`) calling `startEditing`. This is the one item with a **Purpose question** attached (below) — don't build until answered.

5. **Sutradhar brand center slot.**
   `css:1452–1460` uses absolute-center + `pointer-events:none`. Folding it inline (remove the absolute positioning) is pure CSS + leaving the JSX node where it is. Decorative, so it can also be dropped — see Q1.

6. **Files touched (later build):** `Navbar.css` (rail rules), `NavBar.jsx` (links→menu), `PostDetailPage.jsx` (remove toggle+Edit, Delete→overflow), `PostDetailPage.css` (overflow menu, brand fold). **No** `App.jsx` state change needed (the hook exists), **no** backend/service/data changes.

---

## Questions for Adarsh

1. **Sutradhar brand — keep, fold, or drop?** It's a decorative, non-interactive center label (`pointer-events:none`, hidden < 820px). Purpose says chrome should serve reading/marking/writing/tracing. Options: (a) fold it inline at the topbar's start as a quiet page-title, (b) drop it entirely (the "who wrote what" trace is carried by block `origin`, not this label), (c) keep the center slot. I lean **(a) or (b)** — it currently earns a whole center slot for a word.

2. **Navbar collapse shape — menu vs slim-always-visible?** On `/posts/*`, do you want the 9 links (a) hidden behind a single "☰ ▾" disclosure (cleanest, one row), or (b) kept visible but shrunk to a thin rail? Both use the same existing `app-layout--fullscreen` hook; (a) removes the most competition for attention.

3. **Is a standalone Edit button wanted at all?** Lane 5 already makes Content directly block-editable. I propose removing the top Edit button and letting the Content pane own entry (direct edit, or a pencil on its header). Confirm you're OK losing the top-level Edit button, and pick: **direct-edit-on-focus** vs **explicit pencil on the Content header**. (Direct-edit is leaner but has a "did I mean to edit?" risk on a reading page.)

4. **AI Assistant — is it staying as a topbar button** given the locked direction that AI writing moves into slash and "the deep AI sidebar stays for real conversation only" (decisions-log)? I've kept it as the one primary topbar action, but if the sidebar is being de-emphasized, it could also become an overflow/rail item. Confirm it stays primary.

5. **Upload vs back-link redundancy** — three "leave/next" affordances share the viewport (logo→/, Upload→/gallery, back→/gallery). I kept all three (different jobs). If you'd rather thin this, tell me which sense to drop; I didn't want to remove a global action from Lane 1's narrow mandate.
