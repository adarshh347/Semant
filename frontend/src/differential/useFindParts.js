// CIRCUIT-001 P2 — asking the image to open itself, from inside Differential.
//
// Until now a curator who entered Differential and found no parts could do nothing about
// it: the operation lived only on the Field surface, so the fix was to leave, act, and come
// back. This hook is that same call, available where the composing happens.
//
// It is deliberately thin and deliberately NOT new machinery:
//   - the route, method and payload keys are byte-for-byte what RegionSurface already sends;
//   - `dissect` remains the operation id — this changes where the button is, not the wire;
//   - regions land through `store.setRegions`, the same channel the Field commits through,
//     so both surfaces stay one source of truth;
//   - it does not save. The detect route persists regions itself; nothing here schedules an
//     extra write, so a run that fails leaves the post exactly as it was.
import { useCallback, useRef, useState } from 'react';
import { API_URL } from '../config/api';
import { FIND_PARTS_FAILED } from './seeingConsole';

const BASE = `${API_URL}/api/v1/posts`;

export default function useFindParts(postId, store) {
    const [status, setStatus] = useState('idle');   // idle | looking | error
    const [error, setError] = useState('');
    // One look at a time. A second click while one is in flight is a slip, not an intent,
    // and two concurrent merges over the same post is exactly the race P1F instrumented.
    const inFlight = useRef(false);

    const find = useCallback(async (opts = {}) => {
        if (!postId || inFlight.current) return;
        inFlight.current = true;
        setStatus('looking'); setError('');
        try {
            const res = await fetch(`${BASE}/${postId}/detect-regions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: opts.mode ?? 'general',
                    lens: opts.lens ?? '',
                    coarse_only: !!opts.coarseOnly,
                }),
            });
            if (!res.ok) throw new Error(String(res.status));
            const data = await res.json();
            store?.setRegions?.(data.regions || []);
            store?.selectRegion?.(null);
            setStatus('idle');
        } catch {
            setError(FIND_PARTS_FAILED);
            setStatus('error');
        } finally {
            inFlight.current = false;
        }
    }, [postId, store]);

    return { find, status, error, busy: status === 'looking' };
}
