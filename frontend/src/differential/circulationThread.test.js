import { describe, it, expect } from 'vitest';
import {
    buildCirculationThread, threadSummary, recordsOf, judgementsOf, RELATION, VOICE,
} from './circulationThread.js';
import { mentionsFromBlocks } from '../state/perceptMentions.js';
import { setGroundRole } from './groundRoles.js';
import { buildPerceptPacket } from './perceptPacket.js';

const percept = (ground_ids) => ({ id: 'pctx_a', expression: 'the upper head', ground_ids });
const regionGround = (id, region_id) => ({ id, ground_type: 'region', region_id });
const chipBlock = (bid, pid) => ({
    id: bid,
    content: `<p><span data-region-ref="" data-inline-type="percept" data-region-ids="gnd_1" data-percept-id="${pid}">x</span></p>`,
});

const rel = (thread, r) => thread.find((l) => l.relation === r);

describe('Circulation Thread — relations, in two voices, without the causes', () => {
    const grounds = [regionGround('gnd_1', 'region_1'), regionGround('gnd_2', 'region_2')];
    const regions = [{ id: 'region_1' }, { id: 'region_2' }];

    it('a healthy percept: records present, and NO judgement about its evidence', () => {
        const t = buildCirculationThread(percept(['gnd_1', 'gnd_2']), {
            grounds, regions, mentions: mentionsFromBlocks([chipBlock('blk1', 'pctx_a')]), recallCount: 2,
        });
        expect(rel(t, RELATION.FORMED).text).toBe('formed in Differential');
        expect(rel(t, RELATION.CITES).text).toBe('cites 2 grounds');
        expect(rel(t, RELATION.MENTIONED).text).toBe('mentioned in 1 passage');
        expect(rel(t, RELATION.RECALLED).text).toBe('recalled 2× this session');
        // Degradation-only: silence IS the healthy state.
        expect(rel(t, RELATION.MISSING)).toBeUndefined();
        expect(rel(t, RELATION.DEGRADED)).toBeUndefined();
        expect(judgementsOf(t).some((l) => l.state === 'degraded')).toBe(false);
    });

    it('RECORDS and JUDGEMENTS are separate voices, records first', () => {
        const t = buildCirculationThread(percept(['gnd_1']), { grounds, regions: [] });
        expect(recordsOf(t).length + judgementsOf(t).length).toBe(t.length);
        // Every record precedes every judgement.
        const lastRecord = t.map((l) => l.voice).lastIndexOf(VOICE.RECORD);
        const firstJudgement = t.map((l) => l.voice).indexOf(VOICE.JUDGEMENT);
        expect(lastRecord).toBeLessThan(firstJudgement);
        // The count of grounds is a RECORD; what is wrong with them is a JUDGEMENT.
        expect(rel(t, RELATION.CITES).voice).toBe(VOICE.RECORD);
        expect(rel(t, RELATION.MISSING).voice).toBe(VOICE.JUDGEMENT);
    });

    it('names the roles its grounds play, when the curator named them', () => {
        let p = setGroundRole(percept(['gnd_1', 'gnd_2']), 'gnd_1', 'anchor');
        p = setGroundRole(p, 'gnd_2', 'counterforce');
        const t = buildCirculationThread(p, { grounds, regions });
        expect(rel(t, RELATION.CITES).text).toBe('cites 2 grounds: anchor, counterforce');
        expect(rel(t, RELATION.CITES).roles).toEqual(['anchor', 'counterforce']);
    });

    it('does not repeat a role name when two grounds share one', () => {
        let p = setGroundRole(percept(['gnd_1', 'gnd_2']), 'gnd_1', 'anchor');
        p = setGroundRole(p, 'gnd_2', 'anchor');
        expect(rel(buildCirculationThread(p, { grounds, regions }), RELATION.CITES).text)
            .toBe('cites 2 grounds: anchor');
    });

    it('partly detached evidence is a DEGRADED judgement, and states no cause', () => {
        const t = buildCirculationThread(percept(['gnd_1', 'gnd_2']), { grounds, regions: [{ id: 'region_1' }] });
        const d = rel(t, RELATION.DEGRADED);
        expect(d.voice).toBe(VOICE.JUDGEMENT);
        expect(d.text).toBe('1 of 2 cited grounds no longer resolves');
        for (const l of t) {
            expect(l.text).not.toMatch(/because|caused|re-dissect|replaced|deleted|due to/i);
        }
    });

    it('wholly detached evidence is a MISSING judgement', () => {
        const t = buildCirculationThread(percept(['gnd_1']), { grounds, regions: [] });
        expect(rel(t, RELATION.MISSING).text).toBe('none of the 1 cited ground still resolves');
        expect(rel(t, RELATION.DEGRADED)).toBeUndefined();
    });

    it('a cited ground whose RECORD is gone counts as not resolving', () => {
        const t = buildCirculationThread(percept(['gnd_missing']), { grounds: [], regions: [] });
        expect(rel(t, RELATION.MISSING)).toBeDefined();
    });

    it('not yet written about, not yet recalled — absent, never "none"', () => {
        const t = buildCirculationThread(percept(['gnd_1']), { grounds, regions });
        expect(rel(t, RELATION.MENTIONED).state).toBe('absent');
        expect(rel(t, RELATION.MENTIONED).text).toBe('not yet in the writing');
        expect(rel(t, RELATION.RECALLED).text).toBe('not recalled yet');
    });

    it('mentioned with no knowable passage still reports the crossing', () => {
        // A chip inserted into an empty document has no block id to be inserted
        // against. Saying nothing would under-report a crossing that happened.
        const mentions = [{ perceptId: 'pctx_a', blockId: null }];
        expect(rel(buildCirculationThread(percept([]), { mentions }), RELATION.MENTIONED).text)
            .toBe('mentioned in the writing');
    });

    it('a model reading is UNRECORDED, never "none" — no entity carries a run_id', () => {
        const t = buildCirculationThread(percept([]), {});
        const m = rel(t, RELATION.MODEL_READING);
        expect(m.text).toBe('no model reading recorded');
        // It is a fact about our ledger, so it speaks in the RECORD voice.
        expect(m.voice).toBe(VOICE.RECORD);
        const withRuns = buildCirculationThread(percept([]), { visionRuns: [{ id: 'r1' }] });
        // Scope declared: the runs are on the IMAGE, not tied to this percept.
        expect(rel(withRuns, RELATION.MODEL_READING).scope).toBe('post');
        expect(rel(withRuns, RELATION.MODEL_READING).text).toBe('1 model run on this image');
    });

    it('what we have NOT looked at says so — silence is not a clean bill', () => {
        const t = buildCirculationThread(percept(['gnd_1']), { grounds, regions });
        expect(rel(t, RELATION.EXTERNAL).state).toBe('unassessed');
        expect(rel(t, RELATION.EXTERNAL).text).toBe('external claims not assessed');
        expect(rel(t, RELATION.SUSPECT).text).toBe('substitution not assessed');
        expect(rel(t, RELATION.SUSPECT).voice).toBe(VOICE.JUDGEMENT);
    });

    it('counts only the passages that carry THIS percept', () => {
        const mentions = mentionsFromBlocks([chipBlock('blk1', 'pctx_a'), chipBlock('blk2', 'pctx_other')]);
        expect(rel(buildCirculationThread(percept([]), { mentions }), RELATION.MENTIONED).blocks).toEqual(['blk1']);
    });

    it('no percept, no thread', () => {
        expect(buildCirculationThread(null, {})).toEqual([]);
        expect(threadSummary([])).toBe('');
    });
});

