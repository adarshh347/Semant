// PERCEPTUAL-FORMS-001E — the layer, and the six things it is not allowed to leave unsaid.
//
// THE PROBLEM THIS MODULE EXISTS TO MAKE STRUCTURAL.
//
// A renderer lab draws nineteen different kinds of answer on one stage. Some of those answers are
// measurements of this image. Some are arithmetic performed in this browser a moment ago. Some are
// assertions about pixels nobody has ever seen — the legs behind the table. Some are one of
// several readings held at once, none chosen.
//
// Those four things can be drawn with the same path element. That is the whole danger. A hard mask
// and an inferred completion are both a closed ring with a fill, and if the lab renders them the
// same way then every question this laboratory was built to ask has already been answered wrongly,
// silently, before anybody looked.
//
// So a LAYER is the unit here, not a shape. A layer is a drawing PLUS its declaration, and the
// declaration is not optional prose in a tooltip — `assertLayer` throws. A renderer that forgets
// to say where a drawing came from cannot render at all. That is deliberately harsher than a
// lint rule: the failure mode being prevented is invisible by construction, so the check has to
// be one that cannot be passed by accident.
//
// THE SIX DECLARATIONS, each of which is a specific way to mislead if omitted:
//
//   form + source        which of the nineteen forms this came from, and which record. Without
//                        it, two views of two artifacts on one stage become one picture.
//   evidence             measured · derived · inferred · hypothetical · absent. The axis above.
//   coordinate_system    image_normalized · raster_cells · diagram · none. A graph node is NOT
//                        at a pixel, and a stage that draws it over the image says it is.
//   basis                what the claim was computed FROM. `box` and `mask` are not the same
//                        shape and are routinely the same rectangle on screen.
//   hypothesis           which alternative this belongs to, where there is more than one.
//   threshold            the number that turned a scalar field into a binary one. A wash with
//                        no threshold is a field; a mask with no threshold shown is a lie.
//
// PART is the seventh and it is narrower: `visible` / `inferred` / `unknown`, from the contract's
// `partition_parts`. It is carried separately from `evidence` because a partition payload
// declares it per region, and the two must agree — `assertLayer` checks that they do.
//
// PURE MODULE. No DOM, no React, no fetch. Every renderer in this directory produces these and
// nothing else, which is why the stage can enforce the rules in one place.

/**
 * The four kinds of claim a drawing can be, plus the fifth that is not a drawing.
 *
 * These are NOT the contract's `epistemic_status`. Status is how strong a claim is; evidence is
 * what KIND of act produced the thing on screen. A `measured` status can arrive here as `derived`
 * evidence — the browser tracing a boundary from a measured mask produces a drawing the producer
 * never made, of a measurement the producer did make, and a person needs both facts.
 */
export const EVIDENCE = Object.freeze([
    'measured',      // the producer looked at this image and reported this geometry
    'derived',       // computed in THIS browser from records already made
    'inferred',      // asserted where nothing was seen
    'hypothetical',  // one of several readings, none chosen
    'absent',        // could not be drawn, and says why
]);

/** Ordered weakest-to-strongest, for the legend and for the "never indistinguishable" test. */
export const EVIDENCE_ORDER = Object.freeze(['absent', 'hypothetical', 'inferred', 'derived', 'measured']);

export const COORDINATE_SYSTEMS = Object.freeze([
    // [0,1] over the source image. The stage letterboxes it exactly as the image letterboxes.
    'image_normalized',
    // A field of h×w cells over the image. Normalized like the above, but the CELL SIZE is a real
    // fact about the measurement's resolution and is carried so the legend can state it.
    'raster_cells',
    // Abstract diagram space, [0,1]×[0,1], with no relation to any pixel. Trees and graphs live
    // here. The stage refuses these; `FormDiagram` refuses everything else.
    'diagram',
    // The layer carries no geometry at all — a measurement rendered as text, or an absence.
    'none',
]);

export const STAGE_SYSTEMS = Object.freeze(['image_normalized', 'raster_cells']);

/** The contract's `partition_parts`, repeated here only as the set this module range-checks. */
export const PARTS = Object.freeze(['visible', 'inferred', 'unknown']);

/**
 * What each evidence class is permitted to look like.
 *
 * THREE REDUNDANT CHANNELS, and this table is why the "colour is not the sole distinction" test
 * can be written at all. Every layer differs from every other in its STROKE DASH and its FILL
 * PATTERN and its printed WORD, before colour is considered. Remove the stylesheet's colours
 * entirely and a person can still tell an inferred completion from a measured mask.
 *
 * `dash` is in natural-pixel units at the stage's viewBox scale and is applied with
 * `vectorEffect: non-scaling-stroke`, so it reads the same at every zoom.
 */
