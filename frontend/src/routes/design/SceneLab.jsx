import React from 'react';
import NearArrival from '../../components/scene/NearArrival.jsx';

/**
 * Dev-only staging lab for the hero scene (/_design/scene) — the "verified
 * against the staging lab side by side" check from the migration spec. Mounts
 * NearArrival in a hero-sized frame on the real page ground so the composed
 * still, the play-on-scroll and the pointer parallax can all be eyeballed.
 */
export default function SceneLab() {
  return (
    <div className="pe-scope" style={{ background: 'var(--page)', minHeight: '100vh', padding: 24 }}>
      <div style={{ maxWidth: 1080, margin: '0 auto' }}>
        <figure style={{ margin: 0, aspectRatio: '1200 / 760', borderRadius: 20, overflow: 'hidden', border: '1px solid var(--hairline)' }}>
          <NearArrival />
        </figure>
      </div>
    </div>
  );
}
