import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it } from 'vitest';
import { createFixtureClient } from './clients/fixtureClient';
import useLabSession from './useLabSession';

it('a late source listing cannot erase the source verified while reopening', async () => {
    const client = createFixtureClient();
    const listing = await client.listSources();
    const source = listing.sources[0];
    const session = await client.createSession({ source_id: source.id,
        selected_organ: 'extent', mode: 'isolation' });
    const history = await client.history({ session_id: session.session_id });
    history.session.source.post_id = source.id;
    client.history = async () => history;
    client.openSource = async () => ({ source: { ...source, photo_url: '/verified-source.png',
        image_digest: history.session.source.image_digest } });
    let finishListing;
    client.listSources = () => new Promise((resolve) => { finishListing = resolve; });
    let lab;
    function Probe() {
        lab = useLabSession(client);
        return <pre>{JSON.stringify(lab.sources)}</pre>;
    }
    const element = document.createElement('div');
    const root = createRoot(element);
    try {
        await act(async () => { root.render(<Probe />); });
        await act(async () => { await lab.resumeSession(session.session_id); });
        await act(async () => { finishListing({ sources: [{ ...source, image_digest: null }] }); });
        expect(element.textContent).toContain('/verified-source.png');
        expect(lab.sources.filter((item) => item.id === source.id)).toHaveLength(1);
    } finally {
        await act(async () => root.unmount());
    }
});