export const EVIDENCE_TREATMENT = Object.freeze({
    measured: Object.freeze({
        dash: null, pattern: null, word: 'measured', fillOpacity: 0.16, strokeWidth: 2,
        sentence: 'the producer looked at this image and reported this geometry',
    }),
    derived: Object.freeze({
        dash: '6 4', pattern: 'dots', word: 'derived here', fillOpacity: 0.10, strokeWidth: 1.5,
        sentence: 'computed in this browser from records already made — not the measurement',
    }),
    inferred: Object.freeze({
        dash: '10 6', pattern: 'hatch-45', word: 'inferred', fillOpacity: 0.12, strokeWidth: 2,
        sentence: 'asserted where nothing was seen; never visible, never measured',
    }),
    hypothetical: Object.freeze({
        dash: '2 5', pattern: 'hatch-135', word: 'hypothesis', fillOpacity: 0.10, strokeWidth: 2,
        sentence: 'one of several readings the picture supports, and none of them is chosen',
    }),
    absent: Object.freeze({
        dash: null, pattern: null, word: 'not drawn', fillOpacity: 0, strokeWidth: 0,
        sentence: 'there is nothing to draw, and the reason is stated rather than left blank',
    }),
});

/**
 * The evidence class implied by a contract partition.
 *
 * This is the ONE place the mapping lives. `interpretive_grouping` maps to `hypothetical` rather
 * than `derived` because a grouping is a reading — the members are measured and the decision that
 * they go together is not, and a person looking at a fused tree needs the dotted treatment even
 * though every fragment in it was measured exactly.
 */
export const EVIDENCE_FOR_PARTITION = Object.freeze({
    visible_measured: 'measured',
    exact_derivation: 'derived',
    interpretive_grouping: 'hypothetical',
    inferred_completion: 'inferred',
    unresolved_alternative: 'hypothetical',
});

/** The evidence class implied by a partition PART, which is the finer of the two. */
export const EVIDENCE_FOR_PART = Object.freeze({
    visible: 'measured',
    inferred: 'inferred',
    unknown: 'hypothetical',
});

const isFiniteNumber = (v) => typeof v === 'number' && Number.isFinite(v);

/**
 * Build a layer, and refuse to build a dishonest one.
 *
 * Throws rather than returning a flawed object, because the caller of this function is always a
 * renderer in this directory and the only way to reach the throw is to have written one wrongly.
 * A layer that reached the stage with a missing declaration would be a drawing nobody can
 * describe, which is exactly the state this module exists to make unreachable.
 */
export function layer(spec) {
    const out = {
        layer_id: spec.layer_id,
        label: spec.label,
        // ── the declaration ───────────────────────────────────────────────
        form: spec.form ?? null,
        source: spec.source ?? null,               // {artifact_id, instance_id, revision, …}
        evidence: spec.evidence,
        coordinate_system: spec.coordinate_system,
        basis: spec.basis ?? null,
        epistemic_status: spec.epistemic_status ?? null,
        hypothesis_id: spec.hypothesis_id ?? null,
        part: spec.part ?? null,
        threshold: spec.threshold ?? null,          // {value, source, applied}
        binarized: spec.binarized === true,
        raster: spec.raster ?? null,                // {h, w} where the geometry was measured
        calibration: spec.calibration ?? null,
        // ── the drawing ───────────────────────────────────────────────────
        draw: spec.draw ?? { kind: 'none' },
        projection_kind: spec.projection_kind ?? null,
        // ── the sentence a person reads ───────────────────────────────────
        note: spec.note ?? null,
        why_absent: spec.why_absent ?? null,
        measurements: spec.measurements ?? null,
    };
    assertLayer(out);
    return Object.freeze(out);
}

/**
 * The gate. Every sentence here names a specific misreading it prevents.
 *
 * Note what is NOT checked: nothing about whether the geometry is *correct*. This module cannot
 * know that and does not pretend to. It checks only that the drawing is accompanied by the facts
 * needed to read it, which is the part a renderer can get wrong through omission.
 */
