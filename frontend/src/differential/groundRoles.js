/**
 * Ground Roles — what a ground DOES for a percept.
 *
 * CIRCUIT-001 P1C. Pure data + vocabulary; no component, no persistence beyond
 * the percept record the curator already saves.
 *
 * THE LOAD-BEARING RULE, and the reason this is not a field on a Ground:
 *
 *   A role is a property of THIS PERCEPT'S USE of a ground, not of the ground.
 *
 * The same region is an anchor in one noticing and a counterforce in another. A
 * ground says "this part of the image"; a role says "and here is what it is
 * doing in what I am claiming". Writing the role onto `post.grounds` would make
 * the second percept overwrite the first's reading — the evidence record would
 * start carrying an interpretation, and the last curator to speak would win.
 *
 * This is also what makes a percept a READING rather than a list. "The arch and
 * the shadow" is two grounds. "The arch, held against the shadow" is a percept.
 *
 * Roles are OPTIONAL everywhere. A percept with no roles is complete and always
 * remains valid — the vocabulary is an affordance, never a required field, and
 * nothing in the circuit may refuse a percept for lacking one.
 */

/**
 * The vocabulary. Deliberately small, and ordered by how often a curator is
 * likely to reach for it rather than alphabetically.
 *
 * `core: true` marks the five offered up-front in the compact UI; the rest stay
 * available to the data layer and to a later, roomier surface. Adding a role is
 * a one-line change here and requires no migration, because roles live in the
 * percept record the curator already writes.
 */
export const GROUND_ROLES = [
    { key: 'anchor', label: 'anchor', core: true, hint: 'what the noticing rests on' },
    { key: 'support', label: 'support', core: true, hint: 'corroborates the anchor' },
    { key: 'counterforce', label: 'counterforce', core: true, hint: 'pulls against it — kept, not resolved' },
    { key: 'threshold', label: 'threshold', core: true, hint: 'where one thing becomes another' },
    { key: 'field', label: 'field', core: true, hint: 'the ambient condition it happens in' },
    { key: 'rhythm', label: 'rhythm', hint: 'repetition, interval, beat' },
    { key: 'atmosphere', label: 'atmosphere', hint: 'light, air, weather of the image' },
    { key: 'aperture', label: 'aperture', hint: 'an opening the eye goes through' },
    { key: 'trace', label: 'trace', hint: 'evidence of something no longer present' },
    { key: 'external-limit', label: 'external limit', hint: 'where the frame stops the claim' },
];

export const ROLE_KEYS = GROUND_ROLES.map((r) => r.key);
export const CORE_ROLES = GROUND_ROLES.filter((r) => r.core);
export const isRoleKey = (k) => ROLE_KEYS.includes(k);
export const roleLabel = (k) => GROUND_ROLES.find((r) => r.key === k)?.label || k;

/**
 * Read a percept's roles as a plain map. Tolerates every historical shape: the
 * field absent (every percept written before P1C), null, or an array left by
 * some future writer.
 */
export function rolesOf(percept) {
    const raw = percept?.ground_roles;
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
    const out = {};
    for (const [gid, role] of Object.entries(raw)) {
        if (gid && isRoleKey(role)) out[gid] = role;
    }
    return out;
}

/** What does this ground do for this percept? `null` when it does not say. */
export const roleFor = (percept, groundId) => rolesOf(percept)[groundId] || null;

/**
 * Set (or with `null`, clear) one ground's role for one percept. Returns a NEW
 * percept; never mutates, and never touches the ground record.
 *
 * A role may only be attached to a ground the percept actually cites — a reading
 * cannot assign meaning to evidence it did not bring.
 */
export function setGroundRole(percept, groundId, role) {
    if (!percept || !groundId) return percept;
    if (!(percept.ground_ids || []).includes(groundId)) return percept;
    if (role !== null && !isRoleKey(role)) return percept;

    const next = { ...rolesOf(percept) };
    if (role === null) delete next[groundId];
    else next[groundId] = role;

    // Drop the key entirely when empty, so a percept that never used roles is
    // byte-identical to one whose roles were all cleared.
    if (!Object.keys(next).length) {
        const { ground_roles, ...rest } = percept;   // eslint-disable-line no-unused-vars
        return rest;
    }
    return { ...percept, ground_roles: next };
}

/**
 * Roles paired with their grounds, in the percept's own citation order — the
 * order the curator built the reading in, which is not the order the grounds
 * happen to sit in storage.
 *
 * `resolve` is optional and, when given, adds `detached` per ground. It is
 * injected rather than imported so this module stays free of resolution
 * concerns: roles are about MEANING, and evidence state is about TRUTH. They
 * meet in the packet, not here.
 */
export function groundRoleList(percept, grounds = [], resolve = null) {
    const roles = rolesOf(percept);
    return (percept?.ground_ids || []).map((gid) => {
        const ground = (grounds || []).find((g) => g.id === gid) || null;
        const entry = {
            ground_id: gid,
            ground_type: ground?.ground_type || null,
            label: ground?.label || null,
            role: roles[gid] || null,
            present: !!ground,
        };
        if (resolve) entry.detached = ground ? !!resolve(ground)?.detached : true;
        return entry;
    });
}

/** A short human line: "anchor, counterforce" — for a quiet one-line summary. */
export function rolesSummary(percept) {
    const roles = Object.values(rolesOf(percept));
    if (!roles.length) return '';
    const seen = [];
    for (const r of roles) if (!seen.includes(r)) seen.push(r);
    return seen.map(roleLabel).join(', ');
}
