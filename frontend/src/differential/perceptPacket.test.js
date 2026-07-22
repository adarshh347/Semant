import { describe, it, expect } from 'vitest';
import { buildPerceptPacket, packetSummary, INTENT_KEYS, DEFAULT_CONSTRAINTS } from './perceptPacket.js';
import { setGroundRole } from './groundRoles.js';
import { resolveGround } from './grounds.js';
import { mentionsFromBlocks } from '../state/perceptMentions.js';

const percept = (ground_ids = ['gnd_1', 'gnd_2']) => ({
    id: 'pctx_a', expression: 'the arch held against the shadow',
    ground_ids, properties: ['light'], actor: 'creator',
});
const rg = (id, region_id) => ({ id, ground_type: 'region', region_id, label: id });
const chip = (bid, pid) => ({
    id: bid,
    content: `<p><span data-region-ref="" data-inline-type="percept" data-region-ids="gnd_1" data-percept-id="${pid}">x</span></p>`,
});

const resolverFor = (regions, grounds) => (g) => resolveGround(g, { regions, grounds });

describe('Percept Packet — an inspectable request, and nothing is sent', () => {
    const grounds = [rg('gnd_1', 'region_1'), rg('gnd_2', 'region_2')];
    const regions = [{ id: 'region_1' }, { id: 'region_2' }];

    it('a healthy percept: intact evidence, roles carried, constraints defaulted', () => {
        const p = setGroundRole(percept(), 'gnd_1', 'anchor');
        const pkt = buildPerceptPacket(p, {
            postId: 'post_1', grounds, resolve: resolverFor(regions, grounds),
            mentions: mentionsFromBlocks([chip('blk1', 'pctx_a')]),
            blocks: [chip('blk1', 'pctx_a')],
        });

        expect(pkt.packet_version).toBe(1);
        expect(pkt.percept.id).toBe('pctx_a');
        expect(pkt.source.post_id).toBe('post_1');
        expect(pkt.evidence.state).toBe('intact');
        expect(pkt.evidence.note).toBe('cites 2 grounds');
        expect(pkt.grounds.find((g) => g.ground_id === 'gnd_1').role).toBe('anchor');
        expect(pkt.percept.has_roles).toBe(true);
        expect(pkt.manuscript.cited_in_blocks).toEqual(['blk1']);
        expect(pkt.manuscript.context[0].block_id).toBe('blk1');
        expect(pkt.constraints).toEqual(DEFAULT_CONSTRAINTS);
    });

    it('NOTHING IS SENT — the packet says so about itself', () => {
        const pkt = buildPerceptPacket(percept(), { grounds, resolve: resolverFor(regions, grounds) });
        expect(pkt.dispatch.sent).toBe(false);
        expect(pkt.dispatch.run_id).toBeNull();
    });

    it('a degraded percept reports partial evidence, without a cause', () => {
        const pkt = buildPerceptPacket(percept(), {
            grounds, resolve: resolverFor([{ id: 'region_1' }], grounds),
        });
        expect(pkt.evidence.state).toBe('partial');
        expect(pkt.evidence.resolving).toBe(1);
        expect(pkt.evidence.detached).toBe(1);
        expect(pkt.evidence.note).toBe('1 of 2 cited grounds no longer resolves');
        expect(pkt.evidence.note).not.toMatch(/because|re-dissect|deleted|replaced/i);
    });

    it('a wholly detached percept is "detached", not "intact"', () => {
        const pkt = buildPerceptPacket(percept(), { grounds, resolve: resolverFor([], grounds) });
        expect(pkt.evidence.state).toBe('detached');
        expect(pkt.evidence.resolving).toBe(0);
        expect(pkt.evidence.note).toBe('none of the 2 cited grounds still resolves');
    });

    it('WITHOUT a resolver the evidence state is UNKNOWN — never assumed healthy', () => {
        const pkt = buildPerceptPacket(percept(), { grounds });
        expect(pkt.evidence.state).toBe('unknown');
        expect(pkt.evidence.resolving).toBeNull();
        expect(pkt.evidence.detached).toBeNull();
    });

    it('a percept citing nothing is "ungrounded"', () => {
        const pkt = buildPerceptPacket(percept([]), { grounds, resolve: resolverFor(regions, grounds) });
        expect(pkt.evidence.state).toBe('ungrounded');
        expect(pkt.evidence.note).toBe('cites no grounds');
    });

    it('no manuscript mention: empty, and it does not pretend otherwise', () => {
        const pkt = buildPerceptPacket(percept(), { grounds, resolve: resolverFor(regions, grounds) });
        expect(pkt.manuscript.cited_in_blocks).toEqual([]);
        expect(pkt.manuscript.mention_count).toBe(0);
        expect(pkt.manuscript.context).toEqual([]);
    });

    it('counts only mentions of THIS percept', () => {
        const pkt = buildPerceptPacket(percept(), {
            grounds, mentions: mentionsFromBlocks([chip('blk1', 'pctx_a'), chip('blk2', 'pctx_other')]),
        });
        expect(pkt.manuscript.cited_in_blocks).toEqual(['blk1']);
    });

    it('intent defaults to read and rejects an unknown verb', () => {
        expect(buildPerceptPacket(percept(), {}).intent).toBe('read');
        expect(buildPerceptPacket(percept(), { intent: 'challenge' }).intent).toBe('challenge');
        expect(buildPerceptPacket(percept(), { intent: 'hallucinate' }).intent).toBe('read');
        expect(INTENT_KEYS).toContain('transfer');
    });

    it('constraints can be overridden per request, and default conservatively', () => {
        const pkt = buildPerceptPacket(percept(), { constraints: { image_only: false } });
        expect(pkt.constraints.image_only).toBe(false);
        expect(pkt.constraints.ask_for_contradictions).toBe(true);
        expect(pkt.constraints.no_identity_claims).toBe(true);
    });

    it('BACK-COMPAT: a percept with no roles, no mentions and no blocks still builds', () => {
        const pkt = buildPerceptPacket({ id: 'pctx_old', ground_ids: ['gnd_1'] }, {});
        expect(pkt.percept.has_roles).toBe(false);
        expect(pkt.grounds).toHaveLength(1);
        expect(pkt.percept.expression).toBe('');
    });

    it('is JSON-serialisable — it must survive being looked at', () => {
        const pkt = buildPerceptPacket(setGroundRole(percept(), 'gnd_1', 'anchor'), {
            postId: 'post_1', grounds, resolve: resolverFor(regions, grounds),
        });
        expect(JSON.parse(JSON.stringify(pkt))).toEqual(pkt);
    });

    it('no percept, no packet', () => {
        expect(buildPerceptPacket(null, {})).toBeNull();
        expect(buildPerceptPacket({}, {})).toBeNull();
    });
});

describe('packetSummary', () => {
    const grounds = [rg('gnd_1', 'region_1'), rg('gnd_2', 'region_2')];
    const regions = [{ id: 'region_1' }, { id: 'region_2' }];

    it('reads as one honest line', () => {
        const p = setGroundRole(percept(), 'gnd_1', 'anchor');
        const s = packetSummary(buildPerceptPacket(p, {
            grounds, resolve: resolverFor(regions, grounds),
            mentions: mentionsFromBlocks([chip('blk1', 'pctx_a')]),
        }));
        expect(s).toBe('read · cites 2 grounds · 1 role named · in the writing');
    });

    it('says when nothing is named and nothing has crossed', () => {
        const s = packetSummary(buildPerceptPacket(percept(), { grounds, resolve: resolverFor(regions, grounds) }));
        expect(s).toBe('read · cites 2 grounds · no roles named · not yet in the writing');
    });

    it('no packet, no summary', () => {
        expect(packetSummary(null)).toBe('');
    });
});
