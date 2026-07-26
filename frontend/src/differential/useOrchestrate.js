import { useCallback, useRef, useState } from 'react';
import { API_URL } from '../config/api';

/**
 * useOrchestrate (CIRCUIT-001 SURFACE-001) — intention → plan → review.
 *
 * The Director's last mile, built as a sibling of `useProduceField`: `orchestrate(intention)`
 * POSTs to `/{post_id}/orchestrate`, the backend plans + executes (WIRE) into a quarantine, and
 * the returned SUGGESTIONS are handed to `store.ingestSuggestions` so they land in the SAME
 * `SuggestionReview` every producer uses — accepting one mints a `user_confirmed` mark, dismissing
 * discards it. Nothing here accepts or persists; the review surface is unchanged.
 *
 * The resolved plan (steps + refused, each with its reason) and the chain provenance (per-step
 * ok/empty/unavailable/skipped + gaps) travel back on the hook, so the UI can show a PARTIAL plan
 * plainly — never hide what could not run.
 */
export default function useOrchestrate(postId, store) {
  const [status, setStatus] = useState('idle');   // idle | loading | ready | empty | error
  const [error, setError] = useState('');
  const [plan, setPlan] = useState(null);          // { steps, refused, notes, ... }
  const [provenance, setProvenance] = useState(null);
  const reqSeq = useRef(0);
  // FIX-UI-001 follow-up: an AbortController so an in-flight orchestrate (which runs real models
  // for seconds) can be cancelled on unmount — leaving the workspace must not leave a request
  // resolving against a torn-down tree. Mirrors useProduceField/useFindSimilar.
  const abortRef = useRef(null);

  const orchestrate = useCallback(async (intention, { phrase = null } = {}) => {
    const text = (intention || '').trim();
    if (!postId || !text) return null;
    const seq = ++reqSeq.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setStatus('loading'); setError('');
    try {
      const res = await fetch(`${API_URL}/api/v1/posts/${postId}/orchestrate`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ intention: text, phrase }),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`orchestrate ${res.status}`);
      const data = await res.json();
      if (seq !== reqSeq.current) return null;
      setPlan(data.plan || null);
      setProvenance(data.provenance || null);
      const suggestions = data.suggestions || [];
      // Readings (presence/count) are sentences, not marks — they must never reach the quarantine
      // (same rule useProduceField keeps). Only mark-shaped suggestions feed the review.
      const marks = suggestions.filter(
        (s) => s?.type !== 'presence_reading' && s?.type !== 'count_reading');
      if (marks.length && store?.ingestSuggestions) store.ingestSuggestions(marks);
      setStatus(marks.length ? 'ready' : 'empty');
      return data;
    } catch (e) {
      if (seq !== reqSeq.current) return null;
      if (e.name === 'AbortError') { setStatus((s) => (s === 'loading' ? 'idle' : s)); return null; }
      setError(String(e.message || e)); setStatus('error');
      return null;
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [postId, store]);

  // Abort an in-flight orchestrate and stop caring about its result (bump the seq).
  const cancel = useCallback(() => {
    reqSeq.current++;
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus((s) => (s === 'loading' ? 'idle' : s));
  }, []);

  const clear = useCallback(() => {
    reqSeq.current++; setStatus('idle'); setError(''); setPlan(null); setProvenance(null);
  }, []);

  return { status, error, plan, provenance, orchestrate, cancel, clear };
}
