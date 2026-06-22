# Semant / Sharirasutra — Project Context

> **Living document.** Maintained by Claude to carry context across sessions. Update it as the repo is explored or changed. Last updated: 2026-06-18.

## 0. RESUME HERE (read first)
State as of 2026-06-18, end of session:
- **App runs locally**, fully wired to real services (Mongo Atlas, Cloudinary, Groq) via root `.env` + `frontend/.env`. Atlas needs your IP in the **Network Access allowlist** (current dev IP was `152.57.142.194`; re-add if connection 500s with `TLSV1_ALERT_INTERNAL_ERROR`).
- **Local run** (servers are NOT persistent across machine restarts — relaunch as needed):
  - Backend: `PYTHONPATH="$PWD" ./venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 5007 --reload`
  - Frontend: `cd frontend && npm run dev` (Vite :5173)
- **Frozen branch** `v1` exists (local only) as a pre-redesign snapshot. Active work is on `main`. Nothing has been committed/pushed this session — all changes are in the working tree.
- **Done this session**: (1) Editorial-Gallery redesign applied to global tokens + NavBar + Landing + Gallery (§11); (2) Chrome extension fixed for Instagram + recolored (§12); (3) **Brainstorm/Aletheia** image-interpretation feature — backend `/brainstorm` endpoint + extension Brainstorm button & panel (§12.5); (4) **Motive** manifesto page at `/motive` (§12.6); (5) **Research Article Agent + Sankalpa** — background agent that picks a topic from the gallery, weaves images into an essay, and infers the reader's *will* from feedback at `/research` (§14).
- **Open / not done**: 2nd-pass redesign of Highlights/Feed (still old dark hardcoded styles; PostDetail/editor now reworked as **Sutradhar** §15); `OPENROUTER_API_KEY` is required by config but unused; no tests; nothing committed. New since: **Research Agent + Sankalpa** (§14), **Sutradhar** editor (§15), **Darpan** IG personas (§16) — all verified, none committed.


## 1. What this project is

A **visual storytelling & semantic-curation platform** (internal tagline *दृष्टिकोण / Drishtikone*; backend FastAPI title is `"visual dictionary"`). Users upload images, annotate them (bounding boxes, tags, rich text), and use AI to generate phrases, prose, and long-form "epic" narratives that weave images and text together.

Three deployable pieces:
- **`backend/`** — FastAPI + MongoDB API (deployed on **Render** at `https://sharirasutra.onrender.com`).
- **`frontend/`** — React 19 + Vite SPA (deployed on **Vercel**).
- **`chrome-extension/`** — One-click "save image from any website" extension that posts to the backend.

## 2. Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Motor (async MongoDB driver), Pydantic Settings, Uvicorn/Gunicorn |
| Database | MongoDB Atlas — DB name `visualDictionaryDB`, collections: `posts`, `epics`, `phrase_learning` |
| Image storage | **Cloudinary** (CDN; stores `photo_url` + `photo_public_id`) |
| AI / LLM | **Groq API** (the `groq` SDK). `GROQ_API_KEY`. Config also declares `OPENROUTER_API_KEY` (see open questions). |
| Frontend | React 19.1, Vite 7, react-router-dom 7, axios, TipTap (rich text), lucide-react, allotment (split panes) |
| Runtime | Python 3.12.10 (`runtime.txt`) |

### Groq models in use
- `openai/gpt-oss-120b` — story/plot generation, literary refinement (`llm_service`, `editor_llm_service`)
- `meta-llama/llama-4-maverick-17b-128e-instruct` — vision (editor)
- `meta-llama/llama-4-scout-17b-16e-instruct` — vision (`vision_service`)
- `llama-3.3-70b-versatile` — story-block segmentation (`story_block_service`)

## 3. Repository layout

