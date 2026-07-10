import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { API_URL } from '../config/api';

const BASE = `${API_URL}/api/v1/posts`;
const AUTOSAVE_MS = 800;

/**
 * The shared region + lens store (Darshan · Visual↔Content).
 *
 * The marked regions and the Aletheia reading used to live inside the Visual pane, as
 * its private state. That was right while the pane was the only thing that could see
 * them — and wrong the moment the story could point at a part. A `/part` chip in the
 * text and a polygon on the image have to be talking about the *same* region object, or
 * "hover the region, light up the sentence" is two states pretending to agree.
 *
 * So the state moves up to the one component that owns both panes, and both read it
 * from here. The pane still does the marking; it just no longer owns what it marked.
 *
 * Held here, and only here:
 *   regions        — the unified Region[] (auto segments + creator marks)
 *   aletheia       — the reading, whose lenses cite region ids
 *   selectedId     — the part under discussion, across both panes
 *   hoveredId      — transient, drives the region→block highlight
 *   lensRegionIds  — the parts a hovered lens (or a clicked chip) points at
 *
 * `focusIds` folds the last three into the single question the surfaces actually ask:
 * *what am I looking at right now* — so a lens hover, a row hover and a chip click all
 * dim the image the same way, instead of each inventing its own notion of focus.
 */
const RegionStoreContext = createContext(null);

export function useRegionStore() {
    const ctx = useContext(RegionStoreContext);
    if (!ctx) throw new Error('useRegionStore must be used inside <RegionStoreContext.Provider>');
    return ctx;
}

export { RegionStoreContext };

export function useRegionState(post, onPostChange) {
    const [regions, setRegionsState] = useState([]);
    const [aletheia, setAletheia] = useState(null);
    const [selectedId, setSelectedId] = useState(null);
    const [hoveredId, setHoveredId] = useState(null);
    const [lensRegionIds, setLensRegionIds] = useState(null); // Set | null
    const [feedPersona, setFeedPersona] = useState(true);
    const [saveState, setSaveState] = useState('idle');       // idle | saving | saved
    const [error, setError] = useState('');

    // The autosave debounce fires long after the render that scheduled it, so it must
    // read the regions from a ref — a stale closure would silently persist an old array.
    const regionsRef = useRef(regions);
    const saveTimer = useRef(null);
    const loadedFor = useRef(null);

    const setRegions = useCallback((next) => {
        regionsRef.current = typeof next === 'function' ? next(regionsRef.current) : next;
        setRegionsState(regionsRef.current);
    }, []);

    // Hydrate when the post arrives (or we navigate to a different one). Keyed on the
    // id, not the object: `persist` hands a fresh post back through onPostChange, and
    // re-seeding from it would stamp on edits the curator made while the save was
    // in flight.
    useEffect(() => {
        if (!post || loadedFor.current === post.id) return;
        loadedFor.current = post.id;
        setRegions(post.region_annotations || []);
        setAletheia(post.local_context?.aletheia || null);
        setSelectedId(null);
        setHoveredId(null);
        setLensRegionIds(null);
    }, [post, setRegions]);

    // A pending edit must not be lost because a pane unmounted.
    useEffect(() => () => clearTimeout(saveTimer.current), []);

    const postId = post?.id;

    const persist = useCallback(async (next) => {
        if (!postId) return;
        setSaveState('saving');
        try {
            const res = await fetch(`${BASE}/${postId}/region-annotations`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regions: next, feed_to_persona: feedPersona }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            onPostChange?.(data.post);
            setSaveState('saved');
            setTimeout(() => setSaveState(s => (s === 'saved' ? 'idle' : s)), 1600);
        } catch {
            setError('Could not save your marks.');
            setSaveState('idle');
        }
    }, [postId, feedPersona, onPostChange]);

    // The endpoint takes the whole array, so a burst of edits must collapse into one
    // write rather than race each other.
    const scheduleSave = useCallback(() => {
        clearTimeout(saveTimer.current);
        saveTimer.current = setTimeout(() => persist(regionsRef.current), AUTOSAVE_MS);
    }, [persist]);

    const updateRegion = useCallback((id, patch, { save = false } = {}) => {
        setRegions(rs => rs.map(r => (r.id === id ? { ...r, ...patch } : r)));
        if (save) scheduleSave();
    }, [setRegions, scheduleSave]);

    const addRegion = useCallback((region, { save = false } = {}) => {
        setRegions(rs => [...rs, region]);
        if (save) scheduleSave();
    }, [setRegions, scheduleSave]);

    const regionById = useCallback(
        (id) => regionsRef.current.find(r => r.id === id) || null, [],
    );

    const lensFor = useCallback(
        (id) => (aletheia?.lenses || []).find(l => (l.region_ids || []).includes(id)) || null,
        [aletheia],
    );

    // Selecting a part is also the act of stopping pointing at a lens's parts —
    // otherwise a stale lens highlight outlives the reading that produced it.
    const selectRegion = useCallback((id) => {
        setSelectedId(id);
        setLensRegionIds(null);
    }, []);

    /** The region→story link (`Region.block_id`), written when a chip is inserted. */
    const linkRegionToBlock = useCallback((regionId, blockId) => {
        if (!regionId || !blockId) return;
        updateRegion(regionId, { block_id: blockId }, { save: true });
    }, [updateRegion]);

    // What the surfaces are looking at. Everything else recedes.
    const focusIds = useMemo(() => {
        if (lensRegionIds?.size) return lensRegionIds;
        if (hoveredId) return new Set([hoveredId]);
        if (selectedId) return new Set([selectedId]);
        return null;
    }, [lensRegionIds, hoveredId, selectedId]);

    return useMemo(() => ({
        regions, setRegions, updateRegion, addRegion, regionById,
        selectedId, selectRegion, setSelectedId,
        hoveredId, setHoveredId,
        lensRegionIds, setLensRegionIds,
        focusIds,
        aletheia, setAletheia, lensFor,
        feedPersona, setFeedPersona,
        saveState, error, setError,
        persist, scheduleSave, linkRegionToBlock,
    }), [
        regions, setRegions, updateRegion, addRegion, regionById,
        selectedId, selectRegion, hoveredId, lensRegionIds, focusIds,
        aletheia, lensFor, feedPersona, saveState, error,
        persist, scheduleSave, linkRegionToBlock,
    ]);
}
