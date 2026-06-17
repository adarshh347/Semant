# Semant / Sharirasutra — Project Context

> **Living document.** Maintained by Claude to carry context across sessions. Update it as the repo is explored or changed. Last updated: 2026-06-17.

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

## 13. Session log
- **2026-06-17**: Initial repo exploration; created this doc, root `.env`, and `frontend/.env` (user later filled in real Mongo/Cloudinary/Groq creds). Ran the app locally (backend uvicorn :5007, frontend Vite :5173, Mongo connected). Created frozen branch `v1` (local only). Built + synced the "Drishtikone Design System" to claude.ai/design (8 cards + tokens).
