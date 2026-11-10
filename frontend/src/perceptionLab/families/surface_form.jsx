import React from 'react';
import UnavailableFamily from './UnavailableFamily';
import SurfaceNormalPreview from './SurfaceNormalPreview';
import analyticalAxes from '../../../../contracts/perception-lab-families/surface_form-normal-fixture.v1.json';

const reason = 'No admitted direct surface-normal estimator. Metric3Dv2 Small checkpoint permission '
    + 'and Mac runtime are unverified; DSINE has restrictive research-use terms. '
    + 'Analytical normal readers are not a live producer.';

function Panel() {
    return <>
        <UnavailableFamily label="Surface form" reason={reason} />
        <section className="pl-panel" aria-label="Surface form admission gap">
            <p className="pl-panel-sub">Next step: resolve checkpoint permission, then validate a pinned
                direct normal estimator on this Mac under the shared model lease. No weights were
                downloaded or terms accepted. Brightness and depth gradients are not substitutes.</p>
            <details><summary>Inspect analytical direction encoding (FIXTURE only)</summary>
                <SurfaceNormalPreview data={analyticalAxes} />
            </details>
        </section>
    </>;
}

export const SLOT = Object.freeze({ family: 'surface_form', label: 'Surface form', available: false,
    reason, forms: [], operations: [], views: [], promptIntents: [],
    Panel });
