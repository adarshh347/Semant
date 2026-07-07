import React, { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { Menu, ChevronDown, Upload as UploadIcon } from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import './Navbar.css';

// One source of truth for the global links — rendered inline everywhere, and
// again inside the disclosure menu that replaces them on /posts/* (Drishya).
const NAV_LINKS = [
  ['/gallery', 'Gallery'],
  ['/highlights', 'Highlights'],
  ['/feed', 'Feed'],
  ['/epics', 'Epics'],
  ['/research', 'Research'],
  ['/personas', 'Personas'],
  ['/unconceal', 'Unconceal'],
  ['/anatomy', 'Anatomy'],
  ['/motive', 'Motive'],
];

function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const discRef = useRef(null);

  // Close the disclosure on outside-click / Escape (same shape as the block menu).
  useEffect(() => {
    if (!menuOpen) return undefined;
    const onDocPointer = (e) => {
      if (discRef.current && !discRef.current.contains(e.target)) setMenuOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onDocPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  return (
    <header className="navbar-wrap">
      <nav className="navbar">
        <NavLink to="/" className="nav-logo">
          <span className="nav-logo-mark" aria-hidden="true"></span>
          Drishtikone
        </NavLink>

        {/* Inline links — the everyday nav. CSS hides these on /posts/*. */}
        <div className="nav-links">
          {NAV_LINKS.map(([to, label]) => (
            <NavLink key={to} to={to}>{label}</NavLink>
          ))}
        </div>

        <div className="nav-actions">
          <ThemeToggle />
          {/* Standing Upload CTA — CSS hides it on /posts/*, where it folds
              into the disclosure menu instead. */}
          <NavLink to="/gallery" className="btn btn-primary btn-sm nav-cta">
            Upload
          </NavLink>

          {/* Disclosure — CSS reveals it only on /posts/*. Holds all 9 links
              plus Upload, so nothing is lost when the rail collapses. */}
          <div className="nav-disclosure" ref={discRef}>
            <button
              type="button"
              className="nav-disclosure-btn"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              aria-label="Navigation menu"
              onClick={() => setMenuOpen((o) => !o)}
            >
              <Menu size={18} />
              <ChevronDown size={14} />
            </button>

            {menuOpen && (
              <div className="nav-disclosure-menu" role="menu">
                {NAV_LINKS.map(([to, label]) => (
                  <NavLink
                    key={to}
                    to={to}
                    role="menuitem"
                    className="nav-disclosure-item"
                    onClick={() => setMenuOpen(false)}
                  >
                    {label}
                  </NavLink>
                ))}
                <div className="nav-disclosure-sep" />
                <NavLink
                  to="/gallery"
                  role="menuitem"
                  className="nav-disclosure-item nav-disclosure-upload"
                  onClick={() => setMenuOpen(false)}
                >
                  <UploadIcon size={15} /> Upload
                </NavLink>
              </div>
            )}
          </div>
        </div>
      </nav>
    </header>
  );
}

export default Navbar;
