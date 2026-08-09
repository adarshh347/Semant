import { useId, useState } from 'react';
import axios from 'axios';

import { API_URL } from '../config/api';

/**
 * The one uploader. Every surface that adds an image to the archive goes through this form.
 *
 * ## What HARNESS-003C repaired, and why it mattered
 *
 * The 002R rehearsal's sixth tree cause: this form called `onUploadSuccess()` **after a failed
 * request**, and called it with **nothing**. Both halves were load-bearing.
 *
 *   · The success callback ran in the `catch` path's continuation, so a failed upload closed the
 *     dialog, invalidated the posts cache and raised a green "Image added" toast. The only
 *     evidence anything had gone wrong was an `alert('Upload failed.')` the toast then talked
 *     over.
 *   · Calling it with no argument meant no caller could learn what had been created. An inquiry
 *     that wants to upload an image and immediately read it had nothing to select.
 *
 * Both routes already return the created documents — `POST /api/v1/posts/` is
 * `response_model=Post` and `/bulk-upload` is `List[Post]`, both 201 — so this needed no backend
 * change. The response was being thrown away.
 *
 * ## The contract now
 *
 *     onUploadSuccess(posts)   posts is ALWAYS an array, ALWAYS non-empty, and ONLY on 2xx
 *
 * Callers that ignore the argument are unaffected, which is the whole of `UploadDialog` and the
 * Gallery path through it. A caller that wants the posts reads them.
 *
 * A `semant:posts-created` event carries the same array to listeners that do not mount this form
 * — the inquiry workbench is one, and it lives in a different part of the shell. The event echoes
 * the `requestId` of the `semant:open-upload` that asked for it, so a surface can tell an upload
 * IT requested from one the person started somewhere else. Without that, opening the Archive's
 * own upload button while an inquiry is open would silently add images to the inquiry.
 *
 * ## No `alert()`
 *
 * A modal alert is not an error state: it blocks the page, it cannot be styled, it cannot be read
 * by anything that inspects the DOM, and it disappears on acknowledgement leaving the form looking
 * exactly as it did before. The error now stays in the form, beside the button that caused it,
 * with the files still selected so a retry costs nothing.
 */
function UploadForm({ onUploadSuccess, requestId = '' }) {
  const [files, setFiles] = useState([]);
  const [description, setDescription] = useState('');
  const [generalTagsStr, setGeneralTagsStr] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const ids = useId();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    if (files.length === 0) {
      setError('Choose at least one image first.');
      return;
    }

    const formData = new FormData();
    const bulk = files.length > 1;

    if (bulk) {
      for (let i = 0; i < files.length; i += 1) formData.append('files', files[i]);
    } else {
      formData.append('file', files[0]);
      formData.append('description', description);
      formData.append('general_tags_str', generalTagsStr);
    }

    setBusy(true);
    let created;
    try {
      const url = bulk
        ? `${API_URL}/api/v1/posts/bulk-upload`
        : `${API_URL}/api/v1/posts/`;
      const response = await axios.post(url, formData);
      // `List[Post]` from bulk, one `Post` from single. Normalised to an array so no caller has
      // to branch, and filtered so a malformed body cannot deliver an entry with no id — a
      // selection keyed on `undefined` is worse than a selection that came back short.
      const body = response?.data;
      created = (Array.isArray(body) ? body : [body]).filter((p) => p && p.id);
    } catch (err) {
      // THE FAILURE PATH ENDS HERE. It does not fall through to the success callback, and the
      // form keeps the person's files so a retry costs nothing.
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' && detail
        ? detail
        : (err?.message || 'The upload did not go through.'));
      setBusy(false);
      return;
    }
    setBusy(false);

    if (!created.length) {
      // A 2xx that carried no usable post is not a success this form can report. Saying so is
      // better than calling back with an empty array a caller would read as "nothing selected".
      setError('The upload returned no post. Nothing was added to your selection.');
      return;
    }

    setFiles([]);
    setDescription('');
    setGeneralTagsStr('');

    window.dispatchEvent(new CustomEvent('semant:posts-created', {
      detail: { posts: created, requestId },
    }));
    onUploadSuccess?.(created);
  };

  return (
    <div className="upload-form-container">
      {/* Heading omitted: the dialog already titles this ("Add to the archive"). */}
      <form onSubmit={handleSubmit} aria-label="Upload images">
        <div>
          <label htmlFor={`${ids}-files`}>Select Image(s):</label>
          <input
            id={`${ids}-files`}
            type="file"
            multiple
            disabled={busy}
            onChange={(e) => { setFiles([...e.target.files]); setError(''); }}
            required
          />
        </div>
        <div>
          <label htmlFor={`${ids}-desc`}>Description (for single upload only):</label>
          <input
            id={`${ids}-desc`}
            type="text"
            value={description}
            disabled={busy}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor={`${ids}-tags`}>General Tags (comma-separated, for single upload only):</label>
          <input
            id={`${ids}-tags`}
            type="text"
            value={generalTagsStr}
            disabled={busy}
            onChange={(e) => setGeneralTagsStr(e.target.value)}
            placeholder="e.g., nature,sky,mountain"
          />
        </div>

        {error ? (
          <p className="upload-error" role="alert" data-upload-error="true">{error}</p>
        ) : null}

        <button type="submit" disabled={busy}>
          {busy ? 'Uploading…' : 'Upload'}
        </button>
      </form>
    </div>
  );
}

export default UploadForm;
