# Findings — "AI as part of the pen": inline generation + slash commands

**Mode:** research + plan only. No composer was removed. Every current generation
path still works.
**Scope answered:** the four research questions, the interaction spec, the final
command set, a phased build plan, and — called out up front — a clear **Path A vs
Path B verdict for the slash menu**.

Evidence is cited as `file:line` and by installed package version so nothing here
rests on memory.

---

## 0. Headline verdict (read this first)

- **The slash menu does NOT force Path B.** A per-block editor (Path A) supports a
  caret-anchored `/` menu cleanly, using the official `@tiptap/suggestion` utility
  wired into each block's editor. **Build the slash menu on Path A.**
- Path B (one editor for the whole document) is still the right *eventual* home for
  cross-block selection and a single undo stack, but the slash menu is **not** the
  reason to pay for that rewrite now. This agrees with the already-LOCKED sequencing
  in `decisions-log.md:39` ("Path A first, plan Path B").
- **Streaming is not implemented anywhere** — the backend calls Groq with
  `stream=False` and the routes return whole-JSON. Inline streaming needs a new
  backend endpoint + a frontend `fetch`-reader. It is additive; nothing has to break.
- **Range-level origin is feasible** as a custom TipTap mark, but it is a Phase-3
  concern. Keep the existing block-level `origin` until streaming lands.

---

## 1. TipTap feasibility

### What is actually installed
From `frontend/package.json` and `node_modules/@tiptap/*/package.json`:

| Package | Version | Notes |
|---|---|---|
| `@tiptap/react` | 3.7.2 | `useEditor`, `EditorContent`, `BubbleMenu` (from `@tiptap/react/menus`) |
| `@tiptap/starter-kit` | 3.7.2 | in use |
| `@tiptap/extension-underline` | 3.7.2 | in use |
| `@tiptap/extension-floating-menu` | 3.8.0 | **in deps but unused** in code |
| `@tiptap/core`, `@tiptap/pm` | 3.8.0 | ProseMirror bundled and complete |
| `@tiptap/suggestion` | **NOT installed** | the slash/mention utility |
| `@tiptap/extension-mention` | **NOT installed** | — |
| `@tiptap/extension-placeholder` | **NOT installed** | needed for the empty-block prompt |
| `tippy.js` / `@floating-ui` | **NOT installed** | no popup-positioning lib present |

React is 19.1.1. `@tiptap/pm` ships the full ProseMirror stack (`state`, `view`,
`model`, `transform`, …), so a slash plugin can be built even without the helper
package — but we shouldn't hand-roll what `@tiptap/suggestion` already does.

### Current editor architecture (Path A, confirmed)
`RichTextBlock.jsx:36` creates **one `useEditor` per block** with
`extensions: [StarterKit, Underline]`. The parent `PostDetailPage.jsx` owns the
block array and the single source of truth for focus:

- `activeBlockId` is set on focus (`RichTextBlock.jsx:40` → `onFocusBlock` →
  `PostDetailPage.jsx:697 setActiveBlockId`).
- All creation flows through `makeBlock` (`PostDetailPage.jsx:280`) and the single
  position-aware `insertBlock` (`PostDetailPage.jsx:290`), which already inserts
  *after the active block*. This is exactly the hook a slash command needs.
- `origin: 'human' | 'sutradhar'` is already set at every creation point
  (`addBlock` 301, `handleSuggestionSelect` 329, `draftFromImage` 415,
  `writeFromPrompt` 432).

### Does a per-block editor support a `/` menu? — Yes.
`@tiptap/suggestion` attaches to an editor as a ProseMirror plugin keyed on a
trigger char (`char: '/'`). It fires `items()`, gives you a live `clientRect()` for
the caret, and a `command()` callback to apply the choice. Nothing about it requires
a single-document model — it works inside each block's editor instance.

The only real Path-A friction, and how we handle it:

1. **Popup positioning.** No `tippy`/`floating-ui` is installed. We render our own
   fixed-position `<SlashMenu>` React component at `props.clientRect()` (a plain
   `position: fixed` div with a small flip-up-if-near-bottom check). No new heavy
   dependency required; `@tiptap/suggestion` is the only add.
