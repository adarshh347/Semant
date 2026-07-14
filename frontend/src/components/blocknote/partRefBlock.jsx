import React from 'react';
import { createReactBlockSpec } from '@blocknote/react';

/**
 * Phase 0 spike — a trivial custom block, `partRef`.
 *
 * It exists only to prove BlockNote's schema extension point works: a block type we
 * declare, rendered by our own React component, carrying our own props. This is the seam
 * the real `/part` (a region reference) and `/lens` (an Aletheia reading) blocks will use
 * in Phase 3 — the moat stays ours, expressed through BlockNote's API rather than a raw
 * TipTap mark. Nothing here is wired to real Region/aletheia data yet; that is Phase 3.
 */
export const partRefBlock = createReactBlockSpec(
    {
        type: 'partRef',
        // our own props — the same shape provenance/links will ride on later
        propSchema: {
            label: { default: 'an untethered part' },
            regionId: { default: '' },
        },
        content: 'none', // an atom; no editable inline content
    },
    {
        render: ({ block }) => {
            const { label, regionId } = block.props;
            return (
                <div className="bn-partref" data-region-id={regionId || undefined} contentEditable={false}>
                    <span className="bn-partref__kind">◈ part</span>
                    <span className="bn-partref__label">{label}</span>
                </div>
            );
        },
    },
);
