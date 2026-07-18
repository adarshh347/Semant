import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { API_URL } from '../config/api';
import RefineSurface from '../components/RefineSurface';
import './RefineLab.css';

/**
 * RefineLab (VISION-BUILD-001 B4) — a focused surface to exercise + verify the exact-mask
 * refinement loop end to end: click/box → preview → confirm → reload proves persistence.
 *   /lab/refine/:postId
 */
export default function RefineLab() {
  const { postId } = useParams();
  const [post, setPost] = useState(null);
  const [saved, setSaved] = useState(null);
  const [err, setErr] = useState('');

  const load = useCallback(() => {
    setErr('');
    fetch(`${API_URL}/api/v1/posts/${postId}`)
      .then((r) => { if (!r.ok) throw new Error(`post ${r.status}`); return r.json(); })
      .then(setPost)
      .catch((e) => setErr(String(e.message || e)));
  }, [postId]);

  useEffect(() => { load(); }, [load]);

  if (err) return <div className="refine-page"><p className="rf-page-err">Could not load post: {err}</p></div>;
  if (!post) return <div className="refine-page"><p>Loading…</p></div>;

  const masked = (post.region_annotations || []).filter((r) => r.mask_rle || (r.polygons && r.polygons.length));

  return (
    <div className="refine-page">
      <header className="refine-head">
        <div>
          <h1>Refine mask</h1>
          <p className="rf-sub">post {postId} · {masked.length} mask region{masked.length === 1 ? '' : 's'}</p>
        </div>
        <div className="refine-head-actions">
          {saved && <span className="rf-saved">saved <code>{saved.id}</code> · rev {saved.geometry_rev} · {Math.round((saved.confidence || 0) * 100)}%</span>}
          <button className="rf-reload" onClick={load}>Reload from server</button>
        </div>
      </header>
      <RefineSurface
        post={post}
        postId={postId}
        onConfirmed={(region, updated) => {
          if (region) { setSaved(region); if (updated) setPost(updated); }
        }}
      />
    </div>
  );
}
