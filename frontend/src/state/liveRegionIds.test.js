import { describe, it, expect } from 'vitest';
import { liveRegionIds } from './regionStore.js';

/**
 * CIRCUIT-001 P1B — the rule behind the fourth silent recall failure.
 *
 * A `/part` chip whose region no longer exists used to run the full "I am
 * showing you this" choreography — expand the panel, scroll the pane into view,
 * light the chip — and then dim EVERY region and light none. The surface pointed
 * confidently at nothing, and said nothing. `focusRegions` now asks this question
 * first and refuses the reference when the answer is empty.
 */
describe('liveRegionIds — a reference is only followed as far as it resolves', () => {
    const regions = [{ id: 'region_1' }, { id: 'region_2' }];

    it('refuses a wholly dead /part reference', () => {
        expect(liveRegionIds(['region_9'], regions)).toEqual([]);
    });

    it('still follows a lens that has lost only SOME of its parts', () => {
        // Withholding the whole citation would hide evidence that is still true —
        // a partly-degraded lens has something honest to show.
        expect(liveRegionIds(['region_1', 'gone'], regions)).toEqual(['region_1']);
    });

    it('follows everything when everything resolves', () => {
        expect(liveRegionIds(['region_1', 'region_2'], regions)).toEqual(['region_1', 'region_2']);
    });

    it('preserves the cited order, so the first live id is the one selected', () => {
        expect(liveRegionIds(['gone', 'region_2', 'region_1'], regions)).toEqual(['region_2', 'region_1']);
    });

    it('tolerates the empty and the malformed', () => {
        expect(liveRegionIds([], regions)).toEqual([]);
        expect(liveRegionIds(undefined, regions)).toEqual([]);
        expect(liveRegionIds([null, '', 'region_1'], regions)).toEqual(['region_1']);
        expect(liveRegionIds(['region_1'], [])).toEqual([]);
        expect(liveRegionIds(['region_1'], undefined)).toEqual([]);
    });
});
