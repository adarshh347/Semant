import { describe, it, expect } from 'vitest';
import {
    emptyHandoff, requestHandoff, canFlush, completeHandoff, wasDelivered, handoffStatus,
} from './manuscriptHandoff.js';

const p = (id) => ({ id, expression: 'the upper head', ground_ids: ['gnd_1'] });

describe('Manuscript handoff — the crossing survives an editor that is not there yet', () => {
    it('queues a percept instead of dropping it', () => {
        const s = requestHandoff(emptyHandoff(), p('pctx_a'));
        expect(s.percept.id).toBe('pctx_a');
    });

    it('REFUSES to flush while the editor is absent — the P1A bug, pinned', () => {
        const s = requestHandoff(emptyHandoff(), p('pctx_a'));
        // Arriving from Differential the curator is usually not editing, so
        // <Manuscript> is unmounted and the ref is null. P1A called insertRef
        // anyway; insertRef returned silently and the percept was lost.
        expect(canFlush(s, { isEditing: false, hasHandle: false })).toBe(false);
        expect(canFlush(s, { isEditing: true, hasHandle: false })).toBe(false);
        expect(canFlush(s, { isEditing: false, hasHandle: true })).toBe(false);
        // …and the request is still there, waiting.
        expect(s.percept.id).toBe('pctx_a');
    });

    it('flushes once every condition holds', () => {
        const s = requestHandoff(emptyHandoff(), p('pctx_a'));
        expect(canFlush(s, { isEditing: true, hasHandle: true })).toBe(true);
    });

    it('nothing pending never flushes', () => {
        expect(canFlush(emptyHandoff(), { isEditing: true, hasHandle: true })).toBe(false);
    });

    it('DELIVERS AT MOST ONCE — a remount cannot mint a second chip', () => {
        let s = requestHandoff(emptyHandoff(), p('pctx_a'));
        s = completeHandoff(s);
        expect(s.percept).toBeNull();
        expect(canFlush(s, { isEditing: true, hasHandle: true })).toBe(false);
        expect(wasDelivered(s, 'pctx_a')).toBe(true);
    });

    it('a double-click is one crossing, not two', () => {
        let s = requestHandoff(emptyHandoff(), p('pctx_a'));
        const again = requestHandoff(s, p('pctx_a'));
        expect(again).toBe(s);            // same object — no re-queue, no re-render
    });

    it('but a percept may be carried into the writing more than once, deliberately', () => {
        let s = completeHandoff(requestHandoff(emptyHandoff(), p('pctx_a')));
        s = requestHandoff(s, p('pctx_a'));
        expect(s.percept.id).toBe('pctx_a');
        expect(canFlush(s, { isEditing: true, hasHandle: true })).toBe(true);
    });

    it('a second, different percept queues while the first is pending', () => {
        let s = requestHandoff(emptyHandoff(), p('pctx_a'));
        s = requestHandoff(s, p('pctx_b'));
        expect(s.percept.id).toBe('pctx_b');
    });

    it('ignores a percept with no id', () => {
        expect(requestHandoff(emptyHandoff(), null)).toEqual(emptyHandoff());
        expect(requestHandoff(emptyHandoff(), {})).toEqual(emptyHandoff());
    });

    it('completing nothing is a no-op', () => {
        const s = emptyHandoff();
        expect(completeHandoff(s)).toBe(s);
    });
});

describe('handoffStatus — derived from mentions, never from a "sent" flag', () => {
    it('says where the noticing got to', () => {
        expect(handoffStatus(1)).toBe('in the writing · 1 passage');
        expect(handoffStatus(3)).toBe('in the writing · 3 passages');
    });

    it('says the true part when the passage is unknown — an empty document has no block id', () => {
        // The chip is in the writing; where exactly is not yet knowable. Saying
        // nothing would under-report a crossing that really happened.
        expect(handoffStatus(0, 1)).toBe('in the writing');
    });

    it('says nothing when it has not crossed — and when the chip is gone again', () => {
        // 0 is what a deleted chip produces. A stored "sent" flag would keep
        // claiming the crossing; this cannot.
        expect(handoffStatus(0)).toBe('');
        expect(handoffStatus(undefined)).toBe('');
    });
});