2. **One menu, many editors.** Each block registers its own Suggestion instance, but
   they should all drive **one shared `<SlashMenu>`** mounted once in
   `PostDetailPage` (via a small context/ref), so we don't mount N popups. The
   active editor's `render` callbacks feed that single component.
3. **Cross-block context is already reachable.** `/continue` needs the surrounding
   prose and `/draft` needs the image — the parent already computes
   `existingTextForAI()` (`PostDetailPage.jsx:398`) and holds `post.photo_url`. The
   slash `command()` calls back up to the parent, same as `insertBlock` does today.

### Verdict — Path A vs Path B for the slash menu
**Choose Path A.** Add `@tiptap/suggestion` (+ `@tiptap/extension-placeholder`),
register a `SlashCommands` extension per block, and route selections through the
existing `insertBlock`/`activeBlockId` machinery.

Where Path B genuinely wins — and why none of it blocks the slash menu:

| Capability | Path A story | Needs Path B? |
|---|---|---|
| `/` menu anchored to caret | per-block Suggestion plugin | **No** |
| `/paragraph /heading /quote` | convert the current block in place | **No** |
| Insert AI block after caret | existing `insertBlock(atActive)` | **No** |
| Ghost text in current block | decoration inside that block's editor | **No** |
| Range-level `origin` mark | custom mark within a block | **No** (marks live inside one block) |
| Cross-**block** text selection | not possible per-block | Yes — but slash never needs it |
| One unified undo stack | per-block undo only | Yes — nice-to-have, not required |
| Drag-reorder as native nodes | already custom in Path A (works) | No |

**Bottom line:** the slash menu is buildable, testable, and shippable on Path A
through all three phases below. Path B stays a *separate, later* architectural pass
justified by cross-block selection and unified undo — **not** by slash. Recommend we
do **not** couple the slash work to a Path-B rewrite.

---

## 2. Streaming

### What exists today — whole-response only
- Backend generation goes through `VisionService.analyze_image`
  (`backend/services/vision_service.py:35`), which calls the **Groq** SDK
  (`self.client.chat.completions.create(..., stream=False)`,
  `vision_service.py:51-73`) with model `meta-llama/llama-4-scout-17b-16e-instruct`.
  Every call site (`auto_recommend_text` 130, `prompt_enhanced_text` 167,
  `brainstorm_image` 306, region passes) uses `stream=False`.
- The routes return a finished JSON body: `return {"suggestion": result}`
  (`backend/routers/epics.py:263, 288`).
- Frontend consumes them with `fetch(...).json()` in `epicService.js:97-123`, and
  drops the whole string into one new block (`draftFromImage`
  `PostDetailPage.jsx:408`, `writeFromPrompt` 423).

So: **no token streaming anywhere, end to end.**

### What a streaming path needs
**Backend (additive — do not change the existing endpoints):**
- Groq's SDK supports `stream=True`, which yields chunks you read as
  `chunk.choices[0].delta.content`. Add a streaming variant of `analyze_image`
  (a generator) and expose **new** routes, e.g. `POST /vision/auto-recommend/stream`
  and `/vision/prompt-enhance/stream`, returning FastAPI `StreamingResponse`
  (SSE `text/event-stream`, or newline-delimited chunks).
- Caveat: the service methods are `async def` but call the **sync** Groq client
  today. For streaming, either use Groq's async client, or run the sync generator in
  a threadpool and yield from it. Note the current call is already blocking the event
  loop — worth fixing when we touch this.
- Keep `stream=False` routes alive until the slash UI fully replaces the old
  composer (per the constraint in the design doc).

**Frontend:**
- Use `fetch` with `response.body.getReader()` + `TextDecoder` to read chunks and
  append them into the active block as they arrive. **Not `EventSource`** — it is
  GET-only and can't set headers, and we need `X-API-Key`.
- Auth already works with streaming: `config/api.js:21-32` monkey-patches
  `window.fetch` to inject `X-API-Key` for any `API_URL` request, and that patch
  applies to a streaming `fetch` too. No per-call auth work needed.
- **Single-undo (design doc asks for this):** incremental insertion is many
  transactions, which pollutes undo. Recommended approach — stream into a **live
  decoration** (visual only, not the real doc), and on completion commit the full
  text as **one** `insertContentAt` transaction that also applies the origin mark.
  That gives one undo step and atomic origin marking. During the stream show the
  quiet "Sutradhar is writing…" state in the block (§4), not a panel spinner.

