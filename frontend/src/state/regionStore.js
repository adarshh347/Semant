import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { API_URL } from '../config/api';
import {
    makePercept, upsertPercept, perceptForRegion,
    makeExpressionPercept, isExpressionPercept, perceptsForGround as perceptsForGroundPure,
    makeMention, addMention as addMentionPure, removeMentionsForBlock,
    blockIdsForRegion as blockIdsForRegionPure, mentionsFromBlocks,
} from './perceptMentions';
import { hydrateGrounds } from '../differential/grounds';

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

/**
 * Which of these referenced ids still exist on the image?
 *
 * CIRCUIT-001 P1B. Exported as a pure function so the rule can be pinned by a
 * test without mounting a store — the behaviour it guards (a reference from the
 * writing that resolves to nothing) is one of the four silent recall failures
 * CIRCUIT-001 P0 found, and it shipped green precisely because it lived inside
 * a hook nothing could reach.
 */
export function liveRegionIds(ids = [], regions = []) {
    return (ids || []).filter(Boolean).filter((id) => regions.some((r) => r.id === id));
}

export function useRegionState(post, onPostChange) {
    const [regions, setRegionsState] = useState([]);
    const [aletheia, setAletheia] = useState(null);
    // Product-layer relationship model (Chiasm assembly · Phase 1 + Differential v1).
    // Attention percepts (`pct_…`) are reconstructed client-side; expression percepts
    // (`pctx_…`) and grounds persist as post.grounds / post.percepts via PATCH.
    // Mentions stay the region↔block join. `Region.block_id` stays the primary edge.
    const [percepts, setPercepts] = useState([]);
    const [mentions, setMentions] = useState([]);
    const [grounds, setGroundsState] = useState([]);          // Differential v1 evidence
    const [selectedId, setSelectedId] = useState(null);
    const [hoveredId, setHoveredId] = useState(null);
    const [selectedGroundId, setSelectedGroundId] = useState(null);
    const [hoveredGroundId, setHoveredGroundId] = useState(null);
    const [lensRegionIds, setLensRegionIds] = useState(null); // Set | null
    // A reference from the writing that resolves to nothing on the image. Held so
    // the surface can SAY so; cleared by the next resolving focus or by Escape.
    const [missingRef, setMissingRef] = useState(null);   // { ids, at } | null
    const [recall, setRecall] = useState(null);               // { perceptId } | null
    const [feedPersona, setFeedPersona] = useState(true);
    const [saveState, setSaveState] = useState('idle');       // idle | saving | saved
    const [metaSaveState, setMetaSaveState] = useState('idle'); // grounds/percepts PATCH
    const [error, setError] = useState('');

    // The autosave debounce fires long after the render that scheduled it, so it must
    // read the regions from a ref — a stale closure would silently persist an old array.
    const regionsRef = useRef(regions);
    const groundsRef = useRef(grounds);
    const perceptsRef = useRef(percepts);
    const saveTimer = useRef(null);
    const metaSaveTimer = useRef(null);
    const loadedFor = useRef(null);

    const setRegions = useCallback((next) => {
        regionsRef.current = typeof next === 'function' ? next(regionsRef.current) : next;
        setRegionsState(regionsRef.current);
    }, []);

    const setGrounds = useCallback((next) => {
        groundsRef.current = typeof next === 'function' ? next(groundsRef.current) : next;
        setGroundsState(groundsRef.current);
    }, []);

    // The meta debounce reads percepts through a ref for the same stale-closure reason.
    useEffect(() => { perceptsRef.current = percepts; }, [percepts]);

    // Hydrate when the post arrives (or we navigate to a different one). Keyed on the
    // id, not the object: `persist` hands a fresh post back through onPostChange, and
    // re-seeding from it would stamp on edits the curator made while the save was
    // in flight.
    useEffect(() => {
        if (!post || loadedFor.current === post.id) return;
        loadedFor.current = post.id;
        const loadedRegions = post.region_annotations || [];
        setRegions(loadedRegions);
        setGrounds(hydrateGrounds(post.grounds));
        setAletheia(post.local_context?.aletheia || null);
        setSelectedId(null);
        setHoveredId(null);
        setSelectedGroundId(null);
        setHoveredGroundId(null);
        setLensRegionIds(null);
        setMissingRef(null);
        setRecall(null);
        // Reconstruct the relationship model from what's already stored, so existing
        // links resolve with no backend table and nothing regresses migrating off
        // Path A: mentions from the chips in the blocks, creator percepts for every
        // region that already bears an attention signal (a block_id or a note).
        // Expression percepts (Differential) hydrate from post.percepts as stored.
        setMentions(mentionsFromBlocks(post.text_blocks || []));
        setPercepts([
            ...loadedRegions
                .filter((r) => r.block_id || r.user_note || r.prioritised)
                .reduce((ps, r) => upsertPercept(ps, makePercept(r, { actor: 'creator' })), []),
            ...(post.percepts || []).filter(isExpressionPercept),
        ]);
    }, [post, setRegions, setGrounds]);

    // A pending edit must not be lost because a pane unmounted.
    useEffect(() => () => { clearTimeout(saveTimer.current); clearTimeout(metaSaveTimer.current); }, []);

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

    // ── Grounds + expression Percepts persistence (Differential v1) ──────────
    // A separate write path from region-annotations on purpose: grounds/percepts
    // ride PATCH /{post_id} (exclude_unset), so a re-dissect that replaces
    // region_annotations can never wipe them. Only expression percepts persist —
    // attention percepts (`pct_…`) are reconstructed from regions on hydrate.
    const persistMeta = useCallback(async () => {
        if (!postId) return;
        setMetaSaveState('saving');
        try {
            const res = await fetch(`${API_URL}/api/v1/posts/${postId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    grounds: groundsRef.current,
                    percepts: perceptsRef.current.filter(isExpressionPercept),
                }),
            });
            if (!res.ok) throw new Error();
            const data = await res.json();
            onPostChange?.(data);
            setMetaSaveState('saved');
            setTimeout(() => setMetaSaveState(s => (s === 'saved' ? 'idle' : s)), 1600);
        } catch {
            setError('Could not save your grounds.');
            setMetaSaveState('idle');
        }
    }, [postId, onPostChange]);

    const scheduleMetaSave = useCallback(() => {
        clearTimeout(metaSaveTimer.current);
        metaSaveTimer.current = setTimeout(persistMeta, AUTOSAVE_MS);
    }, [persistMeta]);

    const addGround = useCallback((ground, { save = true } = {}) => {
        setGrounds(gs => [...gs, ground]);
        if (save) scheduleMetaSave();
        return ground;
    }, [setGrounds, scheduleMetaSave]);

    const updateGround = useCallback((id, patch, { save = true } = {}) => {
        setGrounds(gs => gs.map(g => (g.id === id ? { ...g, ...patch } : g)));
        if (save) scheduleMetaSave();
    }, [setGrounds, scheduleMetaSave]);

    const removeGround = useCallback((id, { save = true } = {}) => {
        setGrounds(gs => gs.filter(g => g.id !== id));
        // A removed member leaves compositions intact — they degrade via resolveGround.
        setSelectedGroundId(s => (s === id ? null : s));
        if (save) scheduleMetaSave();
    }, [setGrounds, scheduleMetaSave]);

    const groundById = useCallback(
        (id) => groundsRef.current.find(g => g.id === id) || null, [],
    );

    /** Compose a durable act of noticing over one or more Grounds. Persists. */
    const addExpressionPercept = useCallback((input) => {
        const p = makeExpressionPercept(input);
        setPercepts(ps => [...ps, p]);
        scheduleMetaSave();
        return p;
    }, [scheduleMetaSave]);

    const perceptsForGround = useCallback(
        (groundId) => perceptsForGroundPure(perceptsRef.current, groundId), [],
    );

    const selectGround = useCallback((id) => {
        setSelectedGroundId(id);
        // Selecting evidence and selecting a part are one act of looking — a
        // region-adapter ground keeps Chiasm's selection channel in step.
        const g = id ? groundsRef.current.find(x => x.id === id) : null;
        if (g?.ground_type === 'region' && g.region_id) {
            setSelectedId(g.region_id);
            setLensRegionIds(null);
        }
    }, []);

    // ── Recall — the visual re-performance of a Percept (player lands in B) ──
    const playRecall = useCallback((perceptId) => {
        if (!perceptId) return;
        setRecall({ perceptId, startedAt: Date.now() });
    }, []);
    const clearRecall = useCallback(() => setRecall(null), []);

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

    /**
     * Look at these regions — the story pointing back at the image.
     *
     * A `/part` chip names one region and behaves exactly like clicking its polygon. A
     * `/lens` chip names several, and there is no such thing as selecting several parts:
     * it borrows the lens-citation channel, which already knows how to hold a set and
     * already dims everything outside it.
     */
    const focusRegions = useCallback((ids) => {
        const list = (ids || []).filter(Boolean);
        if (!list.length) return;
        // CIRCUIT-001 P1B — a reference can outlive what it points at. Selecting a
        // dead id used to run the full "I am showing you this" choreography and
        // then dim EVERY region and light none: the surface pointed confidently at
        // nothing, silently. Say it instead, and change nothing on the image.
        //
        // Only a reference that resolves NOWHERE is refused. A lens that has lost
        // some of its parts still has something true to show, and showing it is
        // better than withholding the whole citation.
        const live = liveRegionIds(list, regionsRef.current);
        if (!live.length) {
            setMissingRef({ ids: list, missing: list, someLive: false, at: Date.now() });
            return;
        }
        // A lens that has lost only SOME of its parts still shows the rest — and
        // says that some are gone. Withholding the whole citation would hide
        // evidence that is still true; showing it silently would overstate what
        // the citation now covers.
        setMissingRef(live.length < list.length
            ? { ids: list, missing: list.filter((id) => !live.includes(id)), someLive: true, at: Date.now() }
            : null);
        setSelectedId(live[0]);
        setLensRegionIds(live.length > 1 ? new Set(live) : null);
    }, []);

    /** The region→story link (`Region.block_id`), written when a chip is inserted. */
    const linkRegionToBlock = useCallback((regionId, blockId) => {
        if (!regionId || !blockId) return;
        updateRegion(regionId, { block_id: blockId }, { save: true });
    }, [updateRegion]);

    // ── Percepts + Mentions (product-layer; Phase 1) ─────────────────────────
    // The attention object around a region — idempotent (one creator per region).
    const ensurePercept = useCallback((region, { actor = 'creator' } = {}) => {
        if (!region?.id) return null;
        const p = makePercept(region, { actor });
        setPercepts((ps) => upsertPercept(ps, p));
        return p;
    }, []);

    const perceptForRegionId = useCallback(
        (regionId, actor = 'creator') => perceptForRegion(percepts, regionId, actor),
        [percepts],
    );

    // Record a region↔block edge. Idempotent per edge (deterministic id).
    const addMention = useCallback((input) => {
        const men = makeMention(input);
        setMentions((ms) => addMentionPure(ms, men));
        return men;
    }, []);

    // When a block is deleted (or its chip removed), drop its edges.
    const removeBlockMentions = useCallback((blockId) => {
        setMentions((ms) => removeMentionsForBlock(ms, blockId));
    }, []);

    // Which blocks talk about this region — Mentions ∪ the primary Region.block_id.
    const blockIdsForRegion = useCallback(
        (regionId) => blockIdsForRegionPure(mentions, regions, regionId),
        [mentions, regions],
    );

    // What the surfaces are looking at. Everything else recedes.
    const focusIds = useMemo(() => {
        if (lensRegionIds?.size) return lensRegionIds;
        if (hoveredId) return new Set([hoveredId]);
        if (selectedId) return new Set([selectedId]);
        return null;
    }, [lensRegionIds, hoveredId, selectedId]);

    // Ground-aware focus — the same question, asked of evidence. A Set so recall
    // and multi-ground compositions can light several at once.
    const focusGroundIds = useMemo(() => {
        if (hoveredGroundId) return new Set([hoveredGroundId]);
        if (selectedGroundId) return new Set([selectedGroundId]);
        return null;
    }, [hoveredGroundId, selectedGroundId]);

    return useMemo(() => ({
        regions, setRegions, updateRegion, addRegion, regionById,
        selectedId, selectRegion, setSelectedId, focusRegions, missingRef, setMissingRef,
        hoveredId, setHoveredId,
        lensRegionIds, setLensRegionIds,
        focusIds,
        aletheia, setAletheia, lensFor,
        feedPersona, setFeedPersona,
        saveState, error, setError,
        persist, scheduleSave, linkRegionToBlock,
        // Percepts + Mentions (Phase 1)
        percepts, ensurePercept, perceptForRegionId,
        mentions, addMention, removeBlockMentions, blockIdsForRegion,
        // Grounds + expression Percepts + recall (Differential v1)
        grounds, addGround, updateGround, removeGround, groundById,
        selectedGroundId, selectGround, hoveredGroundId, setHoveredGroundId,
        focusGroundIds,
        addExpressionPercept, perceptsForGround,
        recall, playRecall, clearRecall,
        metaSaveState, persistMeta, scheduleMetaSave,
        // The image, so a /part evidence block can crop a region by reference.
        photoUrl: post?.photo_url ?? null,
    }), [
        regions, setRegions, updateRegion, addRegion, regionById,
        selectedId, selectRegion, focusRegions, hoveredId, lensRegionIds, focusIds, missingRef,
        aletheia, lensFor, feedPersona, saveState, error,
        persist, scheduleSave, linkRegionToBlock,
        percepts, ensurePercept, perceptForRegionId,
        mentions, addMention, removeBlockMentions, blockIdsForRegion,
        grounds, addGround, updateGround, removeGround, groundById,
        selectedGroundId, selectGround, hoveredGroundId, focusGroundIds,
        addExpressionPercept, perceptsForGround, recall, playRecall, clearRecall,
        metaSaveState, persistMeta, scheduleMetaSave,
        post,
    ]);
}
