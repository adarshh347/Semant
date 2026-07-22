import { describe, it, expect } from 'vitest';
import { buildCirculationThread, threadSummary, RELATION } from './circulationThread.js';
import { mentionsFromBlocks } from '../state/perceptMentions.js';

const percept = (ground_ids) => ({ id: 'pctx_a', expression: 'the upper head', ground_ids });
const regionGround = (id, region_id) => ({ id, ground_type: 'region', region_id });
const chipBlock = (bid, pid) => ({
    id: bid,
    content: `<p><span data-region-ref="" data-inline-type="percept" data-region-ids="gnd_1" data-percept-id="${pid}">x</span></p>`,
});

const rel = (thread, r) => thread.find((l) => l.relation === r);

describe('Circulation Thread — the chain, without the causes', () => {
    it('a healthy percept: every link nominal, nothing announced about health', () => {
        const grounds = [regionGround('gnd_1', 'region_1'), regionGround('gnd_2', 'region_2')];
        const regions = [{ id: 'region_1' }, { id: 'region_2' }];
        const t = buildCirculationThread(percept(['gnd_1', 'gnd_2']), {
            grounds, regions, mentions: mentionsFromBlocks([chipBlock('blk1', 'pctx_a')]), recallCount: 2,
        });
        expect(rel(t, RELATION.CITES).text).toBe('cites 2 grounds');
        expect(rel(t, RELATION.CITES).state).toBe('nominal');
        expect(rel(t, RELATION.MENTIONED).text).toBe('mentioned in 1 passage');
        expect(rel(t, RELATION.RECALLED).text).toBe('recalled 2× this session');
        // Degradation-only: a healthy citation must not acquire a warning.
        expect(t.some((l) => l.state === 'degraded')).toBe(false);
    });

    it('detached evidence: says what no longer resolves, never why', () => {
        const grounds = [regionGround('gnd_1', 'region_1'), regionGround('gnd_2', 'gone')];
        const t = buildCirculationThread(percept(['gnd_1', 'gnd_2']), { grounds, regions: [{ id: 'region_1' }] });
        const cites = rel(t, RELATION.CITES);
        expect(cites.state).toBe('degraded');
        expect(cites.text).toBe('cites 2 grounds · 1 no longer resolves');
        expect(cites.resolving).toBe(1);
        // The causal-language guard, copied from visionActivity's contract.
        for (const l of t) {
            expect(l.text).not.toMatch(/because|caused|re-dissect|replaced|deleted|due to/i);
        }
    });

    it('wholly detached evidence still reports the citation, degraded', () => {
        const grounds = [regionGround('gnd_1', 'gone')];
        const t = buildCirculationThread(percept(['gnd_1']), { grounds, regions: [] });
        expect(rel(t, RELATION.CITES).text).toBe('cites 1 ground · 1 no longer resolves');
        expect(rel(t, RELATION.CITES).resolving).toBe(0);
    });

    it('a cited ground whose RECORD is gone counts as not resolving', () => {
        const t = buildCirculationThread(percept(['gnd_missing']), { grounds: [], regions: [] });
        expect(rel(t, RELATION.CITES).resolving).toBe(0);
        expect(rel(t, RELATION.CITES).state).toBe('degraded');
    });

    it('not yet written about, not yet recalled — absent, not "none"', () => {
        const t = buildCirculationThread(percept(['gnd_1']), {
            grounds: [regionGround('gnd_1', 'region_1')], regions: [{ id: 'region_1' }],
        });
        expect(rel(t, RELATION.MENTIONED).state).toBe('absent');
        expect(rel(t, RELATION.MENTIONED).text).toBe('not yet in the writing');
        expect(rel(t, RELATION.RECALLED).text).toBe('not recalled yet');
    });

    it('a model reading is reported as UNRECORDED, never as none — no entity carries a run_id', () => {
        const t = buildCirculationThread(percept([]), {});
        expect(rel(t, RELATION.UNAVAILABLE).text).toBe('no model reading recorded');
        const withRuns = buildCirculationThread(percept([]), { visionRuns: [{ id: 'r1' }] });
        // Scope is declared: the runs are on the IMAGE, not tied to this percept.
        expect(rel(withRuns, RELATION.RECORDED).scope).toBe('post');
    });

    it('counts only the passages that carry THIS percept', () => {
        const mentions = mentionsFromBlocks([chipBlock('blk1', 'pctx_a'), chipBlock('blk2', 'pctx_other')]);
        const t = buildCirculationThread(percept([]), { mentions });
        expect(rel(t, RELATION.MENTIONED).blocks).toEqual(['blk1']);
    });

    it('summary is degradation-first and quiet when healthy', () => {
        const healthy = buildCirculationThread(percept(['gnd_1']), {
            grounds: [regionGround('gnd_1', 'region_1')], regions: [{ id: 'region_1' }],
            mentions: mentionsFromBlocks([chipBlock('blk1', 'pctx_a')]),
        });
        expect(threadSummary(healthy)).toBe('mentioned in 1 passage');

        const broken = buildCirculationThread(percept(['gnd_1']), { grounds: [regionGround('gnd_1', 'gone')], regions: [] });
        expect(threadSummary(broken)).toMatch(/no longer resolves/);
    });

    it('no percept, no thread', () => {
        expect(buildCirculationThread(null, {})).toEqual([]);
        expect(threadSummary([])).toBe('');
    });
});
