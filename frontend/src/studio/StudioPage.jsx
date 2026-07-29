import React, { useCallback, useEffect, useRef, useState } from 'react';
import Manuscript from '../components/blocknote/Manuscript';
import { manuscriptService } from '../services/manuscriptService';
import {
  chapterScenes,
  totalWordCount,
  sceneCount,
  firstSceneId,
  applyChapterMove,
  applySceneMove,
} from './studioModel';
import './StudioPage.css';

/**
 * StudioPage — the Writing Studio (WS-0A · the sacred manuscript).
 *
 * A standalone writing tool built on the vision app's kernel: the manuscript is the
 * canon, and in this gate every write is an explicit author commit (no AI yet — the
 * orchestrating Studio arrives in WS-0B and will only ever *propose*). This surface
 * is the block editor, the chapter/scene hierarchy, version snapshots, and export.
 */

const SAVE_DEBOUNCE_MS = 900;

export default function StudioPage() {
  const [shelf, setShelf] = useState([]);
  const [manuscript, setManuscript] = useState(null);   // full: chapters + scene stubs
  const [activeSceneId, setActiveSceneId] = useState(null);
  const [activeScene, setActiveScene] = useState(null);  // full scene w/ blocks
  const [saveState, setSaveState] = useState('idle');    // idle | dirty | saving | saved
  const [versions, setVersions] = useState(null);        // null = panel closed
  const [exportText, setExportText] = useState(null);    // non-null = export modal open
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const pendingBlocks = useRef(null);
  const saveTimer = useRef(null);

  // --- shelf ---
  const loadShelf = useCallback(async () => {
    setLoading(true);
    try {
      const { manuscripts } = await manuscriptService.list();
      setShelf(manuscripts);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadShelf(); }, [loadShelf]);

  const refreshManuscript = useCallback(async (id) => {
    const ms = await manuscriptService.get(id);
    setManuscript(ms);
    return ms;
  }, []);

  async function openManuscript(id) {
    setError(null);
    try {
      const ms = await refreshManuscript(id);
      const first = firstSceneId(ms);
      if (first) await selectScene(first);
      else { setActiveSceneId(null); setActiveScene(null); }
    } catch (e) { setError(e.message); }
  }

  async function createManuscript() {
    const title = window.prompt('Title of the new manuscript', 'Untitled manuscript');
    if (title === null) return;
    try {
      const ms = await manuscriptService.create({ title: title || 'Untitled manuscript' });
      await loadShelf();
      await openManuscript(ms.id);
    } catch (e) { setError(e.message); }
  }

  function closeManuscript() {
    flushSave();
    setManuscript(null);
    setActiveSceneId(null);
    setActiveScene(null);
    setVersions(null);
    loadShelf();
  }

  // --- scene selection + save ---
  const selectScene = useCallback(async (sceneId) => {
    flushSave();
    setVersions(null);
    setActiveSceneId(sceneId);
    setActiveScene(null); // triggers loading state + editor remount
    try {
      const scene = await manuscriptService.getScene(sceneId);
      setActiveScene(scene);
      setSaveState('idle');
    } catch (e) { setError(e.message); }
  }, []);

  function flushSave() {
    if (saveTimer.current) { clearTimeout(saveTimer.current); saveTimer.current = null; }
    if (pendingBlocks.current && activeSceneId) {
      const blocks = pendingBlocks.current;
      pendingBlocks.current = null;
      manuscriptService.saveScene(activeSceneId, { blocks }).catch(() => {});
    }
  }

  const onEditorChange = useCallback((blocks) => {
    pendingBlocks.current = blocks;
    setSaveState('dirty');
    if (saveTimer.current) clearTimeout(saveTimer.current);
    const sceneId = activeSceneId;
    saveTimer.current = setTimeout(async () => {
      if (!pendingBlocks.current || !sceneId) return;
      const toSave = pendingBlocks.current;
      pendingBlocks.current = null;
      setSaveState('saving');
      try {
        const saved = await manuscriptService.saveScene(sceneId, { blocks: toSave });
        setSaveState('saved');
        // reflect the fresh word count in the tree + header without a full reload
        setManuscript((ms) => {
          if (!ms || !ms.scenes?.[sceneId]) return ms;
          return { ...ms, scenes: { ...ms.scenes, [sceneId]: { ...ms.scenes[sceneId], word_count: saved.word_count } } };
        });
      } catch (e) { setError(e.message); setSaveState('dirty'); }
    }, SAVE_DEBOUNCE_MS);
  }, [activeSceneId]);

  // flush on unmount
  useEffect(() => () => flushSave(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // --- structure edits ---
  async function addChapter() {
    const title = window.prompt('Chapter title', `Chapter ${(manuscript?.chapters?.length || 0) + 1}`);
    if (title === null) return;
    try { setManuscript(await manuscriptService.addChapter(manuscript.id, title || 'Untitled chapter')); }
    catch (e) { setError(e.message); }
  }

  async function addScene(chapterId) {
    const title = window.prompt('Scene title', 'Untitled scene');
    if (title === null) return;
    try {
      const scene = await manuscriptService.addScene(manuscript.id, chapterId, title || 'Untitled scene', []);
      await refreshManuscript(manuscript.id);
      await selectScene(scene.id);
    } catch (e) { setError(e.message); }
  }

  async function renameChapter(chapterId, current) {
    const title = window.prompt('Rename chapter', current);
    if (title === null || title === current) return;
    try { setManuscript(await manuscriptService.updateChapter(manuscript.id, chapterId, title)); }
    catch (e) { setError(e.message); }
  }

  async function deleteChapter(chapterId, title) {
    if (!window.confirm(`Delete "${title}" and all its scenes? This cannot be undone.`)) return;
    try {
      const ms = await manuscriptService.removeChapter(manuscript.id, chapterId);
      setManuscript(ms);
      if (activeSceneId && !ms.scenes?.[activeSceneId]) { setActiveSceneId(null); setActiveScene(null); }
    } catch (e) { setError(e.message); }
  }

  async function renameScene(sceneId, current) {
    const title = window.prompt('Rename scene', current);
    if (title === null || title === current) return;
    try {
      await manuscriptService.saveScene(sceneId, { title });
      await refreshManuscript(manuscript.id);
      if (sceneId === activeSceneId) setActiveScene((s) => (s ? { ...s, title } : s));
    } catch (e) { setError(e.message); }
  }

  async function deleteScene(sceneId, title) {
    if (!window.confirm(`Delete scene "${title}"? This cannot be undone.`)) return;
    try {
      const ms = await manuscriptService.removeScene(sceneId);
      setManuscript(ms);
      if (sceneId === activeSceneId) {
        const next = firstSceneId(ms);
        if (next) await selectScene(next); else { setActiveSceneId(null); setActiveScene(null); }
      }
    } catch (e) { setError(e.message); }
  }

  async function reorder(newChapters) {
    try { setManuscript(await manuscriptService.reorder(manuscript.id, newChapters)); }
    catch (e) { setError(e.message); }
  }

  async function editTitle() {
    const title = window.prompt('Manuscript title', manuscript.title);
    if (title === null || title === manuscript.title) return;
    try {
      const ms = await manuscriptService.update(manuscript.id, { title });
      setManuscript((m) => ({ ...m, title: ms.title }));
    } catch (e) { setError(e.message); }
  }

  // --- versions ---
  async function snapshot() {
    if (!activeSceneId) return;
    const label = window.prompt('Label this version (optional)', '');
    if (label === null) return;
    flushSave();
    try {
      await manuscriptService.snapshot(activeSceneId, label);
      await openVersions();
    } catch (e) { setError(e.message); }
  }

  async function openVersions() {
    if (!activeSceneId) return;
    try {
      const { versions: v } = await manuscriptService.listVersions(activeSceneId);
      setVersions(v);
    } catch (e) { setError(e.message); }
  }

  async function restore(versionId) {
    if (!window.confirm('Restore this version? Your current text is snapshotted first, so nothing is lost.')) return;
    try {
      const scene = await manuscriptService.restoreVersion(activeSceneId, versionId);
      setActiveScene(null);
      // remount the editor with the restored body
      setTimeout(() => setActiveScene(scene), 0);
      await refreshManuscript(manuscript.id);
      await openVersions();
    } catch (e) { setError(e.message); }
  }

  // --- export ---
  async function doExport() {
    flushSave();
    try {
      const res = await manuscriptService.export(manuscript.id);
      setExportText(res.content);
    } catch (e) { setError(e.message); }
  }

  function downloadExport() {
    const blob = new Blob([exportText], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(manuscript?.title || 'manuscript').replace(/[^\w-]+/g, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ============================ render ============================
  if (loading && !manuscript) {
    return <div className="studio studio--center"><p className="studio-dim">Opening the studio…</p></div>;
  }

  if (!manuscript) return <Shelf shelf={shelf} onOpen={openManuscript} onCreate={createManuscript} error={error} />;

  const words = totalWordCount(manuscript);
  const scenesTotal = sceneCount(manuscript);

  return (
    <div className="studio">
      {error && <div className="studio-error" onClick={() => setError(null)}>{error} · dismiss</div>}

      {/* ---- structure rail ---- */}
      <aside className="studio-rail">
        <button className="studio-back" onClick={closeManuscript}>← All manuscripts</button>
        <div className="studio-ms-head">
          <h1 className="studio-ms-title" onClick={editTitle} title="Rename">{manuscript.title}</h1>
          <div className="studio-ms-meta">{scenesTotal} scene{scenesTotal === 1 ? '' : 's'} · {words} words</div>
        </div>

        <div className="studio-tree">
          {(manuscript.chapters || []).length === 0 && (
            <p className="studio-dim studio-empty">No chapters yet. Add one to begin.</p>
          )}
          {(manuscript.chapters || []).map((ch, ci) => (
            <div className="studio-chapter" key={ch.id}>
              <div className="studio-chapter-head">
                <span className="studio-chapter-title" onClick={() => renameChapter(ch.id, ch.title)}>{ch.title}</span>
                <span className="studio-rowbtns">
                  <button title="Move up" disabled={ci === 0} onClick={() => reorder(applyChapterMove(manuscript.chapters, ci, -1))}>↑</button>
                  <button title="Move down" disabled={ci === manuscript.chapters.length - 1} onClick={() => reorder(applyChapterMove(manuscript.chapters, ci, 1))}>↓</button>
                  <button title="Delete chapter" onClick={() => deleteChapter(ch.id, ch.title)}>✕</button>
                </span>
              </div>
              <ul className="studio-scenes">
                {chapterScenes(manuscript, ch.id).map((sc, si) => (
                  <li key={sc.id} className={sc.id === activeSceneId ? 'is-active' : ''}>
                    <button className="studio-scene-btn" onClick={() => selectScene(sc.id)}>
                      <span className="studio-scene-title">{sc.title || 'Untitled scene'}</span>
                      <span className="studio-scene-wc">{sc.word_count || 0}</span>
                    </button>
                    <span className="studio-rowbtns studio-rowbtns--scene">
                      <button title="Move up" disabled={si === 0} onClick={() => reorder(applySceneMove(manuscript.chapters, ch.id, si, -1))}>↑</button>
                      <button title="Move down" disabled={si === (ch.scene_ids?.length || 0) - 1} onClick={() => reorder(applySceneMove(manuscript.chapters, ch.id, si, 1))}>↓</button>
                      <button title="Rename" onClick={() => renameScene(sc.id, sc.title)}>✎</button>
                      <button title="Delete" onClick={() => deleteScene(sc.id, sc.title)}>✕</button>
                    </span>
                  </li>
                ))}
                <li><button className="studio-add studio-add--scene" onClick={() => addScene(ch.id)}>+ Scene</button></li>
              </ul>
            </div>
          ))}
          <button className="studio-add" onClick={addChapter}>+ Chapter</button>
        </div>

        <p className="studio-creed">The manuscript is sacred. Every word here is yours — the orchestrating Studio arrives next, and will only ever propose.</p>
      </aside>

      {/* ---- editor pane ---- */}
      <main className="studio-main">
        <header className="studio-toolbar">
          <div className="studio-scene-name">{activeScene ? (activeScene.title || 'Untitled scene') : '—'}</div>
          <div className="studio-tools">
            <SaveBadge state={saveState} />
            <button className="studio-tbtn" disabled={!activeSceneId} onClick={snapshot}>Snapshot</button>
            <button className="studio-tbtn" disabled={!activeSceneId} onClick={() => (versions ? setVersions(null) : openVersions())}>Versions</button>
            <button className="studio-tbtn" onClick={doExport}>Export</button>
          </div>
        </header>

        <div className="studio-canvas">
          {activeSceneId && activeScene ? (
            <div className="studio-doc">
              {/* key by scene id so each scene seeds a fresh editor (Manuscript seeds once) */}
              <Manuscript key={activeScene.id} initialBlocks={activeScene.blocks || []} onChange={onEditorChange} />
            </div>
          ) : activeSceneId ? (
            <p className="studio-dim studio-center-note">Loading scene…</p>
          ) : (
            <p className="studio-dim studio-center-note">
              {scenesTotal === 0 ? 'Add a chapter and a scene in the rail to start writing.' : 'Select a scene to write.'}
            </p>
          )}
        </div>
      </main>

      {/* ---- versions drawer ---- */}
      {versions && (
        <aside className="studio-versions">
          <div className="studio-versions-head">
            <span>Versions</span>
            <button onClick={() => setVersions(null)}>✕</button>
          </div>
          {versions.length === 0 && <p className="studio-dim">No snapshots yet. Use “Snapshot” to freeze this scene.</p>}
          <ul>
            {versions.map((v) => (
              <li key={v.id}>
                <div className="studio-version-meta">
                  <span className="studio-version-label">{v.label || '(unlabelled)'}</span>
                  <span className="studio-version-wc">{v.word_count} words</span>
                </div>
                <div className="studio-version-time">{v.created_at ? new Date(v.created_at).toLocaleString() : ''}</div>
                <button className="studio-restore" onClick={() => restore(v.id)}>Restore</button>
              </li>
            ))}
          </ul>
        </aside>
      )}

      {/* ---- export modal ---- */}
      {exportText !== null && (
        <div className="studio-modal-backdrop" onClick={() => setExportText(null)}>
          <div className="studio-modal" onClick={(e) => e.stopPropagation()}>
            <div className="studio-modal-head">
              <span>Export · {manuscript.title}</span>
              <button onClick={() => setExportText(null)}>✕</button>
            </div>
            <textarea className="studio-export-text" readOnly value={exportText} />
            <div className="studio-modal-actions">
              <button onClick={() => navigator.clipboard?.writeText(exportText)}>Copy</button>
              <button className="studio-primary" onClick={downloadExport}>Download .md</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SaveBadge({ state }) {
  const map = {
    idle: ['', ''],
    dirty: ['Unsaved', 'is-dirty'],
    saving: ['Saving…', 'is-saving'],
    saved: ['Saved', 'is-saved'],
  };
  const [label, cls] = map[state] || ['', ''];
  if (!label) return <span className="studio-save-badge" />;
  return <span className={`studio-save-badge ${cls}`}>{label}</span>;
}

function Shelf({ shelf, onOpen, onCreate, error }) {
  return (
    <div className="studio studio--shelf">
      <div className="studio-shelf-inner">
        <header className="studio-shelf-head">
          <div>
            <h1>The Writing Studio</h1>
            <p className="studio-dim">Writing by orchestration. The manuscript is sacred; you commit every word.</p>
          </div>
          <button className="studio-primary" onClick={onCreate}>+ New manuscript</button>
        </header>
        {error && <div className="studio-error">{error}</div>}
        {shelf.length === 0 ? (
          <p className="studio-dim studio-shelf-empty">No manuscripts yet. Create your first to begin.</p>
        ) : (
          <ul className="studio-shelf-list">
            {shelf.map((m) => (
              <li key={m.id}>
                <button onClick={() => onOpen(m.id)}>
                  <span className="studio-shelf-title">{m.title}</span>
                  {m.synopsis && <span className="studio-shelf-syn">{m.synopsis}</span>}
                  <span className="studio-shelf-meta">{m.chapter_count} chapters · {m.scene_count} scenes</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
