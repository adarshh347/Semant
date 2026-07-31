import React, { useMemo } from 'react';
import ArticleView from '../article/ArticleView.jsx';
import fixture from '../article/articleFixture.js';

/**
 * DEV-ONLY harness for the perceptual article — CIRCUIT-003 M4 verification.
 *
 * The real article mounts over a `resolve_article()` payload fetched from a run. This harness
 * mounts the SAME `ArticleView` over an offline fixture: a real M3 draft (produced by the M3
 * composer and captured verbatim) joined to real geometry, with the source images generated as
 * data-URI canvases so nothing is fetched.
 *
 * It exists because the article is the one artifact in this stack whose correctness is partly
 * VISUAL — whether a percept lands on the part of the image it measured, whether the defect
 * channel is actually legible beside the prose rather than technically present. Those cannot be
 * asserted in a unit test, and mounting the whole backend to see them is a slower loop than the
 * question deserves.
 *
 * The fixture deliberately includes the failures, because they are the interesting part: one
 * section carries a relevance flag, one names an image it does not cite, one citation is
 * AMBIGUOUS and therefore refuses to draw, one claim is refused entirely and appears only as a
 * qualification. An article harness that only ever renders the happy path would tell you nothing
 * about the artifact's actual job.
 *
 * Not linked from any nav. Reachable at /lab/article.
 */
export default function ArticleLab() {
    const article = useMemo(() => fixture(), []);
    const onReopen = (target, citation) => {
        // The harness has no backend to reopen INTO, so it reports the resolved target rather
        // than navigating to a post that does not exist here. The production caller navigates.
        // eslint-disable-next-line no-console
        console.log('[M4] reopen-on-source →', target.href, citation.step_id);
        const el = document.getElementById('m4-reopen-readout');
        if (el) el.textContent = `reopen → ${target.href}  (${citation.step_id})`;
    };
    return (
        <div className="art-lab">
            <ArticleView article={article} onReopen={onReopen} />
            <div id="m4-reopen-readout" className="art-lab-readout" role="status" />
        </div>
    );
}
