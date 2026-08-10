// PERCEPTUAL-ORGANS-002 Lane E — the states the responsive proof has to survive.
//
// THE SCENARIOS ARE THE POINT OF THE HARNESS. A harness that only showed a happy path would prove
// that a working laboratory fits in a phone, which is not in doubt and is not what the build is
// asking. These four are the states that are hard to render honestly when space runs out: they
// are the ones a designer under pressure collapses into each other, and every one of them means
// something different about whether an organ looked at the image.
//
// Separate module because `ResponsiveHarness.jsx` may only export components — a constant living
// beside a component breaks fast refresh, and the lint rule that says so is right.

import { defaultCapabilityStates } from './clients/fixtureClient';

export const HARNESS_SCENARIOS = Object.freeze([
    {
        key: 'dense',
        label: 'Densely populated',
        why: 'five instances, two of them near-duplicates. The case where a stage runs out of '
            + 'room and an inspector runs out of column.',
        options: {},
    },
    {
        key: 'empty',
        label: 'Nothing found',
        why: 'the organ looked and there was nothing of that kind. It must not read as a bug, '
            + 'and it must not read as `unavailable`.',
        options: {},
        scene: 'scene_absent',
    },
    {
        key: 'unavailable',
        label: 'Adapters not running here',
        why: 'the operations stay in the catalogue, disabled, carrying the reason. A control '
            + 'that vanished at 320px would teach nothing about the deployment.',
        options: {
            capabilityStates: defaultCapabilityStates({
                sam3_concept: 'unavailable',
                grounded_sam: 'unavailable',
                distance_transform: 'deferred',
            }),
        },
    },
    {
        key: 'failed',
        label: 'The adapter raised',
        why: 'no claim is made about the image at all, and the run has no end time. The hardest '
            + 'state to render as distinct from `empty`.',
        options: { failOperations: ['extent.find_all'] },
    },
]);
