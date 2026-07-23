import './states.css';

// Hand-drawn plum line motifs in the region-mark language — the illustration
// that leads a branded empty state. Thick-line, one plum accent (per the taste
// spec §7, matching the landing See·Read·Write cards), drawn a touch loose so
// they read as drawn, not clip-art. Each says what the empty room is *for*, so
// the state can be a door rather than a dead box. Static — no motion.
//
// Everything rides on currentColor (the plum accent, set in states.css); the
// one soft fill uses --accent-soft so it survives the light/dark flip.
const VIEW = '0 0 72 72';
const COMMON = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2.4,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  xmlns: 'http://www.w3.org/2000/svg',
};

// seed — nothing started yet: an open frame with a dashed region and a small
// mark waiting to be made. "Begin here."
function Seed() {
  return (
    <svg viewBox={VIEW} {...COMMON} aria-hidden="true">
      <path d="M14 15 Q13 12 16 12 L55 13 Q59 13 58 17 L57 54 Q57 58 53 57 L16 56 Q13 56 13 53 Z" />
      <rect x="25" y="24" width="22" height="20" rx="4" strokeDasharray="3 5" opacity="0.75" />
      <path d="M36 30 L36 38 M32 34 L40 34" />
    </svg>
  );
}

// stack — an empty reel of written stories: offset cards, the top one a frame.
function Stack() {
  return (
    <svg viewBox={VIEW} {...COMMON} aria-hidden="true">
      <rect x="20" y="14" width="38" height="26" rx="5" opacity="0.45" />
      <rect x="15" y="22" width="42" height="30" rx="5" fill="var(--accent-soft)" />
      <path d="M23 32 L44 32 M23 39 L49 39 M23 46 L38 46" opacity="0.85" />
    </svg>
  );
}

// collect — several grounds gathered into one long narrative (Epics).
function Collect() {
  return (
    <svg viewBox={VIEW} {...COMMON} aria-hidden="true">
      <path d="M13 20 Q12 16 16 16 L56 17 Q60 17 59 21 L58 51 Q58 55 54 54 L16 53 Q13 53 13 50 Z" opacity="0.5" />
      <rect x="21" y="25" width="13" height="11" rx="2.6" fill="var(--accent-soft)" />
      <rect x="39" y="24" width="13" height="11" rx="2.6" />
      <rect x="30" y="39" width="13" height="11" rx="2.6" />
    </svg>
  );
}

// infer — a reading not yet made: a soft frame with an aperture waiting to name
// what's inside (Research / "not yet inferred").
function Infer() {
  return (
    <svg viewBox={VIEW} {...COMMON} aria-hidden="true">
      <rect x="14" y="15" width="44" height="42" rx="7" fill="var(--accent-soft)" />
      <path d="M22 36 Q36 24 50 36 Q36 48 22 36 Z" />
      <path d="M33 36 L36 33 L39 36 L36 39 Z" fill="currentColor" stroke="none" />
    </svg>
  );
}

// parts — a frame divided into anatomy sub-regions, some resolved, some dashed
// (Anatomy / "no annotations yet").
function Parts() {
  return (
    <svg viewBox={VIEW} {...COMMON} aria-hidden="true">
      <path d="M14 16 Q13 13 16 13 L56 14 Q59 14 58 18 L57 55 Q57 58 54 57 L16 56 Q13 56 13 53 Z" />
      <rect x="21" y="23" width="16" height="14" rx="3" fill="var(--accent-soft)" />
      <rect x="41" y="23" width="12" height="14" rx="3" strokeDasharray="3 5" opacity="0.7" />
      <rect x="21" y="41" width="12" height="11" rx="3" strokeDasharray="3 5" opacity="0.7" />
      <rect x="37" y="41" width="16" height="11" rx="3" />
    </svg>
  );
}

// portrait — a signature forming from your own motifs (the /you room).
function Portrait() {
  return (
    <svg viewBox={VIEW} {...COMMON} aria-hidden="true">
      <path d="M18 16 Q13 16 13 22 L13 50 Q13 56 19 56 L53 56 Q59 56 59 50 L59 22 Q59 16 53 16 Z" opacity="0.5" />
      <path d="M22 46 Q30 30 36 40 T50 30" />
      <circle cx="36" cy="40" r="3" fill="var(--accent-soft)" />
      <rect x="42.5" y="26.5" width="7" height="7" rx="1.6" transform="rotate(45 46 30)" fill="currentColor" stroke="none" />
    </svg>
  );
}

const MOTIFS = { seed: Seed, stack: Stack, collect: Collect, infer: Infer, parts: Parts, portrait: Portrait };

export function RegionMotif({ variant = 'seed', size = 72, className = '' }) {
  const Motif = MOTIFS[variant] || Seed;
  return (
    <span className={`region-motif ${className}`.trim()} style={{ width: size, height: size }}>
      <Motif />
    </span>
  );
}

export default RegionMotif;
