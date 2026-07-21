// CIRCULATION-SPINE-001 · P2.2 — read-only data hook for the Vision Activity Rail.
//
// Fetches the four latest-operation runs in parallel from the existing read API, aborts
// in-flight requests on unmount / post change, refreshes after a Differential action finishes,
// and polls on a bounded interval ONLY while a run is actively RUNNING (never a permanent
// high-frequency loop). No timeline endpoint, no WebSocket/SSE.
import { useCallback, useEffect, useRef, useState } from 'react';
import { API_URL } from '../config/api';
import { fetchAllRuns, isTerminalActionStatus } from './visionActivity';

const ACTIVE_POLL_MS = 3500; // bounded; scheduled only while some run is RUNNING (not stale)

export function useVisionActivity(postId, { actionStatus } = {}) {
  // results: { operation: { run: <run|null>, unreadable: bool } } — absence vs unreadability
  // are both represented per-operation (P2.2R-B1); there is no separate rail-level error.
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);
  const abortRef = useRef(null);
  const seqRef = useRef(0);
  const pollRef = useRef(null);

  const fetchAll = useCallback(async () => {
    if (!postId) return;
    const seq = ++seqRef.current;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const map = await fetchAllRuns(API_URL, postId, { signal: controller.signal });
      if (seq !== seqRef.current) return; // a newer fetch (or unmount) won
      setResults(map);
    } catch (e) {
      // Only AbortError reaches here (per-op failures are captured as {unreadable:true} in the
      // map); a superseded/aborted fetch is silently dropped, not shown as an error.
      if (e.name !== 'AbortError') throw e;
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, [postId]);

  // Mount / post change: reset state, fetch once, and abort any in-flight on cleanup.
  useEffect(() => {
    setResults({});
    if (postId) fetchAll();
    return () => {
      abortRef.current?.abort();
      seqRef.current++;
    };
  }, [postId, fetchAll]);

  // Bounded poll: schedule ONE delayed refresh while a run is actively running; it re-arms
  // itself through `results` updates and stops the moment nothing is active. Cleared on unmount.
  useEffect(() => {
    const active = Object.values(results).some(
      (r) => r && r.run && (r.run.status === 'running' || r.run.status === 'pending') && !r.run.stale,
    );
    clearTimeout(pollRef.current);
    if (active) pollRef.current = setTimeout(fetchAll, ACTIVE_POLL_MS);
    return () => clearTimeout(pollRef.current);
  }, [results, fetchAll]);

  // Refresh promptly when a Differential action (refine/read/similar) transitions to a
  // terminal hook status — immediate, without a permanent poll.
  const prevAction = useRef(actionStatus);
  useEffect(() => {
    const prev = prevAction.current || {};
    const cur = actionStatus || {};
    const justFinished = Object.keys(cur).some(
      (k) => cur[k] !== prev[k] && isTerminalActionStatus(cur[k]),
    );
    prevAction.current = cur;
    if (justFinished && postId) fetchAll();
  }, [actionStatus, postId, fetchAll]);

  return { results, loading, refresh: fetchAll };
}
