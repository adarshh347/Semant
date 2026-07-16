import { useState } from 'react';
import { cldRegionCrop } from '../../lib/cloudinary';

// The "lifted percept" — the pixels of one marked region, cropped by Cloudinary
// to the region's bounding box and then clipped to the region's own polygon
// shape (CSS clip-path, the modern equivalent of an SVG <clipPath>). The tile
// takes the crop's true aspect (read on load) so object-fit never distorts the
// shape, and the polygon coordinates — re-based into the crop's local 0..1 box —
// line up exactly.
const clampPct = (n) => Math.min(100, Math.max(0, n * 100)).toFixed(1);

export default function PerceptCrop({ photoUrl, region, label }) {
  const box = region?.box;
  // Fall back to the box's normalized ratio until the real pixels report their
  // aspect; a portrait default keeps the row from jumping too far.
  const [aspect, setAspect] = useState(box && box.w && box.h ? box.w / box.h : 0.8);
  if (!box || !photoUrl) return null;

  const cropUrl = cldRegionCrop(photoUrl, box, 360);
  const poly = Array.isArray(region.polygon) && region.polygon.length > 2;
  const clipPath = poly
    ? `polygon(${region.polygon
        .map(([px, py]) => `${clampPct((px - box.x) / box.w)}% ${clampPct((py - box.y) / box.h)}%`)
        .join(', ')})`
    : 'none';

  return (
    <div className="percept-crop" style={{ aspectRatio: aspect }} title={label}>
      <img
        src={cropUrl}
        alt={label || 'a marked part'}
        loading="lazy"
        style={{ clipPath }}
        onLoad={(e) => {
          const { naturalWidth: w, naturalHeight: h } = e.currentTarget;
          if (w && h) setAspect(w / h);
          e.currentTarget.classList.add('is-loaded');
        }}
      />
    </div>
  );
}
