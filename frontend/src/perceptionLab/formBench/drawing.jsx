import React from 'react';
import { FormSurface, renderView } from '../forms';

/**
 * PERCEPTUAL-FORMS-001H — drawing a derived payload with Lane E's renderers.
 *
 * SEPARATE FROM THE PANEL because a file that exports a component AND a helper cannot be fast
 * refreshed, and the split is honest anyway: `FormBench` decides what a person may ask for, this
 * decides what they are shown, and `thresholds.js` reads the scalars that decided it.
 */

/**
 * One of Lane E's renderers, and its refusal made visible when it cannot draw.
 *
 * Lane E's `assertLayer` throws for a drawing that does not say where it came from. Catching it
 * and PRINTING it is the honest response: a blank pane would let an undeclared drawing look like
 * an empty measurement, which is the one confusion this whole lane is arranged against.
 */
export default function SafeView({ form, view, payload, natural }) {
    let built;
    try {
        built = renderView(form, view, payload);
    } catch (cause) {
        return (
            <p className="fb-refused" role="note" data-refused="render">
                {view} cannot be drawn from this record: {cause?.message || String(cause)}
            </p>
        );
    }
    return (
        <FormSurface view={built.view} layers={built.layers} sides={built.sides}
            items={built.items} error={built.error} natural={natural} />
    );
}
