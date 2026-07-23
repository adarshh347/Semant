import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import GroundLayers from './GroundLayers';

/**
 * CIRCUIT-001 P3-B — GroundLayers renders the completed instrument set honestly:
 *   (2a) an ambiguous trace shows a soft terminus, never a sharp arrowhead; a
 *        detached endpoint reads as a distinct hollow ring.
 *   (2b) a relation whose member no longer resolves DEGRADES — it never crashes.
 *   (2d) the evidence layer's visibility control wraps the committed grounds.
 *
 * A square natural size makes normalized coords equal viewBox px / 1000; a fake
 * content box lets the svg mount (jsdom has no layout).
 */

let container; let root;
async function mount(node) { await act(async () => { root.render(node); }); }
beforeEach(() => { container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
afterEach(async () => { await act(async () => { root.unmount(); }); container.remove(); });

const NAT = { w: 1000, h: 1000 };
const CONTENT = { x: 0, y: 0, w: 1000, h: 1000 };
const pathGround = (extra) => ({ id: 'g_path', ground_type: 'path', points: [[0.2, 0.5], [0.5, 0.5], [0.8, 0.5]], ...extra });

describe('GroundLayers — P3-B honest termini', () => {
    it('a plain path shows an arrowhead chevron, no soft terminus', async () => {
        await mount(<GroundLayers grounds={[pathGround()]} natural={NAT} content={CONTENT} />);
        expect(container.querySelector('.gl-path-chevron')).not.toBeNull();
        expect(container.querySelector('.gl-path-soft')).toBeNull();
    });

    it('(2a) an ambiguous trace replaces the arrowhead with a soft terminus', async () => {
        await mount(<GroundLayers grounds={[pathGround({ ambiguous: true })]} natural={NAT} content={CONTENT} />);
        expect(container.querySelector('.gl-path-soft')).not.toBeNull();
        expect(container.querySelector('.gl-path-chevron')).toBeNull();
    });

    it('(2a) arrowhead:false suppresses the chevron', async () => {
        await mount(<GroundLayers grounds={[pathGround({ arrowhead: false })]} natural={NAT} content={CONTENT} />);
        expect(container.querySelector('.gl-path-chevron')).toBeNull();
        expect(container.querySelector('.gl-path-soft')).toBeNull();
    });

    it('(2a) a detached endpoint reads as a distinct hollow ring', async () => {
        const g = pathGround({ anchors: { from: null, to: { kind: 'ground', ref: 'gone', at: [0.8, 0.5], detached_from_ref: true } } });
        await mount(<GroundLayers grounds={[g]} natural={NAT} content={CONTENT} />);
        expect(container.querySelector('.gl-anchor-detached')).not.toBeNull();
    });
});

describe('GroundLayers — P3-B relation degrades, never crashes (2b)', () => {
    it('a relation with an unresolvable member renders without throwing', async () => {
        const rel = { id: 'g_rel', ground_type: 'relation', member_ids: ['does_not_exist_1', 'does_not_exist_2'] };
        // The point is that mount() does not throw; with no resolvable members the
        // connector simply does not draw (compositionNodes yields < 2 nodes).
        await mount(<GroundLayers grounds={[rel]} natural={NAT} content={CONTENT} />);
        expect(container.querySelector('.gl-svg')).not.toBeNull();
        expect(container.querySelector('.gl-relation-connector')).toBeNull();
    });

    it('a relation with one resolvable member and one dangling still does not crash', async () => {
        const grounds = [
            pathGround(),   // resolvable member centre
            { id: 'g_rel', ground_type: 'relation', member_ids: ['g_path', 'dangling'] },
        ];
        await mount(<GroundLayers grounds={grounds} natural={NAT} content={CONTENT} />);
        expect(container.querySelector('.gl-svg')).not.toBeNull();
    });
});

describe('GroundLayers — P3-B evidence layer visibility (2d)', () => {
    it('evidenceVisible=false collapses the committed group to opacity 0', async () => {
        await mount(<GroundLayers grounds={[pathGround()]} natural={NAT} content={CONTENT} evidenceVisible={false} />);
        const group = container.querySelector('.gl-evidence');
        expect(group).not.toBeNull();
        expect(group.style.opacity).toBe('0');
    });

    it('evidenceOpacity flows onto the committed group', async () => {
        await mount(<GroundLayers grounds={[pathGround()]} natural={NAT} content={CONTENT} evidenceOpacity={0.3} />);
        expect(container.querySelector('.gl-evidence').style.opacity).toBe('0.3');
    });
});
