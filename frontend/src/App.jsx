// frontend/src/App.jsx
import { Outlet, useLocation } from 'react-router-dom';
import Navbar from './components/NavBar';
import CommandPalette from './components/CommandPalette';
import UploadDialog from './components/UploadDialog';
import GlobalShortcuts from './components/GlobalShortcuts';
import ShortcutsDialog from './components/ShortcutsDialog';
import './App.css';

function App() {
  const location = useLocation();
  // The full-bleed marketing landing now lives at /welcome; '/' is the bento Home,
  // which sits in the standard content column like the other app pages.
  const isLandingPage = location.pathname === '/welcome';
  // Full-screen pages that should not have the app-content wrapper
  const isFullscreenPage = location.pathname.startsWith('/posts/');

  return (
    <div className={`app-layout ${isLandingPage ? 'app-layout--landing' : ''} ${isFullscreenPage ? 'app-layout--fullscreen' : ''}`}>
      <Navbar />
      <main className={isFullscreenPage ? 'app-main--fullscreen' : (isLandingPage ? '' : 'app-content')}>
        <Outlet />
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