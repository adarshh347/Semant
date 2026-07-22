import { describe, it, expect } from 'vitest';
import {
    GROUND_ROLES, CORE_ROLES, ROLE_KEYS, isRoleKey, roleLabel,
    rolesOf, roleFor, setGroundRole, groundRoleList, rolesSummary,
} from './groundRoles.js';
import { makeExpressionPercept } from '../state/perceptMentions.js';

const percept = (extra = {}) => makeExpressionPercept({
    id: 'pctx_a', expression: 'the arch held against the shadow',
    ground_ids: ['gnd_1', 'gnd_2'], ...extra,
});

describe('Ground Roles — a role belongs to a percept’s USE of a ground', () => {
    it('sets and reads a role without touching the ground record', () => {
        const g1 = { id: 'gnd_1', ground_type: 'region', region_id: 'region_1' };
        const grounds = [g1, { id: 'gnd_2', ground_type: 'field' }];
        const before = JSON.stringify(grounds);

        const p = setGroundRole(percept(), 'gnd_1', 'anchor');
        expect(roleFor(p, 'gnd_1')).toBe('anchor');
        // THE RULE: the global evidence record is untouched.
        expect(JSON.stringify(grounds)).toBe(before);
        expect(g1.role).toBeUndefined();
        expect(g1.ground_roles).toBeUndefined();
    });

    it('the SAME ground can be an anchor in one percept and a counterforce in another', () => {
        // This is why a role cannot live on the ground: two readings would fight
        // over one field and the last curator to speak would win.
        const a = setGroundRole(percept({ id: 'pctx_a' }), 'gnd_1', 'anchor');
        const b = setGroundRole(percept({ id: 'pctx_b' }), 'gnd_1', 'counterforce');
        expect(roleFor(a, 'gnd_1')).toBe('anchor');
        expect(roleFor(b, 'gnd_1')).toBe('counterforce');
    });

    it('never mutates the percept it is given', () => {
        const p = percept();
        const frozen = JSON.stringify(p);
        setGroundRole(p, 'gnd_1', 'anchor');
        expect(JSON.stringify(p)).toBe(frozen);
    });

    it('refuses a role on a ground the percept does not cite', () => {
        const p = setGroundRole(percept(), 'gnd_99', 'anchor');
        expect(rolesOf(p)).toEqual({});
    });

    it('refuses a role outside the vocabulary', () => {
        expect(rolesOf(setGroundRole(percept(), 'gnd_1', 'vibes'))).toEqual({});
        expect(isRoleKey('vibes')).toBe(false);
        expect(isRoleKey('anchor')).toBe(true);
    });

    it('clearing the last role removes the key, so it matches a percept that never had one', () => {
        const none = percept();
        const cleared = setGroundRole(setGroundRole(none, 'gnd_1', 'anchor'), 'gnd_1', null);
        expect('ground_roles' in cleared).toBe(false);
        expect(JSON.stringify(cleared)).toBe(JSON.stringify(none));
    });

    it('BACK-COMPAT: a percept written before roles existed reads as no roles', () => {
        expect(rolesOf({ id: 'pctx_old', ground_ids: ['gnd_1'] })).toEqual({});
        expect(rolesOf(null)).toEqual({});
        expect(roleFor(undefined, 'gnd_1')).toBeNull();
        // …and malformed shapes do not throw or leak.
        expect(rolesOf({ ground_roles: ['anchor'] })).toEqual({});
        expect(rolesOf({ ground_roles: { gnd_1: 'nonsense' } })).toEqual({});
    });

    it('survives the storage round-trip the percept already uses', () => {
        const p = setGroundRole(percept(), 'gnd_1', 'threshold');
        expect(JSON.parse(JSON.stringify(p))).toEqual(p);
        expect(roleFor(JSON.parse(JSON.stringify(p)), 'gnd_1')).toBe('threshold');
    });

    it('the factory carries roles through, and omits the key when empty', () => {
        const withRoles = makeExpressionPercept({ ground_ids: ['g1'], ground_roles: { g1: 'anchor' } });
        expect(withRoles.ground_roles).toEqual({ g1: 'anchor' });
        expect('ground_roles' in makeExpressionPercept({ ground_ids: ['g1'] })).toBe(false);
        expect('ground_roles' in makeExpressionPercept({ ground_ids: ['g1'], ground_roles: {} })).toBe(false);
    });
});

describe('groundRoleList — evidence and meaning meet, in citation order', () => {
    const grounds = [
        { id: 'gnd_2', ground_type: 'field', label: 'the shadow' },
        { id: 'gnd_1', ground_type: 'region', label: 'the arch' },
    ];

    it('follows the percept’s citation order, not storage order', () => {
        const p = setGroundRole(percept(), 'gnd_1', 'anchor');
        expect(groundRoleList(p, grounds).map((e) => e.ground_id)).toEqual(['gnd_1', 'gnd_2']);
        expect(groundRoleList(p, grounds)[0].role).toBe('anchor');
        expect(groundRoleList(p, grounds)[1].role).toBeNull();
    });

    it('adds resolution only when a resolver is injected — meaning and truth stay separable', () => {
        const p = percept();
        expect(groundRoleList(p, grounds)[0].detached).toBeUndefined();
        const withState = groundRoleList(p, grounds, (g) => ({ detached: g.id === 'gnd_2' }));
        expect(withState.find((e) => e.ground_id === 'gnd_2').detached).toBe(true);
        expect(withState.find((e) => e.ground_id === 'gnd_1').detached).toBe(false);
    });

    it('a cited ground whose record is gone is present:false and detached', () => {
        const e = groundRoleList(percept(), [], () => ({ detached: false }))[0];
        expect(e.present).toBe(false);
        expect(e.detached).toBe(true);
    });
});

describe('vocabulary', () => {
    it('exposes five core roles and a stable key set', () => {
        expect(CORE_ROLES).toHaveLength(5);
        expect(CORE_ROLES.map((r) => r.key)).toEqual(['anchor', 'support', 'counterforce', 'threshold', 'field']);
        expect(ROLE_KEYS).toHaveLength(GROUND_ROLES.length);
        expect(new Set(ROLE_KEYS).size).toBe(ROLE_KEYS.length);   // no duplicate keys
        expect(roleLabel('external-limit')).toBe('external limit');
    });

    it('summarises without repeating a role name', () => {
        let p = setGroundRole(percept({ ground_ids: ['g1', 'g2', 'g3'] }), 'g1', 'anchor');
        p = setGroundRole(p, 'g2', 'anchor');
        p = setGroundRole(p, 'g3', 'counterforce');
        expect(rolesSummary(p)).toBe('anchor, counterforce');
        expect(rolesSummary(percept())).toBe('');
    });
});
