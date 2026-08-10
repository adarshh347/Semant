import React, { useMemo, useRef, useState } from 'react';
import useLabSession from './useLabSession';
import useContainerWidth from './useContainerWidth';
import SourcePicker from './components/SourcePicker';
import OrganCatalogue from './components/OrganCatalogue';
import ModeControls from './components/ModeControls';
import DirectControls from './components/DirectControls';
import PromptConversation from './components/PromptConversation';
import PlanPreview from './components/PlanPreview';
import RunStream from './components/RunStream';
import ArtifactInspector from './components/ArtifactInspector';
import ExtentStage from './components/ExtentStage';
import ExtentReadout from './components/ExtentReadout';
import TopologyStage from './components/TopologyStage';
import RelationReadout from './components/RelationReadout';
import ReviewTray from './components/ReviewTray';
import HistoryPanel from './components/HistoryPanel';
import ExportBar from './components/ExportBar';
import Ledger from './components/Ledger';
import { EmptyState } from './components/Chips';
import { inputRef } from './records';
import './perceptionLab.css';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the Perception Lab shell.
 *
 * One prop: a client (see `clients/labClient.js`). Lane F mounts this at `/lab/perception` and
 * passes an HTTP client; every test in this lane passes a fixture one. Nothing below this file
 * knows what a URL is.
 *
 * WHAT THE SHELL ITSELF IS RESPONSIBLE FOR, and it is only these:
 *
 *   1. the identity line — which organ, which scope, which arm, and WHICH WIRE. `clientIdentity`
 *      says what this page is talking to; the LIVE/REPLAY/FIXTURE badge on a run comes from the
 *      run and is rendered next to the run, because those are two different questions and a page
 *      that answered them with one badge would be lying about one of them;
 *   2. the container band, which drives the whole responsive layout off one attribute;
 *   3. wiring the panels to the one state hook.
 *
 * It renders no measurement and decides no status.
 */
