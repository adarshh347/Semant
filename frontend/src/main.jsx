import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

// Import early so the X-API-Key header (axios default + fetch patch) is
// installed before any component fires a request.
import './config/api.js';

import App from './App.jsx';
import RouteError from './components/RouteError.jsx';
import NotFoundPage from './components/NotFoundPage.jsx';
import PlaceholderPage from './components/PlaceholderPage.jsx';
import './index.css';
// Landing design-system tokens (six hues + two @property anim props), scoped to
// `.pe-scope`. Imported once here so the whole app can reference them but only
// the landing surfaces (which wear `.pe-scope`) actually adopt the palette.
import './styles/tokens.css';
// Self-hosted fonts (replaces Inter + Spline Sans Mono on the app's Google Fonts
// link — both used app-wide, so imported globally, not just on the landing).
// Playfair Display is landing-only and self-hosted in LandingPage.jsx.
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/spline-sans-mono/400.css';
import '@fontsource/spline-sans-mono/500.css';

// Route pages are code-split (React.lazy) so a navigation resolves its chunk
// behind the branded RouteFallback (App.jsx) instead of loading the whole app
// up front. App / PlaceholderPage / the error surfaces stay eager — the shell
// and its error boundary must never themselves suspend.
const HomePage = React.lazy(() => import('./pages/HomePage.jsx'));
const LandingPage = React.lazy(() => import('./pages/LandingPage.jsx'));
const GalleryPage = React.lazy(() => import('./pages/GalleryPage.jsx'));
const PostDetailPage = React.lazy(() => import('./components/PostDetailPage.jsx'));
const ReadDeeperPage = React.lazy(() => import('./pages/ReadDeeperPage.jsx'));
const RegionSurfaceLab = React.lazy(() => import('./pages/RegionSurfaceLab.jsx'));
const RefineLab = React.lazy(() => import('./pages/RefineLab.jsx'));
const DifferentialLab = React.lazy(() => import('./pages/DifferentialLab.jsx')); // DEV-ONLY · CIRCUIT-001 P2E-B harness
const ArticleLab = React.lazy(() => import('./pages/ArticleLab.jsx')); // DEV-ONLY · CIRCUIT-003 M4 harness
// AGENT-DEMO — the run surface: images + a prompt → the orchestrator working, in the open.
// Its OWN route and shell, deliberately not folded into /differential, which is the manual
// instrument and has diverged from this on purpose.
const AgentDemoPage = React.lazy(() => import('./agentDemo/AgentDemoPage.jsx'));
const HighlightsPage = React.lazy(() => import('./pages/HighlightsPage.jsx'));
const TextFeedPage = React.lazy(() => import('./pages/TextFeedPage.jsx'));
const EpicsPage = React.lazy(() => import('./pages/EpicsPage.jsx'));
const EpicEditorPage = React.lazy(() => import('./pages/EpicEditorPage.jsx'));
const MotivePage = React.lazy(() => import('./pages/MotivePage.jsx'));
const ResearchPage = React.lazy(() => import('./pages/ResearchPage.jsx'));
const PersonasPage = React.lazy(() => import('./pages/PersonasPage.jsx'));
const UnconcealQueuePage = React.lazy(() => import('./pages/UnconcealQueuePage.jsx'));
const AnatomyPage = React.lazy(() => import('./pages/AnatomyPage.jsx'));
const BlockNoteLab = React.lazy(() => import('./pages/BlockNoteLab.jsx'));
const ManuscriptLab = React.lazy(() => import('./pages/ManuscriptLab.jsx'));
// Writing Studio (WS-0A) — the standalone manuscript-oriented writing tool.
const StudioPage = React.lazy(() => import('./studio/StudioPage.jsx'));
// DEV-ONLY · landing-migration checkpoint — the glyph contact sheet, proving the
// 21 glyphs render identically once migrated into Semant (asset-layer fidelity).
// Guarded so vite statically drops both the const and its dynamic-import chunk
// from production builds (import.meta.env.DEV → false → dead branch eliminated).
const GlyphContactSheet = import.meta.env.DEV
  ? React.lazy(() => import('./routes/design/GlyphContactSheet.jsx'))
  : null;
