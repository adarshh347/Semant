// The Home — a curated plum bento (the app's index route). Each tile is a door
// into the work, fed by a small cached useQuery; size = importance. Editorial,
// one accent per tile, the ◈ region-mark as the running motif. Responsive 4→2→1.
import HeroTile from '../components/home/HeroTile';
import ContinueTile from '../components/home/ContinueTile';
import TasteTile from '../components/home/TasteTile';
import ReadTile from '../components/home/ReadTile';
import ArchiveTile from '../components/home/ArchiveTile';
import PerceptsTile from '../components/home/PerceptsTile';
import WeekTile from '../components/home/WeekTile';
import './HomePage.css';

export default function HomePage() {
  return (
    <div className="home-bento">
      <HeroTile />
      <ContinueTile />
      <TasteTile />
      <ReadTile />
      <ArchiveTile />
      <PerceptsTile />
      <WeekTile />
    </div>
  );
}