export default function PerceptionLab({ client, initialOrgan = 'extent',
    initialMode = 'isolation', now = () => new Date().toISOString() }) {
    const rootRef = useRef(null);
    const stageRef = useRef(null);
    const { band, width } = useContainerWidth(rootRef);
    const [arm, setArm] = useState('direct');
    const [comparisonRunId, setComparisonRunId] = useState(null);
    const lab = useLabSession(client, { initialOrgan, initialMode });

    const source = useMemo(
        () => (lab.sources || []).find((s) => s.id === lab.sourceId) || null,
        [lab.sources, lab.sourceId]);

    /**
     * The extent set on the stage, and the one it is being compared against.
     *
     * `stageArtifact` follows the ACTIVE artifact when that artifact is an extent set, and
     * otherwise falls back to the last extent set in the ledger — because activating a topology
     * relation should not blank the picture the relation is about. `comparisonArtifact` is the
     * previous extent set from a DIFFERENT run, which is what makes the repeat metrics a
     * statement about stability rather than about one answer read twice.
     */
    const extentSets = useMemo(
        () => lab.ledger.filter((a) => a.identity.artifact_kind === 'extent_set'),
        [lab.ledger]);

    /**
     * The topology artifact on the stage.
     *
     * It follows the ACTIVE artifact only. A relation set is a specific answer to a specific
     * question, and falling back to "the most recent one" the way the extent stage does would put
     * a picture of one measurement under the heading of another.
     */
    const topologyArtifact = lab.active
        && ['topology_relation_set', 'negative_space_field'].includes(
            lab.active.identity.artifact_kind)
        ? lab.active : null;
    const stageArtifact = lab.active?.identity.artifact_kind === 'extent_set'
        ? lab.active : (extentSets[extentSets.length - 1] || null);
    /**
     * The comparison side.
     *
     * A run chosen explicitly in the history wins. Otherwise the most recent extent set from a
     * DIFFERENT run stands in — which is what makes the repeat metrics a statement about
     * stability rather than about one answer read twice. Choosing it in the history is the
     * stronger form: it says which two answers a person meant to put beside each other.
     */
    const comparisonArtifact = useMemo(() => {
        if (!stageArtifact) return null;
        if (comparisonRunId) {
            return extentSets.find((a) => a.identity.run_id === comparisonRunId
                && a.identity.artifact_id !== stageArtifact.identity.artifact_id) || null;
        }
        return [...extentSets].reverse().find(
            (a) => a.identity.artifact_id !== stageArtifact.identity.artifact_id
                && a.identity.run_id !== stageArtifact.identity.run_id) || null;
    }, [extentSets, stageArtifact, comparisonRunId]);

    /**
     * A stage gesture becomes a PROPOSAL, never a dispatch.
     *
     * Both of these go through `planDirectly`, which is the same call the Direct controls make
     * and therefore the same four gates. A refinement that reached the runner from a pointer
     * event would be a control doing something a prompt is refused.
     */
    const proposeRefine = (mode, { points, box, instanceId }) => lab.planDirectly(
        'extent.refine',
        { mode, ...(points.length ? { points } : {}), ...(box ? { box } : {}) },
        [inputRef('base', stageArtifact.identity.artifact_id, { instance_id: instanceId })]);

    const proposeDraw = (stroke) => lab.planDirectly(
        'extent.draw', { tool: 'polygon', polygon: stroke }, []);

    /**
     * Reopen an earlier run.
     *
     * NOTHING RUNS. The artifacts are already in the ledger and this makes them active and
     * selected again — which is deliberately a different act from Replay, and a different button.
     * Replay writes a new run record; reopening writes nothing at all, because reading the history
     * must not rewrite it.
     */
    const reopenRun = (run) => {
        const ids = run.artifact_ids;
        if (!ids.length) return;
        lab.select(ids, ids[ids.length - 1]);
    };

    const capabilitySummary = useMemo(() => {
        const values = Object.values(lab.capabilities);
        const off = values.filter((v) => v === 'unavailable').length;
        if (!values.length) return 'adapter states not yet read';
        return off
            ? `${values.length - off} of ${values.length} adapters available here`
            : `all ${values.length} adapters available here`;
    }, [lab.capabilities]);

    return (
        <div className="pl" ref={rootRef} data-w={band} data-organ={lab.organ}
            data-mode={lab.mode} data-arm={arm} data-client={lab.clientIdentity}>
            <header className="pl-bar">
                <span className="pl-kicker">Perception laboratory</span>
                <h1 className="pl-title">Extent &amp; Topology</h1>
                <span className="pl-bar-spacer" />
                <span className="pl-chip" data-client-identity={lab.clientIdentity}
                    title="what this page is talking to. The badge on a run says where that run's
                        answer came from, and they are different questions.">
                    client: {lab.clientIdentity}
                </span>
                <span className="pl-chip" title="read from the backend, never guessed here">
                    {capabilitySummary}
                </span>
                {width ? (
                    <span className="pl-chip" data-band={band} title="the width of this container,
                        which is what the layout responds to">
                        {Math.round(width)}px · {band}
                    </span>
                ) : null}
            </header>

            {lab.error ? (
                <p className="pl-error" role="alert">
                    Could not finish {lab.error.what}: {lab.error.message}. Nothing on this page
                    has been changed by the attempt.
                </p>
            ) : null}

            <div className="pl-body">
                <div className="pl-rail">
                    <SourcePicker
                        sources={lab.sources}
                        activeSourceId={lab.sourceId}
                        onOpen={lab.openSession}
                        onUpload={lab.uploadSource}
                        uploadError={lab.uploadError}
                        busy={lab.busy} />
                    <OrganCatalogue
                        selected={lab.organ}
                        onSelect={lab.setOrgan}
                        capabilities={lab.capabilities} />
                </div>

                <div className="pl-main">
                    <ModeControls
                        mode={lab.mode}
                        arm={arm}
                        organ={lab.organ}
                        onMode={lab.setMode}
                        onArm={setArm} />
                    {!lab.session ? (
                        <section className="pl-panel" aria-label="Stage">
                            <EmptyState
                                title="No session is open"
                                hint="Choose a source on the left. A session records the image
                                    digest it was opened against, so every run can say whether
                                    the ground moved under it." />
                        </section>
                    ) : (
                        <>
                            {topologyArtifact ? (
                                <TopologyStage
                                    artifact={topologyArtifact}
                                    source={source}
                                    session={lab.session}
                                    byId={lab.byId}
                                    stageRef={stageRef}
                                    focusedRelationId={lab.focus.relationId}
                                    onFocusRelation={(relationId) => lab.setFocus(
                                        (f) => ({ ...f, relationId }))} />
                            ) : null}
                            {!topologyArtifact && (lab.organ === 'extent' || stageArtifact) ? (
                                <ExtentStage
                                    artifact={stageArtifact}
                                    source={source}
                                    session={lab.session}
                                    focusedInstanceId={lab.focus.instanceId}
                                    comparisonArtifact={comparisonArtifact}
                                    onFocusInstance={(instanceId) => lab.setFocus(
                                        (f) => ({ ...f, instanceId }))}
                                    onRefine={proposeRefine}
                                    onDraw={proposeDraw}
                                    stageRef={stageRef}
                                    busy={lab.busy} />
                            ) : null}
                            {arm === 'direct' ? (
                                <DirectControls
                                    organ={lab.organ}
                                    mode={lab.mode}
                                    capabilities={lab.capabilities}
                                    selectedIds={lab.selectedIds}
                                    ledger={lab.ledger}
                                    onPropose={lab.planDirectly}
                                    busy={lab.busy} />
                            ) : (
                                <PromptConversation
                                    organ={lab.organ}
                                    turns={lab.session.prompt_turns}
                                    plans={lab.plans}
                                    selectedIds={lab.selectedIds}
                                    activeId={lab.activeId}
                                    byId={lab.byId}
                                    onAsk={lab.planFromText}
                                    busy={lab.busy} />
                            )}
                            <PlanPreview
                                plan={lab.plan}
                                onRun={lab.runPlan}
                                onReplay={lab.runs.length
                                    ? () => lab.replayRun(lab.runs[lab.runs.length - 1].run_id)
                                    : null}
                                canRunLive={lab.clientIdentity === 'LIVE'}
                                busy={lab.busy} />
                            <RunStream
                                run={lab.run}
                                plan={lab.plan}
                                onReplay={lab.replayRun}
                                busy={lab.busy} />
                        </>
                    )}
                </div>

                <div className="pl-inspector">
                    {lab.session ? (
                        <>
                            <Ledger
                                ledger={lab.ledger}
                                selectedIds={lab.selectedIds}
                                activeId={lab.activeId}
                                reviewsFor={lab.reviewsFor}
                                onToggleSelect={lab.toggleSelected}
                                onActivate={lab.setActiveId} />
                            <ArtifactInspector
                                artifact={lab.active}
                                reviews={lab.active
                                    ? lab.reviewsFor(lab.active.identity.artifact_id) : []}
                                focusedInstanceId={lab.focus.instanceId}
                                onFocusInstance={(instanceId) => lab.setFocus(
                                    (f) => ({ ...f, instanceId }))} />
                            {topologyArtifact ? (
                                <RelationReadout
                                    artifact={topologyArtifact}
                                    byId={lab.byId}
                                    focusedRelationId={lab.focus.relationId}
                                    onFocusRelation={(relationId) => lab.setFocus(
                                        (f) => ({ ...f, relationId }))} />
                            ) : null}
                            {stageArtifact ? (
                                <ExtentReadout
                                    artifact={stageArtifact}
                                    comparisonArtifact={comparisonArtifact}
                                    byId={lab.byId}
                                    focusedInstanceId={lab.focus.instanceId}
                                    onFocusInstance={(instanceId) => lab.setFocus(
                                        (f) => ({ ...f, instanceId }))} />
                            ) : null}
                            <ReviewTray
                                artifact={lab.active}
                                reviews={lab.active
                                    ? lab.reviewsFor(lab.active.identity.artifact_id) : []}
                                onReview={lab.review}
                                onLifecycle={lab.setLifecycle}
                                busy={lab.busy} />
                            <HistoryPanel
                                session={lab.session}
                                runs={lab.runs}
                                plans={lab.plans}
                                byId={lab.byId}
                                comparisonRunId={comparisonRunId}
                                onReopen={reopenRun}
                                onReplay={lab.replayRun}
                                onCompare={setComparisonRunId}
                                busy={lab.busy} />
                            <ExportBar
                                session={lab.session}
                                plans={lab.plans}
                                runs={lab.runs}
                                artifacts={lab.ledger}
                                reviews={lab.reviews}
                                run={lab.run}
                                artifact={lab.active}
                                clientIdentity={lab.clientIdentity}
                                stageRef={stageRef}
                                now={now} />
                        </>
                    ) : null}
                </div>
            </div>
        </div>
    );
}
