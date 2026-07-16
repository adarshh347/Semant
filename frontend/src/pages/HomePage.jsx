// The Home — a curated plum bento (the app's /home route). Each tile is a door
// into the work, fed by a small cached useQuery; size = importance. Editorial,
// one accent per tile, the ◈ region-mark as the running motif. Responsive 4→2→1.
//
// Motion (MIT) owns the entrance choreography — a gentle staggered reveal — and
// the hover-lift, both disabled under prefers-reduced-motion. Each tile sits in
// a motion "slot" that carries the grid placement, so the tile components stay
// layout-agnostic.
import { motion, useReducedMotion } from 'motion/react';
import HeroTile from '../components/home/HeroTile';
import ContinueTile from '../components/home/ContinueTile';
import TasteTile from '../components/home/TasteTile';
import ReadTile from '../components/home/ReadTile';
import ArchiveTile from '../components/home/ArchiveTile';
import PerceptsTile from '../components/home/PerceptsTile';
import WeekTile from '../components/home/WeekTile';
import './HomePage.css';

const EASE = [0.22, 1, 0.36, 1]; // --ease

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.03 } },
};
const slot = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
};

const TILES = [
  ['hero', HeroTile],
  ['cont', ContinueTile],
  ['taste', TasteTile],
  ['read', ReadTile],
  ['archive', ArchiveTile],
  ['percept', PerceptsTile],
  ['week', WeekTile],
];

export default function HomePage() {
  const reduce = useReducedMotion();

  return (
    <motion.div
      className="home-bento"
      variants={reduce ? undefined : container}
      initial={reduce ? false : 'hidden'}
      animate={reduce ? false : 'show'}
    >
      {TILES.map(([area, Tile]) => (
        <motion.div
          key={area}
          className={`bento-slot slot-${area}`}
          variants={reduce ? undefined : slot}
          whileHover={reduce ? undefined : { y: -3 }}
          transition={{ duration: 0.25, ease: EASE }}
        >
          <Tile />
        </motion.div>
      ))}
    </motion.div>
  );
}
