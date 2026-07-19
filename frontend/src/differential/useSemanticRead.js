import { useCallback, useRef, useState } from 'react';
import { API_URL } from '../config/api';

/**
 * useSemanticRead (VISION-D · D4) — the curator's loop over the VLM semantic reading.
 *
 * The VLM is an INTERPRETER of the candidate masks, never a geometry generator: this hook
 * only ever reads assertions/relations/global and writes curator state (accept / edit /
 * reject / tentative). It NEVER touches region_annotations — geometry stays owned by the
 * detector / SAM / Refine path. `read` runs `POST /semantic-read` (cancellable, with a
 * client timeout and stale-response dropping); `curate` runs `PATCH /semantics/:id`; both
 * fold the server's returned `semantics` back into state so the panel re-renders in place.
 *
 * `seed` is the post's existing `post.semantics` (already delivered by GET /posts/:id), so a
 * prior reading shows immediately without re-calling the model.
 *
 * @param {string} postId
 * @param {object|null} seed  the post's existing `post.semantics`
 */
const READ_TIMEOUT_MS = 70000;   // generous client ceiling; the server itself times out at 45s

// map the orchestrator job status to the panel's state machine.
const _statusFromMeta = (meta) => {
  const s = meta?.status;
  if (s === 'succeeded' || s === 'partial') return 'ready';
  if (s === 'unavailable') return 'unavailable';
  if (s === 'timed_out') return 'timeout';
  return 'error';
};

export default function useSemanticRead(postId, seed) {
  const [semantics, setSemantics] = useState(seed || null);
  // idle | loading | ready | unavailable | timeout | error
  const [status, setStatus] = useState(
    seed && (seed.assertions || []).length ? 'ready' : 'idle');
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState(null);   // candidate id whose curate PATCH is in flight
  const reqSeq = useRef(0);
  const abortRef = useRef(null);

  const cancel = useCallback(() => {
    reqSeq.current++;                            // any in-flight response is now stale
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus((s) => (s === 'loading' ? 'idle' : s));
  }, []);

  const read = useCallback(async ({ intent = 'name', force = false } = {}) => {
    const seq = ++reqSeq.current;
    const controller = new AbortController();
    abortRef.current = controller;
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, READ_TIMEOUT_MS);
    setStatus('loading'); setError('');
    try {
      const res = await fetch(`${API_URL}/api/v1/posts/${postId}/semantic-read`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intent, force }), signal: controller.signal,
      });
      if (!res.ok) throw new Error(res.status === 503 ? 'reader unavailable' : `reader ${res.status}`);
      const data = await res.json();
      if (seq !== reqSeq.current) return null;   // a newer request (or a cancel) won
      setSemantics(data.semantics || null);
      setStatus(_statusFromMeta(data.semantics?.meta));
      const err = data.semantics?.meta?.error;
      if (err) setError(err);
      return data.semantics || null;
    } catch (e) {
      if (seq !== reqSeq.current && !timedOut) return null;
      if (timedOut) { setStatus('timeout'); setError('the reading took too long'); return null; }
      if (e.name === 'AbortError') { setStatus('idle'); return null; }   // user cancelled
      setError(String(e.message || e)); setStatus('error');
      return null;
    } finally {
      clearTimeout(timer);
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [postId]);

  // Curator decision on ONE assertion. `status` ∈ accepted|rejected|tentative|proposed, or a
  // `curator_label` edit (→ the server marks it 'overridden'). Never overwrites geometry.
  const curate = useCallback(async (candidateId, patch) => {
    setBusyId(candidateId); setError('');
    try {
      const res = await fetch(
        `${API_URL}/api/v1/posts/${postId}/semantics/${candidateId}`, {
          method: 'PATCH', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch),
        });
      if (!res.ok) throw new Error(`curate ${res.status}`);
      const data = await res.json();
      setSemantics(data.semantics || null);
      return data.semantics || null;
    } catch (e) {
      setError(String(e.message || e));
      return null;
    } finally {
      setBusyId(null);
    }
  }, [postId]);

  return { semantics, status, error, busyId, read, curate, cancel };
}
