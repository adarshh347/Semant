import React from 'react';
import { NavLink } from 'react-router-dom';
import ThemeToggle from './ThemeToggle';
import './Navbar.css';

function Navbar() {
  return (
    <header className="navbar-wrap">
      <nav className="navbar">
        <NavLink to="/" className="nav-logo">
          <span className="nav-logo-mark" aria-hidden="true"></span>
          Drishtikone
        </NavLink>

        <div className="nav-links">
          <NavLink to="/gallery">Gallery</NavLink>
          <NavLink to="/highlights">Highlights</NavLink>
          <NavLink to="/feed">Feed</NavLink>
          <NavLink to="/epics">Epics</NavLink>
          <NavLink to="/research">Research</NavLink>
          <NavLink to="/personas">Personas</NavLink>
          <NavLink to="/motive">Motive</NavLink>
        </div>

        <div className="nav-actions">
          <ThemeToggle />
          <NavLink to="/gallery" className="btn btn-primary btn-sm nav-cta">
            Upload
          </NavLink>
        </div>
      </nav>
    </header>
  );
}

export default Navbar;
