import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    ArrowLeft, MousePointer2, Brush, PenTool, Group, Waypoints, Frame, Eye, EyeOff, Check,
    Undo2, X, Plus, Scan, Sparkles, Search, Lock, Unlock,
} from 'lucide-react';
import RegionOverlay from '../components/RegionOverlay';
import GroundLayers from './GroundLayers';
import InstrumentHandles from './InstrumentHandles';
import useStageGeometry, { useNaturalSize, pointerToNormalized } from './useStageGeometry';
import useMaskRefine from './useMaskRefine';
import useSemanticRead from './useSemanticRead';
import SemanticReading from './SemanticReading';
import useFindSimilar from './useFindSimilar';
import FindSimilar from './FindSimilar';
import SeeingConsole from './SeeingConsole';
import PassageRail from './PassageRail';
import { acceptedMarksForRun } from './passageRail';
import PerceptWorkshop from './PerceptWorkshop';
import AttunementPanel from './AttunementPanel';
import SuggestionReview from './SuggestionReview';
import useFindParts from './useFindParts';
import { makeGround, groundFromRegion, resolveGround, groundCenter } from './grounds';
import { useRecallPlayer } from './recall';
import { CORE_ROLES } from './groundRoles';
import { hasMaskPolygons, ringsToPath } from '../lib/maskGeometry';
// CIRCUIT-001 P2D-A — the renderer-independent truth model. Marks emitted here are the
// canonical record of what an instrument produced; grounds stay the persisted surface.
import {
    normalizeMark, markSummary, roleLabel,
    FIELD_ROLE_KEYS, TRACE_ROLE_KEYS, RELATION_ROLE_KEYS, regionMaskMark,
} from './visualMarks';
import {
    quarantineSuggestion, acceptSuggestion, dismissSuggestion, isSuggestion,
    summarizeProvenance, hasModelInvolvement,
} from './suggestionQuarantine';
// CIRCUIT-001 P3-B — Debt 2: a model_suggested/fixture action becomes a quarantined
// draft through the real staging bridge (no DEV fork in production).
import { draftMarkFromAction } from './markStaging';
// CIRCUIT-001 P3-B (2d) — the four system layers, via Lane A3's layer vocabulary.
import {
    createDefaultLayers, toggleLayerVisibility, setLayerOpacity, lockLayer, unlockLayer, isSystemLayer,
} from './visualLayers';
// CIRCUIT-001 P2E-B/P3-B — production instrument mechanics: editable anchors on
// normalized geometry, endpoint ref-anchoring, and the perfect-freehand ribbon.
import {
    editablePoints, withEditedPoints, moveAnchor, insertAnchor, removeAnchor, applyPointEdit,
    isEditableGround, anchorForEndpoint,
} from './handleEditing';
import './DifferentialWorkspace.css';

// The role vocabularies the instruments offer (contract §2), from Lane A's
// module — never a fourth dialect. Brush → field roles, Trace → trace roles,
// Connect → relation roles. Each instrument mints its family with its own role.
const BRUSH_ROLES = FIELD_ROLE_KEYS;
const TRACE_ROLES = TRACE_ROLE_KEYS;
const RELATION_ROLES = RELATION_ROLE_KEYS;

/**
 * Differential — the dedicated percept-construction workspace (v1).
 *
 * A full-workspace MODE inside PostDetailPage, not a route: the Chiasm shell
 * stays mounted (hidden) so unsaved Manuscript state survives enter/leave.
 *
 * A+B: shell, shared geometry, grounds/percepts round-trip, Soft Field loop.
 * C: spatial vocabulary (Path, Boundary, Frame, Region select).
 * D: compositional vocabulary — Collect (Constellation), Connect (Relation),
 *    and an accumulative tray for composing one Percept from several Grounds.
 */

const TOOLS = [
    { key: 'select', label: 'Select', icon: MousePointer2, hint: 'Point at parts — ⇧ to gather several' },
    { key: 'brush', label: 'Brush', icon: Brush, hint: 'Soft Field — paint where the light lives' },
    { key: 'trace', label: 'Trace', icon: PenTool, hint: 'Path or Boundary — draw a line' },
    { key: 'collect', label: 'Collect', icon: Group, hint: 'Constellation — gather grounds and points' },
    { key: 'connect', label: 'Connect', icon: Waypoints, hint: 'Relation — tie two grounds together' },
    { key: 'frame', label: 'Frame', icon: Frame, hint: 'The whole image as evidence' },
    { key: 'refine', label: 'Refine', icon: Scan, hint: 'Select a part, then click/drag to tighten it to an exact mask' },
    { key: 'read', label: 'Read', icon: Sparkles, hint: 'Ask the model to interpret the parts — name, qualify, relate; it never moves a mask' },
    { key: 'similar', label: 'Similar', icon: Search, hint: 'Find a selected part\'s visual neighbours — research to inspect, never facts' },
];

const PERCEPT_PROPERTIES = [
    'light', 'colour', 'material', 'movement', 'composition',
    'attention', 'atmosphere', 'repetition', 'contrast',
];

const GROUND_GLYPH = { field: '◐', path: '↝', boundary: '∥', frame: '▣', region: '◈', constellation: '⁘', relation: '⤝' };
const regionName = (r) => r?.label || r?.part || r?.category || 'part';

const groundTitle = (g, regions = []) => {
    if (!g) return '';
    if (g.label) return g.label;
    switch (g.ground_type) {
        case 'field': return `Soft field · ${(g.strokes || []).length} stroke${(g.strokes || []).length !== 1 ? 's' : ''}`;
        case 'path': return 'Path';
        case 'boundary': return 'Boundary';
        case 'frame': return 'Frame · whole image';
        case 'constellation': return `Constellation · ${(g.member_ids || []).length + (g.points || []).length} nodes`;
        case 'relation': return g.relation_label ? `Relation · ${g.relation_label}` : 'Relation';
        case 'region': {
            const r = regions.find((x) => x.id === g.region_id);
            return r ? regionName(r) : 'Region';
        }
        default: return g.ground_type;
    }
};

const MIN_SAMPLE_DIST = 0.004;

