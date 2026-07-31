import { API_URL } from '../config/api';

// Writing Studio · WS-0A — the sacred manuscript client. Mirrors the repo's
// per-domain service pattern (raw fetch, throw on !ok). The X-API-Key header, when
// the backend requires one, is installed globally by config/api.js.
const BASE = `${API_URL}/api/v1/manuscript`;

async function json(res, action) {
  if (!res.ok) throw new Error(`Failed to ${action} (${res.status})`);
  return res.json();
}

const post = (url, body) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });

const patch = (url, body) =>
  fetch(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });

export const manuscriptService = {
  // --- Manuscripts ---
  async list() {
    return json(await fetch(`${BASE}/`), 'list manuscripts');
  },
  async create(data) {
    return json(await post(`${BASE}/`, data), 'create manuscript');
  },
  async get(id) {
    return json(await fetch(`${BASE}/${id}`), 'load manuscript');
  },
  async update(id, data) {
    return json(await patch(`${BASE}/${id}`, data), 'update manuscript');
  },
  async remove(id) {
    return json(await fetch(`${BASE}/${id}`, { method: 'DELETE' }), 'delete manuscript');
  },
  async reorder(id, chapters) {
    return json(await post(`${BASE}/${id}/reorder`, { chapters }), 'reorder');
  },
  async export(id, format = 'markdown') {
    return json(await fetch(`${BASE}/${id}/export?format=${format}`), 'export');
  },

  // --- Chapters ---
  async addChapter(id, title) {
    return json(await post(`${BASE}/${id}/chapters`, { title }), 'add chapter');
  },
  async updateChapter(id, chapterId, title) {
    return json(await patch(`${BASE}/${id}/chapters/${chapterId}`, { title }), 'rename chapter');
  },
  async removeChapter(id, chapterId) {
    return json(await fetch(`${BASE}/${id}/chapters/${chapterId}`, { method: 'DELETE' }), 'delete chapter');
  },

  // --- Scenes ---
  async addScene(id, chapterId, title, blocks) {
    return json(await post(`${BASE}/${id}/scenes`, { chapter_id: chapterId, title, blocks }), 'add scene');
  },
  async getScene(sceneId) {
    return json(await fetch(`${BASE}/scenes/${sceneId}`), 'load scene');
  },
  async saveScene(sceneId, data) {
    // The canonical write — the author committing to canon.
    return json(await patch(`${BASE}/scenes/${sceneId}`, data), 'save scene');
  },
  async removeScene(sceneId) {
    return json(await fetch(`${BASE}/scenes/${sceneId}`, { method: 'DELETE' }), 'delete scene');
  },

  // --- Version snapshots ---
  async snapshot(sceneId, label) {
    return json(await post(`${BASE}/scenes/${sceneId}/versions`, { label }), 'snapshot scene');
  },
  async listVersions(sceneId) {
    return json(await fetch(`${BASE}/scenes/${sceneId}/versions`), 'list versions');
  },
  async restoreVersion(sceneId, versionId) {
    return json(await post(`${BASE}/scenes/${sceneId}/versions/${versionId}/restore`), 'restore version');
  },
};
