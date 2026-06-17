import React from 'react';
import { Link } from 'react-router-dom';
import legPalmImage from '../assets/leg-palm.jpg';
import './LandingPage.css';

function LandingPage() {
  return (
    <div className="landing-page">
      <section className="landing-hero">
        {/* Left - Content */}
        <div className="landing-content">
          <span className="landing-tagline eyebrow">A Visual Storytelling Studio</span>

          <h1 className="landing-title">
            <span className="landing-title-hindi">दृष्टिकोण</span>
            See more in <em>every</em> frame.
          </h1>

          <p className="landing-description">
            An interactive canvas where images meet narrative. Gather your frames,
            tag the details that matter, and let Drishtikone weave them into
            semantic stories and long-form visual epics.
          </p>

          <div className="landing-cta-row">
            <Link to="/gallery" className="landing-cta">
              Explore Gallery
              <span className="landing-cta-arrow">→</span>
            </Link>
            <Link to="/epics" className="landing-cta-secondary">
              See an epic
            </Link>
          </div>

          <div className="landing-features">
            <div className="landing-feature">
              <div className="landing-feature-number">01</div>
              <div className="landing-feature-text">
                Curate collections with semantic tagging and AI-powered organization.
              </div>
            </div>
            <div className="landing-feature">
              <div className="landing-feature-number">02</div>
              <div className="landing-feature-text">
                Weave images into compelling, long-form visual narratives.
              </div>
            </div>
          </div>
        </div>

        {/* Right - Image */}
        <div className="landing-image-container">
          <div className="landing-image-frame">
            <img
              src={legPalmImage}
              alt="Visual storytelling"
              className="landing-image"
            />
          </div>
          <span className="landing-decorative-text">Art &amp; Narrative</span>
        </div>
      </section>
    </div>
  );
}

export default LandingPage;
