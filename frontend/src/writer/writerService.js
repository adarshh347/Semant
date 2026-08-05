import { API_URL } from '../config/api';

// Semant Writer · W1 — the executable-document client. Mirrors the repo's per-domain
// service pattern (raw fetch, throw on !ok); the X-API-Key header is installed globally
// by config/api.js.
//
// ONE THING TO NOTE ABOUT `run`: a refusal is NOT an error. The backend answers 200 with
// `status: "refused"` and a reason on the entry that refused, so this client must never
// treat a refused directive as a failed request. The reason is the most useful thing the
// system produces when the author's ontology is thin, and it belongs on screen.
const BASE = `${API_URL}/api/v1/writer`;

async function json(res, action) {
  if (!res.ok) {
    let detail = '';
    try {
      detail = (await res.json())?.detail ?? '';
    } catch {
      /* a non-JSON error body is not worth a second failure */
    }
    throw new Error(detail || `Failed to ${action} (${res.status})`);
  }
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

export const writerService = {
  // --- Operators (the author's ontology) ---
  async listOperators(projectId) {
    return json(await fetch(`${BASE}/${projectId}/operators`), 'list operators');
  },
  // Draft from a description. Returns it UNSAVED — the author confirms with `create`.
  async proposeOperator(projectId, { name, description, author }) {
    return json(
      await post(`${BASE}/${projectId}/operators/propose`, { name, description, author }),
      'propose operator',
    );
  },
  async createOperator(projectId, operator) {
    return json(await post(`${BASE}/${projectId}/operators`, operator), 'create operator');
  },
  async updateOperator(projectId, name, data) {
    return json(await patch(`${BASE}/${projectId}/operators/${name}`, data), 'update operator');
  },
  async deleteOperator(projectId, name) {
    return json(
      await fetch(`${BASE}/${projectId}/operators/${name}`, { method: 'DELETE' }),
      'delete operator',
    );
  },

  // --- The operator graph (W3) ---
  // A READ over the ledger: nodes are operators, edges are typed relations. Nothing here
  // can reach the manuscript.
  async graph(projectId) {
    return json(await fetch(`${BASE}/${projectId}/graph`), 'load operator graph');
  },
  // Replace an operator's whole edge set. The server validates (undefined target, unknown
  // kind, cycle) and bumps the version — relations are part of what an operator IS.
  async setRelations(projectId, name, relations) {
    return json(
      await fetch(`${BASE}/${projectId}/operators/${name}/relations`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relations }),
      }),
      'save relations',
    );
  },

  // --- Assemblages (W4) ---
  // A READ over the usage log. Each suggestion cites the blocks it rests on; a candidate
  // that cannot be cited is not returned at all.
  async assemblageSuggestions(projectId) {
    return json(
      await fetch(`${BASE}/${projectId}/assemblages/suggestions`),
      'load assemblage suggestions',
    );
  },
  // Records a dismissal so the cluster stops nagging. Changes NO ontology.
  async dismissAssemblage(projectId, members, support = 0) {
    return json(
      await post(`${BASE}/${projectId}/assemblages/dismiss`, { members, support }),
      'dismiss suggestion',
    );
  },
  // THE commit. `rendering_intent` is the author's — the system never supplies the meaning.
  async createAssemblage(projectId, assemblage) {
    return json(
      await post(`${BASE}/${projectId}/assemblages`, assemblage),
      'author assemblage',
    );
  },

  // --- The loop ---
  // Parse only: the `/` ÷ `//` split, with no model called and nothing stored.
  async parse(projectId, text) {
    return json(await post(`${BASE}/${projectId}/parse`, { text }), 'parse block');
  },
  // Execute a block. Every render comes back QUARANTINED; nothing reaches the manuscript.
  // `onlyDirectives` is BLOCK SCOPE (W3 §1): the indices of the directives still pending.
  // `null`/omitted runs the whole block, which is the explicit re-run-everything action.
  async run(projectId, { text, manuscriptId, sceneId, quarantine = true, onlyDirectives = null }) {
    return json(
      await post(`${BASE}/${projectId}/run`, {
        text,
        manuscript_id: manuscriptId ?? '',
        scene_id: sceneId ?? '',
        quarantine,
        only_directives: onlyDirectives,
      }),
      'run block',
    );
  },

  // --- Quarantine → canon ---
  async listPassages(projectId, { sceneId = '', status = 'quarantined' } = {}) {
    const qs = new URLSearchParams({ scene_id: sceneId, status });
    return json(await fetch(`${BASE}/${projectId}/passages?${qs}`), 'list passages');
  },
  // The author's commit — the only path from quarantine into the sacred manuscript.
  async accept(passageId, sceneId) {
    return json(
      await post(`${BASE}/passages/${passageId}/accept`, { scene_id: sceneId ?? '' }),
      'accept passage',
    );
  },
  async dismiss(passageId, reason) {
    return json(
      await post(`${BASE}/passages/${passageId}/dismiss`, { reason: reason ?? '' }),
      'dismiss passage',
    );
  },

  // --- Instrumentation (recorded from day one; nothing reasons on it in W1) ---
  async usage(projectId, limit = 200) {
    return json(await fetch(`${BASE}/${projectId}/usage?limit=${limit}`), 'load usage');
  },
};

export default writerService;
