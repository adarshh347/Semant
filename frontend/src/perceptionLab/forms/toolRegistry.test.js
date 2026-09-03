// PERCEPTUAL-FORMS-001E — the tools, and the promise that they write nothing.
//
// The last describe block is the one that matters. "No save, no promotion, no real API" is easy
// to honour today and easy to break by accident in six weeks, so it is checked as a property of
// the MODULE GRAPH: nothing reachable from `forms/index.js` imports a client, a fetch, or the
// session hook. A test that only checked the tool objects would pass on the day somebody added
// `await client.promote(...)` inside a component.

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
    TOOL_BEHAVIOUR, VERDICTS, VERDICT_NOTE, toolsFor, proposal, isVerdict, groupProposals,
} from './toolRegistry';
import {
    PERCEPTUAL_FORMS, form, MANUAL_TOOL_KINDS, REVIEW_VERDICTS,
} from '../contract/perceptionLabContract';

const HERE = path.dirname(fileURLToPath(import.meta.url));

describe('the tools are the contract\'s own', () => {
    it('offers a behaviour for every kind in the closed set', () => {
        expect(Object.keys(TOOL_BEHAVIOUR).sort()).toEqual([...MANUAL_TOOL_KINDS].sort());
    });

    it('resolves the tools every form declares, with no gaps', () => {
        for (const key of PERCEPTUAL_FORMS) {
            const tools = toolsFor(key);
            expect(tools.map((t) => t.kind), key).toEqual(form(key).manual_tools);
            for (const t of tools) {
                expect(t.label, `${key}/${t.kind}`).toBeTruthy();
                expect(t.produces, `${key}/${t.kind}`).toBeTruthy();
            }
        }
    });

    it('cannot lose an entry at runtime, and would throw if one were missing at build', () => {
        // Two halves of the same guarantee. The table is frozen, so nothing can delete a
        // behaviour while the page is running; and `toolsFor` throws rather than returning an
        // empty menu, so a contract that GAINS a tool kind fails here instead of shipping a form
        // whose declared tool silently does not appear.
        expect(Object.isFrozen(TOOL_BEHAVIOUR)).toBe(true);
        expect(() => { delete TOOL_BEHAVIOUR.mask_brush; }).toThrow();
        expect(TOOL_BEHAVIOUR.mask_brush).toBeTruthy();
        for (const key of PERCEPTUAL_FORMS) expect(() => toolsFor(key), key).not.toThrow();
        // The failure path, over a form declaration the contract does not contain.
        expect(() => toolsFor('extent.no_such_form')).toThrow(/not a registered perceptual form/);
    });

    it('gives the hypothesis forms an accept/reject control and the others none', () => {
        expect(toolsFor('extent.hypothesis_set').map((t) => t.kind)).toContain('hypothesis_choose');
        expect(toolsFor('topology.uncertain_relation_set').map((t) => t.kind))
            .toContain('hypothesis_choose');
        expect(toolsFor('extent.hard_mask').map((t) => t.kind)).not.toContain('hypothesis_choose');
    });

    it('gives the fragment form both group and split, which are the membership correction', () => {
        const kinds = toolsFor('extent.fragment_set').map((t) => t.kind);
        expect(kinds).toContain('fragment_group');
        expect(kinds).toContain('fragment_split');
    });

    it('gives the boundary form a vertex editor', () => {
        expect(toolsFor('extent.boundary_rings').map((t) => t.kind)).toContain('ring_edit');
    });
});

describe('the verdicts come from the contract, not from this file', () => {
    it('offers exactly the four the closed set names', () => {
        expect(VERDICTS.map((v) => v.key)).toEqual([...REVIEW_VERDICTS]);
        expect(VERDICTS.map((v) => v.key).sort())
            .toEqual(['correct', 'partial', 'unclear', 'wrong']);
    });

    it('says what each one means, including the one people skip', () => {
        for (const v of VERDICTS) expect(VERDICT_NOTE[v.key], v.key).toBeTruthy();
        expect(VERDICT_NOTE.unclear).toMatch(/behind a ref|does not let you tell/);
        expect(VERDICT_NOTE.wrong).toMatch(/MEASUREMENT, not about the drawing/);
    });
});