```
backend/
  config.py            # Pydantic Settings — declares ALL backend env vars
  database.py          # MongoDB (Motor) client; DB=visualDictionaryDB; 3 collections
  main.py              # FastAPI app, CORS (allow_origins="*"), router includes, /health
  routers/             # posts.py, epics.py, phrases.py
  schemas/             # post.py, epic.py, phrase.py (Pydantic models)
  services/            # llm, editor_llm, vision, phrase, epic, story_block
  requirements.txt
frontend/
  src/
    config/api.js      # API_URL = VITE_API_URL || http://127.0.0.1:5007
    services/          # epicService.js (fetch), phraseService.js (axios)
    pages/             # Landing, Gallery, Highlights, TextFeed, PostDetail, CroppedAnnotations, Epics, EpicEditor
    components/        # editors, cards, annotation, chatbot, story flow, etc.
    context/ThemeContext.jsx
  .env.example         # VITE_API_URL
  vite.config.js, vercel.json
chrome-extension/      # manifest v3; popup.js hits http://localhost:5007 (local) — see open questions
requirements.txt       # root (Render installs from here) — superset of backend/requirements.txt
runtime.txt            # python-3.12.10
start.sh               # Render start cmd: gunicorn backend.main:app -k UvicornWorker
notes_theory/          # scratch notes
```

## 4. Backend API surface

**Posts** (`/api/v1/posts`)
- `POST /` — create post from file upload → Cloudinary
- `POST /upload-from-url` — create from image URL (Chrome extension)
- `POST /bulk-upload` — multiple files
- `GET /` — list (paginated; `?tag=` filter) · `GET /{id}` · `PATCH /{id}` · `DELETE /{id}` (also deletes from Cloudinary)
- `GET /tags/`, `GET /tags/popular`, `GET /highlights`
- `GET /with-text` — posts that have text_blocks (defined directly in `main.py`)
- `GET /summary/{tag}` — aggregate text + generate summary & plot suggestions
- `POST /summary/generate_story`, `POST /summary/generate_story_flow`
- `POST /suggestions/generate` — prose/story from text blocks
- `POST /chat/vision`, `POST /rewrite/vision`, `POST /flow/expand-node`
- `PATCH /{id}/add-tag`, `PATCH /{id}/add-tag-and-story`
- `GET /untagged/random`

**Epics** (`/api/v1/epics`)
- CRUD: `POST /`, `GET /` (paginated, `?status=`), `GET /{id}`, `PUT /{id}`, `DELETE /{id}`
- `POST /generate-full`, `POST /complete-story`, `POST /{id}/segment-blocks`
- `GET /{id}/suggest-images/{block_id}`, `POST /{id}/associate-image`, `POST /{id}/randomize-images/{block_id}`
- `POST /vision/auto-recommend`, `POST /vision/prompt-enhance`, `POST /vision/add-to-post`
- `GET /{id}/stats`

**Phrases** (`/api/v1/phrases`)
- `POST /generate` (optionally uses learning memory), `POST /enhance` (save user edit to learning DB), `POST /save`, `GET /stats`

## 5. Data models (MongoDB documents)

- **Post**: `id`, `photo_url`, `photo_public_id`, `updated_at`, `text_blocks[]` (`{id,type,content,color}`), `bounding_box_tags{name→{x,y,w,h}}`, `general_tags[]`, `associated_epics[]`, `highlights[]`.
- **Epic**: `id`, `title`, `description`, `status` (draft/completed/archived), `generation_mode`, `source_tags[]`, `story_blocks[]` (`{block_id,sequence_order,content,associated_image_id,image_url,coherence_score}`), `metadata`.
- **PhraseLearning**: `enhancement{original_phrase,enhanced_phrase,image_context,tags[]}`, `embedding[]`, `usage_count`, timestamps. Stores user improvements to AI phrases for future reuse.

## 6. Frontend routes

| Route | Page | Purpose |
|---|---|---|
| `/` | LandingPage | Hero / intro |
| `/gallery` | GalleryPage | Upload, tag filter, summary/story generation |
| `/highlights` | HighlightsPage | Recent highlighted posts |
| `/feed` | TextFeedPage | Paginated feed of text-bearing posts |
| `/posts/:postId` | PostDetailPage | Split-screen image + text editor |
| `/posts/:postId/crops` | CroppedAnnotationsPage | Cropped bounding-box regions |
| `/epics` | EpicsPage | List epics |
| `/epics/:id` | EpicEditorPage | Create/edit epic narratives |

