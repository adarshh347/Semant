import { describe, expect, it } from 'vitest';
import { checkedFamilySlots, FAMILY_KEYS, FAMILY_SLOTS } from './registry';

describe('six fixed family slots', () => {
    const slots = () => FAMILY_KEYS.map((key) => FAMILY_SLOTS[key]);

    it('enables only slots with complete form and producer declarations', () => {
        for (const slot of slots()) {
            if (slot.available) {
                expect(slot.forms.length).toBeGreaterThan(0);
                expect(slot.operations.length).toBeGreaterThan(0);
            } else {
                expect(slot.forms).toEqual([]);
                expect(slot.operations).toEqual([]);
            }
        }
    });

    it('admits one complete fixture family without changing the central registry', () => {
        const replacement = { ...slots()[0], available: true, reason: 'FIXTURE only',
            views: ['colour'], promptIntents: ['show synthetic field'],
            forms: [{ key: 'colour.synthetic', label: 'Synthetic', quantity: 'relative signal',
                views: ['colour'] }],
            operations: [{ key: 'colour.synthetic', label: 'Synthetic',
                form_key: 'colour.synthetic', producer_key: 'colour.fixture', parameters: {} }] };
        const installed = checkedFamilySlots([replacement, ...slots().slice(1)]);
        expect(installed.colour.available).toBe(true);
        expect(FAMILY_SLOTS.colour.forms.some((form) => form.key === 'colour.synthetic')).toBe(false);
        expect(() => checkedFamilySlots([{ ...replacement,
            promptIntents: ['x'.repeat(161)] }, ...slots().slice(1)])).toThrow(/bounded prompt/);
    });
});
