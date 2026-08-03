import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';

import DifferentialWorkspace from '../differential/DifferentialWorkspace';
import { RegionStoreContext, useRegionState } from '../state/regionStore';
import { API_URL } from '../config/api';

/**
 * ATLAS C2 — opening one image of the canvas in the Differential.
 *
 * PURE INTEGRATION. There is no percept logic in this file and there must never be. It loads a
 * post, builds the SAME store the workspace has always used (`useRegionState`), provides the SAME
 * context, and mounts the SAME component — the mounting idiom is lifted from `DifferentialLab`
 * and `PostDetailPage` rather than invented. Everything a curator does inside is the existing
 * quarantine → review → Accept path, unchanged: the same producers, the same suggestions, the same
 * refusals, worded the same way. If a sensory mode refuses on the Atlas, it refuses in exactly the
 * words it uses on the post page, because it IS the post page's component.
 *
 * WHY A FOCUSED VIEW AND NOT A PANEL. The Differential is a full instrument — stage, tools,
 * inspector, suggestion review. Shrinking it into a node-sized panel would have meant a second,
 * smaller Differential, and a second one is the thing this gate exists to avoid. So the canvas
 * steps aside and gives it the viewport, then comes back.
 *
 * THE ATLAS DOES NOT LEARN WHAT WAS MADE. It is told only that the curator is done. The overlays
 * refresh by re-reading `/view` — the ledger's current answer — rather than by this component
 * handing back a percept it saw go past. Threading the new percept through here would be faster
 * and would also be the Atlas starting to hold percept truth, which is the invariant C1 spent its
 * whole design on. One extra request is the correct price.
 */
export default function AtlasDifferential({ postId, title = '', onClose }) {
    const [post, setPost] = useState(null);
    const [error, setError] = useState('');
    // The store is a hook: it must be called on every render, and it tolerates a null post while
    // the document loads (every effect in it guards on `post?.id`).
    const store = useRegionState(post, setPost);

    useEffect(() => {
        let live = true;
        setError('');
        setPost(null);
        (async () => {
            try {
                const res = await axios.get(`${API_URL}/api/v1/posts/${postId}`);
                if (live) setPost(res.data);
            } catch (e) {
                if (live) setError(e?.message || 'Could not open this image.');
            }
        })();
        return () => { live = false; };
    }, [postId]);

    // Escape leaves, the same gesture the workspace's own exit uses.
    const close = useCallback(() => onClose?.(), [onClose]);
    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') close(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [close]);

    return (
        <div className="atlas-focus" role="dialog" aria-modal="true"
            aria-label={`${title || postId} in the Differential`} data-post-id={postId}>
            {error && (
                <div className="atlas-focus-error" role="alert">
                    {error}
                    <button type="button" className="atlas-focus-back" onClick={close}>
                        ← back to the Atlas
                    </button>
                </div>
            )}

            {!post && !error && (
                <div className="atlas-focus-loading" role="status">opening the image…</div>
            )}

            {post && (
                <RegionStoreContext.Provider value={store}>
                    <DifferentialWorkspace
                        post={post}
                        store={store}
                        onExit={close}
                        onPostChange={setPost}
                    />
                </RegionStoreContext.Provider>
            )}
        </div>
    );
}