## 7. Running locally

**Backend** (from repo root so `backend.*` imports resolve):
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 5007   # frontend & chrome-ext expect 5007
```
Needs a `.env` at repo root (see §8). API docs at http://127.0.0.1:5007/docs.

**Frontend**:
```bash
cd frontend
npm install
npm run dev        # Vite dev server on http://localhost:5173
```
Create `frontend/.env` with `VITE_API_URL=http://127.0.0.1:5007` (or omit — defaults to that).

**Chrome extension**: load `chrome-extension/` unpacked at `chrome://extensions`. It targets `http://localhost:5007` for local use.

## 8. Environment variables

### Backend — repo-root `.env` (git-ignored). Declared in `backend/config.py`:
| Var | Required | Purpose |
|---|---|---|
| `MONGO_DETAILS` | ✅ | MongoDB Atlas connection string (`mongodb+srv://…`) |
| `CLOUDINARY_NAME` | ✅ | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | ✅ | Cloudinary key |
| `CLOUDINARY_API_SECRET` | ✅ | Cloudinary secret |
| `OPENROUTER_API_KEY` | ✅ (per config) | Declared required in Settings — see open questions |
| `GROQ_API_KEY` | optional in config, but **needed** for any AI feature | Groq LLM/vision |

> Note: `config.py` marks `GROQ_API_KEY` as optional and `OPENROUTER_API_KEY` as required, but the services actually call **Groq**. In practice both Cloudinary + Mongo + Groq must be set for the app to function; `OPENROUTER_API_KEY` must at least be present (non-empty) or `Settings()` will raise at import.

### Frontend — `frontend/.env` (git-ignored):
| Var | Purpose |
|---|---|
| `VITE_API_URL` | Backend base URL. Defaults to `http://127.0.0.1:5007` if unset. |

## 9. Deployment notes
- **Backend → Render**: uses root `requirements.txt`, `runtime.txt`, `start.sh` (gunicorn, 2 workers, `$PORT`). `start.sh` uninstalls standalone `bson` to avoid conflict with pymongo's bundled bson. Render detected via the `PORT` env var.
- **Frontend → Vercel**: `vercel.json` present; set `VITE_API_URL` to the Render URL.
- **CORS**: `main.py` uses `allow_origins=["*"]`, `allow_credentials=False` (wide-open so the Chrome extension works from any site).

## 10. Open questions / things to verify
- **OpenRouter vs Groq**: `OPENROUTER_API_KEY` is required by `config.py` but no service appears to use it (all AI goes through Groq). Confirm whether it's vestigial or used somewhere not yet read. The provided `.env` includes it as a placeholder so the app boots.
- Whether `GROQ_API_KEY` should be promoted to required in `config.py` (AI features fail silently/at-call without it).
- Chrome extension hardcodes `localhost:5007`; confirm there's a production build/config for the Render URL.
- No backend test suite or README found; no CLAUDE.md yet.