describe('the packet row — prepared, and explicitly not sent', () => {
    const grounds = [regionGround('gnd_1', 'region_1')];
    const regions = [{ id: 'region_1' }];

    it('reports the packet and its intent, and that nothing left', () => {
        const packet = buildPerceptPacket(percept(['gnd_1']), { grounds, intent: 'challenge' });
        const t = buildCirculationThread(percept(['gnd_1']), { grounds, regions, packet });
        const p = rel(t, RELATION.PACKET);
        expect(p.voice).toBe(VOICE.RECORD);
        expect(p.text).toBe('packet prepared, not sent · intent challenge');
        expect(p.sent).toBe(false);
    });

    it('BACK-COMPAT: no packet, no packet row', () => {
        expect(rel(buildCirculationThread(percept(['gnd_1']), { grounds, regions }), RELATION.PACKET)).toBeUndefined();
    });
});

describe('threadSummary — quiet when healthy, degradation-first when not', () => {
    const grounds = [regionGround('gnd_1', 'region_1'), regionGround('gnd_2', 'region_2')];
    const regions = [{ id: 'region_1' }, { id: 'region_2' }];

    it('healthy and cited reads as plain relations', () => {
        const t = buildCirculationThread(percept(['gnd_1', 'gnd_2']), {
            grounds, regions, mentions: mentionsFromBlocks([chipBlock('blk1', 'pctx_a')]),
        });
        expect(threadSummary(t)).toBe('formed · cites 2 grounds · mentioned in 1 passage');
    });

    it('degradation displaces the mention in the resting line', () => {
        const t = buildCirculationThread(percept(['gnd_1', 'gnd_2']), { grounds, regions: [] });
        expect(threadSummary(t)).toBe('formed · cites 2 grounds · none of the 2 cited grounds still resolves');
    });

    it('an uncited, unwritten percept still reads honestly', () => {
        expect(threadSummary(buildCirculationThread(percept([]), {}))).toBe('formed · cites no grounds');
    });
});

describe('backward compatibility', () => {
    it('a percept with no roles, no mentions, no packet builds a full thread', () => {
        const t = buildCirculationThread({ id: 'pctx_old', ground_ids: ['gnd_1'] }, {});
        expect(rel(t, RELATION.CITES).text).toBe('cites 1 ground');
        expect(rel(t, RELATION.CITES).roles).toEqual([]);
        expect(rel(t, RELATION.MENTIONED).state).toBe('absent');
        expect(recordsOf(t).length).toBeGreaterThan(0);
        expect(judgementsOf(t).length).toBeGreaterThan(0);
    });
});
