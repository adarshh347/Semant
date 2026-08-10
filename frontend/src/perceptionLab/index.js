// PERCEPTUAL-ORGANS-002 Lane E — what Lane F imports.
//
// The lane owns `frontend/src/perceptionLab/` and mounts nothing. This is the whole public
// surface, so the integration diff at the route is one import and one element:
//
//     import PerceptionLab from '@/perceptionLab';
//     <Route path="/lab/perception" element={<PerceptionLab client={perceptionLabHttpClient} />} />
//
// `createFixtureClient` stays exported because the route is useful with it before the backend
// exists, and because the browser proof and the human rehearsal both need a deterministic wire.
// `assertClientShape` is exported so the integration suite can run the same check over the real
// client that this lane runs over the fake one — including the negative half, that no promotion
// path exists on it.

export { default } from './PerceptionLab';
export { default as PerceptionLab } from './PerceptionLab';

export { createFixtureClient, defaultCapabilityStates } from './clients/fixtureClient';
export {
    assertClientShape, assertNoPromotionSurface, assertUploadedSource,
    REQUIRED_CLIENT_METHODS, FORBIDDEN_CLIENT_METHODS,
} from './clients/labClient';

export { TARGET_WIDTHS, widthBand } from './useContainerWidth';
