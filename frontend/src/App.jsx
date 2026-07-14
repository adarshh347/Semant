// frontend/src/App.jsx
import { Suspense } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Navbar from './components/NavBar';
import CommandPalette from './components/CommandPalette';
import RouteFallback from './components/RouteFallback';
import './App.css';

function App() {
  const location = useLocation();
  const isLandingPage = location.pathname === '/';
  // Full-screen pages that should not have the app-content wrapper
  const isFullscreenPage = location.pathname.startsWith('/posts/');

  return (
    <div className={`app-layout ${isLandingPage ? 'app-layout--landing' : ''} ${isFullscreenPage ? 'app-layout--fullscreen' : ''}`}>
      <Navbar />
      <main className={isFullscreenPage ? 'app-main--fullscreen' : (isLandingPage ? '' : 'app-content')}>
        {/* One Suspense boundary for every lazy route — the chrome stays put
            while the route chunk loads. */}
        <Suspense fallback={<RouteFallback />}>
          <Outlet />
        </Suspense>
      </main>
      {/* Global ⌘K command palette — one shell-level mount for every route. */}
      <CommandPalette />
    </div>
  );
}
export default App;