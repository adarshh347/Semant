// frontend/src/App.jsx
import { Outlet, useLocation } from 'react-router-dom';
import Navbar from './components/NavBar';
import CommandPalette from './components/CommandPalette';
import UploadDialog from './components/UploadDialog';
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
        <Outlet />
      </main>
      {/* Global ⌘K command palette — one shell-level mount for every route. */}
      <CommandPalette />
      {/* Global upload dialog — opened from ⌘K or the Archive's Upload button. */}
      <UploadDialog />
    </div>
  );
}
export default App;