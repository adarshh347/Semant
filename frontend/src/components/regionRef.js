import { Node, mergeAttributes } from '@tiptap/core';

/**
 * `regionRef` — an inline reference from the story to something on the image.
 *
 * Two kinds, one node:
 *   part — points at a Region (`/part`). Carries exactly one region id.
 *   lens — cites an Aletheia lens (`/lens`). Carries every region the lens rests on.
 *
 * It is an **atom**: a chip is one indivisible thing, so a caret can't wander into the
 * middle of "Dress" and split the link in half. It is also inline, because a reference
 * belongs inside a sentence — "the /Dress holds the light" — not stranded on its own row.
 *
 * The link lives in the markup, not in a side table. `data-region-ids` survives
 * `editor.getHTML()` → Mongo → `dangerouslySetInnerHTML`, which is what lets the *read*
 * view (plain HTML, no TipTap) light up the same regions the editor does. `parseHTML`
 * closes that loop on the way back in; without it a saved chip would reload as dead
 * text and the story would quietly forget what it was pointing at.
 *
 * `Region.block_id` records the same edge from the other side. Both directions are
 * written, because each is asked a different question: given a region, which block?
 * (the pane's hover) and given a block, which regions? (the chip's click).
 */
const RegionRef = Node.create({
    name: 'regionRef',
    group: 'inline',
    inline: true,
    atom: true,
    selectable: true,

    addAttributes() {
        return {
            refKind: {
                default: 'part',
                parseHTML: (el) => el.getAttribute('data-ref-kind') || 'part',
                renderHTML: (attrs) => ({ 'data-ref-kind': attrs.refKind }),
            },
            // Comma-joined: one id for a part, one-or-more for a lens.
            regionIds: {
                default: '',
                parseHTML: (el) => el.getAttribute('data-region-ids') || '',
                renderHTML: (attrs) => ({ 'data-region-ids': attrs.regionIds }),
            },
            // Held as an attribute as well as the text: the chip's face is the region's
            // label at insert time, and a later re-label must not silently rewrite the
            // sentence the curator already wrote around it.
            label: {
                default: '',
                parseHTML: (el) => el.getAttribute('data-label') || el.textContent || '',
                renderHTML: (attrs) => ({ 'data-label': attrs.label }),
            },
        };
    },

    parseHTML() {
        return [{ tag: 'span[data-region-ref]' }];
    },

    renderHTML({ node, HTMLAttributes }) {
        return ['span', mergeAttributes(HTMLAttributes, {
            'data-region-ref': '',
            class: `ref-chip ref-chip--${node.attrs.refKind}`,
        }), node.attrs.label];
    },

    // Word counts and the AI's view of the story should read the chip as its label,
    // not as an empty node.
    renderText({ node }) {
        return node.attrs.label;
    },

    addCommands() {
        return {
            insertRegionRef: (attrs) => ({ chain }) => chain()
                .focus()
                .insertContent([
                    { type: this.name, attrs },
                    // A trailing space, or the caret lands glued to the atom and the next
                    // keystroke feels like it is being typed inside the chip.
                    { type: 'text', text: ' ' },
                ])
                .run(),
        };
    },
});

export default RegionRef;