export function assertLayer(l) {
    const at = l?.layer_id ? `layer "${l.layer_id}"` : 'an unnamed layer';
    if (!l || typeof l !== 'object') throw new Error('a layer must be an object');
    if (!l.layer_id) throw new Error('a layer must carry a layer_id; two layers that cannot be '
        + 'told apart cannot be individually turned off, cited, or disbelieved');
    if (!EVIDENCE.includes(l.evidence)) {
        throw new Error(`${at} declares evidence "${l.evidence}". It must be one of `
            + `${EVIDENCE.join(', ')} — a drawing whose kind of claim is unstated is drawn as if `
            + 'it were a measurement, which is the one thing this lab may never do');
    }
    if (!COORDINATE_SYSTEMS.includes(l.coordinate_system)) {
        throw new Error(`${at} declares coordinate system "${l.coordinate_system}". It must be one `
            + `of ${COORDINATE_SYSTEMS.join(', ')} — a graph node is not at a pixel and a stage `
            + 'that letterboxes one as though it were puts it somewhere real and wrong');
    }
    if (l.evidence === 'absent') {
        if (!l.why_absent) {
            throw new Error(`${at} is absent and says nothing about why. An empty stage that does `
                + 'not explain itself reads as a bug, and a person debugs their selection instead '
                + 'of reading the finding');
        }
        if (l.draw && l.draw.kind !== 'none') {
            throw new Error(`${at} is absent and carries a drawing. It is one or the other`);
        }
    }
    // A HYPOTHESIS MUST BE NAMEABLE, because the point of drawing one is that a person can accept
    // it, reject it, or tell it from its rivals — and none of those is possible for a shape with
    // no id.
    //
    // The `unknown` part of a partition is the one exception, and it is a real distinction rather
    // than a let-out. `unknown` does not compete with anything: it is the region whose status was
    // not determined, and there is no rival reading to choose it over. It still gets the dotted
    // treatment, because it is still not something that was seen.
    if (l.evidence === 'hypothetical' && !l.hypothesis_id && l.part !== 'unknown') {
        throw new Error(`${at} is a hypothesis and names no hypothesis_id. An alternative that `
            + 'cannot be named cannot be accepted, rejected, or told from its rivals');
    }
    if (l.binarized) {
        if (!l.threshold || !isFiniteNumber(l.threshold.value)) {
            throw new Error(`${at} turns a scalar field into a binary one and does not carry the `
                + 'threshold that did it. The threshold IS the claim — without it a wash of '
                + 'graded confidence has been redrawn as a hard mask nobody measured');
        }
        if (!l.threshold.source) {
            throw new Error(`${at} carries a threshold value with no source. A number the producer `
                + 'recorded and a number a person dragged to are different claims');
        }
    }
    if (l.part !== null && !PARTS.includes(l.part)) {
        throw new Error(`${at} declares part "${l.part}"; the contract's parts are ${PARTS.join(', ')}`);
    }
    if (l.part && EVIDENCE_FOR_PART[l.part] !== l.evidence && l.evidence !== 'absent') {
        throw new Error(`${at} is the "${l.part}" part of a partition and is drawn as `
            + `"${l.evidence}". The partition already said what kind of claim this region is; `
            + `drawing it as anything else contradicts the record it came from`);
    }
    if (l.coordinate_system === 'raster_cells' && !l.raster) {
        throw new Error(`${at} is a cell field and does not carry its raster shape. A 4×4 field `
            + 'drawn without saying it is 4×4 looks like a smooth measurement of a whole image');
    }
    if (l.coordinate_system === 'none' && l.draw && l.draw.kind !== 'none'
        && l.draw.kind !== 'text') {
        throw new Error(`${at} has no coordinate system and yet carries a "${l.draw.kind}" drawing`);
    }
    return l;
}

/** A layer that could not be drawn. The only constructor for an honest empty stage. */
export const absentLayer = ({ layer_id, label, form = null, source = null, why }) => layer({
    layer_id, label, form, source,
    evidence: 'absent', coordinate_system: 'none', why_absent: why,
});

/** Whether this layer belongs on the image stage rather than in a diagram panel. */
export const isStageLayer = (l) => STAGE_SYSTEMS.includes(l.coordinate_system);
export const isDiagramLayer = (l) => l.coordinate_system === 'diagram';

/**
 * The legend rows for a set of layers — one per layer, in drawing order, never collapsed.
 *
 * DELIBERATELY NOT DEDUPLICATED BY EVIDENCE CLASS. A legend that says "measured · inferred" once
 * for eleven layers tells a person that both kinds are present and not WHICH shape is which, and
 * "which shape is which" is the entire question. One row per layer, or the legend is decoration.
 */
export function legendFor(layers = []) {
    return layers.map((l) => ({
        layer_id: l.layer_id,
        label: l.label,
        evidence: l.evidence,
        word: EVIDENCE_TREATMENT[l.evidence].word,
        sentence: EVIDENCE_TREATMENT[l.evidence].sentence,
        form: l.form,
        source: l.source,
        basis: l.basis,
        epistemic_status: l.epistemic_status,
        coordinate_system: l.coordinate_system,
        raster: l.raster,
        hypothesis_id: l.hypothesis_id,
        part: l.part,
        threshold: l.threshold,
        binarized: l.binarized,
        calibration: l.calibration,
        note: l.note,
        why_absent: l.why_absent,
    }));
}

/**
 * Do any two layers in this set render identically?
 *
 * The invariant the build states as "never make inferred geometry visually indistinguishable from
 * visible geometry", written as a function so a test can assert it over every view of every form
 * rather than over the two examples somebody remembered to check.
 *
 * Two layers COLLIDE when they carry different evidence and the same treatment. Because the
 * treatment table is keyed by evidence, a collision can only happen if somebody edits that table
 * to give two classes the same dash and pattern — which is exactly the regression worth failing on.
 */
export function treatmentCollisions(layers = []) {
    const seen = new Map();
    const collisions = [];
    for (const l of layers) {
        const t = EVIDENCE_TREATMENT[l.evidence];
        const key = `${t.dash}|${t.pattern}|${t.word}`;
        const prior = seen.get(key);
        if (prior && prior !== l.evidence) {
            collisions.push({ a: prior, b: l.evidence, treatment: key });
        }
        seen.set(key, l.evidence);
    }
    return collisions;
}

/** Every distinct evidence class present, strongest last, for the stage's summary line. */
export function evidenceSummary(layers = []) {
    const present = new Set(layers.map((l) => l.evidence));
    return EVIDENCE_ORDER.filter((e) => present.has(e));
}
