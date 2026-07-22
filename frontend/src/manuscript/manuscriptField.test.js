import { describe, it, expect } from 'vitest';
import {
    describeSelection, selectionQuestions, buildChipInspection,
    actionsForSelection, inspectorSummary, MANUSCRIPT_OBJECTS, MANUSCRIPT_ACTIONS,
} from './manuscriptField';
import { makeExpressionPercept } from '../state/perceptMentions';

const ground = (id, extra = {}) => ({ id, ground_type: 'region', label: id, region_id: `reg_${id}`, ...extra });
// A resolver that says a named set of grounds is gone. Supplying one at all is
// what makes evidence assessable; withholding it must yield `unknown`.
const resolverMissing = (missing = []) => (g) => ({ detached: missing.includes(g.id) });

describe('describeSelection — records, not judgements', () => {
    it('reports cites_nothing for prose with no chips', () => {
        const s = describeSelection({ kind: 'text', text: 'the light falls hard' });
        expect(s.citation_state).toBe('cites_nothing');
        expect(s.cited_percept_ids).toEqual([]);
    });

    it('distinguishes not-assessed from cites-nothing', () => {
        // The difference between "we looked and found none" and "we did not look"
        // is the whole discipline. Collapsing them is how absence becomes proof.
        const s = describeSelection({ kind: 'text', text: 'x', assessed: false });
        expect(s.citation_state).toBe('not_assessed');
        expect(s.citation_state).not.toBe('cites_nothing');
    });

    it('collects percept ids and treats chip region-ids as GROUND ids', () => {
        const s = describeSelection({
            kind: 'text', text: 'a b',
            chips: [{ perceptId: 'pctx_1', regionIds: 'gnd_1,gnd_2' }],
        });
        expect(s.citation_state).toBe('cites_percepts');
        expect(s.cited_percept_ids).toEqual(['pctx_1']);
        expect(s.cited_ground_ids).toEqual(['gnd_1', 'gnd_2']);
    });

    it('keeps the selected prose verbatim', () => {
        // compose_percept is seeded with the curator's own sentence, never a paraphrase.
        const text = '  the shoulder folds like architecture  ';
        expect(describeSelection({ kind: 'text', text }).text).toBe(text);
    });

    it('dedupes repeated citations of the same percept', () => {
        const s = describeSelection({
            kind: 'text', text: 'x',
            chips: [{ perceptId: 'pctx_1', regionIds: 'gnd_1' }, { perceptId: 'pctx_1', regionIds: 'gnd_1' }],
        });
        expect(s.cited_percept_ids).toEqual(['pctx_1']);
    });
});

describe('selectionQuestions — a sentence answering honestly', () => {
    const q = (sel, key) => selectionQuestions(sel).find((x) => x.key === key);

    it('never claims a sentence is unsupported', () => {
        const sel = describeSelection({ kind: 'text', text: 'x' });
        const unsupported = q(sel, 'unsupported');
        expect(unsupported.answerable).toBe(false);
        expect(unsupported.voice).toBe('judgement');
        expect(unsupported.answer).toMatch(/not assessed/);
    });

    it('reports external claims as not assessed — there is no assessor', () => {
        const ext = q(describeSelection({ kind: 'text', text: 'x' }), 'external');
        expect(ext.answerable).toBe(false);
        expect(ext.answer).toBe('external claims not assessed');
    });

    it('labels record questions as records and proposals as proposals', () => {
        const sel = describeSelection({ kind: 'text', text: 'x', chips: [{ perceptId: 'pctx_1' }] });
        expect(q(sel, 'cites').voice).toBe('record');
        expect(q(sel, 'become_percept').voice).toBe('proposal');
    });

    it('answers the citation questions from the markup', () => {
        const sel = describeSelection({
            kind: 'text', text: 'x', chips: [{ perceptId: 'pctx_1', regionIds: 'gnd_1,gnd_2' }],
        });
        expect(q(sel, 'cites').answer).toBe('1 percept');
        expect(q(sel, 'grounds').answer).toMatch(/2 grounds/);
        expect(q(sel, 'recall').answer).toMatch(/1 noticing/);
    });

    it('refuses to propose a percept from an empty selection', () => {
        expect(q(describeSelection({ kind: 'text', text: '   ' }), 'become_percept').answerable).toBe(false);
    });
});

