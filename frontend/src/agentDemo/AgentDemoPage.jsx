import React, { useCallback, useEffect, useRef, useState } from 'react';
import RunEntry from './RunEntry.jsx';
import RunProgress from './RunProgress.jsx';
import ProductionPanel from './ProductionPanel.jsx';
import QuestionFlow from './QuestionFlow.jsx';
import RunOutput from './RunOutput.jsx';
import { createRunClient } from './runClient.js';
import { API_URL } from '../config/api';
import './agentDemo.css';

/**
 * AGENT-DEMO — the surface: pick images, ask a question, watch it think, see what it produced.
 *
 * ITS OWN ROUTE AND SHELL, deliberately not folded into `/differential`. The Differential is the
 * manual instrument — a curator marking one image by hand — and it has diverged from this on
 * purpose. This is the opposite entry: raw images and a sentence, with the machine doing the
 * looking. Sharing a shell would force one of them to pretend to be the other.
 *
 * The client is injectable so the whole surface can be driven by `createMockRunClient` in tests
 * and by the real routes in the browser, with no branch inside any component. That is also the
 * Lane A swap point: when the run routes land, nothing here changes.
 *
 * STATE IS A SINGLE RunView. Every panel is a pure function of it, so there is no second copy of
 * the run's truth to fall out of step with the first — the same one-source-of-truth discipline
 * PROV-001 settled on for provenance, applied to the surface's own state.
 */
export default function AgentDemoPage({ client = null, posts: injectedPosts = null }) {
    const runClient = useRef(client || createRunClient()).current;

    const [posts, setPosts] = useState(injectedPosts || []);
    const [view, setView] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const unwatch = useRef(null);

    // The corpus to choose from. Failure is soft on purpose: the tag field is an independent way
    // to name a corpus, so a gallery that will not load must not block starting a run.
    useEffect(() => {
        if (injectedPosts) return undefined;
        let live = true;
        (async () => {
            try {
                const res = await fetch(`${API_URL}/api/v1/posts?page=1&limit=24`);
                if (!res.ok) return;
                const data = await res.json();
                if (live) setPosts(Array.isArray(data?.posts) ? data.posts : []);
            } catch { /* the tag field still works */ }
        })();
        return () => { live = false; };
    }, [injectedPosts]);

    useEffect(() => () => { unwatch.current?.(); }, []);

    const listen = useCallback((runId) => {
        unwatch.current?.();
        unwatch.current = runClient.watch(runId, {
            onView: setView,
            onError: (e) => setError(e?.message || 'Lost the run.'),
        });
    }, [runClient]);

    const start = useCallback(async (input) => {
        setBusy(true);
        setError('');
        try {
            const runId = await runClient.start(input);
            if (!runId) throw new Error('The run did not come back with an id.');
            // Seed from the first read so the shell switches over immediately rather than
            // sitting on the form until the first delta arrives.
            try { setView(await runClient.get(runId)); } catch { /* the watch will fill it */ }
            listen(runId);
        } catch (e) {
            setError(e?.message || 'Could not start the run.');
        } finally {
            setBusy(false);
        }
    }, [runClient, listen]);

    const answer = useCallback(async (text) => {
        if (!view?.run_id) return;
        setBusy(true);
        setError('');
        try {
            const next = await runClient.answer(view.run_id, text);
            setView(next);
            // The SAME run, resumed — so pick the watch back up rather than starting anything.
            listen(view.run_id);
        } catch (e) {
            setError(e?.message || 'The answer did not go through.');
        } finally {
            setBusy(false);
        }
    }, [runClient, view, listen]);

    const reset = () => {
        unwatch.current?.();
        unwatch.current = null;
        setView(null);
        setError('');
    };

    if (!view) {
        return (
            <main className="ad-shell">
                <RunEntry posts={posts} busy={busy} error={error} onStart={start} />
            </main>
        );
    }

    return (
        <main className="ad-shell ad-shell--run">
            <div className="ad-col ad-col--run">
                <RunProgress view={view} />
                <QuestionFlow
                    question={view.question}
                    busy={busy}
                    error={error}
                    onAnswer={answer}
                />
                <ProductionPanel records={view.production_records} />
                <button type="button" className="ad-again" onClick={reset}>
                    Ask something else
                </button>
            </div>
            <div className="ad-col ad-col--out">
                <RunOutput view={view} />
            </div>
        </main>
    );
}
