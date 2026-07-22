// frontend/src/App.jsx
import { Suspense } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Navbar from './components/NavBar';
import CommandPalette from './components/CommandPalette';
import UploadDialog from './components/UploadDialog';
import GlobalShortcuts from './components/GlobalShortcuts';
import ShortcutsDialog from './components/ShortcutsDialog';
import { MarkLoader } from './components/brand/MarkLoader';
import './App.css';

// Shown while a lazily-loaded route chunk resolves — the branded mark loader,
// not a generic spinner. Reduced-motion falls back to a static mark (brand.css).
function RouteFallback() {
  return <MarkLoader label="Loading…" />;
}

function App() {
  const location = useLocation();
  // '/' is the full-bleed motive landing (the front door); the bento Home lives
  // at /home and sits in the standard content column like the other app pages.
  const isLandingPage = location.pathname === '/';
  // Full-screen pages that should not have the app-content wrapper
  const isFullscreenPage = location.pathname.startsWith('/posts/');

  return (
    <div className={`app-layout ${isLandingPage ? 'app-layout--landing' : ''} ${isFullscreenPage ? 'app-layout--fullscreen' : ''}`}>
      <Navbar />
      <main className={isFullscreenPage ? 'app-main--fullscreen' : (isLandingPage ? '' : 'app-content')}>
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </main>
      {/* Global ⌘K command palette — one shell-level mount for every route. */}
      <CommandPalette />
      {/* Global upload dialog — opened from ⌘K or the Archive's Upload button. */}
      <UploadDialog />
      {/* App-wide keyboard shortcuts (g-nav, ?) + the shortcuts sheet. */}
      <GlobalShortcuts />
      <ShortcutsDialog />
    </div>
  );
}
export default App;