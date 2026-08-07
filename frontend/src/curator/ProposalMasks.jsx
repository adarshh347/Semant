import React, { useEffect, useMemo, useState } from 'react';
import RegionOverlay from '../components/RegionOverlay';
import { API_URL } from '../config/api';
import './proposalMasks.css';

/**
 * WAVE4 — the two masks, on the photograph. The strongest evidence a curator can commit on.
 *
 * The queue shows an occlusion as numbers: an ordering of 0.9656 against a floor of 0.95. Those
 * are the right numbers and they are not the evidence a person is best at judging. The evidence is
 * that the lattice window's mask is visibly *in front of* the mosque wall's — which the system has
 * been able to draw since the region surface existed, and has never shown at the one seam where a
 * human decides.
 *
 * ## One renderer
 *
 * Shapes are drawn by `RegionOverlay` — the same component the region surface and the lightbox
 * use, and the one place the alignment contract lives (natural-pixel viewBox, `xMidYMid meet`,
 * letterboxing identically to the image). This lane adds no second renderer: a curator looking at
 * a mask and an editor looking at the same mask must be looking at the same code, or the thing the
 * curator commits on is not the thing the system measured.
 *
 * Which of the two is in front is expressed through the overlay's OWN attention mechanism —
 * `litIds` carries the front region, so it renders `is-lit` and the back one `is-dim`. That is the
 * component's existing vocabulary for "this one is the figure", used for its meaning rather than
 * re-implemented.
 *
 * ## What it will not do
 *
 * **No approximation.** Geometry comes from the scene route, which serves the mask outlines the
 * segmenter actually drew. If either region is missing, or carries no outline, this renders a
 * stated absence and the panel stays as it is today — numbers only. A box drawn where a mask
 * should be would be the curator committing on a shape nobody measured, which is the WAVE2.5
 * failure arriving at the exact moment it would become durable.
 *
 * **No implication of commitment.** The overlay carries the proposal's two statuses as data
 * attributes and the stroke follows them — dashed for an interpretive basis, and never the solid
 * treatment a committed relation would earn. Looking at the geometry must not feel like accepting
 * it; accepting it is the button below.
 *
 * Read-only. This fetches one scene and renders it.
 */

const NO_GEOMETRY = 'no_geometry';
const LOADING = 'loading';
const READY = 'ready';
const UNREACHABLE = 'unreachable';

export default function ProposalMasks({ proposal, fetchScene }) {
    const postId = proposal?.post_id || '';
    const frontId = proposal?.subject?.front_region_id || '';
    const backId = proposal?.subject?.back_region_id || '';

    const [scene, setScene] = useState(null);
    const [state, setState] = useState(LOADING);
    const [natural, setNatural] = useState(null);

    useEffect(() => {
        if (!postId || !frontId || !backId) { setState(NO_GEOMETRY); return undefined; }
        let alive = true;
        setState(LOADING);
        setNatural(null);
        const load = fetchScene || defaultFetchScene;
        load(postId)
            .then((data) => { if (alive) { setScene(data); setState(READY); } })
            .catch(() => { if (alive) { setScene(null); setState(UNREACHABLE); } });
        return () => { alive = false; };
    }, [postId, frontId, backId, fetchScene]);

    const pair = useMemo(() => {
        if (!scene) return null;
        const byId = new Map((scene.regions || []).map((r) => [r.id, r]));
        const front = byId.get(frontId);
        const back = byId.get(backId);
        if (!front || !back) return null;
        return { front, back };
    }, [scene, frontId, backId]);

    // A region the segmenter drew but whose outline did not survive is still a region WITH a mask;
    // drawing its bounding box instead would be showing the estimate as though it were the
    // measurement. Either both outlines are here or this shows nothing.
    const drawable = !!pair
        && (pair.front.polygons || []).length > 0
        && (pair.back.polygons || []).length > 0;

    if (state === NO_GEOMETRY || (state === READY && !drawable)) {
        return <MasksAbsent reason={absenceReason(state, pair)} />;
    }
    if (state === UNREACHABLE) {
        return <MasksAbsent reason="the scene route did not answer, so the geometry could not be
            read. The numbers above are unaffected." />;
    }
    if (state === LOADING || !scene) {
        return <p className="cm-note">Reading the geometry…</p>;
    }

    const basis = proposal?.evidence?.basis || '';
    const regions = [pair.front, pair.back];

    return (
        <figure className="cm-figure"
                data-epistemic={proposal?.epistemic || 'unknown'}
                data-ledger={proposal?.ledger_status || 'proposed'}
                data-basis={basis || 'unknown'}>
            <div className="cm-stage">
                {scene.photo_url && (
                    <img
                        src={scene.photo_url} alt=""
                        onLoad={(e) => setNatural({
                            w: e.currentTarget.naturalWidth,
                            h: e.currentTarget.naturalHeight,
                        })} />
                )}
                {natural && (
                    <RegionOverlay
                        className="cm-svg"
                        natural={natural}
                        regions={regions}
                        viewMap="outline"
                        // The overlay's own attention vocabulary, used for its meaning: the front
                        // region is the figure, the one behind recedes.
                        litIds={new Set([pair.front.id])}
                        interactive={false} />
                )}
            </div>

            <figcaption className="cm-legend">
                <ul className="cm-roles">
                    <RoleRow role="in front" region={pair.front} />
                    <RoleRow role="behind" region={pair.back} />
                </ul>
                <p className="cm-status">
                    <span className="cm-badge" data-status={proposal?.epistemic || 'unknown'}>
                        {proposal?.epistemic || 'unknown'}
                    </span>
                    <span className="cm-badge" data-ledger={proposal?.ledger_status || 'proposed'}>
                        {proposal?.ledger_status || 'proposed'}
                    </span>
                    {basis && <span className="cm-basis">{basis} basis</span>}
                </p>
                <p className="cm-caption">
                    The outlines are the masks the segmenter drew, at the coordinates they were
                    measured in. Nothing here is accepted — deciding that is the step below.
                </p>
            </figcaption>
        </figure>
    );
}

function RoleRow({ role, region }) {
    return (
        <li className={`cm-role cm-role--${role.replace(/\s+/g, '-')}`}>
            <span className="cm-swatch" aria-hidden="true" />
            <span className="cm-role-name">{role}</span>
            <code>{region.id}</code>
            {region.label ? <em>{region.label}</em> : null}
            <span className="cm-maker" title={region.maker?.detail || ''}>
                {region.maker?.attributed
                    ? (region.maker.adapter || region.maker.model || region.maker.actor
                        || 'attributed')
                    : 'maker unknown'}
            </span>
        </li>
    );
}

function MasksAbsent({ reason }) {
    return (
        <p className="cm-note cm-note--absent">
            No geometry to show: {reason}
        </p>
    );
}

function absenceReason(state, pair) {
    if (state === NO_GEOMETRY) {
        return 'this proposal does not name two regions in a post, so there is nothing to look up.';
    }
    if (!pair) {
        return 'one of the two regions is not in this post any more — a proposal outlives the '
            + 'geometry it was measured on, and a shape drawn from the other one would be a guess.';
    }
    return 'the regions carry no mask outline. A bounding box drawn in their place would be an '
        + 'estimate shown where a measurement belongs.';
}

async function defaultFetchScene(postId) {
    const resp = await fetch(`${API_URL}/api/v1/scene/${postId}`);
    if (!resp.ok) throw new Error(`scene ${resp.status}`);
    return resp.json();
}