const SceneLab = import.meta.env.DEV
  ? React.lazy(() => import('./routes/design/SceneLab.jsx'))
  : null;

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    // Root error boundary — a thrown route (or a 404 Response) renders the
    // branded RouteError surface instead of the browser's raw stack.
    errorElement: <RouteError />,
    children: [
      // '/' is the motive See·Read·Write front door; its "Enter" CTA leads into
      // the app at /home, the curated bento dashboard.
      { index: true, element: <LandingPage /> },
      // DEV-ONLY · landing-migration asset checkpoint (stripped from prod builds).
      ...(import.meta.env.DEV
        ? [
            { path: "_design/glyphs", element: <GlyphContactSheet /> },
            { path: "_design/scene", element: <SceneLab /> },
          ]
        : []),
      { path: "home", element: <HomePage /> },
      { path: "gallery", element: <GalleryPage /> },
      { path: "highlights", element: <HighlightsPage /> },
      { path: "posts/:postId", element: <PostDetailPage /> },
      // Track F — the audience's "read deeper" pause (Écart), the lite variant of the
      // creator's Visual pane.
      { path: "read/:postId", element: <ReadDeeperPage /> },
      // Track D Phase 1 — dev harness for RegionSurface, before it is mounted for real.
      { path: "lab/region-surface/:postId", element: <RegionSurfaceLab /> },
      { path: "lab/refine/:postId", element: <RefineLab /> },
      // DEV-ONLY · CIRCUIT-001 P2E-B — offline Differential harness (fixture post).
      { path: "lab/differential", element: <DifferentialLab /> },
      // DEV-ONLY · CIRCUIT-003 M4 — the perceptual article over an offline fixture draft.
      { path: "lab/article", element: <ArticleLab /> },
      // AGENT-DEMO — a real user surface, not a lab: images + a prompt, and the run in the open.
      { path: "agent", element: <AgentDemoPage /> },
      { path: "feed", element: <TextFeedPage /> },
      { path: "epics", element: <EpicsPage /> },
      { path: "epics/:id", element: <EpicEditorPage /> },
      { path: "research", element: <ResearchPage /> },
      { path: "personas", element: <PersonasPage /> },
      { path: "unconceal", element: <UnconcealQueuePage /> },
      { path: "anatomy", element: <AnatomyPage /> },
      // Editor Path B · Phase 0 — isolated BlockNote spike, before Phase 2 touches PostDetailPage.
      { path: "lab/blocknote", element: <BlockNoteLab /> },
      { path: "lab/manuscript", element: <ManuscriptLab /> },
      // Writing Studio (WS-0A) — writing by orchestration; the manuscript is sacred.
      { path: "studio", element: <StudioPage /> },
      // Primary-nav destinations, stubbed on-taste until their full pages land.
      // Atelier = the per-post workspace (/posts/:postId); this is its on-ramp
      // until the route rename. You = the taste/profile hub over Highlights/Epics.
      {
        path: "atelier",
        element: (
          <PlaceholderPage
            eyebrow="Workspace"
            title="The Atelier"
            lede="Your image, read part by part, and written from — all in one room. Open an image from the Gallery to begin."
            cta={{ to: "/gallery", label: "Open the Gallery" }}
          />
        ),
      },
      {
        path: "you",
        element: (
          <PlaceholderPage
            motif="portrait"
            eyebrow="Your taste"
            title="You"
            lede="Your eye, written down — the details you keep noticing, given back to you. Your highlights and epics live here; the taste portrait is on the way."
            links={[
              { to: "/highlights", label: "Highlights" },
              { to: "/epics", label: "Epics" },
            ]}
          />
        ),
      },
      { path: "motive", element: <MotivePage /> },
      { path: "motive/:slug", element: <MotivePage /> },
      // Catch-all — a branded 404 inside the app shell (keeps the nav + chrome).
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

import { ThemeProvider } from './context/ThemeContext';
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './lib/queryClient';
import { ToastProvider, TooltipProvider } from './components/ui';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <TooltipProvider delayDuration={250}>
          <ToastProvider>
            <RouterProvider router={router} />
          </ToastProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </React.StrictMode>
);