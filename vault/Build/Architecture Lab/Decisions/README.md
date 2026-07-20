# Architecture Lab — Post Detail page

This folder is a **conversation between two assistants**:

- **Claude (desktop / Cowork)** — writes the study and the research prompts. Files ending in `.prompt.md`.
- **Claude Code (local CLI, running in this repo)** — does the deep reading and writes findings into `responses/`.

The human (Adarsh) reads both sides and decides what actually gets built.

## The rule for this whole folder

We are doing **architecture only**. That means:

- Which components exist, how they nest, which wrappers are redundant.
- What the *optimal* set of components would be (fewer boxes, less nesting, one clear home for each thing).
- **No colours, no fonts, no spacing polish, no copywriting.** Those come later.

If a prompt or a reply starts talking about "premium feel" or "make it beautiful", it has drifted. Pull it back.

## How a round works

1. Claude Code picks a lane, e.g. `lane-5-writing-studio.prompt.md`.
2. It does the reading the prompt asks for (open the real files, trace the component tree).
3. It writes its answer to `responses/lane-5-writing-studio.findings.md`, following the output contract at the bottom of the prompt.
4. It does **not** edit any app code yet. Research and plan only.
5. Adarsh + Claude read the findings, decide, then a *separate, narrow* build prompt is written later.

## The six lanes

1. `lane-1-top-chrome.prompt.md` — the two stacked top bars, the navbar, the trio buttons, the persona line.
2. `lane-2-split-shell.prompt.md` — the split container, the divider, the panel headers, how the two panes relate.
3. `lane-3-visual-annotation.prompt.md` — inside the Visual pane: stats bar, image, bounding-box overlays, tag list.
4. `lane-4-content-view.prompt.md` — the Content pane in *view* mode: source row, empty state, story blocks, tags.
5. `lane-5-writing-studio.prompt.md` — the Content pane in *edit* mode: the block editor and its sub-tools.
6. `lane-6-unconceal.prompt.md` — the Unconceal tab: anatomy + Aletheia + commentary.

Start with `00-architecture-map.md` for the plain-language overview.