describe('buildChipInspection — the chip as a living citation', () => {
    const percept = makeExpressionPercept({
        id: 'pctx_1', expression: 'the upper head', ground_ids: ['g1', 'g2'],
        ground_roles: { g1: 'anchor', g2: 'counterforce' },
    });
    const grounds = [ground('g1'), ground('g2')];

    it('reports evidence as unknown, never intact, without a resolver', () => {
        // Absent is not nominal. buildPerceptPacket makes the same refusal.
        const i = buildChipInspection(percept, { grounds });
        expect(i.evidence.state).toBe('unknown');
        expect(i.evidence.note).toBe('evidence state not computed');
    });

    it('renders NO evidence section when the evidence is healthy', () => {
        // Degradation-only: a healthy percept carries no health marks at all.
        const i = buildChipInspection(percept, { grounds, resolve: resolverMissing([]) });
        expect(i.evidence.state).toBe('intact');
        expect(i.sections.find((s) => s.key === 'evidence')).toBeUndefined();
    });

    it('adds a judgement section, without a cause, when a ground is gone', () => {
        const i = buildChipInspection(percept, { grounds, resolve: resolverMissing(['g2']) });
        const ev = i.sections.find((s) => s.key === 'evidence');
        expect(ev.voice).toBe('judgement');
        expect(ev.value).toBe('1 of 2 cited grounds no longer resolves');
        expect(ev.value).not.toMatch(/replaced|because|caused/i);
    });

    it('says none resolve when none do', () => {
        const i = buildChipInspection(percept, { grounds, resolve: resolverMissing(['g1', 'g2']) });
        expect(i.evidence.state).toBe('detached');
        expect(i.evidence.note).toBe('none of the 2 cited grounds still resolves');
    });

    it('shows ground roles only when named, and flags a counterforce', () => {
        const withRoles = buildChipInspection(percept, { grounds, resolve: resolverMissing([]) });
        const roles = withRoles.sections.find((s) => s.key === 'roles');
        expect(roles.hasCounterforce).toBe(true);

        const bare = makeExpressionPercept({ id: 'pctx_2', expression: 'x', ground_ids: ['g1'] });
        const none = buildChipInspection(bare, { grounds, resolve: resolverMissing([]) });
        expect(none.sections.find((s) => s.key === 'roles')).toBeUndefined();
    });

    it('derives "in the writing" from mentions, never from a flag', () => {
        const i = buildChipInspection(percept, {
            grounds, resolve: resolverMissing([]),
            mentions: [{ perceptId: 'pctx_1', blockId: 'b1' }, { perceptId: 'pctx_1', blockId: 'b1' }],
        });
        expect(i.sections.find((s) => s.key === 'mentions').value).toBe('1 passage');
    });

    it('says not yet in the writing when no mention records it', () => {
        const i = buildChipInspection(percept, { grounds, resolve: resolverMissing([]), mentions: [] });
        expect(i.sections.find((s) => s.key === 'mentions').value).toBe('not yet in the writing');
    });

    it('says recall counts are session-local', () => {
        const i = buildChipInspection(percept, { grounds, resolve: resolverMissing([]), recallCount: 2 });
        expect(i.sections.find((s) => s.key === 'recall').value).toBe('recalled 2× this session');
    });

    it('reports an unresolvable citation as a record about the store', () => {
        const i = buildChipInspection(null, { label: 'the upper head' });
        expect(i.resolved).toBe(false);
        expect(i.label).toBe('the upper head');
        expect(i.note).toMatch(/no longer resolves/);
        expect(i.evidence.state).toBe('unknown');
    });

    it('does not refuse a percept for citing no grounds', () => {
        const ungrounded = makeExpressionPercept({ id: 'pctx_3', expression: 'x', ground_ids: [] });
        const i = buildChipInspection(ungrounded, { grounds, resolve: resolverMissing([]) });
        expect(i.resolved).toBe(true);
        expect(i.sections.find((s) => s.key === 'grounds').value).toBe('cites no grounds');
    });
});

describe('actionsForSelection — everything is preview-only', () => {
    it('offers nothing when nothing is selected', () => {
        expect(actionsForSelection(describeSelection())).toEqual([]);
    });

    it('marks every action unwired, with the reason on the action', () => {
        const forText = actionsForSelection(describeSelection({ kind: 'text', text: 'x' }));
        const forChip = actionsForSelection(describeSelection({ kind: 'percept_chip', chips: [{ perceptId: 'p' }] }));
        expect(forText.length).toBeGreaterThan(0);
        expect(forChip.length).toBeGreaterThan(0);
        for (const a of [...forText, ...forChip]) {
            expect(a.wired).toBe(false);
            expect(a.note).toMatch(/Preview only/);
        }
    });

    it('offers different acts to prose than to a chip', () => {
        const text = actionsForSelection(describeSelection({ kind: 'text', text: 'x' })).map((a) => a.type);
        const chip = actionsForSelection(describeSelection({ kind: 'percept_chip', chips: [{ perceptId: 'p' }] })).map((a) => a.type);
        expect(text).toContain('create_percept_from_sentence');
        expect(chip).toContain('recall_percept');
        expect(text).not.toContain('recall_percept');
    });

    it('names which action types do not yet exist in the grammar', () => {
        // normalizeAction returns null for an unknown type — the correct failure.
        // None of these may render an Apply until its spec exists.
        expect(MANUSCRIPT_ACTIONS.filter((a) => a.newType).length).toBeGreaterThan(0);
    });
});

describe('inspectorSummary', () => {
    it('says nothing selected at rest', () => {
        expect(inspectorSummary(describeSelection())).toBe('Nothing selected');
    });
    it('reports cites nothing as a plain record', () => {
        expect(inspectorSummary(describeSelection({ kind: 'text', text: 'x' }))).toBe('Selection · cites nothing');
    });
    it('never uses reassuring language for healthy evidence', () => {
        const s = inspectorSummary(
            describeSelection({ kind: 'percept_chip', chips: [{ perceptId: 'p' }] }),
            { resolved: true, evidence: { state: 'intact' } },
        );
        expect(s).toBe('Percept');
        expect(s).not.toMatch(/verified|healthy|ok|good/i);
    });
    it('surfaces a degraded state in the resting line', () => {
        expect(inspectorSummary(
            describeSelection({ kind: 'percept_chip', chips: [{ perceptId: 'p' }] }),
            { resolved: true, evidence: { state: 'detached' } },
        )).toBe('Percept · evidence detached');
    });
});

describe('the object catalogue is honest about what exists', () => {
    it('marks unbuilt objects as not existing', () => {
        const byKey = Object.fromEntries(MANUSCRIPT_OBJECTS.map((o) => [o.key, o]));
        expect(byKey.percept_chip.exists).toBe(true);
        expect(byKey.field_ref.exists).toBe(false);
        expect(byKey.external_claim.exists).toBe(false);
        // Recorded structurally, rendered indistinguishably — the live hazard.
        expect(byKey.model_draft.partial).toBe(true);
    });
});
