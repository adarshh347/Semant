/**
 * studioModel — pure helpers for the Writing Studio structure (WS-0A).
 *
 * No React, no fetch, no DOM. These derive views over the manuscript shape the
 * backend returns ({ id, title, synopsis, chapters:[{id,title,scene_ids}], scenes:{id->stub} })
 * and compute reorder payloads for structure edits (move chapter/scene up or down).
 * Kept pure so the tree logic is unit-testable in isolation, per the repo's
 * workspace convention (a `.js` beside a `.test.js`).
 */

/** Ordered scene stubs for a chapter, skipping ids with no loaded stub. */
export function chapterScenes(manuscript, chapterId) {
  if (!manuscript) return [];
  const chapter = (manuscript.chapters || []).find((c) => c.id === chapterId);
  if (!chapter) return [];
  const scenes = manuscript.scenes || {};
  return (chapter.scene_ids || []).map((id) => scenes[id]).filter(Boolean);
}

/** Manuscript-wide word count, summed from the scene stubs. */
export function totalWordCount(manuscript) {
  const scenes = manuscript?.scenes || {};
  return Object.values(scenes).reduce((sum, s) => sum + (s.word_count || 0), 0);
}

/** Total scene count from the hierarchy (source of truth), not the stub map. */
export function sceneCount(manuscript) {
  return (manuscript?.chapters || []).reduce((n, c) => n + (c.scene_ids || []).length, 0);
}

/**
 * Flatten to reading order: [{ chapterId, chapterTitle, scene }]. Powers prev/next
 * navigation and "first scene" selection after load.
 */
export function flattenScenes(manuscript) {
  const scenes = manuscript?.scenes || {};
  const out = [];
  for (const c of manuscript?.chapters || []) {
    for (const sid of c.scene_ids || []) {
      const scene = scenes[sid];
      if (scene) out.push({ chapterId: c.id, chapterTitle: c.title, scene });
    }
  }
  return out;
}

/** The id of the first scene in reading order, or null. */
export function firstSceneId(manuscript) {
  const flat = flattenScenes(manuscript);
  return flat.length ? flat[0].scene.id : null;
}

/** Reduce chapters to the minimal outline the reorder endpoint accepts. */
export function buildOutline(chapters) {
  return (chapters || []).map((c) => ({
    id: c.id,
    title: c.title,
    scene_ids: [...(c.scene_ids || [])],
  }));
}

/** Move item at `index` by `delta` (±1), returning a NEW array. Out-of-range is a no-op. */
export function moveWithin(list, index, delta) {
  const arr = [...(list || [])];
  const to = index + delta;
  if (index < 0 || index >= arr.length || to < 0 || to >= arr.length) return arr;
  const [item] = arr.splice(index, 1);
  arr.splice(to, 0, item);
  return arr;
}

/** New chapters array with the chapter at `index` moved by `delta`. */
export function applyChapterMove(chapters, index, delta) {
  return buildOutline(moveWithin(chapters, index, delta));
}

/** New chapters array with a scene moved within its chapter by `delta`. */
export function applySceneMove(chapters, chapterId, sceneIndex, delta) {
  return buildOutline(chapters).map((c) =>
    c.id === chapterId ? { ...c, scene_ids: moveWithin(c.scene_ids, sceneIndex, delta) } : c,
  );
}
