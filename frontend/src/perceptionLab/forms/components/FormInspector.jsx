import React from 'react';
import { form } from '../../contract/perceptionLabContract';
import { examinationOf } from '../formGeometry';
import { GEOMETRY_ARTIFACTS, resolvableIds } from '../fixtures/endpointGeometry';

/**
 * PERCEPTUAL-FORMS-001E — what is on screen, and where it came from.
 *
 * The legend describes each LAYER. This describes the RECORD: which of the nineteen forms it is,
 * what question that form answers, what it is permitted to claim, what it looked at, and — the
 * part that is easy to leave out — which of the references it makes can be followed and which
 * cannot.
 *
 * WHY THE LIMITS ARE ON SCREEN RATHER THAN IN A README. A person using this laboratory to judge a
 * renderer needs to know that `inst_piazza` is missing from the fixture set before they conclude
 * that the containment tree is broken. Putting that in a doc means they find it after they have
 * filed the bug.
 */

const Row = ({ label, children, k }) => (
    <>
        <dt data-inspect-key={k}>{label}</dt>
        <dd data-inspect-value={k}>{children}</dd>
    </>
);

export default function FormInspector({ formKey, payload, scenario, scenarioNote }) {
    const d = form(formKey);
    const looked = examinationOf(payload, formKey);

    return (
        <section className="pl-fm-panel" aria-label="The record" data-inspector={formKey}>
            <h3>The record</h3>
            <dl className="pl-fm-decl">
                <Row k="form" label="form">{d.key}</Row>
                <Row k="question" label="question">{d.question}</Row>
                <Row k="organ" label="organ">{d.organ}</Row>
                <Row k="variant" label="payload">{d.payload_variant}</Row>
                <Row k="artifact_kind" label="artifact kind">{d.artifact_kind}</Row>
                <Row k="scenario" label="scenario">
                    {scenario}
                    <span className="pl-fm-rowdetail">{scenarioNote}</span>
                </Row>
                {/* THE READINESS, said plainly. Sixteen of the nineteen forms have an empty
                    `produced_by_operations`: their payloads are frozen and nothing writes one
                    yet. A lab that showed them without saying so would imply a pipeline. */}
                <Row k="state" label="state">
                    <span className="pl-fm-state" data-state={d.state}>{d.state}</span>
                    <span className="pl-fm-rowdetail" data-produced-by={d.produced_by_operations.length}>
                        {d.produced_by_operations.length
                            ? `produced by ${d.produced_by_operations.join(', ')}`
                            : 'no operation produces this form yet — the payload is frozen and '
                              + 'reviewed a phase before anything computes it'}
                    </span>
                </Row>
                <Row k="ceiling" label="reaches at most">
                    {d.epistemic_ceiling}
                    <span className="pl-fm-rowdetail">
                        from {d.admissible_bases.join(', ')} · partitions{' '}
                        {d.admissible_partitions.join(', ')}
                    </span>
                </Row>
                {d.carries_hypothesis ? (
                    <Row k="hypothesis" label="carries a hypothesis">
                        yes — an artifact of this form may not be kept or promoted. Resolving it
                        produces a new artifact of a resolved form, and nothing here writes one.
                    </Row>
                ) : null}
                {looked ? (
                    /* Keyed by the field the CONTRACT names, not by a generic "examined" — so a
                       reader sees `pairs_examined` and can go and look it up. */
                    <Row k={looked.field} label={looked.label}>
                        {looked.members ? looked.members.join(', ') : String(looked.value)}
                        <span className="pl-fm-rowdetail" data-empty-means>
                            if this were empty it would mean: {looked.empty_means}
                        </span>
                    </Row>
                ) : null}
                <Row k="comparison" label="compared by">
                    {d.comparison_methods.join(', ')}
                </Row>
            </dl>

            <h4>What this fixture set can follow</h4>
            <p className="pl-fm-note" data-resolvable={resolvableIds().length}>
                Geometry is carried for {Object.keys(GEOMETRY_ARTIFACTS).join(' and ')} — that is{' '}
                {resolvableIds().join(', ')}. A reference to anything else resolves to nothing and
                says so on the layer. Aliasing one onto whichever mask is available would draw a
                shape nobody measured, at the exact pixel boundary of a real raster.
            </p>
        </section>
    );
}

/**
 * Lineage and revision identity for one drawn layer.
 *
 * `RevisionRef` is `InstanceRef` reaching one depth further — artifact, instance, revision — and
 * the third level is the one that goes wrong quietly. A relation measured at `geometry_rev 0` and
 * drawn against `geometry_rev 1` looks perfectly fine and describes geometry that is no longer
 * there. So the revision a layer CITES and the revision that was DRAWN are printed separately
 * whenever they differ.
 */
export function LayerLineage({ layer }) {
    if (!layer) {
        return (
            <section className="pl-fm-panel" aria-label="Lineage">
                <h3>Lineage</h3>
                <p className="pl-fm-note">
                    Select a layer in the legend to see what it cites.
                </p>
            </section>
        );
    }
    const s = layer.source || {};
    return (
        <section className="pl-fm-panel" aria-label="Lineage" data-lineage={layer.layer_id}>
            <h3>Lineage</h3>
            <dl className="pl-fm-decl">
                <Row k="layer" label="layer">{layer.layer_id}</Row>
                <Row k="form" label="from form">{layer.form}</Row>
                {s.artifact_id ? <Row k="artifact" label="artifact">{s.artifact_id}</Row> : null}
                {s.instance_id ? <Row k="instance" label="instance">{s.instance_id}</Row> : null}
                {s.geometry_rev !== undefined && s.geometry_rev !== null ? (
                    <Row k="geometry_rev" label="cited revision">
                        {s.geometry_rev}
                        {s.geometry_rev > 0 ? (
                            <span className="pl-fm-rowdetail" data-revision-gap="true">
                                drawn against revision 0, which is the only one this fixture set
                                carries — so what is on screen is not the geometry this claim was
                                measured against
                            </span>
                        ) : null}
                    </Row>
                ) : null}
                {s.region_id ? (
                    <Row k="region" label="canonical Region">
                        {s.region_id}
                        <span className="pl-fm-rowdetail">
                            a Semant record with a revision of its own. This laboratory is
                            fixture-only and does not reach it.
                        </span>
                    </Row>
                ) : null}
                {layer.hypothesis_id ? (
                    <Row k="conditioned" label="conditioned on">{layer.hypothesis_id}</Row>
                ) : null}
                {layer.part ? <Row k="part" label="partition part">{layer.part}</Row> : null}
                <Row k="evidence" label="evidence">{layer.evidence}</Row>
                {layer.raster ? (
                    <Row k="raster" label="measured on">
                        {layer.raster.h}×{layer.raster.w}
                        <span className="pl-fm-rowdetail">
                            the edge is drawn crisply and was not measured crisply
                        </span>
                    </Row>
                ) : null}
            </dl>
        </section>
    );
}
