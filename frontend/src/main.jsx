import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

// Import early so the X-API-Key header (axios default + fetch patch) is
// installed before any component fires a request.
import './config/api.js';

import App from './App.jsx';
import LandingPage from './pages/LandingPage.jsx';
import GalleryPage from './pages/GalleryPage.jsx';
import PostDetailPage from './components/PostDetailPage.jsx';
import ReadDeeperPage from './pages/ReadDeeperPage.jsx';
import HighlightsPage from './pages/HighlightsPage.jsx';
import './index.css';
import TextFeedPage from './pages/TextFeedPage.jsx';
import EpicsPage from './pages/EpicsPage.jsx';
import EpicEditorPage from './pages/EpicEditorPage.jsx';
import MotivePage from './pages/MotivePage.jsx';
import ResearchPage from './pages/ResearchPage.jsx';
import PersonasPage from './pages/PersonasPage.jsx';
import UnconcealQueuePage from './pages/UnconcealQueuePage.jsx';
import AnatomyPage from './pages/AnatomyPage.jsx';
import BlockNoteLab from './pages/BlockNoteLab.jsx';
import PlaceholderPage from './components/PlaceholderPage.jsx';

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
      { path: "feed", element: <TextFeedPage /> },
      { path: "epics", element: <EpicsPage /> },
      { path: "epics/:id", element: <EpicEditorPage /> },
      { path: "research", element: <ResearchPage /> },
      { path: "personas", element: <PersonasPage /> },
      { path: "unconceal", element: <UnconcealQueuePage /> },
      { path: "anatomy", element: <AnatomyPage /> },
      // Editor Path B · Phase 0 — isolated BlockNote spike, before Phase 2 touches PostDetailPage.
      { path: "lab/blocknote", element: <BlockNoteLab /> },
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
      { path: "motive", element: <MotivePage /> }
    ],
  },
]);

import { ThemeProvider } from './context/ThemeContext';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ThemeProvider>
      <RouterProvider router={router} />
    </ThemeProvider>
  </React.StrictMode>
);