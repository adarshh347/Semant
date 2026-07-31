import React, { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { Menu, ChevronDown, Upload as UploadIcon, Command as CommandIcon } from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { Tooltip } from './ui';
import { SemantLogo } from './brand/SemantMark';
import { SectionDivider } from './brand/SectionEyebrow';
import './Navbar.css';

// Ask the shell-level CommandPalette (App.jsx) to open. Decoupled via event so
// the NavBar owns no palette state.
const openCommandPalette = () => window.dispatchEvent(new CustomEvent('semant:open-command'));

// Primary nav — only what a user *does* (the IA declutter). Home is the bento
// dashboard (index route); the rest are what you do from there.
const PRIMARY_LINKS = [
  ['/home', 'Home'],
  ['/gallery', 'Gallery'],
  ['/feed', 'Read'],
  ['/atelier', 'Atelier'],
  ['/you', 'You'],
];

// Demoted tooling — reachable, not shouting. Behind the "Tools" overflow now;
// moves under ⌘K in the Foundation pass. (Highlights/Epics fold into "You".)
const TOOLS_LINKS = [
  ['/research', 'Research'],
  ['/unconceal', 'Unconceal'],
  ['/anatomy', 'Anatomy'],
  ['/motive', 'Motive'],
];

function Navbar() {
  // One open-menu at a time: 'tools' (normal nav overflow) | 'disclosure'
  // (the collapsed rail on /posts/*) | null.
  const [openMenu, setOpenMenu] = useState(null);
  const navRef = useRef(null);

  // Close any menu on outside-click / Escape (same shape as the block menu).
  useEffect(() => {
    if (!openMenu) return undefined;
    const onDocPointer = (e) => {
      if (navRef.current && !navRef.current.contains(e.target)) setOpenMenu(null);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpenMenu(null); };
    document.addEventListener('mousedown', onDocPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [openMenu]);

  const close = () => setOpenMenu(null);

  return (
    <header className="navbar-wrap">
      <nav className="navbar" ref={navRef}>
        {/* The logo (d.1 §8.1): the bespoke "Ground" mark + the Fraunces
            wordmark — one on-concept glyph, no generic dot/asterisk. The mark
            rides on currentColor, reversing with the ink on dark surfaces. */}
        <NavLink to="/" className="nav-logo" aria-label="Semant — home">
          <SemantLogo size={24} />
        </NavLink>

        {/* Inline primary links — the everyday nav. CSS hides these on /posts/*. */}
        <div className="nav-links">
          {PRIMARY_LINKS.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === '/home'}>{label}</NavLink>
          ))}
        </div>

        <div className="nav-actions">
          {/* Tools overflow — the demoted tooling, one quiet dropdown. CSS hides
              it on /posts/*, where the full disclosure carries everything. */}
          <div className="nav-tools">
            <button
              type="button"
              className="nav-tools-btn"
              aria-haspopup="menu"
              aria-expanded={openMenu === 'tools'}
              onClick={() => setOpenMenu((m) => (m === 'tools' ? null : 'tools'))}
            >
              Tools <ChevronDown size={14} />
            </button>
            {openMenu === 'tools' && (
              <div className="nav-menu" role="menu">
                {TOOLS_LINKS.map(([to, label]) => (
                  <NavLink
                    key={to}
                    to={to}
                    role="menuitem"
                    className="nav-menu-item"
                    onClick={close}
                  >
                    {label}
                  </NavLink>
                ))}
              </div>
            )}
          </div>

          {/* ⌘K command palette trigger — the demoted Tools also live in here. */}
          <Tooltip content="Search — ⌘K">
            <button
              type="button"
              className="nav-cmdk-btn"
              aria-label="Open command palette (⌘K)"
              onClick={openCommandPalette}
            >
              <CommandIcon size={15} />
              <span className="nav-cmdk-kbd">K</span>
            </button>
          </Tooltip>

          <ThemeToggle />

          {/* Standing Upload CTA — CSS hides it on /posts/*, where it folds into
              the disclosure menu instead. */}
          <NavLink to="/gallery" className="btn btn-primary btn-sm nav-cta">
            Upload
          </NavLink>

          {/* Disclosure — CSS reveals it only on /posts/*. Holds primary + tools
              + Upload, so nothing is lost when the rail collapses. */}
          <div className="nav-disclosure">
            <button
              type="button"
              className="nav-disclosure-btn"
              aria-haspopup="menu"
              aria-expanded={openMenu === 'disclosure'}
              aria-label="Navigation menu"
              onClick={() => setOpenMenu((m) => (m === 'disclosure' ? null : 'disclosure'))}
            >
              <Menu size={18} />
              <ChevronDown size={14} />
            </button>

            {openMenu === 'disclosure' && (
              <div className="nav-menu nav-menu--wide" role="menu">
                {PRIMARY_LINKS.map(([to, label]) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/home'}
                    role="menuitem"
                    className="nav-menu-item"
                    onClick={close}
                  >
                    {label}
                  </NavLink>
                ))}
                <SectionDivider className="nav-menu-sep" markSize={11} />
                {TOOLS_LINKS.map(([to, label]) => (
                  <NavLink
                    key={to}
                    to={to}
                    role="menuitem"
                    className="nav-menu-item"
                    onClick={close}
                  >
                    {label}
                  </NavLink>
                ))}
                <SectionDivider className="nav-menu-sep" markSize={11} />
                <NavLink
                  to="/gallery"
                  role="menuitem"
                  className="nav-menu-item nav-menu-upload"
                  onClick={close}
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
