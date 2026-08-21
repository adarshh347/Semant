// PERCEPTUAL-FORMS-001E — what this fixture set can actually resolve, and what it cannot.
//
// TWELVE OF THE NINETEEN FORMS CARRY NO GEOMETRY. They carry REFERENCES: `topology.pair_relation`
// names two instances and reports a containment fraction; `extent.hierarchy` names four nodes and
// reports occupancy; `topology.adjacency_graph` names three piers. Where the shape of any of
// those lives is somebody else's record.
//
// That is a correct design — the contract keeps geometry out of the projection block precisely so
// a drawing cannot be smuggled into a measurement — and it means a renderer for those forms is
// only as good as its resolver. So this module is the resolver, and the interesting thing about
// it is how much it CANNOT do.
//
// The committed payload set carries TWO collections with geometry in them, and the other
// payloads cite them by name: `extent.hard_mask`'s instances are cited as `art_extent_1#inst_1`
// and `#inst_2`, and `extent.fragment_set`'s pieces are cited as `art_fragments_1#frag_1..3`.
// The instance ids match exactly, which is not a coincidence — the nineteen payloads describe one
// scene. So this module declares those two artifact ids ONCE, here, and resolves through them.
//
// Every other endpoint in every other payload — `inst_tree`, `inst_facade`, `inst_piazza`,
// `inst_pier_1`, `art_extent_crowd#inst_1`, `reg_7` — names something no committed fixture
// contains, and stays unresolved.
//
// THE TEMPTING FIX IS THE ONE THIS FILE REFUSES. It would be easy to alias `inst_piazza` onto
// whichever mask is handy, and every view in the lab would fill with shapes. Those shapes would
// be a fiction, and a fiction drawn at the exact pixel boundary of a real raster is a more
// convincing fiction than an empty stage will ever be. So unresolved is unresolved: the renderer
// gets `{resolved: false, why}` and draws the sentence.
//
// The mix is the point. Contact locus resolves both endpoints and draws. Intersection resolves
// neither and refuses. Clearance resolves one of two and says which. A person using this lab sees
// all three states in one sitting, which is what a manual-testing instrument is for.

import { FORM_PAYLOADS } from './formFixtures';
import { ringsFromRle, ringsFromBox } from '../formGeometry';
import { decodeRle } from '../../geometry/maskRaster';

/**
 * The two artifact ids the committed payloads give geometry for, declared once.
 *
 * These names are an assertion this module makes and nothing else in the repo does: the payloads
 * are payloads, not artifacts, so none of them carries an id of its own. The ids chosen are the
 * ones the OTHER payloads already cite, which is what makes the set cohere rather than what makes
 * it convenient — `extent.fused_hypothesis` names `art_fragments_1#frag_1`, and the fragment
 * payload contains `frag_1`.
 */
export const GEOMETRY_ARTIFACTS = Object.freeze({
    art_extent_1: { form: 'extent.hard_mask', collection: 'instances', idField: 'instance_id' },
    art_fragments_1: { form: 'extent.fragment_set', collection: 'fragments', idField: 'fragment_id' },
});

/** Kept for the readouts that name the principal one. */
export const GEOMETRY_ARTIFACT_ID = 'art_extent_1';

const build = () => {
    const table = new Map();
    for (const [artifactId, spec] of Object.entries(GEOMETRY_ARTIFACTS)) {
        for (const member of FORM_PAYLOADS[spec.form][spec.collection]) {
            const memberId = member[spec.idField];
            const fromMask = ringsFromRle(member.mask_rle);
            const fromBox = ringsFromBox(member.box);
            table.set(`${artifactId}#${memberId}`, {
                resolved: true,
                artifact_id: artifactId,
                instance_id: memberId,
                // The BASIS is what the geometry actually IS, not what the citing record hoped
                // for. `inst_2` carries a box and no mask: a relation claiming a mask basis over
                // it is making a claim its own endpoint cannot support, and the renderer says so.
                basis: fromMask ? 'mask' : 'box',
                rings: (fromMask || fromBox)?.rings ?? [],
                raster: fromMask?.raster ?? null,
                centroid: (fromMask || fromBox)?.centroid ?? null,
                box: member.box ?? fromMask?.box ?? null,
                mask: decodeRle(member.mask_rle),
                naming: member.naming ?? null,
                area: member.area ?? null,
                source_form: spec.form,
            });
        }
    }
    return table;
};

const TABLE = build();

const label = (ref) => `${ref?.artifact_id ?? '?'}#${ref?.instance_id ?? '?'}`;

/**
 * Resolve one endpoint reference to geometry, or say plainly that it does not.
 *
 * Mirrors the shape `topologyView.resolveEndpoint` returns for the live instrument, so the two
 * halves of this laboratory report a dangling reference the same way. A `region_id` reference
 * resolves to nothing here for a different and equally honest reason: canonical Regions live in
 * Semant, and this lab is fixture-only and does not reach them.
 */
export function resolveEndpoint(ref) {
    if (!ref) return { resolved: false, id: '?', why: 'the record names no endpoint at all' };
    if (ref.region_id && !ref.artifact_id) {
        return {
            resolved: false,
            id: ref.region_id,
            why: `${ref.region_id} is a canonical Region. This laboratory is fixture-only and `
                + 'does not reach into Semant, so its geometry is not on this page',
        };
    }
    const id = label(ref);
    const found = TABLE.get(id);
    if (found) {
        return {
            ...found,
            id,
            // A citing record may declare a geometry revision. The fixture set carries revision
            // 0 only, so a reference to a later one resolves to geometry that is NOT what the
            // record measured — which has to be said rather than quietly satisfied.
            stale: typeof ref.geometry_rev === 'number' && ref.geometry_rev > 0,
            cited_geometry_rev: ref.geometry_rev ?? null,
        };
    }
    return {
        resolved: false,
        id,
        why: `no committed fixture carries ${id}. The payload set gives geometry for `
            + `${Object.keys(GEOMETRY_ARTIFACTS).join(' and ')} only, and aliasing this reference `
            + 'onto a mask that happens to be available would draw a shape nobody measured',
    };
}

/** Resolve a pair, and report which half failed — "one of two" is a different finding from none. */
export function resolvePair(source, target) {
    const a = resolveEndpoint(source);
    const b = resolveEndpoint(target);
    return {
        source: a,
        target: b,
        both: a.resolved && b.resolved,
        neither: !a.resolved && !b.resolved,
        // Two masks on different rasters cannot be combined, and resampling one to make a picture
        // appear would be this lab deciding what the measurement was.
        same_raster: !!(a.raster && b.raster && a.raster.h === b.raster.h && a.raster.w === b.raster.w),
        why: a.resolved && b.resolved ? null
            : [!a.resolved && a.why, !b.resolved && b.why].filter(Boolean).join('; '),
    };
}

/** Every id this fixture set can resolve — for the inspector, and for the tests. */
export const resolvableIds = () => [...TABLE.keys()];
export const resolvedCount = () => TABLE.size;
