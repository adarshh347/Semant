import { useCallback, useRef, useState } from 'react';
import { API_URL } from '../config/api';

/**
 * useFindSimilar (VISION-E · E5) — the curator's visual-neighbour loop.
 *
 * Search is RESEARCH, never fact: this hook fetches a Region's visual neighbours (indexing the
 * Region on demand, re-indexing when its mask/source changed) and returns them for inspection —
 * it creates no Motifs or Relations. `find(mode)` runs the search; `reindex(mode)` forces a
 * fresh embedding of stale evidence. `cropUrl` builds the exact-mask evidence-crop URL used for
 * result thumbnails and for recalling a neighbour's mask.
 */
export default function useFindSimilar(postId, regionId) {
  const [results, setResults] = useState([]);
  const [meta, setMeta] = useState(null);   // {space, mode, indexed, was_stale, domain}
  // idle | loading | ready | empty | unavailable | error
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const reqSeq = useRef(0);
  const abortRef = useRef(null);

  const cancel = useCallback(() => {
    reqSeq.current++;
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus((s) => (s === 'loading' ? 'idle' : s));
  }, []);

  const run = useCallback(async ({ mode = 'identity', reindex = false, excludeSelfPost = false } = {}) => {
    if (!postId || !regionId) return;
    const seq = ++reqSeq.current;
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('loading'); setError('');
    try {
      const res = await fetch(`${API_URL}/api/v1/posts/${postId}/regions/${regionId}/find-similar`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, reindex, exclude_self_post: excludeSelfPost, top_k: 8 }),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(res.status === 503 ? 'search unavailable' : `search ${res.status}`);
      const data = await res.json();
      if (seq !== reqSeq.current) return;
      setMeta({ space: data.space, mode: data.mode, indexed: data.indexed,
                was_stale: data.was_stale, domain: data.domain });
      if (data.status === 'unavailable') { setStatus('unavailable'); setError(data.reason || ''); setResults([]); return; }
      if (data.status === 'error') { setStatus('error'); setError(data.reason || ''); setResults([]); return; }
      setResults(data.results || []);
      setStatus((data.results || []).length ? 'ready' : 'empty');
    } catch (e) {
      if (seq !== reqSeq.current) return;
      if (e.name === 'AbortError') { setStatus('idle'); return; }
      setError(String(e.message || e)); setStatus('error'); setResults([]);
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [postId, regionId]);

  const find = useCallback((mode) => run({ mode }), [run]);
  const reindex = useCallback((mode) => run({ mode, reindex: true }), [run]);

  const clear = useCallback(() => { reqSeq.current++; setResults([]); setStatus('idle'); setError(''); setMeta(null); }, []);

  const cropUrl = useCallback(
    (pid, rid, role = 'identity') => `${API_URL}/api/v1/posts/${pid}/regions/${rid}/crop?role=${role}`, []);

  return { results, meta, status, error, find, reindex, cancel, clear, cropUrl };
}