## 11. Frontend redesign — "Editorial Gallery" (in progress)
Goal: improve the frontend "a lot" via a **fresh modern redesign**, managed as a **Claude Design system**.
- **Claude Design project**: "Drishtikone Design System", projectId `197575d6-7fdc-455e-b68a-f3650a81ade7` (on claude.ai/design). Synced via the `DesignSync` tool.
- **Local source**: `design-system/` (flat dir). `tokens.css` is the canonical token source; each `*.html` is a preview card with a first-line `<!-- @dsCard group="…" -->` marker. Groups: Foundations (colors, typography, scale), Components (buttons, cards, navbar), Patterns (hero, gallery).
- **Visual language**: warm paper/ink neutrals, single heritage **terracotta** accent (`--accent: #C4533A`), display serif **Fraunces** for headings + **Inter** for UI, soft (non-pill) radii, generous whitespace, light/dark. Deliberately replaces the old teal "Liquid Metallic" theme in `frontend/src/index.css`.
- **Scope agreed (first pass)**: global system + nav, landing page, gallery + cards.
- **APPLIED to the React app (2026-06-17)**:
  - `frontend/index.html` — loads Fraunces + Inter + Noto Sans Devanagari + Spline Sans Mono; title → "Drishtikone".
  - `frontend/src/index.css` — rewritten with the new tokens **plus legacy aliases** (`--bg-primary`→`--bg`, `--text-primary`→`--ink`, `--accent-primary`→`--accent`, etc.) so un-redesigned pages (Epics, PostDetail, Feed, Highlights) keep working and adopt the new palette automatically. Global headings now use Fraunces; `.btn`/`.chip` helper classes added.
  - `components/NavBar.jsx` + `Navbar.css` — floating pill nav; brand renamed "Framewise" → **"Drishtikone"** (matches landing/product name); **ThemeToggle wired in** (it was previously unreachable in the UI).
  - `pages/LandingPage.{jsx,css}` — editorial hero, terracotta accent, framed image w/ accent glow, primary + secondary CTAs.
  - `App.css` — removed the metallic-shine animation on `.main-content-card`; editorial page-header (Fraunces, italic serif subtitle); softened gallery grid/cards.
- **Known leftovers / not yet redesigned** (still use old hardcoded dark colors in `App.css`): Highlights/TextFeed `.feed-card`/`.text-grid-card`, the TipTap `.rich-text-block`/`.ProseMirror` editor chrome, PostDetail panes. `pages/NavBar.jsx` is dead/broken code (unused — App imports `components/NavBar`).
- **Note**: `design-system/tokens.css` (synced to claude.ai/design) is the canonical source; `frontend/src/index.css` mirrors its values and adds the legacy aliases.

## 12. Chrome extension — Instagram/overlay support (2026-06-17)
The "Sharirasutra Image Saver" extension didn't work on Instagram. Two root causes, both fixed:
- **Button never appeared**: `content.js` attached `mouseenter` per `<img>`, but Instagram/Pinterest cover images with transparent overlay `<div>`/`<a>` elements, so the event never fired. Rewrote to **document-level `mousemove` + `document.elementsFromPoint()`** to find the `<img>` *underneath* overlays (also removes the need for the MutationObserver — infinite-scroll feeds work for free). `content.css` recolored to terracotta.
- **Server-side fetch 403**: `backend/routers/posts.py` `upload-from-url` now picks a host-appropriate `Referer` (`https://www.instagram.com/` for cdninstagram/fbcdn/instagram hosts, pinterest for pinimg) instead of the image URL itself. Added `from urllib.parse import urlparse`. Added `source_url` to `UrlUploadRequest` (schemas/post.py) so the extension can record the page an image came from (content.js sends `source_url: location.href`).
- **To pick up changes**: reload the extension at `chrome://extensions` (circular refresh icon on its card) and hard-refresh the Instagram tab. Backend was restarted with `--reload`.

