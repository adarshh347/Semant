import React, { useRef, useState } from 'react';
import { EmptyState } from './Chips';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — choose a picture, or bring one.
 *
 * `UploadForm` is deliberately not embedded here. Its result contract cannot distinguish a stored
 * image from a request that came back 200 with an error body, and a laboratory built on that
 * opens sessions against images the store may not have. So this surface has one rule:
 *
 *     AN UPLOAD EITHER PRODUCES A SOURCE OR IT PRODUCES AN ERROR. There is no third state, no
 *     optimistic row, and no session opened on a source the client did not return.
 *
 * The client's `uploadSource` rejects on failure and `useLabSession` turns that into
 * `uploadError`; nothing here writes into the source list on its own.
 */
export default function SourcePicker({ sources, activeSourceId, onOpen, onUpload, uploadError,
    busy }) {
    const fileRef = useRef(null);
    const [chosen, setChosen] = useState(null);

    if (sources === null) {
        return (
            <section className="pl-panel" aria-label="Source">
                <div className="pl-panel-head"><h2 className="pl-panel-title">Source</h2></div>
                <p className="pl-panel-sub" role="status">Reading the available images…</p>
            </section>
        );
    }

    return (
        <section className="pl-panel" aria-label="Source">
            <div className="pl-panel-head">
                <h2 className="pl-panel-title">Source</h2>
            </div>
            <p className="pl-panel-sub">
                A picture, and its digest. Every run records the digest it started against.
            </p>

            {sources.length === 0 ? (
                <EmptyState
                    title="No images are listed"
                    hint="Upload one below. Nothing else on this page can run without a source." />
            ) : (
                <ul className="pl-sources">
                    {sources.map((s) => (
                        <li key={s.id}>
                            <button type="button" className="pl-source"
                                aria-pressed={activeSourceId === s.id}
                                data-source-id={s.id}
                                disabled={!!busy}
                                onClick={() => onOpen(s.id)}>
                                {s.photo_url
                                    ? <img src={s.photo_url} alt="" />
                                    : <span className="pl-source-blank" aria-hidden="true" />}
                                <span>
                                    <span className="pl-source-title">
                                        {s.title || 'untitled'}
                                    </span>
                                    {/* A LISTING HAS NOT LOOKED YET, and says so rather than
                                      * rendering the absence. The live backend returns null
                                      * dimensions and a null digest for a list — it would have to
                                      * download every image to fill them — and `{null}×{null}`
                                      * came out as a bare "×", which reads as a broken row rather
                                      * than as a fact about when the lab reads a picture. */}
                                    <span className="pl-source-note">
                                        {s.natural_width && s.natural_height
                                            ? `${s.natural_width}×${s.natural_height} · ${s.origin}`
                                            : `${s.origin} · not read yet`}
                                    </span>
                                    <span className="pl-source-note">
                                        {s.image_digest || 'digest on opening'}
                                    </span>
                                </span>
                            </button>
                        </li>
                    ))}
                </ul>
            )}

            <div className="pl-upload">
                <label className="pl-label" htmlFor="pl-file">Or upload an image</label>
                <input ref={fileRef} id="pl-file" className="pl-input" type="file"
                    accept="image/*"
                    onChange={(e) => setChosen(e.target.files?.[0] || null)} />
                <div className="pl-btnrow" style={undefined}>
                    <button type="button" className="pl-btn" disabled={!chosen || busy === 'uploading'}
                        onClick={async () => {
                            const source = await onUpload(chosen);
                            // Only a source the client actually returned opens a session.
                            if (source) { setChosen(null); onOpen(source.id); }
                        }}>
                        {busy === 'uploading' ? 'Uploading…' : 'Upload and open'}
                    </button>
                </div>
                {uploadError ? (
                    <p className="pl-error" role="alert">
                        <strong>The upload did not complete.</strong> {uploadError} Nothing was
                        opened, and this image is not in the list.
                    </p>
                ) : null}
            </div>
        </section>
    );
}
