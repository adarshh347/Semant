// PERCEPTUAL-FORMS-001E — what Lane H imports.
//
// The lane owns `frontend/src/perceptionLab/forms/` and mounts nothing. This is the whole public
// surface, so the integration diff at a route is one import and one element:
//
//     import FormRendererLab from '@/perceptionLab/forms';
//     <Route path="/lab/forms" element={<FormRendererLab />} />
//
// THERE IS NO CLIENT PROP, and that is not an omission. This laboratory renders committed payload
// fixtures and produces proposals that live in React state. Nothing under `forms/` imports a
// client, calls `fetch`, or touches storage — `toolRegistry.test.js` asserts that over the module
// graph as text, so the promise survives somebody adding a component in six weeks.
//
// WHAT LANE H WILL PROBABLY WANT BEYOND THE COMPONENT:
//
//   renderView / viewsFor   to drive the surface from its own state, if the route wants to put
//                           the form and view in the URL.
//   COVERAGE                the table of which projections each form declares and which view
//                           draws them. Useful in an integration test, and it is what a reviewer
//                           reads to see the lane is complete.
//   verifyRegistry          the same check the module runs at import, callable so a failure names
//                           itself in the integration suite rather than at a random import.
//   layer / assertLayer     so a renderer written outside this directory is held to the same gate.

export { default } from './FormRendererLab';
export { default as FormRendererLab } from './FormRendererLab';

// The registry and its gate.
export {
    VIEWS, COVERAGE, SURFACES, ALTERNATIVE_MODES, FORM_GROUPS,
    verifyRegistry, viewsFor, viewFor, defaultViewFor, renderView,
} from './rendererRegistry';

// The layer model — the declaration gate every drawing in this directory passes.
export {
    EVIDENCE, EVIDENCE_ORDER, EVIDENCE_TREATMENT, EVIDENCE_FOR_PARTITION, EVIDENCE_FOR_PART,
    COORDINATE_SYSTEMS, STAGE_SYSTEMS, PARTS,
    layer, assertLayer, absentLayer, legendFor, treatmentCollisions, evidenceSummary,
    isStageLayer, isDiagramLayer,
} from './layerModel';

// The fixtures, and the honest limits of what they can resolve.
export {
    FORM_PAYLOADS, SCENARIOS, SCENARIO_NOTE, FIXTURE_SOURCE, scenariosFor, payloadFor,
} from './fixtures/formFixtures';
export {
    GEOMETRY_ARTIFACTS, resolveEndpoint, resolvePair, resolvableIds,
} from './fixtures/endpointGeometry';

// The tools. Every one produces a proposal stamped `writes: 'nothing'`.
export {
    TOOL_BEHAVIOUR, VERDICTS, VERDICT_NOTE, toolsFor, proposal, isVerdict, groupProposals,
} from './toolRegistry';

// The components, for a route that wants to compose them differently.
export { default as FormStage } from './components/FormStage';
export { default as FormDiagram } from './components/FormDiagram';
export { default as FormSurface } from './components/FormSurface';
export { default as LayerLegend, Measurements } from './components/LayerLegend';
export { default as FormInspector, LayerLineage } from './components/FormInspector';
export { default as ToolTray } from './components/ToolTray';

// The responsive proof, as a mountable component. It needs no backend and no props.
export { default as FormHarness } from './FormHarness';
export { HARNESS_CASES } from './harnessCases';
