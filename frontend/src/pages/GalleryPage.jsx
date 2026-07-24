import { useCallback, useState } from 'react';
import { Upload, ArrowUp, Rows3, Grid3x3 } from 'lucide-react';
import Threads from '../components/Threads';
import ArchiveGrid from '../components/ArchiveGrid';
import ArchiveWall from '../components/ArchiveWall';
import ArchiveTimeline from '../components/ArchiveTimeline';
import { SectionEyebrow } from '../components/brand/SectionEyebrow';

// The Archive — just the archive. Two ways to browse the same images:
//   · Scroll — the justified, infinite scroll, broken by sequence dividers
//     (the archive's real grain: a reel's frames, a carousel's slides).
//   · Field  — the whole corpus laid out by what the images look like.
// The rail (ArchiveTimeline) re-anchors either view to a page offset.
//
// The old uniform "Grid" mode is gone: it said nothing Scroll didn't already
// say better, and a third toggle is a choice with no payoff.
const VIEWS = [
  ['scroll', 'Scroll', Rows3],
  ['wall', 'Field', Grid3x3],
];
const VIEW_KEY = 'semant.archive.view';

function GalleryPage() {
  const [selectedTag, setSelectedTag] = useState(null);
  const [startPage, setStartPage] = useState(1);
  const [sequences, setSequences] = useState([]);
  const [view, setView] = useState(() => {
    const v = localStorage.getItem(VIEW_KEY);
    return v === 'wall' ? 'wall' : 'scroll'; // 'grid' is retired → fall back
  });

  const openUpload = () => window.dispatchEvent(new CustomEvent('semant:open-upload'));

  const onTagSelect = (tag) => {
    setSelectedTag(tag);
    setStartPage(1);
    setSequences([]);
  };

  const chooseView = (v) => {
    setView(v);
    localStorage.setItem(VIEW_KEY, v);
  };

  const backToNewest = () => {
    setStartPage(1);
    window.scrollTo({ top: 0, behavior: 'auto' });
  };

  const onSequences = useCallback((s) => setSequences(s), []);

  return (
    <div className="main-content-card">
      <div className="page-header archive-header">
        <div>
          <SectionEyebrow className="eyebrow">Gallery</SectionEyebrow>
          <h1>The Archive</h1>
          <p>Every image, read part by part — pick one to begin.</p>
        </div>
        <button type="button" className="btn btn-primary btn-sm archive-upload" onClick={openUpload}>
          <Upload size={15} /> Upload
        </button>
      </div>

      <div className="archive-controls">
        <Threads selectedTag={selectedTag} onTagSelect={onTagSelect} />
        <div className="archive-viewtoggle" role="tablist" aria-label="Archive view">
          {VIEWS.map(([id, label, Icon]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={view === id}
              className={`archive-viewbtn${view === id ? ' is-active' : ''}`}
              onClick={() => chooseView(id)}
              title={`${label} view`}
            >
              <Icon size={15} /> <span className="archive-viewlabel">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {startPage > 1 && (
        <button type="button" className="archive-newest" onClick={backToNewest}>
          <ArrowUp size={14} /> Back to newest
        </button>
      )}

      {view === 'scroll' && (
        <ArchiveGrid selectedTag={selectedTag} startPage={startPage} onSequences={onSequences} />
      )}
      {view === 'wall' && <ArchiveWall selectedTag={selectedTag} startPage={startPage} cell={58} fisheye />}

      <ArchiveTimeline
        selectedTag={selectedTag}
        currentPage={startPage}
        onJump={setStartPage}
        sequences={view === 'scroll' ? sequences : []}
        startPage={startPage}
      />
    </div>
  );
}

export default GalleryPage;
