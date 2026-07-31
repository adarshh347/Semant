import { describe, it, expect } from 'vitest';
import {
  chapterScenes,
  totalWordCount,
  sceneCount,
  flattenScenes,
  firstSceneId,
  buildOutline,
  moveWithin,
  applyChapterMove,
  applySceneMove,
} from './studioModel';

const MS = {
  id: 'ms_1',
  title: 'Work',
  chapters: [
    { id: 'ch_a', title: 'A', scene_ids: ['sc_1', 'sc_2'] },
    { id: 'ch_b', title: 'B', scene_ids: ['sc_3'] },
  ],
  scenes: {
    sc_1: { id: 'sc_1', title: 'One', word_count: 10 },
    sc_2: { id: 'sc_2', title: 'Two', word_count: 5 },
    sc_3: { id: 'sc_3', title: 'Three', word_count: 20 },
  },
};

describe('chapterScenes', () => {
  it('returns ordered stubs for a chapter', () => {
    expect(chapterScenes(MS, 'ch_a').map((s) => s.id)).toEqual(['sc_1', 'sc_2']);
  });
  it('skips scene ids with no loaded stub', () => {
    const ms = { ...MS, chapters: [{ id: 'ch_a', title: 'A', scene_ids: ['sc_1', 'ghost'] }] };
    expect(chapterScenes(ms, 'ch_a').map((s) => s.id)).toEqual(['sc_1']);
  });
  it('is safe on missing manuscript/chapter', () => {
    expect(chapterScenes(null, 'x')).toEqual([]);
    expect(chapterScenes(MS, 'nope')).toEqual([]);
  });
});

describe('counts', () => {
  it('totals word counts across scenes', () => {
    expect(totalWordCount(MS)).toBe(35);
    expect(totalWordCount(null)).toBe(0);
  });
  it('counts scenes from the hierarchy', () => {
    expect(sceneCount(MS)).toBe(3);
    expect(sceneCount({ chapters: [] })).toBe(0);
  });
});

describe('flattenScenes / firstSceneId', () => {
  it('flattens in reading order with chapter context', () => {
    const flat = flattenScenes(MS);
    expect(flat.map((f) => f.scene.id)).toEqual(['sc_1', 'sc_2', 'sc_3']);
    expect(flat[2].chapterTitle).toBe('B');
  });
  it('firstSceneId is the first scene in reading order', () => {
    expect(firstSceneId(MS)).toBe('sc_1');
    expect(firstSceneId({ chapters: [], scenes: {} })).toBeNull();
  });
});

describe('buildOutline', () => {
  it('reduces chapters to id/title/scene_ids and copies arrays', () => {
    const out = buildOutline(MS.chapters);
    expect(out).toEqual([
      { id: 'ch_a', title: 'A', scene_ids: ['sc_1', 'sc_2'] },
      { id: 'ch_b', title: 'B', scene_ids: ['sc_3'] },
    ]);
    // scene_ids must be a fresh array, not the original reference
    expect(out[0].scene_ids).not.toBe(MS.chapters[0].scene_ids);
  });
});

describe('moveWithin', () => {
  it('moves an item by delta, returning a new array', () => {
    const src = ['a', 'b', 'c'];
    expect(moveWithin(src, 0, 1)).toEqual(['b', 'a', 'c']);
    expect(moveWithin(src, 2, -1)).toEqual(['a', 'c', 'b']);
    expect(src).toEqual(['a', 'b', 'c']); // unmutated
  });
  it('is a no-op at the boundaries', () => {
    expect(moveWithin(['a', 'b'], 0, -1)).toEqual(['a', 'b']);
    expect(moveWithin(['a', 'b'], 1, 1)).toEqual(['a', 'b']);
  });
});

describe('applyChapterMove / applySceneMove', () => {
  it('moves a chapter down', () => {
    const res = applyChapterMove(MS.chapters, 0, 1);
    expect(res.map((c) => c.id)).toEqual(['ch_b', 'ch_a']);
  });
  it('moves a scene within its chapter only', () => {
    const res = applySceneMove(MS.chapters, 'ch_a', 0, 1);
    expect(res.find((c) => c.id === 'ch_a').scene_ids).toEqual(['sc_2', 'sc_1']);
    expect(res.find((c) => c.id === 'ch_b').scene_ids).toEqual(['sc_3']); // untouched
  });
});
