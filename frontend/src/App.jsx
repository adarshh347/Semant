// frontend/src/App.jsx
import { Outlet, useLocation } from 'react-router-dom';
import Navbar from './components/NavBar';
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
    </div>
  );
}
export default App;