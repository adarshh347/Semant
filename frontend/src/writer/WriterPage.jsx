import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { manuscriptService } from '../services/manuscriptService';
import { manuscriptBlocksToDoc } from './schema/manuscriptExport';
import WriterStudio from './WriterStudio';

/**
 * Semant Writer · W2 — the route.
 *
 * Resolves a manuscript and a scene, then hands them to the studio. It reads canon through
 * the EXISTING `manuscriptService` (WS-0A's client) rather than a writer-specific one:
 * W2 adds no backend write path and needed no new read endpoint either — every call this
 * page makes already existed.
 *
 * `project_id` is the manuscript id for W1/W2 (see `backend/schemas/writer.py`); when W3
 * gives operators a scope of their own, only this line changes.
 */
export default function WriterPage() {
  const { manuscriptId: routeId } = useParams();
  const [manuscript, setManuscript] = useState(null);
  const [sceneId, setSceneId] = useState(null);
  const [initialContent, setInitialContent] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      let id = routeId;
      if (!id) {
        // No manuscript named — open the most recently touched one, so the route is
        // usable without hunting for an id.
        const shelf = await manuscriptService.list();
        id = shelf?.[0]?.id;
        if (!id) {
          setError('No manuscript yet — make one in the Studio first.');
          setLoading(false);
          return;
        }
      }
      const full = await manuscriptService.get(id);
      setManuscript(full);
      const firstScene = full?.chapters?.flatMap((c) => c.scene_ids ?? [])[0] ?? null;
      setSceneId(firstScene);
      if (!firstScene) {
        setError('This manuscript has no scene yet — add one in the Studio.');
      } else {
        // Open on the committed prose, so the author sees the manuscript they are
        // continuing — with its cadence — rather than a blank page.
        const scene = await manuscriptService.getScene(firstScene);
        setInitialContent(manuscriptBlocksToDoc(scene?.blocks ?? []));
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [routeId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <p style={{ padding: '2rem', opacity: 0.6 }}>Loading…</p>;
  if (error && !manuscript) return <p style={{ padding: '2rem' }}>{error}</p>;

  return (
    <WriterStudio
      projectId={manuscript.id}
      manuscriptId={manuscript.id}
      sceneId={sceneId || ''}
      initialContent={initialContent}
      author={manuscript.author || ''}
    />
  );
}
