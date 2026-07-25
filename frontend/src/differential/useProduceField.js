import { useCallback, useRef, useState } from 'react';
import { API_URL } from '../config/api';

/**
 * useProduceField (CIRCUIT-001 P6-C) — the ONE generic field-producer trigger.
 *
 * Every field producer (negative_space, material_field, and whatever plugs in next) is reached
 * through the same backend endpoint, and its suggestions enter the SAME quarantine rhythm as
 * refine/find-similar: `produce(...)` POSTs to `/produce-field`, then hands the returned
 * descriptors to `store.ingestSuggestions` so they land in `SuggestionReview`. Accepting one mints
 * a `user_confirmed` field mark; dismissing discards it — the review surface is unchanged.
 *
 * A refusal is honest, never an error: when the producer returns nothing (no seed, no mask, a
 * degenerate field) the status becomes `empty`; when the model is unavailable it becomes
 * `unavailable`. Neither is an error and neither fabricates a mark. The caller shows a quiet
 * "nothing here" for those.
 */
export default function useProduceField(postId, store) {
  // idle | loading | ready | empty | unavailable | error
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [lastRun, setLastRun] = useState(null);   // { producer, run_id, count }
  const reqSeq = useRef(0);
  const abortRef = useRef(null);

  const cancel = useCallback(() => {
    reqSeq.current++;
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus((s) => (s === 'loading' ? 'idle' : s));
  }, []);

  const produce = useCallback(async ({ producer, regionId = null, seedPoint = null, params = null } = {}) => {
    if (!postId || !producer) return null;
    const seq = ++reqSeq.current;
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('loading'); setError('');
    try {
      const res = await fetch(`${API_URL}/api/v1/posts/${postId}/produce-field`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ producer, region_id: regionId, seed_point: seedPoint, params }),
        signal: controller.signal,
      });
      if (!res.ok) {
        // an unknown producer (400) or missing post (404) is a real error, not a refusal
        throw new Error(`produce ${res.status}`);
      }
      const data = await res.json();
      if (seq !== reqSeq.current) return null;
      const suggestions = data.suggestions || [];
      // the descriptors enter the SAME quarantine path every producer uses — no bespoke ingest
      if (suggestions.length && store?.ingestSuggestions) store.ingestSuggestions(suggestions);
      setLastRun({ producer: data.producer, run_id: data.run_id, count: suggestions.length });
      // an available run with no suggestions is an honest "nothing here", not a failure
      const next = data.available === false ? (data.status || 'unavailable')
        : (suggestions.length ? 'ready' : 'empty');
      setStatus(next);
      return data;
    } catch (e) {
      if (seq !== reqSeq.current) return null;
      if (e.name === 'AbortError') { setStatus('idle'); return null; }
      setError(String(e.message || e)); setStatus('error');
      return null;
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [postId, store]);

  /** Hand the GPU slot back (mirrors the SAM unload). Field producers keep their model resident
   *  for fast re-taps, so releasing is an explicit, idempotent act. */
  const unload = useCallback(async () => {
    try {
      await fetch(`${API_URL}/api/v1/posts/produce-field/unload`, { method: 'POST' });
    } catch { /* best-effort — releasing VRAM must never surface an error to the curator */ }
  }, []);

  const clear = useCallback(() => { reqSeq.current++; setStatus('idle'); setError(''); setLastRun(null); }, []);

  return { status, error, lastRun, produce, unload, cancel, clear };
}
