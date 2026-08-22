import React from 'react';
import FormRendererLab from '../perceptionLab/forms';

/**
 * PERCEPTUAL-FORMS-001H — every form, opened from a fixture, at `/lab/forms`.
 *
 * THE FIXTURE LEVEL, AND IT IS NOT A LESSER ONE. Sixteen of the nineteen forms cannot be produced
 * as artifacts in any deployment, and four of those cannot be produced at all — so for most of the
 * grammar a committed payload is the ONLY way a person can see what the form looks like before
 * deciding whether the shape is right. That is what this route is for, and it is why Lane E built
 * a laboratory that takes no client: there is nothing here to be live or stale about.
 *
 * SEPARATE FROM `/lab/perception` ON PURPOSE. That route is the live laboratory: a session, a
 * source, a ledger, and three levels of asking. This one has no session and no wire, and mixing
 * them would put a rendering of a committed payload one tab away from a rendering of a measurement
 * with nothing but a tab saying which. The live laboratory draws what it produced; this draws what
 * the contract froze.
 */
export default function FormRendererLabPage() {
    return (
        <main className="page">
            <FormRendererLab />
        </main>
    );
}
