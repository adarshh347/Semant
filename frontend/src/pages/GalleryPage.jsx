import { useState } from 'react';
import { Upload, ArrowUp } from 'lucide-react';
import TagFilter from '../components/TagFilter';
import ArchiveGrid from '../components/ArchiveGrid';
import ArchiveTimeline from '../components/ArchiveTimeline';

// The Archive — just the archive now. The upload form and the tag-analysis /
// story-generation tools that used to crowd this page have moved off: upload is
// a ⌘K action + the button below (a shell-level Radix dialog); the archive is a
// justified, virtualized, infinite grid where every image is a door into Chiasm.
//
// The date-scrubber rail (ArchiveTimeline) re-anchors the grid to a page offset
// so you can fling to old images fast; `startPage` is that anchor.
function GalleryPage() {
  const [selectedTag, setSelectedTag] = useState(null);
  const [startPage, setStartPage] = useState(1);

  const openUpload = () => window.dispatchEvent(new CustomEvent('semant:open-upload'));

  // Changing the filter scope invalidates a page offset from the old scope.
  const onTagSelect = (tag) => {
    setSelectedTag(tag);
    setStartPage(1);
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

      <TagFilter onTagSelect={onTagSelect} />

      {startPage > 1 && (
        <button type="button" className="archive-newest" onClick={backToNewest}>
          <ArrowUp size={14} /> Back to newest
        </button>
      )}

      <ArchiveGrid selectedTag={selectedTag} startPage={startPage} />

      <ArchiveTimeline selectedTag={selectedTag} currentPage={startPage} onJump={setStartPage} />
    </div>
  );
}

export default GalleryPage;
