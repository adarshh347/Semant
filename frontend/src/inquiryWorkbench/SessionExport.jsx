import React, { useState } from 'react';

/**
 * INQUIRY WORKBENCH — take the session away and read it somewhere else.
 *
 * ## What is exported, and what deliberately is not
 *
 * **The backend's own response body, verbatim.** Not the normalised view this surface renders
 * from. The normalised object contains fields this client DERIVED — `running`, `underperformed`,
 * `simulated`, counts inferred from ref arrays — and a file that mixed those in with the server's
 * fields would let a reader attribute a client-side inference to the backend. Someone diffing an
 * export against an API response is doing it precisely because they suspect one of them; giving
 * them a third thing helps nobody.
 *
 * So: the raw body, and a filename carrying the session id and revision, because two exports of
 * the same session at different revisions are different documents and should not share a name.
 *
 * ## Quarantined model text
 *
 * If the backend rejected a model's raw output and kept it aside, it travels under
 * `quarantined_text` and renders here under its own heading, never inside the graph. Prose the
 * schema refused is not an artifact of the inquiry; it is the evidence of a stage that failed, and
 * putting it anywhere near the reading would launder it back into the answer.
 */

function copy(value) {
    const text = String(value ?? '');
    if (navigator?.clipboard?.writeText) return navigator.clipboard.writeText(text);
    return Promise.reject(new Error('no clipboard'));
}

export function CopyButton({ value, label = 'Copy', className = 'iw-copy' }) {
    const [state, setState] = useState('');    // '' | 'ok' | 'fail'
    return (
        <button
            type="button"
            className={className}
            data-copy-value={value}
            onClick={() => copy(value).then(
                () => setState('ok'),
                // A clipboard that refused is reported. Saying "Copied" after a rejected write is
                // a small lie that costs a person the thing they were about to paste.
                () => setState('fail'),
            )}
        >
            {state === 'ok' ? 'Copied' : null}
            {state === 'fail' ? 'Could not copy' : null}
            {state === '' ? label : null}
        </button>
    );
}

/** `download` is injectable so the whole control is testable without a DOM download. */
export default function SessionExport({ session, download = null }) {
    if (!session) return null;

    // The server's body, exactly as it arrived. `raw` is captured by `normalizeSession` for this.
    const body = session.raw && typeof session.raw === 'object' ? session.raw : {};
    const json = JSON.stringify(body, null, 2);
    const name = `inquiry-${session.session_id || 'session'}`
        + `${session.revision === null ? '' : `-rev${session.revision}`}.json`;

    const quarantined = String(body.quarantined_text || body.raw_model_text || '');

    const save = () => {
        if (download) { download(name, json); return; }
        const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.click();
        URL.revokeObjectURL(url);
    };

    return (
        <section className="iw-panel iw-export" aria-label="Export and inspect">
            <h2 className="iw-h2">Take it away</h2>

            <div className="iw-export-row">
                <button
                    type="button"
                    className="iw-export-btn"
                    data-download-session="true"
                    data-filename={name}
                    onClick={save}
                >
                    Download session JSON
                </button>
                <span className="iw-quiet">
                    The backend&apos;s own response, verbatim — not this page&apos;s reading of it.
                    Nothing this client derived is mixed in.
                </span>
            </div>

            <dl className="iw-export-ids">
                <div>
                    <dt>session</dt>
                    <dd>
                        <code>{session.session_id || '—'}</code>
                        <CopyButton value={session.session_id} label="Copy id" />
                    </dd>
                </div>
                <div>
                    <dt>inquiry</dt>
                    <dd>
                        <code>{session.inquiry_id || '—'}</code>
                        <CopyButton value={session.inquiry_id} label="Copy id" />
                    </dd>
                </div>
                <div>
                    <dt>graph</dt>
                    <dd>
                        <code>{session.graph.graph_id || '—'}</code>
                        <CopyButton value={session.graph.graph_id} label="Copy id" />
                    </dd>
                </div>
                <div>
                    <dt>revision</dt>
                    <dd>{session.revision === null ? '—' : session.revision}</dd>
                </div>
                <div>
                    <dt>schema</dt>
                    <dd><code>{session.schema_version || '—'}</code></dd>
                </div>
            </dl>

            {quarantined ? (
                <div className="iw-quarantine" data-quarantine="true">
                    <h3 className="iw-h3">Quarantined model text</h3>
                    <p className="iw-quiet">
                        The backend refused this output and kept it aside. It is not part of the
                        graph, it supports nothing, and it is shown here rather than near the
                        reading so it cannot be mistaken for something the inquiry accepted.
                    </p>
                    <pre className="iw-quarantine-text">{quarantined}</pre>
                </div>
            ) : null}
        </section>
    );
}
