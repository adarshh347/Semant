import React, { lazy } from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

// Import early so the X-API-Key header (axios default + fetch patch) is
// installed before any component fires a request.
import './config/api.js';
import './index.css';

// Eager: the shell + the tiny inline placeholder (rendered directly in route
// config, not as a route element).
import App from './App.jsx';
import PlaceholderPage from './components/PlaceholderPage.jsx';

// Lazy: every route page splits into its own chunk and loads on demand. This is
// what pulls the heavy editor deps (BlockNote/TipTap on the /posts, /lab/*, and
// epic-editor routes) and the Gallery out of the initial bundle.
const LandingPage = lazy(() => import('./pages/LandingPage.jsx'));
const GalleryPage = lazy(() => import('./pages/GalleryPage.jsx'));
const PostDetailPage = lazy(() => import('./components/PostDetailPage.jsx'));
const ReadDeeperPage = lazy(() => import('./pages/ReadDeeperPage.jsx'));
const RegionSurfaceLab = lazy(() => import('./pages/RegionSurfaceLab.jsx'));
const HighlightsPage = lazy(() => import('./pages/HighlightsPage.jsx'));
const TextFeedPage = lazy(() => import('./pages/TextFeedPage.jsx'));
const EpicsPage = lazy(() => import('./pages/EpicsPage.jsx'));
const EpicEditorPage = lazy(() => import('./pages/EpicEditorPage.jsx'));
const MotivePage = lazy(() => import('./pages/MotivePage.jsx'));
const ResearchPage = lazy(() => import('./pages/ResearchPage.jsx'));
const PersonasPage = lazy(() => import('./pages/PersonasPage.jsx'));
const UnconcealQueuePage = lazy(() => import('./pages/UnconcealQueuePage.jsx'));
const AnatomyPage = lazy(() => import('./pages/AnatomyPage.jsx'));
const BlockNoteLab = lazy(() => import('./pages/BlockNoteLab.jsx'));
const ManuscriptLab = lazy(() => import('./pages/ManuscriptLab.jsx'));

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "gallery", element: <GalleryPage /> },
      { path: "highlights", element: <HighlightsPage /> },
      { path: "posts/:postId", element: <PostDetailPage /> },
      // Track F — the audience's "read deeper" pause (Écart), the lite variant of the
      // creator's Visual pane.
      { path: "read/:postId", element: <ReadDeeperPage /> },
      // Track D Phase 1 — dev harness for RegionSurface, before it is mounted for real.
      { path: "lab/region-surface/:postId", element: <RegionSurfaceLab /> },
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
      { path: "motive/:slug", element: <MotivePage /> }
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