export default function DifferentialWorkspace({ post, store, onExit, onSendToManuscript = null, onPostChange = null, firstAttentionPrefill = null }) {
    const [tool, setTool] = useState('select');
    const [traceSub, setTraceSub] = useState('path');
    const [untouched, setUntouched] = useState(false);
    const [brushRadius, setBrushRadius] = useState(0.045);
    const [bandWidth, setBandWidth] = useState(0.06);
    const [draft, setDraft] = useState(null);
    const [picked, setPicked] = useState(() => new Set());   // multi-selected region ids (Select)
    const [tray, setTray] = useState(() => new Set());       // accumulative ground gather
    const [composer, setComposer] = useState(null);          // { groundIds, expression, properties }
    const [brushCursor, setBrushCursor] = useState(null);
    const stageRef = useRef(null);
    const drawingRef = useRef(false);
    const [natural, onImgLoad] = useNaturalSize();
    const { content } = useStageGeometry(stageRef, natural);

    const {
        regions, selectedId, selectRegion, hoveredId, setHoveredId,
        grounds, percepts, saveState, metaSaveState,
        addGround, updateGround, removeGround, groundById, selectedGroundId, selectGround,
        setHoveredGroundId, focusGroundIds,
        addExpressionPercept, playRecall, playMarkRecall, clearRecall, recall,
        updateRegion, addRegion,
        // CIRCUIT-001 P3-B Debt 1 — the visual_mark store API landed in P2E-A. Marks
        // now persist alongside grounds; the commit is the write (a draft never thrashes
        // the network — the store filters to committed/superseded, its contract).
        visualMarks, addVisualMark, updateVisualMark, visualMarksForGround,
    } = store;

    const recallPlayer = useRecallPlayer(store);

    // ── Refine (VISION-B5) — exact-mask refinement of the selected part ────────
    const postId = post?._id || post?.id;
    const selectedRegion = regions.find((r) => r.id === selectedId) || null;
    // baseRegion is only meaningful while refining; passing the selection lets
    // Select → Refine upgrade that part's mask in place.
    const refine = useMaskRefine(postId, tool === 'refine' ? selectedRegion : null);
    const [refineBox, setRefineBox] = useState(null);   // live box draft (normalized)
    const refineDrag = useRef(null);

    // ── Similar (VISION-E · E5) — a selected part's visual neighbours (research, not fact) ──
    const similar = useFindSimilar(postId, tool === 'similar' ? selectedId : null);

    // ── Find parts (CIRCUIT-001 P2) — the operation, available where composing happens ──
    const findParts = useFindParts(postId, store);
    const [grain, setGrain] = useState('general');

    // ── CIRCUIT-001 P2B — a mark the curator has ARMED but not yet made. ───────────
    // This is the whole shape of "applying" an image act: the tool is switched and the
    // intended role/label is held here, and the geometry is still the curator's hand. When
    // the draft is committed the staged label rides onto the ground; if they switch tools
    // or clear, it is dropped. Nothing is written by arming.
    const [stagedMark, setStagedMark] = useState(null);   // { kind, role, label, actionId }

    // ── CIRCUIT-001 P2D-A / P3-B Debt 1 — the visual_mark record, now in the store. ──
    // Grounds are the persisted surface; a visual_mark is the renderer-independent TRUTH of
    // what an instrument produced — role, source, status, lineage. It rides on the ground it
    // links via `linked_ground_ids`, so the two never disagree about provenance. Debt 1
    // routed emission through `regionStore.addVisualMark`: committed marks persist, drafts
    // and suggestions stay session-local (the store filters to committed/superseded).
    const marks = visualMarks;
    const emitMark = addVisualMark;

    // ── CIRCUIT-001 P2E-B — production instrument mechanics ────────────────────
    // (2d) the freehand ribbon generator toggle. perfect-freehand is smoother and
    // pressure-expressive; taperedRibbon is the fallback (its ~20× smaller polygon
    // is the measured rollback reason). Raw input points stay the stored truth.
    // P3-B (2e): perfect-freehand is now the DEFAULT — the measurement held (a few
    // ms to generate even the heaviest corpus stroke; render cost, not storage cost,
    // and the corpus tops out at 6 marks/post). taperedRibbon stays the toggle's
    // rollback. Raw input points remain the stored truth either way.
    const [usePerfectFreehand, setUsePerfectFreehand] = useState(true);
    // (2e) the semantic brush's chosen field role — the whole point of the brush.
    const [brushRole, setBrushRole] = useState('light_field');
    // P3-B (2c): the brush's erase mode writes strokes[].op:'sub' as DATA — the
    // canvas composites it destination-out; the op round-trips through the mark.
    const [brushErase, setBrushErase] = useState(false);
    // P3-B (2a): the trace instrument's chosen role, and its terminus honesty —
    // `ambiguous` replaces the arrowhead with a soft fade (no target asserted).
    const [traceRole, setTraceRole] = useState(TRACE_ROLES[0]);
    const [traceAmbiguous, setTraceAmbiguous] = useState(false);
    const [traceArrowhead, setTraceArrowhead] = useState(true);
    // P3-B (2b): the relation instrument's chosen role.
    const [relationRole, setRelationRole] = useState(RELATION_ROLES[0]);
    // P3-B (2d): the four system layers (Lane A3's vocabulary). Minimal controls —
    // visibility / opacity / lock — live in the tool column; a locked evidence layer
    // refuses handle edits and new draws; recall exposes no controls (system-only).
    const [layers, setLayers] = useState(() => createDefaultLayers());
    // (2c) a reshape session: the geometry being edited by hand, still a DRAFT
    // until Kept. `target` is a ground id, or '__draft__' for a fresh trace.
    const [editing, setEditing] = useState(null);   // { target, points } | null

    const layerByType = useMemo(
        () => Object.fromEntries((layers || []).map((l) => [l.layer_type, l])),
        [layers],
    );
    const evidenceLayer = layerByType.evidence;
    const suggestionLayer = layerByType.suggestion;
    const evidenceLocked = !!evidenceLayer?.locked;
    // The layer controls, wired to Lane A3's immutable mutators (never reimplemented).
    const onToggleLayer = useCallback((id) => setLayers((ls) => toggleLayerVisibility(ls, id)), []);
    const onLayerOpacity = useCallback((id, v) => setLayers((ls) => setLayerOpacity(ls, id, v)), []);
    const onToggleLock = useCallback((id) => setLayers((ls) => {
        const l = ls.find((x) => x.id === id);
        if (!l || isSystemLayer(l)) return ls;   // recall can never be unlocked
        return l.locked ? unlockLayer(ls, id) : lockLayer(ls, id);
    }), []);

    // The one sanctioned pointer→normalized path, wrapped for the handle overlay
    // (which has clientX/clientY, not a full event). It never reimplements the
    // letterbox math — it hands a synthetic event to `pointerToNormalized`.
    const clientToNormalized = useCallback((clientX, clientY) => (
        pointerToNormalized({ clientX, clientY }, stageRef.current, content)
    ), [content]);

    // Begin editing a committed path/boundary ground (from a hit-path pick), unless
    // its layer is locked. The points are copied into the edit draft; the ground is
    // untouched until Keep.
    const beginEditGround = useCallback((groundId) => {
        // P3-B (2d): a locked evidence layer refuses handle edits — the committed
        // grounds are held still until it is unlocked.
        if (evidenceLocked) return;
        const g = grounds.find((x) => x.id === groundId);
        if (!g || !isEditableGround(g)) return;
        setEditing({ target: groundId, points: (g.points || []).map((p) => [...p]) });
        selectGround(groundId);
    }, [grounds, selectGround, evidenceLocked]);

    const editMove = useCallback((index, at) => {
        setEditing((ed) => (ed ? { ...ed, points: moveAnchor(ed.points, index, at) } : ed));
    }, []);
    const editInsert = useCallback((segIndex, at, t) => {
        let newIndex = segIndex + 1;
        setEditing((ed) => (ed ? { ...ed, points: insertAnchor(ed.points, segIndex, at, t) } : ed));
        return newIndex;
    }, []);
    const editRemove = useCallback((index) => {
        setEditing((ed) => (ed ? { ...ed, points: removeAnchor(ed.points, index) } : ed));
    }, []);

    // Keep the reshape: write points back through the store's existing updateGround
    // (id-preserving, so linked marks/percepts stay intact and it persists via the
    // established save path — no new store API needed). Any linked mark carrying
    // own geometry is re-synced (anchors honor detached_from_ref).
    const keepEdit = useCallback(() => {
        // Read the edit draft from closure, then commit — never call another
        // component's setState from inside a setEditing updater (React runs the
        // updater during render, and doing so warns "setState while rendering").
        if (!editing) return;
        if (editing.target === '__suggestion__') {
            // P4-B (2b): editing a suggestion's shape STAGES the points into the review
            // edit — it never mutates the suggestion; acceptance folds them into the
            // derived mark, leaving the original proposal intact in lineage.
            setReview((rv) => (rv ? { ...rv, edit: { ...rv.edit, points: editing.points } } : rv));
            setEditing(null);
            return;
        }
        if (editing.target === '__draft__') {
            setDraft((d) => (d && (d.kind === 'path' || d.kind === 'boundary')
                ? { ...d, points: editing.points } : d));
        } else if (editing.points.length >= 2) {
            updateGround(editing.target, { points: editing.points });
            // Re-sync any linked mark that carries its own geometry (anchors honor
            // detached_from_ref) — through the store now (Debt 1), not session state.
            for (const m of visualMarksForGround(editing.target)) {
                if (!editablePoints(m)) continue;
                const next = applyPointEdit(m, editing.points);
                updateVisualMark(m.id, {
                    geometry: next.geometry,
                    ...(next.anchors ? { anchors: next.anchors } : null),
                });
            }
        }
        setEditing(null);
    }, [editing, updateGround, visualMarksForGround, updateVisualMark]);
    const cancelEdit = useCallback(() => setEditing(null), []);

    // (2e) the live quarantine: suggestions still awaiting a human decision — model
    // proposed, not yet accepted or dismissed, and with no descendant already minted.
    const pendingSuggestions = useMemo(() => marks.filter((m) => (
        isSuggestion(m) && m.status !== 'dismissed' && !marks.some((x) => x.derived_from === m.id)
    )), [marks]);

    // Accept a suggestion (Lane A's acceptSuggestion — mints user_confirmed with
    // derived_from, leaves the suggestion untouched). Promote its geometry to a real
    // ground so it becomes citable evidence, and link the two.
    const acceptBrushSuggestion = useCallback((sugg) => {
        const out = acceptSuggestion(sugg);
        if (!out) return;
        let groundId = null;
        const strokes = sugg.geometry?.strokes;
        if (Array.isArray(strokes) && strokes.length) {
            const g = addGround(makeGround('field', { strokes, label: sugg.label || '', instrument_role: sugg.role }));
            groundId = g.id;
        }
        const accepted = groundId
            ? { ...out.accepted, linked_ground_ids: [...(out.accepted.linked_ground_ids || []), groundId] }
            : out.accepted;
        // The suggestion is preserved (lineage points back); the accepted mark is a
        // NEW committed record — added to the store, so it persists (Debt 1).
        addVisualMark(accepted);
    }, [addGround, addVisualMark]);

    const dismissBrushSuggestion = useCallback((sugg) => {
        // dismissSuggestion returns a new mark with status 'dismissed' (kept, not
        // destroyed); patch it in place through the store (Debt 1).
        const d = dismissSuggestion(sugg);
        if (d) updateVisualMark(sugg.id, { status: d.status, warnings: d.warnings });
    }, [updateVisualMark]);

    // ── CIRCUIT-001 P4-B — the suggestion review surface. ──────────────────────────
    // `review` is `{ index, edit, dismissReason } | null`. When on, the review surface
    // cycles the pending suggestions one at a time; `edit` STAGES role/label/geometry
    // corrections (never mutating the suggestion) that acceptance folds into the derived
    // mark (Label Studio edit-before-accept). Accepting many is the a-rhythm — there is
    // deliberately no function that commits more than one suggestion per call.
    const [review, setReview] = useState(null);
    const wrapIndex = (n) => ((n % Math.max(1, pendingSuggestions.length)) + pendingSuggestions.length) % Math.max(1, pendingSuggestions.length);
    const startReview = useCallback(() => {
        if (pendingSuggestions.length) setReview({ index: 0, edit: {}, dismissReason: null });
    }, [pendingSuggestions.length]);
    const endReview = useCallback(() => setReview(null), []);
    const reviewNext = useCallback(() => setReview((rv) => (rv ? { ...rv, index: wrapIndex(rv.index + 1), edit: {}, dismissReason: null } : rv)), [pendingSuggestions.length]);   // eslint-disable-line react-hooks/exhaustive-deps
    const reviewPrev = useCallback(() => setReview((rv) => (rv ? { ...rv, index: wrapIndex(rv.index - 1), edit: {}, dismissReason: null } : rv)), [pendingSuggestions.length]);   // eslint-disable-line react-hooks/exhaustive-deps
    const stageReviewRole = useCallback((role) => setReview((rv) => (rv ? { ...rv, edit: { ...rv.edit, role } } : rv)), []);
    const stageReviewLabel = useCallback((label) => setReview((rv) => (rv ? { ...rv, edit: { ...rv.edit, label } } : rv)), []);
    const setReviewDismissReason = useCallback((reason) => setReview((rv) => (rv ? { ...rv, dismissReason: reason } : rv)), []);

    const currentSuggestion = useCallback(
        () => pendingSuggestions[Math.min(review?.index ?? 0, pendingSuggestions.length - 1)] || null,
        [pendingSuggestions, review],
    );

    // Open the stage handles on the CURRENT suggestion's geometry (a special edit
    // target that stages back into review.edit rather than committing to a ground).
    const editReviewGeometry = useCallback(() => {
        const s = currentSuggestion();
        const pts = s && editablePoints(s);
        if (pts && pts.length) setEditing({ target: '__suggestion__', points: pts.map((p) => [...p]) });
    }, [currentSuggestion]);

    // Accept the current suggestion WITH the staged edits. `acceptSuggestion` mints a
    // NEW mark (user_confirmed when the geometry KIND is unchanged — which the edits
    // always keep, so the accepted mark stays citable), `derived_from` the suggestion,
    // which is returned untouched. One suggestion per call — accepting many is N presses.
    const acceptCurrentSuggestion = useCallback(() => {
        if (!review) return;
        const s = currentSuggestion();
        if (!s) return;
        const edits = {};
        if (review.edit.role != null) edits.role = review.edit.role;
        if (review.edit.label != null) edits.label = review.edit.label;
        if (review.edit.points) edits.geometry = withEditedPoints(s, review.edit.points).geometry;
        const out = acceptSuggestion(s, edits);
        if (!out) return;
        // A field suggestion carries strokes — promote them to a ground so the accepted
        // mark cites real evidence (as the one-at-a-time flow already did).
        let accepted = out.accepted;
        const strokes = out.accepted.geometry?.strokes;
        if (Array.isArray(strokes) && strokes.length) {
            const g = addGround(makeGround('field', { strokes, label: out.accepted.label || '', instrument_role: out.accepted.role }));
            accepted = { ...out.accepted, linked_ground_ids: [...(out.accepted.linked_ground_ids || []), g.id] };
        }
        addVisualMark(accepted);
        // The accepted suggestion drops out of pendingSuggestions (it now has a
        // descendant), so staying at this index lands on the next one; clear the edit.
        setReview((rv) => (rv ? { ...rv, edit: {}, dismissReason: null } : rv));
    }, [review, currentSuggestion, addGround, addVisualMark]);

    const dismissCurrentSuggestion = useCallback(() => {
        if (!review) return;
        const s = currentSuggestion();
        if (!s) return;
        const d = dismissSuggestion(s);
        // P4F: the quarantine's dismissSuggestion takes no reason; until it does, the
        // reason rides as an additive session field on the dismissed (non-persisted) mark.
        if (d) updateVisualMark(s.id, { status: d.status, warnings: d.warnings, ...(review.dismissReason ? { dismiss_reason: review.dismissReason } : {}) });
        setReview((rv) => (rv ? { ...rv, edit: {}, dismissReason: null } : rv));
    }, [review, currentSuggestion, updateVisualMark]);

    // Dismiss-all is one button — refusal needs no ceremony (2d).
    const dismissAllSuggestions = useCallback(() => {
        for (const s of pendingSuggestions) {
            const d = dismissSuggestion(s);
            if (d) updateVisualMark(s.id, { status: d.status, warnings: d.warnings });
        }
        setReview(null);
    }, [pendingSuggestions, updateVisualMark]);

    // Keep review in range as the queue shrinks; leave review when it empties.
    useEffect(() => {
        if (!review) return;
        if (pendingSuggestions.length === 0) { setReview(null); return; }
        if (review.index >= pendingSuggestions.length) {
            setReview((rv) => (rv ? { ...rv, index: pendingSuggestions.length - 1, edit: {}, dismissReason: null } : rv));
        }
    }, [review, pendingSuggestions.length]);

    // ── CIRCUIT-001 P3-B Debt 2 — the real suggestion source. ──────────────────────
    // A model_suggested (or, for tests, `fixture`-source) action arriving through the
    // attunement/action path becomes a quarantined draft via Lane A3's real staging
    // bridge — `draftMarkFromAction` routes any model_suggested mark through
    // `quarantineSuggestion`, so a suggestion can never be constructed outside the
    // quarantine. No DEV fork: the same code path serves a live planner and a fixture.
    // The planner has no image access, so a proposal may arrive with geometry
    // (`payload.geometry`) or unresolved; either way it lands in the suggestion layer
    // and drives the Accept/Dismiss flow below.
    const receiveModelSuggestion = useCallback((action) => {
        const draft = draftMarkFromAction(action);
        if (!draft) return null;
        const geometry = action?.payload?.geometry;
        const withGeom = geometry && typeof geometry === 'object' ? { ...draft, geometry } : draft;
        // This entry point IS the quarantine door. `draftMarkFromAction` already
        // quarantines a model_suggested mark; a fixture-source proposal (tests, and any
        // non-model producer) is quarantined here — so a suggestion is a suggestion no
        // matter who proposed it, and it can never reach evidence without a human Accept.
        const sugg = isSuggestion(withGeom) ? withGeom : quarantineSuggestion(withGeom);
        return addVisualMark(sugg);
    }, [addVisualMark]);

    // ── Read (VISION-D · D4) — the VLM interprets the candidate masks (never geometry) ──
    const reading = useSemanticRead(postId, post?.semantics || null);
    // "needs better evidence" hands the curator straight to Refine on that part.
    const readingToRefine = useCallback((cid) => {
        selectRegion(cid);
        switchTool('refine');
    }, [selectRegion]);   // eslint-disable-line react-hooks/exhaustive-deps -- switchTool stable

    const expressionPercepts = useMemo(
        () => (percepts || []).filter((p) => String(p.id || '').startsWith('pctx_')),
        [percepts],
    );

    // ── CIRCUIT-001 P5-B — the Passage Rail follows the operation under the hand. The tool the
    // curator is holding is the run they want to watch; idle, the passage is the primary dissect.
    // (A single `latest` poll per operation — a cross-operation runs-list would let the rail show
    // the single most-recent run regardless of tool. See the // P5F: marker below.)
    const passageOperation = tool === 'refine' ? 'refine'
        : tool === 'similar' ? 'find_similar'
            : tool === 'read' ? 'semantic_read'
                : 'dissect';
    // 2b — tapping a run event highlights the marks that run produced and the curator accepted.
    // Highlight == the existing read-only recall channel (P3-A): performing the mark IS the
    // highlight, and it then reappears in the rail as a session recall event — a closed loop.
    const highlightRunMarks = useCallback((runId) => {
        const accepted = acceptedMarksForRun(runId, visualMarks);
        if (accepted.length) playMarkRecall(accepted[0].id);
        // P5F: with one recall channel only the first accepted mark performs; a multi-mark
        // highlight (focus every accepted mark from a run at once) wants a store `focusMarks(ids)`.
    }, [visualMarks, playMarkRecall]);
    const highlightMark = useCallback((markId) => {
        if (markId) playMarkRecall(markId);
    }, [playMarkRecall]);

    const composing = tool === 'collect' || tool === 'connect';

    // ── draft, shaped for the layers ─────────────────────────────────────────
    const draftForLayers = useMemo(() => {
        if (!draft) return null;
        if (draft.kind === 'field') {
            const strokes = draft.live ? [...draft.strokes, draft.live] : draft.strokes;
            return { kind: 'field', strokes };
        }
        if (draft.kind === 'path' || draft.kind === 'boundary') {
            return { kind: draft.kind, points: draft.points, band_width: draft.band_width };
        }
        // constellation/relation drafts render as their own ground preview
        return { kind: draft.kind, member_ids: draft.member_ids, points: draft.points || [] };
    }, [draft]);

    // Feed the composition draft into GroundLayers as a live ground, so its
    // halos/connector appear as you gather.
    const groundsForLayers = useMemo(() => {
        if (draftForLayers && (draftForLayers.kind === 'constellation' || draftForLayers.kind === 'relation')) {
            return [...grounds, { id: '__draft__', ground_type: draftForLayers.kind, ...draftForLayers }];
        }
        return grounds;
    }, [grounds, draftForLayers]);

    const draftFocus = useMemo(
        () => ((draft?.kind === 'constellation' || draft?.kind === 'relation') ? new Set(['__draft__', ...(draft.member_ids || [])]) : focusGroundIds),
        [draft, focusGroundIds],
    );

    const hasDrawDraft = draft && (draft.kind === 'field'
        ? (draft.strokes.length > 0 || draft.live)
        : (draft.kind === 'path' || draft.kind === 'boundary') ? draft.points.length > 1 : false);
    const hasCompDraft = draft && (draft.kind === 'constellation' || draft.kind === 'relation')
        && ((draft.member_ids || []).length + (draft.points || []).length) > 0;

    // ── tool switching ───────────────────────────────────────────────────────
    const switchTool = useCallback((key) => {
        setPicked(new Set());
        setDraft(key === 'collect' ? { kind: 'constellation', member_ids: [], points: [] }
            : key === 'connect' ? { kind: 'relation', member_ids: [], relation_label: '' }
                : null);
        // An armed act belongs to the tool it armed. Leaving that tool abandons it — the
        // alternative is a stale label riding onto an unrelated mark later.
        // (P2B: `applyPerceptualAction` calls this first and stages after, so arming works.)
        setStagedMark(null);
        setTool(key);
    }, []);

    // A region-adapter Ground for a region, created once (dedupe by region_id).
    const ensureRegionGround = useCallback((regionId) => {
        const existing = grounds.find((g) => g.ground_type === 'region' && g.region_id === regionId);
        if (existing) return existing.id;
        const r = regions.find((x) => x.id === regionId);
        return addGround(groundFromRegion(regionId, { label: r ? regionName(r) : '' })).id;
    }, [grounds, regions, addGround]);

    const toggleMember = useCallback((groundId) => {
        setDraft((d) => {
            if (!d || (d.kind !== 'constellation' && d.kind !== 'relation')) return d;
            const has = d.member_ids.includes(groundId);
            return { ...d, member_ids: has ? d.member_ids.filter((x) => x !== groundId) : [...d.member_ids, groundId] };
        });
    }, []);

    // ── gestures ─────────────────────────────────────────────────────────────
    const onStagePointerDown = (e) => {
        if (untouched) return;
        const p = pointerToNormalized(e, stageRef.current, content);
        if (!p) return;
        // Refine (VISION-B5): a click plants a point (⇧ = negative), a drag draws a box.
        // Own the gesture so the image never pans while prompting.
        if (tool === 'refine') {
            e.preventDefault();
            e.currentTarget.setPointerCapture?.(e.pointerId);
            refineDrag.current = { x0: p.x, y0: p.y, moved: false };
            setRefineBox(null);
            return;
        }
        // Drawing tools own the gesture — stop the browser's native image-drag /
        // text-selection from hijacking the press-drag (the "brush moves the image"
        // bug). draggable=false + user-drag CSS below are the belt; this is the braces.
        if (tool === 'brush' || tool === 'trace') e.preventDefault();
        if (tool === 'brush') {
            e.currentTarget.setPointerCapture?.(e.pointerId);
            drawingRef.current = true;
            // P3-B (2c): erase is DATA. The stroke's `op` is 'sub' in erase mode (or
            // when ⌥ is held), 'add' otherwise; the canvas composites 'sub' as
            // destination-out, and the op is stored on the stroke so it round-trips.
            const op = (brushErase || e.altKey) ? 'sub' : 'add';
            setDraft((d) => ({
                kind: 'field',
                strokes: d?.kind === 'field' ? d.strokes : [],
                live: { points: [[p.x, p.y, e.pressure || 0]], radius: brushRadius, strength: 0.8, op },
            }));
        } else if (tool === 'trace') {
            e.currentTarget.setPointerCapture?.(e.pointerId);
            drawingRef.current = true;
            setDraft({ kind: traceSub, points: [[p.x, p.y, e.pressure || 0]], band_width: bandWidth });
        } else if (tool === 'collect' && e.target.tagName === 'IMG') {
            // an empty tap plants a raw point in the constellation
            setDraft((d) => (d?.kind === 'constellation' ? { ...d, points: [...(d.points || []), { x: p.x, y: p.y }] } : d));
        }
    };

    const onStagePointerMove = (e) => {
        const p = pointerToNormalized(e, stageRef.current, content);
        if (tool === 'brush') setBrushCursor(p);
        if (tool === 'refine' && refineDrag.current) {
            if (!p) return;
            const d = refineDrag.current;
            if (Math.hypot(p.x - d.x0, p.y - d.y0) > 0.012) {
                d.moved = true;
                setRefineBox({ x0: d.x0, y0: d.y0, x1: p.x, y1: p.y });
            }
            return;
        }
        if (!drawingRef.current || !p) return;
        if (tool === 'brush') {
            setDraft((d) => {
                if (!d?.live) return d;
                const last = d.live.points[d.live.points.length - 1];
                if (Math.hypot(p.x - last[0], p.y - last[1]) < MIN_SAMPLE_DIST) return d;
                return { ...d, live: { ...d.live, points: [...d.live.points, [p.x, p.y, e.pressure || 0]] } };
            });
        } else if (tool === 'trace') {
            setDraft((d) => {
                if (!d?.points) return d;
                const last = d.points[d.points.length - 1];
                if (Math.hypot(p.x - last[0], p.y - last[1]) < MIN_SAMPLE_DIST) return d;
                return { ...d, points: [...d.points, [p.x, p.y, e.pressure || 0]] };
            });
        }
    };

    const onStagePointerUp = (e) => {
        if (tool === 'refine' && refineDrag.current) {
            const d = refineDrag.current; refineDrag.current = null;
            const p = pointerToNormalized(e, stageRef.current, content);
            if (d.moved && p) refine.setBoxPrompt({ x0: d.x0, y0: d.y0, x1: p.x, y1: p.y });
            else if (p) refine.addPoint(p.x, p.y, e.shiftKey ? 0 : 1);
            setRefineBox(null);
            return;
        }
        endStroke(e);
    };

    const endStroke = useCallback(() => {
        if (!drawingRef.current) return;
        drawingRef.current = false;
        setDraft((d) => {
            if (!d) return d;
            if (d.kind === 'field') {
                const strokes = d.live && d.live.points.length > 1 ? [...d.strokes, d.live] : d.strokes;
                return { ...d, strokes, live: null };
            }
            if (d.kind === 'path' || d.kind === 'boundary') return d.points.length > 1 ? d : null;
            return d;
        });
    }, []);

    const clearDraft = useCallback(() => {
        setDraft(composing
            ? (tool === 'collect' ? { kind: 'constellation', member_ids: [], points: [] } : { kind: 'relation', member_ids: [], relation_label: '' })
            : null);
        drawingRef.current = false;
    }, [composing, tool]);

    const undoStroke = useCallback(() => {
        setDraft((d) => (d?.kind === 'field' ? { ...d, strokes: d.strokes.slice(0, -1) } : d));
    }, []);

    const openComposer = useCallback((groundIds, { expression = '' } = {}) => {
        setComposer({
            groundIds: Array.isArray(groundIds) ? groundIds : [groundIds],
            // CIRCUIT-001 P2B: a proposed percept can arrive with the curator's own
            // sentence already in the box. It is still a draft — nothing is written until
            // "Keep this percept".
            expression, properties: [], roles: {},
        });
    }, []);

    // ── commits ──────────────────────────────────────────────────────────────
    const commitDraft = useCallback(() => {
        if (!draft) return;
        // P3-B (2d): a locked evidence layer refuses new draws too — the draft stays a
        // draft (scratch) until the layer is unlocked.
        if (evidenceLocked) return;
        // CIRCUIT-001 P2B/P2D — an armed act contributes its label AND its role AND the id of
        // the act that armed it to the ground the curator just drew. The geometry, and the
        // decision to keep it, are entirely theirs; the act only carried the intent over.
        // P2B dropped everything but `label` here — the role and action_id below close that gap.
        const staged = stagedMark && stagedMark.kind === draft.kind ? stagedMark : null;
        // Additive fields on an untyped ground dict: safe, and never read by the ground store.
        const carry = {
            ...(staged?.label ? { label: staged.label } : {}),
            ...(staged?.role ? { instrument_role: staged.role } : {}),
            ...(staged?.actionId ? { origin_action_id: staged.actionId } : {}),
        };
        // The visual_mark family the drawn ground answers to. P3-B adds the relation family
        // (2b); the trace is `trace_mark` with a polyline geometry that also carries anchors.
        const MARK_TYPE = { field: 'brush_field', path: 'trace_mark', boundary: 'frame_mark', relation: 'relation_mark' };
        // P3-B (2a): resolve a trace endpoint onto whatever ground/region sits under it, so
        // the mark carries `anchor {kind, ref, at}` and a later drag can set detached_from_ref.
        const anchorCandidates = () => {
            const cands = [];
            for (const g of grounds) {
                const c = groundCenter(g, { regions, grounds });
                if (c) cands.push({ kind: 'ground', ref: g.id, at: [c.x, c.y] });
            }
            for (const r of regions) {
                const b = r.box;
                if (b && typeof b.x === 'number') cands.push({ kind: 'region', ref: r.id, at: [b.x + b.w / 2, b.y + b.h / 2] });
            }
            return cands;
        };
        const traceAnchors = (points) => {
            const cands = anchorCandidates();
            return {
                from: anchorForEndpoint(points[0], cands, 0.04),
                to: anchorForEndpoint(points[points.length - 1], cands, 0.04),
            };
        };
        let ground = null;
        let geometry = null;
        if (draft.kind === 'field') {
            const strokes = draft.live ? [...draft.strokes, draft.live] : draft.strokes;
            if (!strokes.length) return;
            ground = addGround(makeGround('field', { strokes, ...carry }));
            geometry = { kind: 'freehand_path' };
        } else if (draft.kind === 'path') {
            if (draft.points.length < 2) return;
            const anchors = traceAnchors(draft.points);
            // Honesty on the terminus (2a): the arrowhead and the soft-fade ambiguity are the
            // curator's own toggles, stored on the ground so the renderer performs them.
            ground = addGround(makeGround('path', {
                points: draft.points, arrowhead: traceArrowhead, ambiguous: traceAmbiguous, anchors, ...carry,
            }));
            geometry = { kind: 'polyline', anchors, ambiguous: traceAmbiguous, arrowhead: traceArrowhead };
        } else if (draft.kind === 'boundary') {
            if (draft.points.length < 2) return;
            ground = addGround(makeGround('boundary', { points: draft.points, band_width: draft.band_width, ...carry }));
            geometry = { kind: 'polyline' };
        } else if (draft.kind === 'constellation') {
            if (!hasCompDraft) return;
            ground = addGround(makeGround('constellation', { member_ids: draft.member_ids, points: draft.points || [], ...carry }));
        } else if (draft.kind === 'relation') {
            if ((draft.member_ids || []).length < 2) return;
            ground = addGround(makeGround('relation', {
                member_ids: draft.member_ids,
                relation_label: draft.relation_label || staged?.role || '',
                ...carry,
            }));
            // P3-B (2b): a relation's geometry is DERIVED — computed from its member refs at
            // render (the compositionNodes idiom), never stored. The mark records only the
            // members it ties; if one stops resolving, the render degrades, never crashes.
            geometry = { kind: 'derived', member_ids: [...draft.member_ids] };
        }
        // Emit the canonical mark alongside the ground. The role comes from the armed act
        // when there is one; otherwise from the instrument's own picker — brush→field role,
        // trace→trace role (2a), connect→relation role (2b) — so EVERY instrument mints a
        // contract-shaped mark of its family. `normalizeMark` fails closed, so a bad role
        // produces no mark, never a wrong one.
        const pickerRole = draft.kind === 'field' ? brushRole
            : draft.kind === 'path' ? traceRole
                : draft.kind === 'relation' ? relationRole : null;
        const markRole = staged?.role || pickerRole;
        if (ground && markRole && MARK_TYPE[draft.kind] && geometry) {
            emitMark(normalizeMark({
                type: MARK_TYPE[draft.kind],
                role: markRole,
                label: staged?.label || '',
                source: 'user',                       // the curator's own hand
                status: 'committed',
                geometry,
                linked_ground_ids: [ground.id],
                linked_action_ids: staged?.actionId ? [staged.actionId] : [],
            }));
        }
        setDraft(null);
        setTool('select');
        setStagedMark(null);
        if (ground) { selectGround(ground.id); openComposer(ground.id); }
    }, [draft, hasCompDraft, addGround, selectGround, openComposer, stagedMark, emitMark,
        brushRole, traceRole, relationRole, traceAmbiguous, traceArrowhead, grounds, regions, evidenceLocked]);

    const commitFrame = useCallback(() => {
        const evidence = [...tray];
        if (selectedGroundId && !evidence.includes(selectedGroundId)) evidence.push(selectedGroundId);
        // Don't multiply whole-image frames: reuse one already holding this same
        // evidence set, so repeated clicks re-open its composer rather than pile up.
        const key = [...evidence].sort().join(',');
        const existing = grounds.find(
            (g) => g.ground_type === 'frame' && [...(g.evidence_ids || [])].sort().join(',') === key,
        );
        const ground = existing || addGround(makeGround('frame', { whole: true, evidence_ids: evidence }));
        selectGround(ground.id);
        openComposer(ground.id);
    }, [tray, selectedGroundId, grounds, addGround, selectGround, openComposer]);

    const composeFromRegions = useCallback(() => {
        const ids = picked.size ? [...picked] : (selectedId ? [selectedId] : []);
        if (!ids.length) return;
        const groundIds = ids.map((rid) => ensureRegionGround(rid));
        setPicked(new Set());
        openComposer(groundIds);
    }, [picked, selectedId, ensureRegionGround, openComposer]);

    const composeFromTray = useCallback(() => {
        if (!tray.size) return;
        openComposer([...tray]);
        setTray(new Set());
    }, [tray, openComposer]);

    const savePercept = useCallback(() => {
        if (!composer) return;
        const expression = composer.expression.trim();
        if (!expression) return;
        // Roles ride on the percept record the curator already saves — no new
        // entity, no migration, and nothing written to post.grounds.
        const named = Object.entries(composer.roles || {}).filter(([, r]) => !!r);
        const p = addExpressionPercept({
            expression, ground_ids: composer.groundIds, properties: composer.properties,
            ...(named.length ? { ground_roles: Object.fromEntries(named) } : {}),
        });
        setComposer(null);
        playRecall(p.id);
    }, [composer, addExpressionPercept, playRecall]);

    // ── CIRCUIT-001 P2B — carrying a proposed act through ────────────────────
    //
    // The deterministic half of the Perceptual Action Grammar. Every branch below is an
    // affordance that already existed; the act only routes to it and carries a name. What
    // this function will NOT do, by construction:
    //
    //   - it never writes geometry (the curator's hand does that);
    //   - it never saves a percept (the composer's own button does that);
    //   - it never sends anything to a model;
    //   - and for anything it cannot do, it is NOT in `ACTION_CAPABILITIES`, so the card
    //     renders "Preview only" instead of an Apply button that quietly no-ops.
    //
    // Returns 'armed' when the curator must still make the mark, 'applied' when the act is
    // complete, and undefined when nothing was carried out.
    const applyPerceptualAction = useCallback((action) => {
        const p = action?.payload || {};
        // Debt 2 — a model-authored (or fixture) proposal does NOT arm the curator's
        // hand; it lands in the quarantine as a suggestion, awaiting Accept/Dismiss.
        // Same path for a live planner and a test fixture — the only honest seam.
        if (action?.source === 'model_suggested' || action?.source === 'fixture') {
            return receiveModelSuggestion(action) ? 'applied' : undefined;
        }
        switch (action?.type) {
            case 'find_parts':
                findParts.find({ mode: grain });
                return 'applied';

            case 'brush_field':
                switchTool('brush');
                setStagedMark({ kind: 'field', role: p.field_role, label: p.label, actionId: action.id });
                return 'armed';

            case 'trace_direction': {
                // A vector reads as a path; anything else the trace tool can hold is a path
                // too — `boundary` is a seam, which is a different act entirely.
                switchTool('trace');
                setTraceSub('path');
                setStagedMark({ kind: 'path', role: p.trace_role, label: p.label, actionId: action.id });
                return 'armed';
            }

            case 'connect_marks':
                switchTool('connect');
                setStagedMark({ kind: 'relation', role: p.relation_role, label: p.label || '', actionId: action.id });
                return 'armed';

            case 'compose_percept': {
                // Opens the composer with the curator's own sentence and whatever evidence
                // they have already gathered. Still a draft: "Keep this percept" is the
                // only thing that writes, and it is theirs to press.
                const gathered = tray.size ? [...tray] : (selectedGroundId ? [selectedGroundId] : []);
                openComposer(gathered, { expression: p.draft_text || '' });
                return 'armed';
            }

            default:
                return undefined;
        }
    }, [findParts, grain, switchTool, tray, selectedGroundId, openComposer, receiveModelSuggestion]);

    // Exactly the acts the branch above can carry out. Anything absent renders as preview
    // only — the list and the switch are read together, so a capability cannot be claimed
    // without an executor behind it.
    const ACTION_CAPABILITIES = [
        'find_parts', 'brush_field', 'trace_direction', 'connect_marks', 'compose_percept',
    ];

    // ── refine commit / cancel / session release ─────────────────────────────
    // Confirm saves the new geometry revision (the endpoint persists) and refreshes
    // the region in the store IN PLACE — no reload, still inside Differential. Cancel
    // changes nothing on the server.
    const confirmRefine = useCallback(async () => {
        // CIRCUIT-001 P2D-A / P3-B Debt 3 — accepting a SAM proposal is an ACCEPT, and it
        // must stay visibly model-assisted rather than flatten to "I drew this". Two cases,
        // both honest:
        //   - refining an existing region → the model tightened the curator's mask → model_refined
        //   - a fresh mask               → the model proposed, the curator accepted → user_confirmed
        // Debt 3: the mark is a `region_mask`, NOT a brush_field. The mask lives on the Region
        // (region_id + geometry_rev); the mark only references it — never inline pixels
        // (contract v2 §7.2-C). The proposal is quarantined, so acceptance MINTS a mark that
        // points back at it (Label Studio parent_prediction), never flips a flag in place.
        const base = tool === 'refine' ? selectedRegion : null;
        const data = await refine.confirm();
        const r = data?.region;
        if (!r) return;
        const geometryRev = r.geometry_rev ?? refine.proposal?.geometry_rev ?? 0;
        const suggestion = quarantineSuggestion(regionMaskMark({
            regionId: r.id, geometryRev, model: 'sam2',
        }));
        // Fresh mask → user_confirmed (no prior geometry); refine-of-existing → model_refined
        // (derives from the base). Both carry lineage back to the suggestion, and both are
        // region_mask marks with role null (a segmented extent has no reading until given one).
        const accepted = base
            ? regionMaskMark({
                regionId: r.id, geometryRev, source: 'model_refined', status: 'committed',
                derivedFrom: suggestion?.id, model: 'sam2',
            })
            : acceptSuggestion(suggestion)?.accepted;
        if (accepted) emitMark(accepted);
        // Stamp the region with additive provenance so the store — and the chip below — show
        // the model's part this session. (Cross-reload PERSISTENCE of these fields needs the
        // confirm endpoint to echo them; that is a backend change, out of P2D-A scope, and is
        // recorded as residue in the report.)
        const stamped = {
            ...r,
            mark_source: accepted?.source || 'user_confirmed',
            refined_from: base?.id || null,
            mark_id: accepted?.id || null,
        };
        if (regions.some((x) => x.id === stamped.id)) updateRegion(stamped.id, stamped, { save: false });
        else addRegion(stamped, { save: false });
        selectRegion(stamped.id);
    }, [refine, tool, selectedRegion, regions, updateRegion, addRegion, selectRegion, emitMark]);

    // Release the SAM session when refinement mode ends…
    const wasRefine = useRef(false);
    useEffect(() => {
        if (wasRefine.current && tool !== 'refine') { refine.clear(); refine.release(); }
        wasRefine.current = tool === 'refine';
        // eslint-disable-next-line react-hooks/exhaustive-deps -- stable refine methods only
    }, [tool, refine.clear, refine.release]);
    // …and when the workspace unmounts.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable refine.release only
    useEffect(() => () => { refine.release(); }, [refine.release]);

    // ── region click (tool-aware) ───────────────────────────────────────────
    const handleRegionClick = useCallback((id, e) => {
        if (tool === 'select' || tool === 'similar') {
            if (e?.shiftKey && tool === 'select') setPicked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
            else setPicked(new Set([id]));
            selectRegion(id);
            selectGround(null);
        } else if (composing) {
            toggleMember(ensureRegionGround(id));
        }
    }, [tool, composing, selectRegion, selectGround, toggleMember, ensureRegionGround]);

    const addToTray = useCallback((groundId) => {
        setTray((s) => { const n = new Set(s); n.add(groundId); return n; });
    }, []);

    // ── keyboard ─────────────────────────────────────────────────────────────
    useEffect(() => {
        const down = (e) => {
            if (e.target.closest?.('input, textarea, [contenteditable="true"]')) return;
            // P4-B (2a): review shortcuts take precedence while reviewing (but not while
            // the geometry handles are open — then Escape/Enter belong to the reshape).
            if (review && !editing) {
                if (e.key === 'n' || e.key === 'ArrowRight') { e.preventDefault(); reviewNext(); return; }
                if (e.key === 'p' || e.key === 'ArrowLeft') { e.preventDefault(); reviewPrev(); return; }
                if (e.key === 'a') { e.preventDefault(); acceptCurrentSuggestion(); return; }
                if (e.key === 'd') { e.preventDefault(); dismissCurrentSuggestion(); return; }
                if (e.key === 'Escape') { e.preventDefault(); endReview(); return; }
            }
            if (tool === 'refine') {
                if (e.key === 'Enter') { e.preventDefault(); confirmRefine(); return; }
                if (e.key === 'Escape') { refine.clear(); return; }
            }
            if (e.code === 'KeyO' && !e.repeat) setUntouched(true);
            else if (e.key === 'Escape') {
                if (editing) cancelEdit();                 // P2E-B: reshape is a draft; Esc reverts it
                else if (recall) clearRecall();
                else if (composer) setComposer(null);
                else if (hasDrawDraft || hasCompDraft) clearDraft();
                else if (picked.size) setPicked(new Set());
                else if (tray.size) setTray(new Set());
                else { selectRegion(null); selectGround(null); setHoveredId(null); }
            } else if (tool === 'brush' && e.key === '[') setBrushRadius((r) => Math.max(0.012, r * 0.82));
            else if (tool === 'brush' && e.key === ']') setBrushRadius((r) => Math.min(0.16, r * 1.22));
            else if (tool === 'trace' && traceSub === 'boundary' && e.key === '[') setBandWidth((w) => Math.max(0.02, w * 0.82));
            else if (tool === 'trace' && traceSub === 'boundary' && e.key === ']') setBandWidth((w) => Math.min(0.2, w * 1.22));
            else if (e.key.toLowerCase() === 'b') switchTool('brush');
            else if (e.key.toLowerCase() === 'v') switchTool('select');
            else if (e.key.toLowerCase() === 't') switchTool('trace');
            else if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); undoStroke(); }
        };
        const up = (e) => { if (e.code === 'KeyO') setUntouched(false); };
        window.addEventListener('keydown', down);
        window.addEventListener('keyup', up);
        return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
        // eslint-disable-next-line react-hooks/exhaustive-deps -- stable refine.clear only
    }, [recall, clearRecall, composer, hasDrawDraft, hasCompDraft, picked, tray, clearDraft, undoStroke, switchTool, tool, traceSub, selectRegion, selectGround, setHoveredId, confirmRefine, refine.clear, editing, cancelEdit,
        review, reviewNext, reviewPrev, acceptCurrentSuggestion, dismissCurrentSuggestion, endReview]);

    const saving = saveState === 'saving' || metaSaveState === 'saving';
    const saved = saveState === 'saved' || metaSaveState === 'saved';

    const selected = regions.find((r) => r.id === selectedId) || null;
    const selectedGround = grounds.find((g) => g.id === selectedGroundId) || null;
    const focusId = hoveredId || selectedId;
    const litIds = composing && draft?.member_ids?.length
        ? new Set(grounds.filter((g) => g.ground_type === 'region' && draft.member_ids.includes(g.id)).map((g) => g.region_id))
        : (picked.size ? picked : null);

    const detachedGrounds = grounds.filter((g) => resolveGround(g, { regions, grounds })?.detached);
    const brushing = tool === 'brush' && !untouched;
    const tracing = tool === 'trace' && !untouched;
    const drawingTool = brushing || tracing;

    const memberSet = new Set(draft?.member_ids || []);

    return (
        <div className="diff-root" data-tool={tool}>
            {/* ── top bar ── */}
            <header className="diff-topbar">
                <button type="button" className="diff-back" onClick={onExit}
                    title="Back to Chiasm — the Manuscript is exactly as you left it">
                    <ArrowLeft size={15} /> Chiasm
                </button>
                <div className="diff-identity">
                    <span className="diff-eyebrow">Differential</span>
                    {post?.instagram_handle && <span className="diff-handle">@{post.instagram_handle}</span>}
                </div>
                <div className="diff-topbar-right">
                    <button type="button" className={`diff-untouched${untouched ? ' on' : ''}`}
                        onClick={() => setUntouched((u) => !u)} title="See the untouched image (hold O)">
                        <Eye size={14} /> <span>Untouched</span>
                    </button>
                    <span className={`diff-save diff-save--${saving ? 'saving' : saved ? 'saved' : 'idle'}`}>
                        {saving && 'saving…'}
                        {!saving && saved && <><Check size={12} /> saved</>}
                    </span>
                </div>
            </header>

            <div className="diff-body">
                {/* ── tool rail ── */}
                <nav className="diff-tools" aria-label="Perceptual operations">
                    {TOOLS.map((t) => (
                        <button key={t.key} type="button"
                            className={`diff-tool${tool === t.key ? ' on' : ''}`}
                            aria-pressed={tool === t.key}
                            title={`${t.label} — ${t.hint}`}
                            onClick={() => { if (t.key === 'frame') commitFrame(); else switchTool(t.key); }}>
                            <t.icon size={16} />
                            <span className="diff-tool-label">{t.label}</span>
                        </button>
                    ))}
                    {/* P3-B (2d) — minimal layer controls: visibility · opacity · lock on the
                        four system layers. No panel framework; a compact strip in the tool
                        column. recall is system-only and exposes no controls. */}
                    <div className="diff-layers" aria-label="Layers">
                        <span className="diff-layers-title">Layers</span>
                        {[...layers].sort((a, b) => b.order - a.order).map((l) => {
                            const system = isSystemLayer(l);
                            return (
                                <div key={l.id} className={`diff-layer-row${l.visibility === false ? ' is-hidden' : ''}`}>
                                    <button type="button" className="diff-layer-eye"
                                        aria-pressed={l.visibility !== false} disabled={system}
                                        title={system ? 'System layer' : (l.visibility === false ? 'Show' : 'Hide')}
                                        onClick={() => { if (!system) onToggleLayer(l.id); }}>
                                        {l.visibility === false ? <EyeOff size={12} /> : <Eye size={12} />}
                                    </button>
                                    <span className="diff-layer-name">{l.name}</span>
                                    {system ? (
                                        <span className="diff-layer-system" title="System layer — no controls">sys</span>
                                    ) : (
                                        <>
                                            <input type="range" className="diff-layer-opacity" min="0" max="1" step="0.05"
                                                value={l.opacity ?? 1} aria-label={`${l.name} opacity`}
                                                onChange={(e) => onLayerOpacity(l.id, Number(e.target.value))} />
                                            <button type="button" className={`diff-layer-lock${l.locked ? ' on' : ''}`}
                                                aria-pressed={!!l.locked} title={l.locked ? 'Unlock' : 'Lock'}
                                                onClick={() => onToggleLock(l.id)}>
                                                {l.locked ? <Lock size={11} /> : <Unlock size={11} />}
                                            </button>
                                        </>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </nav>

                {/* ── stage ── */}
                <main className="diff-stage-col">
                    {tracing && (
                        <div className="diff-subtools" role="radiogroup" aria-label="Trace mode">
                            <button type="button" role="radio" aria-checked={traceSub === 'path'}
                                className={`diff-subtool${traceSub === 'path' ? ' on' : ''}`}
                                onClick={() => setTraceSub('path')}>Path</button>
                            <button type="button" role="radio" aria-checked={traceSub === 'boundary'}
                                className={`diff-subtool${traceSub === 'boundary' ? ' on' : ''}`}
                                onClick={() => setTraceSub('boundary')}>Boundary</button>
                            {traceSub === 'boundary' && (
                                <label className="diff-band">band
                                    <input type="range" min="0.02" max="0.2" step="0.005" value={bandWidth}
                                        onChange={(e) => setBandWidth(Number(e.target.value))} />
                                </label>
                            )}
                        </div>
                    )}

                    {/* P3-B (2a) — the trace instrument: a role picker (like the brush's),
                        and an honest terminus. Arrowhead is a choice; "ambiguous" replaces it
                        with a soft fade so the line never asserts a target the curator never
                        named. Path only — a boundary is a seam, not a directed line. */}
                    {tracing && traceSub === 'path' && (
                        <>
                            <div className="diff-subtools diff-brush-roles" role="radiogroup" aria-label="Trace role">
                                {TRACE_ROLES.map((rk) => (
                                    <button key={rk} type="button" role="radio" aria-checked={traceRole === rk}
                                        className={`diff-subtool diff-role-chip${traceRole === rk ? ' on' : ''}`}
                                        onClick={() => setTraceRole(rk)}>{roleLabel('trace_mark', rk)}</button>
                                ))}
                            </div>
                            <div className="diff-subtools diff-trace-terminus">
                                <label className="diff-pf-toggle" title="A sharp arrowhead asserts a direction toward a target.">
                                    <input type="checkbox" checked={traceArrowhead}
                                        onChange={(e) => setTraceArrowhead(e.target.checked)} />
                                    <span>arrowhead</span>
                                </label>
                                <label className="diff-pf-toggle" title="Ambiguous target — a soft fading terminus, no arrow claiming a target you did not name.">
                                    <input type="checkbox" checked={traceAmbiguous}
                                        onChange={(e) => setTraceAmbiguous(e.target.checked)} />
                                    <span>ambiguous target</span>
                                </label>
                            </div>
                        </>
                    )}

                    {/* P3-B (2b) — the relation instrument: a relation-role picker. The
                        connector geometry is derived from the tied members at render. */}
                    {tool === 'connect' && !untouched && (
                        <div className="diff-subtools diff-brush-roles" role="radiogroup" aria-label="Relation role">
                            {RELATION_ROLES.map((rk) => (
                                <button key={rk} type="button" role="radio" aria-checked={relationRole === rk}
                                    className={`diff-subtool diff-role-chip${relationRole === rk ? ' on' : ''}`}
                                    onClick={() => setRelationRole(rk)}>{roleLabel('relation_mark', rk)}</button>
                            ))}
                        </div>
                    )}

                    {/* P2E-B (2e) — the semantic brush: a field role is the whole point of
                        the brush. Draw with a role and it mints a contract-shaped brush_field.
                        P3-B (2c): an Erase toggle paints strokes[].op:'sub' — erase as DATA. */}
                    {brushing && (
                        <>
                            <div className="diff-subtools diff-brush-roles" role="radiogroup" aria-label="Field role">
                                {BRUSH_ROLES.map((rk) => (
                                    <button key={rk} type="button" role="radio" aria-checked={brushRole === rk}
                                        className={`diff-subtool diff-role-chip${brushRole === rk ? ' on' : ''}`}
                                        onClick={() => setBrushRole(rk)}>{roleLabel('brush_field', rk)}</button>
                                ))}
                            </div>
                            <label className={`diff-pf-toggle diff-erase-toggle${brushErase ? ' on' : ''}`}
                                title="Erase mode — the stroke subtracts (op:'sub'), composited destination-out. ⌥ also erases for one stroke.">
                                <input type="checkbox" checked={brushErase}
                                    onChange={(e) => setBrushErase(e.target.checked)} />
                                <span>{brushErase ? 'erasing' : 'erase'}</span>
                            </label>
                        </>
                    )}

                    {/* P2E-B (2d) — the freehand ribbon generator toggle, shown for the
                        drawing tools where the taper is visible. */}
                    {(brushing || tracing) && (
                        <label className="diff-pf-toggle" title="perfect-freehand: pressure-expressive taper (spike-adopted); off = vendored taperedRibbon">
                            <input type="checkbox" checked={usePerfectFreehand}
                                onChange={(e) => setUsePerfectFreehand(e.target.checked)} />
                            <span>{usePerfectFreehand ? 'perfect-freehand' : 'taperedRibbon'}</span>
                        </label>
                    )}

                    <div className={
                        `diff-stage${untouched ? ' is-untouched' : ''}`
                        + `${drawingTool ? ' is-drawing' : ''}`
                        + `${recallPlayer.receding ? ' is-recalling' : ''}`}
                        ref={stageRef}
                        style={natural ? { '--diff-ar': `${natural.w} / ${natural.h}` } : undefined}
                        onPointerDown={onStagePointerDown}
                        onPointerMove={onStagePointerMove}
                        onPointerUp={onStagePointerUp}
                        onPointerLeave={() => { endStroke(); setBrushCursor(null); }}
                        // Belt-and-braces against the native image drag stealing the gesture.
                        onDragStart={(e) => e.preventDefault()}>
                        <img src={post.photo_url} alt="" referrerPolicy="no-referrer" onLoad={onImgLoad}
                            draggable={false} />
                        {!untouched && (
                            <>
                                <RegionOverlay
                                    natural={natural} regions={regions} viewMap="quiet"
                                    selectedId={selectedId} activeId={hoveredId} focusId={focusId} litIds={litIds}
                                    onSelect={(tool === 'select' || composing || tool === 'similar') ? handleRegionClick : undefined}
                                    onActivate={(tool === 'select' || tool === 'similar') ? setHoveredId : undefined}
                                    className="diff-svg"
                                    interactive={tool !== 'refine'}
                                    // P4-B (2c): the mask preview no longer rides RegionOverlay's
                                    // ad-hoc `rs-proposal` — it renders on the SUGGESTION layer
                                    // (RefineProposalGhost below), visibly distinct and uncitable.
                                    // RegionOverlay keeps only the fg/bg point + box PROMPT.
                                    proposal={null}
                                    prompt={tool === 'refine' ? { points: refine.points, box: refineBox || refine.box } : null}
                                />
                                <GroundLayers
                                    grounds={groundsForLayers} regions={regions} natural={natural} content={content}
                                    focusGroundIds={draftFocus}
                                    recall={recallPlayer.active ? recallPlayer : null}
                                    draft={draftForLayers?.kind === 'field' || draftForLayers?.kind === 'path' || draftForLayers?.kind === 'boundary' ? draftForLayers : null}
                                    // P2E-B (2d) ribbon toggle · (2b) editable-ground hit-paths
                                    usePerfectFreehand={usePerfectFreehand}
                                    // P3-B (2d): a locked evidence layer refuses hit-path picks too.
                                    interactive={tool === 'select' && !editing && !evidenceLocked}
                                    onPickGround={beginEditGround}
                                    editingGroundId={editing?.target}
                                    // P3-B (2d): the evidence layer's visibility/opacity controls.
                                    evidenceVisible={evidenceLayer?.visibility !== false}
                                    evidenceOpacity={evidenceLayer?.opacity ?? 1}
                                />
                                {/* P2E-B (2e) — pending suggestions render as a distinct dashed
                                    ghost: model-proposed, uncitable, never mistaken for evidence.
                                    P3-B (2d): honors the suggestion layer's visibility control. */}
                                {suggestionLayer?.visibility !== false && (
                                    <SuggestionGhosts marks={pendingSuggestions} natural={natural} usePF={usePerfectFreehand} />
                                )}
                                {/* P4-B (2c) — the SAM refine PREVIEW lives on the suggestion
                                    layer: a distinct dashed teal mask, uncitable, never mistaken
                                    for a committed segment. Correction (add/remove fg/bg points,
                                    re-preview) happens under it; Accept persists via confirmRefine. */}
                                {tool === 'refine' && suggestionLayer?.visibility !== false && (
                                    <RefineProposalGhost proposal={refine.proposal} natural={natural} />
                                )}
                                {/* P2E-B (2c) — editable anchors on the geometry being reshaped */}
                                {editing && natural && (
                                    <InstrumentHandles
                                        natural={natural}
                                        points={editing.points}
                                        clientToNormalized={clientToNormalized}
                                        onMove={editMove} onInsert={editInsert} onRemove={editRemove}
                                        // P3-B (2d): if evidence locks mid-edit, the handles go inert.
                                        locked={editing.target !== '__draft__' && evidenceLocked}
                                    />
                                )}
                            </>
                        )}
                        {brushing && brushCursor && content && (
                            <span className="diff-brush-cursor" style={{
                                left: content.x + brushCursor.x * content.w,
                                top: content.y + brushCursor.y * content.h,
                                width: brushRadius * content.w * 2, height: brushRadius * content.w * 2,
                            }} />
                        )}
                        {recallPlayer.caption && (
                            <div className="diff-recall-say">
                                <p className="diff-recall-caption">{recallPlayer.caption}</p>
                                {recallPlayer.evidenceNote && (
                                    <p className="diff-recall-detached">{recallPlayer.evidenceNote}</p>
                                )}
                            </div>
                        )}
                    </div>
                    {/* CIRCUIT-001 P2B — an armed act, waiting for the curator's hand. It
                        says what will be named, and that nothing exists until they draw. */}
                    {stagedMark && (
                        <p className="diff-armed" role="status">
                            <strong>{stagedMark.label || stagedMark.role}</strong>
                            {' — armed. Make the mark; nothing is created until you do.'}
                        </p>
                    )}
                    <p className="diff-stage-hint">
                        {untouched ? 'The untouched image. Release O to see your evidence again.'
                            : brushing ? 'Paint where it lives. [ ] size · ⌥ lifts paint away · Esc clears the draft.'
                                : tracing ? (traceSub === 'path'
                                    ? 'Draw a path — a directed line through what moves you. Esc clears it.'
                                    : 'Draw a boundary — the seam where one thing becomes another. [ ] widen the band.')
                                    : tool === 'collect' ? 'Click grounds and empty points to gather a constellation.'
                                        : tool === 'connect' ? 'Click two or more grounds to tie them into a relation.'
                                            : tool === 'refine' ? (selectedRegion
                                                ? 'Refine — click the part to grow the mask, ⇧-click to subtract, or drag a box. Enter confirms · Esc clears.'
                                                : 'Refine — Select a part first, then click/drag to tighten it to an exact mask.')
                                                : tool === 'read' ? 'Read — ask the model to interpret the parts in the inspector. It names, qualifies and relates them; it never moves a mask.'
                                                    : tool === 'similar' ? 'Similar — select a part; its visual neighbours appear in the inspector as research to inspect (source, exact mask, distance, space), never as facts.'
                                                        : 'Select parts (⇧ to gather several), or take a tool: Brush (B), Trace (T), Collect, Connect, Frame.'}
                    </p>
                </main>

                {/* ── orchestration column (CIRCUIT-001 P2B) ──
                    Was a narrow inspector holding whatever was selected, with the console
                    bolted underneath. Now a sectioned column, ordered by when a curator
                    needs each part: attend → operate → work → review. */}
                <aside className="diff-inspector">

                    {/* 1 — FIRST ATTENTION. The panel a curator meets first, because
                        beginning from what caught you is the point of this gate. */}
                    <section className="diff-insp-section diff-insp-section--attune">
                        <AttunementPanel
                            hasParts={regions.length > 0}
                            wayOfLooking={(post?.domain_profile?.chosen || ['general'])[0]}
                            capabilities={ACTION_CAPABILITIES}
                            onApplyAction={applyPerceptualAction}
                            prefill={firstAttentionPrefill}
                        />
                    </section>

                    {/* P2E-B (2c) — the reshape session. A committed line's points are being
                        edited by hand; nothing is written until Keep. Esc reverts. */}
                    {editing && (
                        <section className="diff-insp-section diff-insp-reshape" role="status">
                            <span className="diff-eyebrow">Reshaping</span>
                            <p className="diff-insp-hint">
                                Drag a handle to move a point · click the line to add one ·
                                right-click a handle to remove it. {editing.points.length} points — still a draft.
                            </p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={keepEdit}>Keep changes</button>
                                <button type="button" className="diff-quiet" onClick={cancelEdit}>Cancel (Esc)</button>
                            </div>
                        </section>
                    )}

                    {/* P4-B (2a) — the suggestion quarantine, now a REVIEW surface. When
                        the model proposes marks they wait here, uncitable and visibly the
                        model's. Not reviewing yet → an entry with the count and a Review
                        button (a single suggestion still gets quick Accept/Dismiss). While
                        reviewing → the full surface: cycle, edit, accept/dismiss, bulk. */}
                    {pendingSuggestions.length > 0 && !review && (
                        <section className="diff-insp-section diff-insp-suggestions">
                            <div className="diff-review-head">
                                <span className="diff-eyebrow">Model suggestions · {pendingSuggestions.length}</span>
                                <button type="button" className="diff-primary diff-review-start" onClick={startReview}>
                                    Review {pendingSuggestions.length}
                                </button>
                            </div>
                            {pendingSuggestions.length === 1 && (
                                <div className="diff-suggestion">
                                    <div className="diff-suggestion-head">
                                        <span className="diff-chip diff-mark-prov-chip is-model">{summarizeProvenance(pendingSuggestions[0])}</span>
                                        <span className="diff-suggestion-role">{roleLabel(pendingSuggestions[0].type, pendingSuggestions[0].role)}</span>
                                    </div>
                                    {pendingSuggestions[0].label && <p className="diff-insp-hint">“{pendingSuggestions[0].label}”</p>}
                                    <div className="diff-insp-row-actions">
                                        <button type="button" className="diff-primary" onClick={() => acceptBrushSuggestion(pendingSuggestions[0])}>Accept</button>
                                        <button type="button" className="diff-quiet" onClick={() => dismissBrushSuggestion(pendingSuggestions[0])}>Dismiss</button>
                                    </div>
                                </div>
                            )}
                        </section>
                    )}
                    {review && pendingSuggestions.length > 0 && (
                        <SuggestionReview
                            suggestions={pendingSuggestions}
                            index={review.index}
                            edit={review.edit}
                            dismissReason={review.dismissReason}
                            geometryEditing={editing?.target === '__suggestion__'}
                            onPrev={reviewPrev}
                            onNext={reviewNext}
                            onAccept={acceptCurrentSuggestion}
                            onDismiss={dismissCurrentSuggestion}
                            onDismissAll={dismissAllSuggestions}
                            onSetRole={stageReviewRole}
                            onSetLabel={stageReviewLabel}
                            onEditGeometry={editReviewGeometry}
                            onSetDismissReason={setReviewDismissReason}
                        />
                    )}

                    {/* 2 — SEEING. Find parts stays one keystroke away, but it is now one
                        act among several rather than the door into the workspace. */}
                    <section className="diff-insp-section">
                        <SeeingConsole
                            postId={postId}
                            profile={post?.domain_profile}
                            onProfile={(p) => onPostChange?.({ ...post, domain_profile: p })}
                            regions={regions}
                            onFindParts={(opts) => findParts.find({ ...(opts || {}), mode: grain })}
                            busy={findParts.busy}
                            grain={grain}
                            onGrain={setGrain}
                            actionStatus={{
                                refine: refine.status,
                                semantic_read: reading.status,
                                find_similar: similar.status,
                            }}
                            compact
                        />
                        {findParts.error && (
                            <p className="diff-insp-hint" role="alert">{findParts.error}</p>
                        )}
                        {/* CIRCUIT-001 P5-B — the Passage: the real run under the hand + this
                            session's circulation, honestly rendered. A witness, not a narrator.
                            P5F: mounted inside the Differential tool column for v1; spanning
                            Field ↔ Manuscript is a recorded future promotion (A5 owns those seams). */}
                        <PassageRail
                            postId={postId}
                            operation={passageOperation}
                            marks={visualMarks}
                            recall={recall}
                            onHighlightRun={highlightRunMarks}
                            onHighlightMark={highlightMark}
                        />
                    </section>

                    {/* 3 — the working area: whatever is under the hand right now. */}
                    {/* refine (VISION-B5) — exact-mask refinement of the selected part */}
                    {tool === 'refine' && (
                        <div className="diff-insp-refine">
                            <span className="diff-eyebrow">Refine mask</span>
                            <p className="diff-insp-hint">
                                {selectedRegion
                                    ? <>Tightening <strong>{regionName(selectedRegion)}</strong> — the exact mask replaces its box.</>
                                    : 'No part selected — this makes a new mask. (Select a part first for Select → Refine.)'}
                            </p>
                            <div className="diff-refine-status" aria-live="polite">
                                {refine.status === 'loading' && (<><span className="diff-refine-spin" /> refining…</>)}
                                {refine.status === 'ok' && `proposed · ${Math.round((refine.proposal.confidence || 0) * 100)}% · rev ${refine.proposal.geometry_rev}`}
                                {refine.status === 'empty' && 'no confident mask yet — add a point or drag a box'}
                                {refine.status === 'error' && <span className="diff-refine-err">refiner error: {refine.error}</span>}
                                {refine.status === 'confirmed' && <span className="diff-refine-ok">saved ✓</span>}
                                {refine.status === 'idle' && (selectedRegion ? 'click the part, or drag a box' : 'select a part first')}
                            </div>
                            {/* CIRCUIT-001 P2D-A — the quarantine, made visible. While the model's
                                mask is only proposed it is a SUGGESTION, and the chip says so out
                                loud (the anti-CVAT rule: invisible provenance is no provenance).
                                Confirm ACCEPTS it — minting a mark that keeps the model's part in
                                the record — rather than laundering it into "I drew this". */}
                            {refine.status === 'ok' && (
                                <p className="diff-mark-prov diff-mark-prov--suggested" role="status">
                                    <span className="diff-prov-dot" aria-hidden="true" />
                                    {summarizeProvenance({ source: 'model_suggested' })}
                                    <span className="diff-prov-note"> — accepting keeps it as “{summarizeProvenance({ source: selectedRegion ? 'model_refined' : 'user_confirmed' })}”.</span>
                                </p>
                            )}
                            <div className="diff-refine-actions">
                                <button type="button" className="diff-mini" onClick={() => refine.clear()} disabled={!refine.hasPrompt}>Clear</button>
                                <button type="button" className="diff-mini" onClick={() => { refine.clear(); switchTool('select'); }}>Dismiss</button>
                                <button type="button" className="diff-mini diff-mini--primary" onClick={confirmRefine} disabled={refine.status !== 'ok'}>Accept</button>
                            </div>
                        </div>
                    )}
                    {/* read (VISION-D · D4) — the VLM reading of the candidate masks */}
                    {tool === 'read' && (
                        <SemanticReading
                            semantics={reading.semantics} status={reading.status}
                            error={reading.error} busyId={reading.busyId} regions={regions}
                            onRead={(intent, force) => reading.read({ intent, force })}
                            onCancel={reading.cancel} onCurate={reading.curate}
                            onFocusRegion={(id) => { selectRegion(id); selectGround(null); }}
                            onHoverRegion={setHoveredId} onRefine={readingToRefine}
                        />
                    )}
                    {/* similar (VISION-E · E5) — visual neighbours of the selected part */}
                    {tool === 'similar' && (
                        <FindSimilar
                            regionName={selectedRegion ? regionName(selectedRegion) : null}
                            status={similar.status} error={similar.error} results={similar.results}
                            meta={similar.meta} cropUrl={similar.cropUrl}
                            onFind={similar.find} onReindex={similar.reindex} onCancel={similar.cancel}
                        />
                    )}
                    {/* draw draft (field/path/boundary) */}
                    {hasDrawDraft && !composer && (
                        <div className="diff-insp-draft">
                            <span className="diff-eyebrow">Draft {draft.kind}</span>
                            <p className="diff-insp-hint">
                                {draft.kind === 'field'
                                    ? `${draftForLayers.strokes.length} stroke${draftForLayers.strokes.length !== 1 ? 's' : ''} — still yours to shape.`
                                    : 'A line, still yours to shape.'}
                            </p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={commitDraft}>Keep this {draft.kind}</button>
                                {draft.kind === 'field' && (
                                    <button type="button" className="diff-quiet" onClick={undoStroke} title="Undo the last stroke (⌘Z)">
                                        <Undo2 size={13} /> Undo
                                    </button>
                                )}
                                <button type="button" className="diff-quiet" onClick={clearDraft}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* composition draft (constellation/relation) */}
                    {composing && !composer && (
                        <div className="diff-insp-draft">
                            <span className="diff-eyebrow">{tool === 'collect' ? 'Constellation' : 'Relation'}</span>
                            <p className="diff-insp-hint">
                                {(draft?.member_ids || []).length} ground{(draft?.member_ids || []).length !== 1 ? 's' : ''}
                                {tool === 'collect' && (draft?.points || []).length > 0 && ` · ${draft.points.length} point${draft.points.length !== 1 ? 's' : ''}`}
                                {' '}gathered — click grounds below or on the image.
                            </p>
                            {tool === 'connect' && (
                                <input className="diff-relation-label" placeholder="How are they related? (optional)"
                                    value={draft?.relation_label || ''}
                                    onChange={(e) => setDraft((d) => ({ ...d, relation_label: e.target.value }))} />
                            )}
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary"
                                    disabled={tool === 'connect' ? (draft?.member_ids || []).length < 2 : !hasCompDraft}
                                    onClick={commitDraft}>
                                    Keep this {tool === 'collect' ? 'constellation' : 'relation'}
                                </button>
                                <button type="button" className="diff-quiet" onClick={clearDraft}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* composer */}
                    {composer && (
                        <div className="diff-composer">
                            <div className="diff-composer-head">
                                <span className="diff-eyebrow">Percept</span>
                                <button type="button" className="diff-icon-btn" onClick={() => setComposer(null)}
                                    title="Later — the grounds stay; compose when ready">
                                    <X size={13} />
                                </button>
                            </div>
                            <p className="diff-composer-ask">What do you notice?</p>
                            <textarea autoFocus className="diff-composer-input" placeholder="Say it as you saw it…"
                                value={composer.expression}
                                onChange={(e) => setComposer((c) => ({ ...c, expression: e.target.value }))}
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); savePercept(); }
                                    if (e.key === 'Escape') { e.stopPropagation(); setComposer(null); }
                                }} />
                            <div className="diff-composer-props">
                                {PERCEPT_PROPERTIES.map((prop) => (
                                    <button key={prop} type="button"
                                        className={`diff-prop${composer.properties.includes(prop) ? ' on' : ''}`}
                                        onClick={() => setComposer((c) => ({
                                            ...c,
                                            properties: c.properties.includes(prop)
                                                ? c.properties.filter((x) => x !== prop) : [...c.properties, prop],
                                        }))}>
                                        {prop}
                                    </button>
                                ))}
                            </div>
                            {/* CIRCUIT-001 P1C — Ground Roles. What each cited ground DOES for
                                this reading. Optional everywhere: a percept with no roles is
                                complete, and nothing downstream may refuse one for lacking them.
                                Click a named role again to clear it. The role belongs to this
                                percept's USE of the ground, never to the ground record — the
                                same region is an anchor in one noticing and a counterforce in
                                another. */}
                            {composer.groundIds.length > 0 && (
                                <div className="diff-composer-roles">
                                    {composer.groundIds.map((gid) => (
                                        <div key={gid} className="diff-role-row">
                                            <span className="diff-role-ground">
                                                {groundTitle(groundById(gid), regions)}
                                            </span>
                                            <span className="diff-role-opts">
                                                {CORE_ROLES.map((r) => (
                                                    <button key={r.key} type="button" title={r.hint}
                                                        className={`diff-role${(composer.roles?.[gid] === r.key) ? ' on' : ''}`}
                                                        onClick={() => setComposer((c) => {
                                                            const roles = { ...(c.roles || {}) };
                                                            if (roles[gid] === r.key) delete roles[gid];
                                                            else roles[gid] = r.key;
                                                            return { ...c, roles };
                                                        })}>
                                                        {r.label}
                                                    </button>
                                                ))}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary"
                                    disabled={!composer.expression.trim()} onClick={savePercept}>Keep this percept</button>
                                <button type="button" className="diff-quiet" onClick={() => setComposer(null)}>Later</button>
                            </div>
                            <p className="diff-insp-hint">
                                Grounded in: {composer.groundIds.map((id) => groundTitle(groundById(id), regions)).join(' · ')}
                            </p>
                        </div>
                    )}

                    {/* the tray — accumulative multi-ground percepts */}
                    {tray.size > 0 && !composer && (
                        <div className="diff-insp-tray">
                            <span className="diff-eyebrow">Gathered · {tray.size}</span>
                            <p className="diff-insp-hint">{[...tray].map((id) => groundTitle(groundById(id), regions)).join(' · ')}</p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={composeFromTray}>Compose a percept</button>
                                <button type="button" className="diff-quiet" onClick={() => setTray(new Set())}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* picked regions (Select) */}
                    {!composer && !hasDrawDraft && !composing && picked.size > 0 && (
                        <div className="diff-insp-ground">
                            <span className="diff-eyebrow">{picked.size} part{picked.size !== 1 ? 's' : ''} gathered</span>
                            <p className="diff-insp-hint">{[...picked].map((id) => regionName(regions.find((r) => r.id === id))).join(' · ')}</p>
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={composeFromRegions}>Compose a percept</button>
                                <button type="button" className="diff-quiet" onClick={() => setPicked(new Set())}>Clear</button>
                            </div>
                        </div>
                    )}

                    {/* a single selected Ground */}
                    {!composer && !hasDrawDraft && !composing && picked.size === 0 && selectedGround && (
                        <div className="diff-insp-ground">
                            <span className="diff-eyebrow">{selectedGround.ground_type} · evidence</span>
                            <h3 className="diff-insp-name">{groundTitle(selectedGround, regions)}</h3>
                            <div className="diff-insp-meta">
                                <span className="diff-chip">{selectedGround.actor}</span>
                                {selectedGround.detector && <span className="diff-chip">{selectedGround.detector}</span>}
                                {selectedGround.ground_type === 'frame' && (selectedGround.evidence_ids || []).length > 0 && (
                                    <span className="diff-chip diff-chip--dim">{selectedGround.evidence_ids.length} inside</span>
                                )}
                                {/* CIRCUIT-001 P2D-A — provenance, made visible on the ground itself.
                                    The mark linked to this ground carries the real source; the chip
                                    speaks it (anti-CVAT). A user's own brush reads "Yours" quietly;
                                    anything the model touched says so. */}
                                {(() => {
                                    const gm = marks.find((m) => (m.linked_ground_ids || []).includes(selectedGround.id));
                                    if (!gm) return null;
                                    return (
                                        <span className={`diff-chip diff-mark-prov-chip${hasModelInvolvement(gm) ? ' is-model' : ''}`}
                                            title={markSummary(gm)}>
                                            {summarizeProvenance(gm)}
                                        </span>
                                    );
                                })()}
                            </div>
                            {selectedGround.ground_type === 'frame' && (
                                <p className="diff-insp-hint">
                                    The whole image as one piece of evidence — for a percept about the
                                    whole composition, not a single part. The brackets mark its edge.
                                </p>
                            )}
                            <div className="diff-insp-row-actions">
                                <button type="button" className="diff-primary" onClick={() => openComposer(selectedGround.id)}>Compose a percept</button>
                                {/* P2E-B (2c) — reshape a committed line by hand. */}
                                {isEditableGround(selectedGround) && !editing && (
                                    <button type="button" className="diff-quiet" onClick={() => beginEditGround(selectedGround.id)}>
                                        <PenTool size={13} /> Adjust points
                                    </button>
                                )}
                                <button type="button" className="diff-quiet" onClick={() => addToTray(selectedGround.id)}>
                                    <Plus size={13} /> Gather
                                </button>
                                <button type="button" className="diff-quiet" onClick={() => removeGround(selectedGround.id)}>Remove</button>
                            </div>
                        </div>
                    )}

                    {!composer && !hasDrawDraft && !composing && picked.size === 0 && !selectedGround && !selected && grounds.length === 0 && tray.size === 0 && (
                        <div className="diff-insp-empty">
                            <span className="diff-eyebrow">Inspector</span>
                            <p>Nothing under attention. Select parts, take the Brush (<kbd>B</kbd>) or Trace
                                (<kbd>T</kbd>), or press <kbd>O</kbd> for the untouched photograph.</p>
                        </div>
                    )}

                    {/* the grounds so far — clickable to select, ⁘/⤝ to gather */}
                    {grounds.length > 0 && !composer && (
                        <div className="diff-insp-grounds">
                            <span className="diff-eyebrow">Grounds</span>
                            {grounds.map((g) => {
                                const inDraft = composing && memberSet.has(g.id);
                                return (
                                    <div key={g.id}
                                        className={`diff-ground-row${selectedGroundId === g.id ? ' is-sel' : ''}${inDraft ? ' is-member' : ''}`}
                                        onMouseEnter={() => setHoveredGroundId(g.id)}
                                        onMouseLeave={() => setHoveredGroundId(null)}>
                                        <button type="button" className="diff-ground-main"
                                            onClick={() => (composing ? toggleMember(g.id) : selectGround(g.id === selectedGroundId ? null : g.id))}>
                                            <span className="diff-ground-glyph" aria-hidden>
                                                {composing ? (inDraft ? '☑' : '☐') : (GROUND_GLYPH[g.ground_type] || '◇')}
                                            </span>
                                            <span className="diff-ground-name">{groundTitle(g, regions)}</span>
                                        </button>
                                        {!composing && (
                                            <button type="button" className="diff-ground-add" title="Gather for a percept"
                                                onClick={(e) => { e.stopPropagation(); addToTray(g.id); }}>
                                                <Plus size={12} />
                                            </button>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* CIRCUIT-001 P2 — the percept workshop. Same percepts, same actions,
                        same P1D thread and P1C roles; what changed is that a percept now
                        reads as a unit of attention — the noticing, what it rests on, where
                        it has got to in the writing — rather than a row with verbs after it. */}
                    <PerceptWorkshop
                        percepts={expressionPercepts}
                        grounds={grounds} regions={regions}
                        mentions={store?.mentions || []} postId={postId}
                        onPlay={playRecall}
                        onSendToManuscript={onSendToManuscript}
                    />

                    {detachedGrounds.length > 0 && (
                        <div className="diff-insp-detached">
                            <span className="diff-eyebrow">Detached evidence</span>
                            {detachedGrounds.map((g) => (
                                <p key={g.id} className="diff-detached-row">
                                    {/* States what no longer resolves, never why. resolveGround
                                        knows only that the region_id does not resolve — a
                                        re-dissect is one cause among several (a deleted region, a
                                        never-existed id), and naming it asserted a fact the code
                                        cannot have. Same rule the Rail already keeps. */}
                                    {g.label || g.ground_type} — its part is no longer in the image
                                </p>
                            ))}
                        </div>
                    )}

                    <footer className="diff-insp-counts">
                        {regions.length} part{regions.length !== 1 ? 's' : ''} ·{' '}
                        {grounds.length} ground{grounds.length !== 1 ? 's' : ''} ·{' '}
                        {expressionPercepts.length} percept{expressionPercepts.length !== 1 ? 's' : ''}
                    </footer>

                </aside>
            </div>
        </div>
    );
}

/**
 * P4-B (2c) — the SAM refine proposal, rendered on the suggestion layer as a
 * DISTINCT dashed teal mask: a preview, visibly the model's, uncitable, never
 * mistaken for a committed segment. Same natural-pixel viewBox as the marks, so
 * it registers exactly with the image. The prompt points (fg/bg) render through
 * RegionOverlay; this is only the mask preview.
 */
export function RefineProposalGhost({ proposal, natural }) {
    if (!natural || !proposal || !hasMaskPolygons(proposal)) return null;
    return (
        <svg className="diff-refine-ghost"
            viewBox={`0 0 ${natural.w} ${natural.h}`} preserveAspectRatio="xMidYMid meet"
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 5 }}
            aria-hidden="true">
            <path d={ringsToPath(proposal.polygons, natural.w, natural.h)} fillRule="evenodd"
                fill="#7FB3A8" fillOpacity={0.16} stroke="#7FB3A8" strokeOpacity={0.85}
                strokeWidth={Math.max(1.5, 0.003 * natural.w)} strokeDasharray="7 5"
                vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
        </svg>
    );
}

/**
 * P2E-B (2e) — render pending suggestions as a DISTINCT dashed ghost over the
 * stage: model-proposed, uncitable, and unmistakable for evidence (the CVAT
 * lesson — provenance you can SEE). A suggestion's stroke is drawn as a dashed
 * centerline in the same natural-pixel viewBox the marks use, so it lands exactly
 * where the model proposed and never touches the committed field wash below it.
 */
function SuggestionGhosts({ marks = [], natural, usePF }) {
    void usePF;
    if (!natural || !marks.length) return null;
    const centerline = (pts) => (pts || [])
        .map((p, i) => {
            const [x, y] = Array.isArray(p) ? p : [p.x, p.y];
            return `${i ? 'L' : 'M'}${(x * natural.w).toFixed(2)},${(y * natural.h).toFixed(2)}`;
        }).join(' ');
    return (
        <svg className="diff-suggestion-ghosts"
            viewBox={`0 0 ${natural.w} ${natural.h}`} preserveAspectRatio="xMidYMid meet"
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 5 }}
            aria-hidden="true">
            {marks.map((m) => (m.geometry?.strokes || []).map((s, i) => {
                const d = centerline(s.points);
                if (!d) return null;
                const w = Math.max(2, (s.radius || 0.05) * natural.w);
                return (
                    <g key={`${m.id}-${i}`} className="diff-suggestion-ghost">
                        <path d={d} fill="none" stroke="#7FB3A8" strokeOpacity={0.35}
                            strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
                        <path d={d} fill="none" stroke="#7FB3A8" strokeWidth={Math.max(1.5, w * 0.18)}
                            strokeDasharray="6 5" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
                    </g>
                );
            }))}
        </svg>
    );
}
