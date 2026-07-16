import { useState } from 'react';
import { Upload, ArrowUp, Rows3, LayoutGrid, Grid3x3 } from 'lucide-react';
import TagFilter from '../components/TagFilter';
import ArchiveGrid from '../components/ArchiveGrid';
import ArchiveWall from '../components/ArchiveWall';
import ArchiveTimeline from '../components/ArchiveTimeline';

// The Archive — just the archive now. Three ways to browse the same images:
//   · Scroll — the justified, infinite grid (every image a door into Chiasm).
//   · Grid   — a calm uniform square grid.
//   · Wall   — dense fisheye thumbs; the tile under the pointer magnifies.
// The date-scrubber rail (ArchiveTimeline) re-anchors any view to a page offset.
const VIEWS = [
  ['scroll', 'Scroll', Rows3],
  ['grid', 'Grid', LayoutGrid],
  ['wall', 'Wall', Grid3x3],
];
const VIEW_KEY = 'semant.archive.view';

function GalleryPage() {
  const [selectedTag, setSelectedTag] = useState(null);
  const [startPage, setStartPage] = useState(1);
  const [view, setView] = useState(() => localStorage.getItem(VIEW_KEY) || 'scroll');

  const openUpload = () => window.dispatchEvent(new CustomEvent('semant:open-upload'));

  const onTagSelect = (tag) => {
    setSelectedTag(tag);
    setStartPage(1);
  };

  const chooseView = (v) => {
    setView(v);
    localStorage.setItem(VIEW_KEY, v);
  };

  const backToNewest = () => {
    setStartPage(1);
    window.scrollTo({ top: 0, behavior: 'auto' });
  };

  return (
    <div className="main-content-card">
      <div className="page-header archive-header">
        <div>
          <h1>The Archive</h1>
          <p>Every image, read part by part — pick one to begin.</p>
        </div>
        <button type="button" className="btn btn-primary btn-sm archive-upload" onClick={openUpload}>
          <Upload size={15} /> Upload
        </button>
      </div>

      <div className="archive-controls">
        <TagFilter onTagSelect={onTagSelect} />
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

      {view === 'scroll' && <ArchiveGrid selectedTag={selectedTag} startPage={startPage} />}
      {view === 'grid' && <ArchiveWall selectedTag={selectedTag} startPage={startPage} cell={150} />}
      {view === 'wall' && <ArchiveWall selectedTag={selectedTag} startPage={startPage} cell={58} fisheye />}

      <ArchiveTimeline selectedTag={selectedTag} currentPage={startPage} onJump={setStartPage} />
    </div>
  );
}

export default GalleryPage;
