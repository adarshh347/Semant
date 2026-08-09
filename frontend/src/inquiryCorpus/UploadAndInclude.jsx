import React, { useCallback, useEffect, useRef, useState } from 'react';
import { normalizePost } from './corpusSource';

/**
 * INQUIRY CORPUS — upload an image and read it in the same breath.
 *
 * ## Why an event round trip rather than a second uploader
 *
 * The shell already owns exactly one upload surface: `UploadDialog` mounts at the app root and
 * opens on a `semant:open-upload` window event, which is how ⌘K and the Archive's button both
 * reach it. Building a second uploader here would mean a second multipart contract, a second set
 * of Cloudinary assumptions and a second thing to fix. So this button opens the shared dialog and
 * waits for the form to say what it created.
 *
 * ## The requestId, and the bug it prevents
 *
 * `semant:posts-created` is a broadcast — every listener in the shell hears it. Without a
 * correlation id, a person who opened the Archive's own Upload button while an inquiry draft was
 * on screen would find those images silently added to their inquiry. The id is minted here, sent
 * out on `semant:open-upload`, echoed back by `UploadForm`, and anything that does not match is
 * ignored.
 *
 * ## The draft is never at risk
 *
 * Nothing here navigates, and nothing here remounts the entry form: the dialog is a sibling at the
 * app root. The prompt, the mode and every previously selected image are untouched by construction
 * rather than by being restored afterwards.
 */
let seq = 0;
const nextRequestId = () => `iq_upload_${(seq += 1)}_${Math.floor(Date.now() % 1e7).toString(36)}`;

export default function UploadAndInclude({ onUploaded, openUpload = null }) {
    const [waiting, setWaiting] = useState(false);
    const [note, setNote] = useState('');
    const requestId = useRef('');

    useEffect(() => {
        const onCreated = (event) => {
            const detail = event?.detail || {};
            // Not ours — someone else's upload, and it stays someone else's.
            if (!requestId.current || detail.requestId !== requestId.current) return;
            const posts = (Array.isArray(detail.posts) ? detail.posts : [])
                .filter((p) => p && p.id)
                .map(normalizePost);
            requestId.current = '';
            setWaiting(false);
            if (!posts.length) {
                setNote('The upload finished but returned no post to include.');
                return;
            }
            setNote(`Added ${posts.length} image${posts.length === 1 ? '' : 's'} to this inquiry.`);
            onUploaded?.(posts);
        };
        window.addEventListener('semant:posts-created', onCreated);
        return () => window.removeEventListener('semant:posts-created', onCreated);
    }, [onUploaded]);

    const open = useCallback(() => {
        const id = nextRequestId();
        requestId.current = id;
        setWaiting(true);
        setNote('');
        if (openUpload) openUpload(id);
        else {
            window.dispatchEvent(new CustomEvent('semant:open-upload', { detail: { requestId: id } }));
        }
    }, [openUpload]);

    return (
        <div className="ic-upload">
            <button
                type="button"
                className="ic-upload-btn"
                data-upload-and-include="true"
                onClick={open}
            >
                Upload and include
            </button>
            {waiting ? (
                <span className="ic-upload-note" role="status">
                    Waiting for the upload dialog…
                </span>
            ) : null}
            {note ? (
                <span className="ic-upload-note" role="status" data-upload-note="true">{note}</span>
            ) : null}
            <span className="ic-upload-hint">
                The dialog opens over this page. Your question and the images you have already
                chosen stay where they are.
            </span>
        </div>
    );
}
