# Semant Android App — Design

**Date:** 2026-07-03
**Status:** Approved
**Scope:** Native Android app (Kotlin + Jetpack Compose) bringing Semant capture and browsing to the phone. Images shared from any app (WhatsApp, Twitter, Chrome, Gallery) flow into the existing FastAPI backend via Android's Share Sheet.

## Vision & Phasing

The end goal is a full Semant mobile app. Built in phases:

- **Phase 1 (this design):** Share Sheet capture + offline upload queue + Gallery browsing + read-only Post Detail + Settings.
- **Phase 2:** Aletheia dialogue on device, annotation editing (Compose Canvas), capture-time "interpret now".
- **Phase 3:** Epics, Research, Personas reading views.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Stack | Kotlin + Jetpack Compose, native Android | Best Share Sheet / background-upload integration; Compose Canvas suits future annotation editing |
| Architecture | Single `:app` module, MVVM, feature packages | Industry-default, most-documented shape; refactor to multi-module later is mechanical |
| Location | `android/` directory in the semant repo | One repo, shared context |
| Min SDK | API 26 (Android 8.0) | ~97% device coverage |
| Auth | Static `X-API-Key` header, checked by backend | Right-sized for a single-curator system; closes the currently-open Render API |
| Offline | Room queue + WorkManager uploads | Sharing never loses an image regardless of network |
| Backend URL | Configurable in Settings (Render default, localhost for dev) | Avoid repeating the extension's hardcoded-localhost problem |

## Architecture

```
android/app/src/main/java/com/semant/
├── capture/     # ShareActivity, capture bottom sheet, UploadWorker
├── gallery/     # GalleryScreen, PostDetailScreen, ViewModels
├── queue/       # QueueScreen, ViewModel
├── settings/    # SettingsScreen, ViewModel
├── data/        # SemantApi (Retrofit), Room DB, repositories, DTOs
└── ui/          # Compose theme (Semant tokens), shared composables
```

- **Pattern:** MVVM — Compose screens observe ViewModels (StateFlow), ViewModels call repositories. Repositories mirror the web frontend's `services/*.js` layer.
- **Libraries:** Retrofit + kotlinx-serialization, OkHttp, Coil (images), Room (queue), WorkManager (uploads), Hilt (DI), Compose Navigation, Paging 3, DataStore (settings).

## Screens & Navigation

Bottom navigation: **Gallery · Queue · Settings**. Post Detail pushed from Gallery. ShareActivity is outside navigation (translucent, over other apps).

- **Gallery** — paged grid from `GET /api/v1/posts/`, tag filter chips, pull-to-refresh.
- **Post Detail** — pinch-zoom image, tags, source account, read-only Aletheia readings, unconcealment commentary, region annotations rendered as Canvas overlays.
- **Queue** — pending/failed captures with thumbnail, status, retry/delete. Nav badge when items pending.
- **Settings** — base URL, API key, connection test.

## Share Capture Flow

1. `ShareActivity` (translucent theme) registered for `ACTION_SEND` / `ACTION_SEND_MULTIPLE`, MIME `image/*` and `text/plain`.
2. Image shares arrive as content URIs; Chrome link shares arrive as URL text. Both open the same Material 3 bottom sheet: preview, tag input (autocomplete from existing tags), optional note, Save.
3. Save copies image bytes to app-private storage (content URIs expire when the sharing app closes), inserts a `QueuedCapture` row in Room, enqueues WorkManager unique work, finishes. ~2-second interaction.
4. Multi-image shares queue each image with the shared tags (mobile equivalent of the extension's carousel sweep).
5. `UploadWorker`: multipart to `POST /api/v1/posts/` for bytes, JSON to `POST /api/v1/posts/upload-from-url` for URLs (keeps backend referer handling for Instagram/Pinterest). Exponential backoff, network-connected constraint. Success → delete local copy; repeated failure → mark `failed`, notification deep-linking to Queue.

## Data Layer

- **`SemantApi`** (Retrofit): list posts (paginated, tag-filtered), get post, upload multipart, upload-from-url, list tags. DTOs match Pydantic schemas.
- **Room:** single table `queued_captures` (id, localFilePath | sourceUrl, tags, note, status, attemptCount, createdAt). No gallery caching in Phase 1 — Coil disk cache covers images.
- **Repositories:** `PostRepository`, `CaptureRepository`, `SettingsRepository`.
- OkHttp interceptor injects `X-API-Key` from DataStore on every request.

## Backend Change (separate commit)

- FastAPI `require_api_key` dependency on all routers; `API_KEY` in `config.py` + Render env. `/health` stays open.
- Web frontend sends the header via axios default (`VITE_API_KEY`); Chrome extension via its settings storage.
- No CORS change needed for the app (native apps bypass CORS).

## Design Language

Port `design-system/tokens.css` to a Compose theme: paper/ink neutrals, terracotta `#C4533A`, light/dark. Fraunces (display) and Inter (UI) as font resources. The app should feel like Semant, not generic Material.

## Error Handling

- Upload failures retry with backoff; permanent failures surface in Queue with the server's message — never silently dropped.
- API/gallery failures: inline error states with retry; unreachable-base-URL banner linking to Settings.
- Share edge cases: unreadable content URI or oversized image (>25MB) → explanatory toast, nothing queued.

## Testing

- Unit: repositories and UploadWorker (in-memory Room, MockWebServer).
- Instrumented: share → queue → upload happy path.
- Manual checklist vs real backend: share from WhatsApp, Twitter, Chrome (URL), Chrome (long-press image), airplane-mode queue-and-recover.