## 12.5 Brainstorm / "Aletheia" interpretive DIALOGUE (2026-06-18)
A second extension action beside "Save": **Brainstorm** runs an interpretive read of any image (not a caption), then turns into a **back-and-forth dialogue** — it poses clickable multiple-choice questions; clicking an option sends that choice back and Aletheia regenerates a sharpened reading. (The earlier static "punctum" idea was replaced by this interactive loop at the user's request.) Verified end-to-end: round 2 readings visibly incorporate the chosen answer and questions narrow/deepen.
- **Backend** `backend/services/vision_service.py`: `brainstorm_image(image_url, answers=None)` + `_parse_aletheia()` + `ALETHEIA_PROMPT`. Groq vision model; when `answers` (prior `{question,choice}` list) are supplied, they're folded into the prompt to reshape lenses + ask fewer/deeper questions (empty `questions` ⇒ "settled"). Output JSON: `{lenses:[{name,reading,intensity}], questions:[{prompt,options[]}], concealed, uncertainty}`.
- **Backend** `backend/routers/posts.py`: `POST /api/v1/posts/brainstorm` uses `BrainstormRequest` (`image_url`, `source_url?`, `answers?: [{question,choice}]` — in schemas/post.py). Fetches the image **server-side** (so Instagram works), base64 → Groq. Shared `_image_fetch_headers()` (host-aware Referer) used by `/brainstorm` + `/upload-from-url`.
- **Extension** `chrome-extension/content.js`: hover toolbar = **Brainstorm** + **Save**. Brainstorm opens the **Aletheia panel** — lenses w/ animated intensity bars, a choice "thread" breadcrumb, **MCQ questions as clickable option chips** (click → `chooseAnswer` → re-fetch with accumulated `bsAnswers` → re-render), concealed + uncertainty. `content.css` is fully self-contained (hardcoded Editorial palette + `!important`).
- **Lenses & questions** are whatever the model returns; prompt specifies lenses Phenomenological / Semiotic / Atmospheric. UI is generic over both lists.

## 12.6 "Motive" manifesto page (2026-06-18)
New page at route **`/motive`** (nav link added after "Epics"). Long-form editorial manifesto on the motto **"unconcealment as context engineering"** (aletheia → the scroll disenchants → context engineering as the answer → human stakes). Files: `frontend/src/pages/MotivePage.{jsx,css}` (Fraunces title, italic motto pull-quote, drop cap, token-driven, light/dark, ~68ch measure). Wired in `main.jsx` + `components/NavBar.jsx`. (Copy drafted by a subagent; page built in main session.)

## 12.7 Alexia — video → frames (2026-06-21)
Branding: the saver is **Alexia**, the interpreter **Aletheia** — "both unconcealers" (manifest renamed). Extension hover toolbar is now type-aware: images → Save + Brainstorm; **videos → "Split → Save"**.
- **Detection fix (Instagram reels)**: Instagram sets `pointer-events:none` on the reel `<video>`, so `elementsFromPoint` excludes it and the Split button never appeared. `videoAtPoint()` now has a **geometric fallback** — scans real `<video>` rects (smallest enclosing) and matches by cursor coords, bypassing pointer-events.
- **Client-side frame extraction + review** (`chrome-extension/content.js`): `splitVideo()` seeks to N evenly-spaced timestamps (N = clamp(round(duration*3), 8..60), ~3 frames/sec — raised from the original ~1/2s), draws each to a `<canvas>`, `toDataURL('image/jpeg')`. It NO LONGER auto-saves — instead `renderFrameReview()` shows a **selectable thumbnail grid** in the panel (all selected by default; tap to deselect; "Select all / Clear all"; "Save N frames" → `saveFrames()` POSTs the kept ones to `/upload-from-url`). Pauses/mutes/restores the video; `seekVideo()` has a 1.5s fallback for streams. Cross-origin videos without CORS taint the canvas → caught, shows "✗ Protected video". (Chosen over server-side because social videos are blob/MSE and not fetchable server-side; MSE blobs are same-origin so canvas usually isn't tainted.)
- **Backend** (`posts.py` `/upload-from-url`): now accepts `data:` URLs — short-circuits httpx and passes the data URI straight to `cloudinary.uploader.upload`. Verified: base64 → Cloudinary post created. Frames tagged `video-frame`.
- Split button styled in `content.css` (`.sharirasutra-split-btn` indigo; shared `.sharirasutra-btn.saving/.success/.error` states).

## 14. Research Article Agent + Sankalpa (2026-06-22)
A background agent that composes illustrated research articles and learns the reader's **will**. Full vertical slice, verified end-to-end.

**Concept.** Per run the agent: (1) reads the gallery's tag landscape, (2) consults **Sankalpa** (the inferred will profile), (3) picks a topic, (4) gathers + captions gallery images, (5) composes a 4–7 section essay with images woven into sections + 2–3 Aletheia-style steering MCQs. Reader feedback flows back into Sankalpa, which steers the next run.

**Sankalpa — the will-detection engine** (`backend/services/sankalpa_service.py`). Sanskrit *संकल्प* = the intention/resolve formed in the heart. Single evolving profile doc (`key:"primary"`, single-reader studio) with weighted lists `themes/tones/lenses` (0–100) + `form` scalars `{length, image_density, depth}` + a natural-language `reading`. `ingest(signals, article)` runs **two layers**: (a) fast deterministic heuristics per signal type (rating → reinforce article tags+lens; section `go_deeper` → +depth/length; `not_me` → decrement; image kept/dropped → image_density; dwell/scroll → depth/length); (b) reflective LLM step (`llm_service.reflect_will`) that proposes higher-order theme/tone/lens/form shifts + rewrites the portrait. `portrait()` renders a compact prompt string. Heuristic nudge = 12, form nudge = 8, themes pruned to top 14.

**Agent + background worker** (`backend/services/research_agent_service.py`). Runs are a **Mongo-backed queue** (`agent_runs`) drained by a single asyncio worker started in `main.py` startup (`start_worker()` → `_worker_loop()` claims `status:pending` via `find_one_and_update`, runs pipeline, ~2s poll). Blocking Groq calls pushed off the event loop with `asyncio.to_thread` so the API stays responsive. Articles stored in `research_articles` (sections each optionally carry `{post_id,url,caption}`; unused images → `leftover_images` "reserve plate"; `steering_questions`; `will_snapshot`).

**LLM methods** added to `llm_service.py`: `pick_research_topic(landscape, portrait, recent)`, `compose_research_article(topic, angle, portrait, images, context)`, `reflect_will(portrait, signals_summary, topic)` — all `gpt-oss-120b`, JSON mode.

**API** (`backend/routers/research.py`, prefix `/api/v1/research`): `POST /agent/run` (optional `{topic,source_tags,angle}`), `GET /agent/runs`, `GET /agent/runs/{id}` (poll progress steps), `GET /articles`, `GET /articles/{id}`, `POST /articles/{id}/feedback` (signals → returns updated Sankalpa), `GET /sankalpa`. Schemas in `backend/schemas/research.py` (`RunAgentRequest`, `Signal{type,payload}`, `FeedbackRequest`). New collections in `database.py`: `research_article_collection`, `agent_run_collection`, `sankalpa_collection`.

**Frontend** (`/research`, in NavBar). `services/researchService.js` (incl. `beaconFeedback` keepalive for implicit signals). `pages/ResearchPage.jsx` + `.css`: hero with topic input + "Run the agent"; live **RunProgress** (polls run, collapses steps by label); **ArticleReader** with interleaved figures, per-section reaction chips (resonates/go_deeper/not_me), steering MCQ chips, reserve-plate keep/drop, 5-star rating; **implicit signals** — IntersectionObserver dwell per section + max scroll depth + image linger, flushed via beacon on tab-hide / article-switch / unmount; **SankalpaPanel** (sticky) visualises themes/tones/lenses as bars + form meters + the `reading` portrait, pulses on explicit feedback. Reuses Editorial-Gallery tokens.

**Signal types** (`Signal.type` → payload): `rating{value 1-5}`, `section{section_id,reaction}`, `mcq{question,choice}`, `image{kept}`, `dwell{section_id,ms}`, `scroll{depth}`, `linger{image_id,ms}`.

**Verified**: enqueued a run with empty gallery-tag set → agent produced *"The Rhythm of Motion: How Video-Frame Sequencing Shapes Narrative Perception"* (phenomenological, 5 sections, 4 images placed) in ~23s; feedback batch (rating 5 + go_deeper + mcq + scroll 95 + keep) updated Sankalpa: themes `video-frame(86)/opening(74)/semiotic symbols(62)`, lenses phenomenological↑/semiotic↑, form depth 70/length 58/image_density 70, portrait rewritten. Note: gallery currently has essentially one tag (`video-frame`) so topics will diversify as more tagged images land. `node`/`vite build` both clean.

## 15. Sutradhar — the post editor (2026-06-22)
Renamed + reworked the post detail/edit page (`/posts/:postId`, `components/PostDetailPage.jsx`). **Sutradhar** (सूत्रधार — the thread-holder / narrator-director of classical Sanskrit theatre; ties to *sutra* in Sharirasutra) is the editor identity, shown as a centered wordmark in the topbar.

**Layout bug fixed** (the reported "big part going out"). Root cause, found via Chrome DevTools-Protocol measurement: the closed **AI Assistant sidebar** (`.ai-sidebar`, `position:absolute` + `translateX(110%)`) sat off-screen at x≈1462–1844, extending `.post-detail-page`'s scrollWidth to 1844 (404px past its 1440 clientWidth). Because the page is `overflow:hidden`, it became a scroll container that auto-scrolled 379px left, dragging the topbar + split panes off the left edge; meanwhile `height:100vh` under the in-flow sticky navbar overflowed vertically. Fixes: (1) `.ai-sidebar` / `.ai-sidebar-backdrop` → `position:fixed` (z 200/150) so the off-screen state no longer contributes to page scroll; (2) new `.app-layout--fullscreen { height:100dvh; overflow:hidden }` + `.app-main--fullscreen { flex:1; min-height:0 }` (App.jsx adds these classes for `/posts/` routes) so the editor is pinned to the viewport and inner panes scroll; (3) `.post-detail-page` now `flex:1; min-height:0` (was `height:100vh`, removed the undefined `--metal-shine` shimmer); (4) `min-width:0` on `.post-detail-left/right` so flex panes shrink instead of overflowing. Verified by CDP: `scrollLeft:0`, `scrollWidth==clientWidth`, `docH==vh`, topbar x=0.

**Theme correctness**: the editor's TipTap styles in `App.css` were hardcoded dark (`rgba(30,30,35)`, `#e0e0e0`, blue accents) and broke in light mode — rewrote them to design tokens (`--surface`, `--ink`, `--accent`, …) so blocks/toolbar/ProseMirror render correctly in both themes.

**Advanced features added** ("Compose with Sutradhar" + editor UX):
- **AI composer** — *Draft from image* (calls `epics/vision/auto-recommend` with the photo + existing text → appends a paragraph block) and a *prompt → Write* input (calls `epics/vision/prompt-enhance`). Plain text → HTML `<p>` blocks via `htmlFromText`. Verified endpoint returns ~2.3k-char drafts.
- **Block reordering** — up/down chevrons on each `RichTextBlock` (new props `onMoveUp/onMoveDown/isFirst/isLast`; `moveBlock(id,dir)` swaps).
- **Add-block menu** — Paragraph / Heading / Quote (seeds `<h1>`/`<blockquote>` so the TipTap node starts in the right form).
- **Unsaved-changes** — `isDirty` (deep-compares edited vs saved); "Unsaved" pill in topbar; **⌘/Ctrl+S** saves; `beforeunload` guard.
- **Word count / reading time / block count** meta row in edit mode.
- Removed the old "Legacy Generator" (`PostSuggestionPanel`) from this page; the ChatbotPanel AI sidebar (now a fixed slide-over) remains.

Files touched: `App.jsx`, `App.css`, `components/PostDetailPage.jsx`, `components/PostDetailPage.css`, `components/RichTextBlock.jsx`. `vite build` clean; verified live via headless-Chrome screenshots (view + edit mode).

## 16. Darpan — Instagram persona context (2026-06-22)
A feature that builds a **context dossier** ("persona") for an Instagram account — both an analytical profile and a generative "create as them" guide — from details the Alexia extension scrapes off the live profile (IG has no open API) plus the images we already saved from that account. Named **Darpan** (दर्पण, "mirror"). Full vertical slice, verified.

**Why extension-scrape**: saved posts only store `source_url` (mostly bare `instagram.com/` for old feed saves — no handle); the backend can't fetch IG profiles (login wall/403). So the extension reads the profile DOM while you view it.

**Extension** (`chrome-extension/content.js` + `content.css`): on an IG **profile page** (`/<handle>/`, non-reserved), a floating bottom-left **"Build persona"** FAB appears (SPA-route-aware via `setInterval` path-watch + `popstate`). `scrapeInstagramProfile()` reads `og:title`/`og:description`/`og:image` (parses display name + Followers/Following/Posts counts), best-effort bio from `header section`, verified badge, external link, and post-thumbnail `alt` text (captions) + image srcs. POSTs to `/api/v1/personas/ingest`; on success shows `✓ @handle · N of ours` + an "Open Darpan ↗" link to `:5173/personas#<handle>`. (Console banner now "Alexia + Aletheia + Darpan".)

**Backend**: `persona_collection` ("personas", keyed by lowercased `handle`). `schemas/persona.py` (`PersonaIngestRequest` + `AccountDetails`). `services/persona_service.py`: `ingest` (merge account details/captions across re-scrapes; correlate gallery via regex `instagram\.com/<handle>(?:[/?#]|$)` over posts' `source_url`), `synthesize` (vision-reads up to 5 of our matched images → `llm_service.synthesize_persona` → dossier), reads. `llm_service.synthesize_persona` returns `{summary, identity, aesthetic[], themes[], voice{tone,vocabulary,devices}, values[], audience, generative_guide, content_ideas[], caption_samples[]}` (evidence-grounded, gpt-oss-120b JSON). `routers/personas.py` under `/api/v1/personas`: `POST /ingest`, `POST /{handle}/synthesize`, `GET /`, `GET /{handle}`, `GET /{handle}/images`.

**Frontend** (`/personas`, in NavBar): `services/personaService.js`; `pages/PersonasPage.jsx`+`.css` — hero ("Persona mirror"), persona list sidebar, account header (avatar/name/verified/bio/stats/external link, "N in our gallery"), Synthesize/Re-synthesize button, dossier render (summary, identity, aesthetic/theme/value chips, voice, audience, generative guide, content ideas, caption samples), grid of "images we have from them" (→ `/posts/:id`), collapsible captured captions. Deep-links via `#handle`. Images use `referrerPolicy="no-referrer"` (IG CDN). Reuses Editorial tokens.

**Correlation caveat**: past IG saves have `source_url = instagram.com/` (no handle) → 0 matches; correlation works for **future** saves made while viewing a profile (`source_url` then carries the handle). Verified: ingest (`@TestPoet`) + synthesize produced a full dossier (identity/aesthetic/voice + generative_guide + content_ideas + caption_samples); handle-match regex unit-tested; `vite build` clean; `/personas` rendered via headless Chrome. (A throwaway `testpoet` persona is in the DB from testing.)

## 13. Session log
- **2026-06-17**: Initial repo exploration; created this doc, root `.env`, and `frontend/.env` (user later filled in real Mongo/Cloudinary/Groq creds). Ran the app locally (backend uvicorn :5007, frontend Vite :5173, Mongo connected). Created frozen branch `v1` (local only). Built + synced the "Drishtikone Design System" to claude.ai/design (8 cards + tokens). Applied the redesign to global tokens + NavBar + Landing + Gallery. Fixed the Chrome extension for Instagram (overlay-aware hover + host-aware Referer).
- **2026-06-18**: Built the **Brainstorm/Aletheia** feature (backend `/brainstorm` + vision_service method + extension Brainstorm button/panel; verified end-to-end). Added the **Motive** manifesto page at `/motive`. Updated this doc as the resume point. Backend restarted with `--reload`. Nothing committed yet.
- **2026-06-22**: Built the **Research Article Agent + Sankalpa** will-detection engine — full vertical slice (backend agent + Mongo-queue background worker + Sankalpa service + 7 API endpoints + `/research` frontend with reader, multi-channel feedback, and a live will-profile panel). Verified end-to-end (run → article with images in ~23s; feedback → Sankalpa profile shift). See §14. Then reworked the post editor as **Sutradhar** (§15): fixed the off-screen-layout bug (root-caused via Chrome DevTools-Protocol to the absolute AI sidebar inflating page scrollWidth), made the editor viewport-fit + theme-correct, and added an AI composer (draft-from-image / prompt-to-write), block reordering, add-block menu, ⌘S/dirty-state, and word-count. Verified with headless-Chrome measurement + screenshots. Then built **Darpan** (§16): an Instagram persona-context feature — extension scrapes a profile's details/captions → backend correlates with our images + synthesizes an analytical+generative dossier → `/personas` page. Verified end-to-end. Still nothing committed.
