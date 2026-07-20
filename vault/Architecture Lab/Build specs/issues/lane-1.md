# Lane 1 — top chrome: slim the two bars

Labels: architecture, drishya
Spec: architecture-lab/lane-1-top-chrome.build.md · Research: architecture-lab/responses/lane-1-top-chrome.findings.md

## Checklist
- [x] Collapse 9 navbar links → one disclosure menu on /posts/* (existing app-layout--fullscreen hook); fold Upload into it.
- [x] Remove duplicate topbar ThemeToggle (keep navbar copy).
- [x] Sutradhar brand → small quiet left label, no center slot.
- [x] AI Assistant → de-weight primary → secondary.
- [x] Edit → remove button; pencil on Content panel header enters edit.
- [x] Delete → topbar "⋯" overflow menu.
- [x] Back-link stays.

Do-no-harm: theme, all 9 links, Upload, leave, AI, edit, delete all reachable. Verify by screenshot. Run after the Compose-card removal (shared file: PostDetailPage.jsx).

## Delivered (commits `644dbd2` navbar, `d1e1c26` topbar — verified by screenshot)
| Item | How | Verified |
|---|---|---|
| Navbar collapse on /posts/* | `NavBar.jsx` disclosure menu (all 9 links + Upload); CSS keyed off `.app-layout--fullscreen` hides `.nav-links` + `.nav-cta`, shows `.nav-disclosure` | shot 20 (slim rail) / 21 (menu open: 9 links + Upload). `/gallery` still shows 9 inline links + standing Upload (scoped) |
| Duplicate ThemeToggle removed | deleted topbar `<ThemeToggle>` + import; navbar copy survives | `.post-detail-topbar .theme-toggle-btn` count = 0; navbar = 1 |
| Sutradhar → quiet left label | folded into `.topbar-left` beside back-link; `.sutradhar-brand` no longer absolute-center | shot 20 ("← Gallery  Sutradhar") |
| AI Assistant de-weighted | always `secondary` (soft-accent `.active` when open), no primary gradient | class = `action-btn topbar-ai-btn secondary` |
| Edit button removed → pencil | `.panel-edit-btn` on the Content panel header; enters edit + activates Story tab; hidden while editing | shot 23 (pencil → edit-shell) |
| Delete → "⋯" overflow | `.topbar-overflow` menu (outside-click/Escape close); reuses block-overflow shape | shot 22 ("Delete post") |
| Back-link kept | unchanged | shot 20 |

Surface deferred: rail/menu/overflow spacing + colour polish left for the Surface pass.
