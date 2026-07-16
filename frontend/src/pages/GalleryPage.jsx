import { useState } from 'react';
import { Upload } from 'lucide-react';
import TagFilter from '../components/TagFilter';
import ArchiveGrid from '../components/ArchiveGrid';

// The Archive — just the archive now. The upload form and the tag-analysis /
// story-generation tools that used to crowd this page have moved off: upload is
// a ⌘K action + the button below (a shell-level Radix dialog); the archive is a
// justified, virtualized, infinite grid where every image is a door into Chiasm.
function GalleryPage() {
  const [selectedTag, setSelectedTag] = useState(null);

  const openUpload = () => window.dispatchEvent(new CustomEvent('semant:open-upload'));

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

      <TagFilter onTagSelect={setSelectedTag} />

      <ArchiveGrid selectedTag={selectedTag} />
    </div>
  );
}

export default GalleryPage;