describe('a proposal writes nothing', () => {
    const p = proposal({
        tool: 'ring_edit',
        formKey: 'extent.boundary_rings',
        target: 'art_extent_1#inst_1',
        value: { ring_id: 'ring_outer', points: [[0.1, 0.1]] },
        at: '2026-08-22T00:00:00Z',
    });

    it('says so on the object, not only in the panel that renders it', () => {
        expect(p.writes).toBe('nothing');
        expect(p.status).toMatch(/no client and writes to no record/);
        expect(Object.isFrozen(p)).toBe(true);
    });

    it('names what it is a proposal about', () => {
        expect(p.form).toBe('extent.boundary_rings');
        expect(p.target).toBe('art_extent_1#inst_1');
        expect(p.kind).toBe('proposed_ring');
    });

    it('takes its timestamp rather than reading a clock', () => {
        // The whole directory is deterministic: a screenshot taken twice must be the same
        // screenshot, and a proposal that stamped Date.now() would differ on every run.
        expect(p.at).toBe('2026-08-22T00:00:00Z');
        expect(proposal({ tool: 'ring_edit', formKey: 'x', target: 't', value: 1 }).at).toBeNull();
    });

    it('refuses a tool that is not in the contract set', () => {
        expect(() => proposal({ tool: 'lasso', formKey: 'x', target: 't', value: 1 }))
            .toThrow(/not a manual tool/);
    });

    it('tells a verdict from a geometry change', () => {
        const v = proposal({ tool: 'hypothesis_choose', formKey: 'extent.hypothesis_set',
            target: 'alt_one_object', value: 'wrong' });
        expect(isVerdict(v)).toBe(true);
        expect(isVerdict(p)).toBe(false);
    });

    it('groups by target, because five proposals about one instance are a disagreement', () => {
        const a = proposal({ tool: 'ring_edit', formKey: 'f', target: 'inst_1', value: 1 });
        const b = proposal({ tool: 'hypothesis_choose', formKey: 'f', target: 'inst_1',
            value: 'partial' });
        const c = proposal({ tool: 'ring_edit', formKey: 'f', target: 'inst_2', value: 1 });
        const groups = groupProposals([a, b, c]);
        expect(groups.map((g) => g.target)).toEqual(['inst_1', 'inst_2']);
        expect(groups[0].proposals).toHaveLength(2);
        expect(groups[0].verdicts).toHaveLength(1);
        expect(groups[0].geometry).toHaveLength(1);
    });
});

describe('nothing in forms/ can reach a client', () => {
    // Read as text, deliberately. An import-graph check by execution would pass on a module that
    // imports a client and never calls it, and the promise being kept here is that the surface
    // has no way to write at all.
    const files = [];
    const walk = (dir) => {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
            const full = path.join(dir, entry.name);
            if (entry.isDirectory()) walk(full);
            else if (/\.(js|jsx)$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name)) {
                files.push(full);
            }
        }
    };
    walk(HERE);

    it('finds the source files to check', () => {
        expect(files.length).toBeGreaterThan(6);
    });

    it.each(files.map((f) => [path.relative(HERE, f), f]))(
        '%s imports no client and calls no network', (_name, file) => {
            const src = fs.readFileSync(file, 'utf8');
            const imports = [...src.matchAll(/from\s+'([^']+)'/g)].map((m) => m[1]);
            for (const spec of imports) {
                expect(spec, `${_name} imports ${spec}`).not.toMatch(/clients?\//);
                expect(spec, `${_name} imports ${spec}`).not.toMatch(/useLabSession/);
            }
            // `fetch(`, `XMLHttpRequest`, `navigator.sendBeacon`, `localStorage` — a laboratory
            // that persisted to storage would be saving, whatever it called the function.
            expect(src, _name).not.toMatch(/\bfetch\s*\(/);
            expect(src, _name).not.toMatch(/XMLHttpRequest|sendBeacon|WebSocket/);
            expect(src, _name).not.toMatch(/localStorage|sessionStorage|indexedDB/);
        });

    it('imports the contract read-only, and never writes to it', () => {
        for (const file of files) {
            const src = fs.readFileSync(file, 'utf8');
            expect(src, path.relative(HERE, file))
                .not.toMatch(/CONTRACT\s*\.\s*\w+\s*=|contract\/\w+\.json'\s*;\s*[\s\S]*\.push\(/);
        }
    });
});