---

## 3. Origin marking at sub-block level

**Feasible with a custom mark.** Define a TipTap `Mark` (e.g. name `sutradhar`) via
`Mark.create({ name, parseHTML, renderHTML: () => ['span', { 'data-origin':
'sutradhar' }, 0] })` and add it to the per-block extension list. It behaves like
bold: it wraps a *range*, survives HTML serialization (blocks are stored as HTML —
`block.content` is `editor.getHTML()`, `RichTextBlock.jsx:39`), and doesn't conflict
with StarterKit. When AI text is committed (§2), wrap the inserted range in the mark.

**Recommendation: block-level now, range-level in Phase 3.**
- The block already carries `origin` (`makeBlock`, `PostDetailPage.jsx:280`); that is
  correct and sufficient while AI still produces *whole* blocks (today's behaviour).
- Range-level only matters once AI streams *into* a block a human also edits — i.e.
  `/continue` and ghost text. Introduce the mark in the same phase that introduces
  streaming, so there's a real mixed-authorship case to mark. Until then, coarse
  block-level origin is honest.
- Keep the two representations consistent: a block that is entirely one origin keeps
  `block.origin`; a mixed block sets `block.origin = 'mixed'` (or derives from marks)
  and the reader-side trace reads the marks. Decide the exact reconciliation when we
  build Phase 3 (flagged as a question below).

---

## 4. Empty-block affordance & `/` trigger

**Placeholder.** Add `@tiptap/extension-placeholder` and configure per block:
`Placeholder.configure({ placeholder: 'Write, or press / for Sutradhar…' })`.
It renders on the empty ProseMirror node via CSS `::before` — no layout cost. (There
is no placeholder today; blocks start blank.) Show the full hint only on the
*active* empty block; other empty blocks can show a shorter "Write…" to keep the
surface quiet.

**Triggering `/` without fighting typing.** Configure `@tiptap/suggestion` with
`char: '/'` and constrain when it opens so a literal slash in prose (URLs, "and/or")
doesn't pop the menu:
- Open only when `/` is at the **start of an empty block** or immediately preceded by
  whitespace/line-start (`allow`/`allowSpaces` guards).
- `Esc` closes the menu and leaves the typed `/` as normal text; selecting a command
  deletes the `/query` range first (the Suggestion `range` gives you this).
- Arrow keys / Enter navigate and pick; the menu filters as you type after `/`.

---

## 5. Final command set (v1 / v2 / v3)

Grouped as the design doc asks: **block-type** (local, instant) vs **AI** (Sutradhar).
"Insertion behaviour" is the exact result of picking the command.

### v1 — Phase 1, no AI (ship the shell)
| Command | Behaviour |
|---|---|
| `/paragraph` | Convert the **current** (empty) block to paragraph in place. If the block is non-empty, insert a new paragraph after it. |
| `/heading` | Same, as `<h1>` (matches `addBlock('h1')`). |
| `/quote` | Same, as `<blockquote>`. |

These replace the manual "Add block" buttons (`PostDetailPage.jsx:728-735`) — but
keep those buttons until v1 is proven, then remove.

### v2 — Phase 2, AI non-streaming (reuse existing endpoints)
| Command | Behaviour | Backend today |
|---|---|---|
| `/draft` | Insert a new `sutradhar` block **after** the caret with a passage drafted from the image. | `autoRecommendText` (`epicService.js:97`) — exists |
| `/describe` | Insert a new `sutradhar` block: a plainer visual description. | `promptEnhancedText` with a fixed "describe" prompt |
| `/continue` | Generate a continuation of the current block's text; insert at caret. | new prompt via `promptEnhancedText`-style call, passing `existingTextForAI()` |
| `/expand` | Operate on the **current block / selection**; replace it with a longer version. | prompt-enhance |
| `/shorten` | Same, shorter. | prompt-enhance |
| `/rewrite` | Same, tone/clarity rewrite. | prompt-enhance |
| `/ask` | No block change — hand off to the deep AI **sidebar** (which stays, per `decisions-log.md:62`). | existing sidebar path |

All v2 commands are non-streaming (whole response), so they land as one insert with
`origin: 'sutradhar'` — trivially single-undo and block-level origin. This replaces
"Draft from image" and "Compose with Sutradhar" (`PostDetailPage.jsx:741-760`); keep
those working until v2 reaches parity, then remove.

### v3 — Phase 3, the hard parts
- Streaming for `/draft`, `/continue`, `/describe` (§2), with the "Sutradhar is
  writing…" in-block state.
- **Ghost text** for `/continue`: faint continuation, `Tab` accepts, `Esc` dismisses
  (Copilot-style) — rendered as a ProseMirror decoration in the current block; on
  accept, commit as one transaction + apply the `sutradhar` range mark.
- **Range-level origin** mark (§3).
- **Selection → AI verbs** in the bubble toolbar (`RichTextBlock.jsx:163` already has
  a `BubbleMenu`): add rewrite/shorten/expand buttons that act on the selected text.

---

## 6. Build plan (phased, so the shell ships before the hard parts)

**Phase 1 — the `/` shell, no AI.**
1. `npm i @tiptap/suggestion @tiptap/extension-placeholder`.
2. Add a `SlashCommands` extension (wraps Suggestion, `char: '/'`) to each block's
   editor in `RichTextBlock.jsx:37`.
3. Build one shared `<SlashMenu>` popup positioned at `clientRect()`; no new
   positioning dep.
4. Wire `/paragraph|/heading|/quote` to the existing type-conversion (`setType`,
   `RichTextBlock.jsx:62`) / `insertBlock`.
5. Add the empty-block placeholder.
6. Keep the old Add-block menu; only remove once this is verified.

**Phase 2 — AI commands, non-streaming.**
1. Add `/draft /describe /continue /expand /shorten /rewrite /ask`, each calling the
   existing vision endpoints via `epicService`.
2. Route inserts through `insertBlock`/current-block replace, always stamping
   `origin: 'sutradhar'`.
3. Add a quiet in-block busy state.
4. Retire "Draft from image" / "Compose with Sutradhar" once parity is reached.

**Phase 3 — streaming + range origin + ghost text.**
1. Backend: streaming `analyze_image` variant + new `StreamingResponse` routes
   (leave old routes intact).
2. Frontend: `fetch`-reader streaming into a decoration; commit as one transaction.
3. Custom `sutradhar` range mark; reconcile with block-level `origin`.
4. Ghost-text `/continue` (Tab/Esc) and bubble-toolbar selection verbs.

Each phase is independently shippable and leaves every existing capability working
until its replacement is proven — satisfying the design doc's two constraints.

---

## 7. Questions for you (Adarsh)

1. **Path confirmation.** Good to lock **Path A for the slash menu** (Path B stays a
   later, separate pass for cross-block selection + unified undo)? My recommendation
   is yes.
2. **New dependencies.** OK to add `@tiptap/suggestion` and
   `@tiptap/extension-placeholder` (both official, same 3.x line)? I'm avoiding
   `tippy`/`floating-ui` by rendering our own popup — acceptable, or would you rather
   pull a positioning lib for robustness?
3. **`/` trigger strictness.** Trigger only on an empty block / after whitespace (my
   plan), or allow `/` anywhere at the caret? Stricter = fewer accidental menus.
4. **Command scope for v2.** Is the seven-command v2 set right, or do you want to
   start narrower (say `/draft` + `/continue` only) and grow?
5. **`/expand /shorten /rewrite` home.** These act on existing text — do you want
   them as slash commands, as **bubble-toolbar** selection verbs, or both? (I lean
   toward bubble-toolbar for selection actions, slash for generation-at-caret.)
6. **Mixed-authorship reconciliation.** When a block holds both human and AI text,
   should `block.origin` become `'mixed'` (derived from the range marks), and is the
   reader-side "who wrote what" trace expected in this round or later?
7. **Streaming appetite.** Is streaming a must-have for the first usable version, or
   fine to ship v2 non-streaming and treat streaming as the Phase-3 polish? (Backend
   streaming is the biggest single lift here.)
8. **Groq streaming + async.** While adding streaming, OK to also move the vision
   calls off the blocking sync client (they currently block the event loop)? Small
   scope creep, real correctness win.
