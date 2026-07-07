# Lane 2 — split shell: divider, headers, edit-narrow (shell only)

Labels: architecture, drishya
Spec: architecture-lab/lane-2-split-shell.build.md · Research: architecture-lab/responses/lane-2-split-shell.findings.md

## Checklist (shell only)
- [x] Drop Visual/Content h3 titles; header = tabs + right actions slot.
- [x] Edit mode narrows Visual pane via the width SSOT (smooth), restore on exit.
- [x] Divider: collapse-to-rail toggle + double-click reset (keep drag, 20–80 clamp).
- [x] Harden divider to ARIA window-splitter (focusable separator, aria-value*, Arrow-key resize). No allotment dep.

## DEFERRED to Darshan Track A (do NOT build here)
Region-model merge (bounding_box_tags + region_annotations) and cross-pane selection linking. Leave BoundingBoxEditor/RegionDetectorModal untouched.

Verify by screenshot + keyboard. Shared file: PostDetailPage.jsx — pull first, don't parallelize builds.

## Delivered (commit `1e87c2a` — verified by screenshot + keyboard test)
| Item | How | Verified |
|---|---|---|
| Tabs-only headers | dropped both `<h3>`; `.panel-header` = `.panel-tabs` (left) + `.panel-actions` (right, pencil on Content, empty slot on Visual) | `document.querySelectorAll('.panel-header h3').length === 0`; shot 30 |
| Edit narrows Visual | `useEffect([isEditing])` sets `leftPanelWidth` 45→`SPLIT_EDIT` (30) and restores the pre-edit width on exit; opacity-dim removed; `width` transition on the panes (suppressed during drag) | 45→30 on edit, →45 on cancel; shot 32 (narrowed, full opacity) |
| Divider presets | `toggleCollapse` (rail 4%, remembers prior width), `resetWidth` (45) on double-click; collapse button on the divider | Home→4 (collapsed class), End→45, Enter toggles 45↔4, dblclick 41→45; shot 31 |
| ARIA window-splitter | `role=separator` `tabindex=0` `aria-orientation=vertical` `aria-valuemin/max/now`; keys ←/→ nudge (clamp 20–80), Home/End/Enter | role/tab/min/max = separator/0/20/80; Arrow 45→51→49; aria-valuenow tracks |
| No allotment dep | hand-rolled divider hardened; `allotment` not imported/added | — |
| Region model untouched | BoundingBoxEditor.jsx / RegionDetectorModal.jsx not opened; no region data touched | git diff = only PostDetailPage.jsx/.css |

Deferred per plan: single boundary grammar (border+gap+line) and the centered-column double-inset flag are Surface/later; cross-pane linking waits on Track A.
