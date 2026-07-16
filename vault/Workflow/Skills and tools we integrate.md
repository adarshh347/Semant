# Skills & tools we integrate (living ledger)

The running account of external agent-skills/tools we bring in. Update this whenever we add, try, or reject one. Related: [[How we work]], [[Frontend beyond visuals - the orchestrator's lens]], [[Constraints we must not break]].

**Status:** installed 2026-07-16 (first real install pass). See [[#Install log 2026-07-16]] for what actually happened vs. what we planned.

## The rule (so we don't create slop by fighting slop)
- **Curate, don't pile.** These are mostly "anti-slop frontend" skills that overlap heavily. Run **one** primary taste skill + **non-overlapping** craft/quality skills. Three competing "make it premium" skills contradict each other.
- **Our project law wins.** The vault's [[Border grammar levels]], [[Purpose Structure Surface]], and the plum v1.3 design tokens are project-specific and override any general skill where they conflict. General skills fill craft we haven't codified (motion, a11y), not re-decide our architecture.
- **Skills are prompts the agent follows; CLIs run code.** `npx skills add <repo>` drops SKILL.md files (low risk, but the agent obeys them — skim before trusting). A CLI like Impeccable executes — review before running in CI.

## Install mechanism (corrected 2026-07-16)
- Installer: `npx skills add <owner/repo | github-url> [--skill <slug>]`.
- **Skills land in `.agents/skills/<name>/SKILL.md`** and are **symlinked** into `.claude/skills/<name>` (they are not written into `.claude/skills` directly). `npx skills list` / `npx skills remove <name>` manage them.
- **A bare `npx skills add <repo>` installs EVERY skill in that repo.** Always pass `--skill <slug>` to take just one. Use `npx skills add <repo> --list` to see valid slugs — **don't guess them** (our two guessed commands below were both wrong).

## Ledger
| Skill / tool | Source | What it's for | Install (verified) | Status |
|---|---|---|---|---|
| **design-taste-frontend** (v2) | Leonxlnx/taste-skill | PRIMARY anti-slop frontend taste (brief inference, dials, pre-flight check) | `npx skills add Leonxlnx/taste-skill --skill design-taste-frontend` | **installed (primary)** |
| **redesign-existing-projects** | Leonxlnx/taste-skill | Audit-first redesign pass on an existing UI | `npx skills add Leonxlnx/taste-skill --skill redesign-existing-projects` | **installed** |
| *11 other taste-skill repo skills* | Leonxlnx/taste-skill | brandkit, design-taste-frontend-v1, full-output-enforcement, gpt-taste, high-end-visual-design, imagegen-frontend-web/-mobile, image-to-code, industrial-brutalist-ui, minimalist-ui, stitch-design-taste | (came in with the bare `add`) | **installed by accident — prune pending** |
| **fixing-accessibility** (ibelick) | ui-skills.com | a11y fixes (keyboard, ARIA, contrast) — craft we haven't codified | `npx skills add https://github.com/ibelick/ui-skills --skill fixing-accessibility` | **blocked (needs approval)** |
| **12-principles-of-animation** (raphaelsalaja) | ui-skills.com | Motion craft (the Behaviour layer) | `npx skills add https://github.com/raphaelsalaja/skill --skill 12-principles-of-animation` | **blocked (needs approval)** |
| **react-doctor** (millionco) | ui-skills.com | React perf/bug audit, 0–100 health score | `npx skills add https://github.com/millionco/react-doctor --skill react-doctor` | **blocked (needs approval)** |
| **vercel-react-best-practices** (vercel-labs) | ui-skills.com | React patterns | `npx skills add https://github.com/vercel-labs/agent-skills --skill vercel-react-best-practices` | **blocked (needs approval)** |
| **playwright-cli** (microsoft) | ui-skills.com | E2E / screenshot verification (fits our "verify by screenshot" rule) | `npx skills add https://github.com/microsoft/playwright-cli --skill playwright-cli` | **blocked (needs approval)** |
| **make-interfaces-feel-better** (jakubkrehel) | ui-skills.com | Micro-interaction / feel polish | — | not installed (overlaps primary) |
| **emil-design-eng** (emilkowalski) | ui-skills.com | Design-engineering craft | — | not installed (overlaps primary) |
| **vitest** (antfu) · **pnpm** (antfu) | ui-skills.com | Testing / package manager | — | optional, not installed |
| **shadcn** (shadcn-ui) | ui-skills.com | shadcn/ui components | — | **skipped** (we are plain CSS + tokens) |
| **Impeccable** | impeccable.style · pbakaus/impeccable | Design-lint CLI (46 rules) for CI | `npx impeccable install` (review first) | **skipped for now** (CLI executes — review before CI) |
| **ui.sh** | ui.sh · Wathan/Schoger | Design/Ideas/Brand-kit skills | invite-gated | **blocked (no invite)** |

## Install log 2026-07-16
- `npx skills add Leonxlnx/taste-skill` → installed **all 13** skills in the repo, not just v2. The curated intent needs `--skill design-taste-frontend`.
- `npx skills add Leonxlnx/taste-skill --skill redesign-skill` → **no such slug**; the installer printed the valid list. The real one is **`redesign-existing-projects`**.
- Our previously-recorded ui-skills command shape (`npx skills add ibelick/fixing-accessibility`) was **wrong**. Every ui-skills.com skill uses a **full GitHub URL + `--skill`** (see table — read off each skill's own page).
- The five ui-skills.com installs and the prune were **denied by the sandbox permission classifier** and await an explicit go.

## Reconciliation — where the skills fight our law
**Our law wins in every row below.** These are noted so the agent doesn't "fix" our deliberate choices.

| Skill says | Our law | Verdict |
|---|---|---|
| Style with **Tailwind v4** (default), design system via **shadcn/ui**; Next.js Server Components / `'use client'` | We are **Vite + React + plain CSS and design tokens**. No Tailwind, no shadcn. | **Ours.** Read the skill's system/stack advice as inapplicable; take only its *reasoning*. |
| **"Discouraged as default: `Inter`"** → pick Geist/Outfit/Cabinet Grotesk/Satoshi; prefer a **sans display** for premium/editorial | Taste **v1.3 LOCKS Fraunces (display serif) + Inter (body)** | **Ours.** The pairing is the brand. |
| Redesign audit: **"flat design with zero texture → add noise/grain/micro-patterns"**, **"break even gradients with radial/mesh/noise"** | Kill-list: **no gradients** (bar the one `--accent-gradient`, ~never), no glow/glass; "mostly flat-on-paper", "go flatter still" | **Ours.** Do not add grain/mesh. |
| **"All-caps subheaders everywhere"** flagged as a problem | The **UPPERCASE eyebrow** (`--fs-caption`, `--tracking-wide`) is one of our three locked type roles | **Ours.** |
| **"Purple/blue AI-gradient aesthetic"** is the #1 AI tell → replace | Our accent **is plum/aubergine `#5E2B50`** — a deliberate identity (v1.3), used as a flat accent + region marks, never an AI gradient | **Ours.** Don't let the skill launder our plum away — the tell is the *gradient*, not the hue. |
| Baseline dials **`VARIANCE 8 / MOTION 6 / DENSITY 4`** | "**Craft = restraint**", ≤1 accent per view, motion 150–320ms, rise 8–16px, nothing bouncy | **Ours.** Use the skill's own *editorial* row (**~5-6 / 3-4 / 2-3**), never the 8/6/4 baseline. |
| Colored/tinted shadows | Our `--shadow-*` scale is ink-tinted already; shadows are rare | **Ours.** |
| *(no equivalent)* | **[[Border grammar levels]]** L0–L5 decides who may draw a border | **Ours — fills a gap the skills don't have.** |
| *(no equivalent)* | **[[Purpose Structure Surface]]** — Purpose decides Structure decides Surface | **Ours — the skills jump to Surface; this gates them.** |

**Where the skills genuinely help (adopt):**
- **Scope honesty** — design-taste-frontend self-scopes to *"landing pages, portfolios, redesigns — not dashboards, not multi-step product UI."* So it applies to **`/` (the motive landing)**, not to Home/Archive/Chiasm, which are product UI.
- **Anti-default list** matches our kill-list (no AI-purple gradient, no centred hero on dark mesh, no three equal feature cards, no glassmorphism-on-everything).
- **Emphasis rule** — emphasise with *italic/bold of the same family*, never a random serif word in a sans headline. Our landing's italic-Fraunces-inside-Fraunces already complies.
- **Never `useState` for continuous pointer/scroll values** — use Motion values or direct writes. Our fisheye Wall already does this (rAF + direct DOM).
- **`text-wrap: balance`, `tabular-nums`, ~65ch measure, negative tracking on large heads, off-black not `#000`** — all already true of our tokens/components.

## Decision log
- **Primary taste skill = design-taste-frontend (v2)**, scoped to the landing. Everything else must complement, not duplicate it.
- **Prune recommended (pending approval):** remove the 11 unrequested repo skills — they are competing aesthetics (`industrial-brutalist-ui` is the literal opposite of our language; `minimalist-ui`, `gpt-taste`, `high-end-visual-design`, `stitch-design-taste` all re-decide Surface) or image-gen tools we don't use. One command:
  `npx skills remove brandkit design-taste-frontend-v1 full-output-enforcement gpt-taste high-end-visual-design imagegen-frontend-mobile imagegen-frontend-web image-to-code industrial-brutalist-ui minimalist-ui stitch-design-taste`
- Skip **shadcn** (wrong stack) and the overlapping taste variants (make-interfaces-feel-better, emil-design-eng).
- **ui.sh** — request an invite; revisit when granted.
