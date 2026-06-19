import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

import App from './App.jsx';
import LandingPage from './pages/LandingPage.jsx';
import GalleryPage from './pages/GalleryPage.jsx';
import PostDetailPage from './components/PostDetailPage.jsx';
import HighlightsPage from './pages/HighlightsPage.jsx';
import CroppedAnnotationsPage from './pages/CroppedAnnotationsPage.jsx';
import './index.css';
import TextFeedPage from './pages/TextFeedPage.jsx';
import EpicsPage from './pages/EpicsPage.jsx';
import EpicEditorPage from './pages/EpicEditorPage.jsx';
import MotivePage from './pages/MotivePage.jsx';

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "gallery", element: <GalleryPage /> },
      { path: "highlights", element: <HighlightsPage /> },
      { path: "posts/:postId", element: <PostDetailPage /> },
      { path: "posts/:postId/crops", element: <CroppedAnnotationsPage /> },
      { path: "feed", element: <TextFeedPage /> },
      { path: "epics", element: <EpicsPage /> },
      { path: "epics/:id", element: <EpicEditorPage /> },
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