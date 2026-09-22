import { SLOT as colour } from './colour';
import { SLOT as illumination } from './illumination';
import { SLOT as surfacePattern } from './surface_pattern';
import { SLOT as orientationFlow } from './orientation_flow';
import { SLOT as depth } from './depth';
import { SLOT as surfaceForm } from './surface_form';

export const FAMILY_KEYS = Object.freeze([
    'colour', 'illumination', 'surface_pattern', 'orientation_flow', 'depth', 'surface_form',
]);

export function checkedFamilySlots(slots = [colour, illumination, surfacePattern,
    orientationFlow, depth, surfaceForm]) {
    if (slots.length !== 6 || slots.some((slot, index) => slot.family !== FAMILY_KEYS[index])) {
        throw new Error('six fixed family slots must appear in registry order');
    }
    const forms = new Set();
    const operations = new Set();
    slots.forEach((slot) => {
        if (!slot.label || !slot.reason || typeof slot.Panel !== 'function'
            || typeof slot.available !== 'boolean' || !Array.isArray(slot.forms)
            || !Array.isArray(slot.operations) || !Array.isArray(slot.views)
            || !Array.isArray(slot.promptIntents)) {
            throw new Error(`malformed family slot ${slot.family}`);
        }
        if (!slot.available && (slot.forms.length || slot.operations.length)) {
            throw new Error(`unavailable family ${slot.family} declares live forms`);
        }
        if (slot.available && (!slot.forms.length || !slot.operations.length || !slot.views.length)) {
            throw new Error(`available family ${slot.family} has no complete panel contract`);
        }
        if (slot.promptIntents.some((intent) => typeof intent !== 'string'
            || !intent.trim() || intent.length > 160)) {
            throw new Error(`malformed bounded prompt intent in ${slot.family}`);
        }
        slot.forms.forEach((form) => {
            if (!form.key?.startsWith(`${slot.family}.`) || !form.label
                || !form.quantity || !Array.isArray(form.views) || !form.views.length
                || form.views.some((view) => !slot.views.includes(view)) || forms.has(form.key)) {
                throw new Error(`malformed or duplicate form ${form.key}`);
            }
            forms.add(form.key);
        });
        slot.operations.forEach((op) => {
            if (!op.key?.startsWith(`${slot.family}.`) || operations.has(op.key)
                || !forms.has(op.form_key) || !op.producer_key?.startsWith(`${slot.family}.`)
                || !op.label || !op.parameters || typeof op.parameters !== 'object') {
                throw new Error(`malformed or duplicate operation ${op.key}`);
            }
            operations.add(op.key);
        });
    });
    return Object.freeze(Object.fromEntries(slots.map((slot) => [slot.family, slot])));
}

export const FAMILY_SLOTS = checkedFamilySlots();
