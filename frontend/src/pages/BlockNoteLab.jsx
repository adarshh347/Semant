import React from 'react';
import {
    BlockNoteSchema,
    defaultBlockSpecs,
    filterSuggestionItems,
    insertOrUpdateBlockForSlashMenu,
} from '@blocknote/core';
import {
    useCreateBlockNote,
    getDefaultReactSlashMenuItems,
    SuggestionMenuController,
} from '@blocknote/react';
import { BlockNoteView } from '@blocknote/mantine';

// BlockNote's own styles first, our token overrides last (so they win on source order).
import '@blocknote/core/fonts/inter.css';
import '@blocknote/mantine/style.css';

import { useTheme } from '../context/ThemeContext';
import { partRefBlock } from '../components/blocknote/partRefBlock';
import './BlockNoteLab.css';

/**
 * Dev harness for the BlockNote spike (Editor Path B · Phase 0).
 *
 *   /lab/blocknote
 *
 * Not linked from the app. It stands BlockNote up in isolation to prove three things
 * before any real wiring (Phase 2 touches PostDetailPage) happens:
 *   1. our design tokens theme it — light and dark, via BlockNote's CSS variables;
 *   2. a custom block (`partRef`) renders through BlockNote's schema API — the seam the
 *      real /part and /lens moat blocks will use;
 *   3. a custom slash item inserts that block, alongside the default items.
 *
 * The document is a single BlockNote instance — the N→1 move that is the whole latency
 * point of Path B (today: one TipTap editor per block).
 */

// (2) register the custom block on the schema — the extension point Phase 3 relies on.
const labSchema = BlockNoteSchema.create({
    blockSpecs: {
        ...defaultBlockSpecs,
        // createReactBlockSpec returns a factory in BlockNote 0.51 — call it to get the spec.
        partRef: partRefBlock(),
    },
});

// (3) a custom slash item that inserts the custom block.
function insertPartRefItem(editor) {
    return {
        title: 'Part (stub)',
        subtext: 'Insert a region reference — proves the /part extension point',
        aliases: ['part', 'region', 'partref'],
        group: 'Drishya',
        icon: <span aria-hidden>◈</span>,
        onItemClick: () =>
            insertOrUpdateBlockForSlashMenu(editor, {
                type: 'partRef',
                props: { label: 'the collar’s turned edge' },
            }),
    };
}

export default function BlockNoteLab() {
    const { theme, toggleTheme } = useTheme();

    const editor = useCreateBlockNote({
        schema: labSchema,
        initialContent: [
            { type: 'heading', props: { level: 2 }, content: 'A single BlockNote document' },
            {
                type: 'paragraph',
                content:
                    'One ProseMirror document, not one editor per block. Type “/” to open the slash menu — the default items plus our custom “Part (stub)”. Drag the handle on the left to reorder; hover a block for the ＋ and ⠿ side menu.',
            },
            {
                type: 'quote',
                content:
                    'The moat stays ours: /part and /lens become custom blocks we own, not library features we rent.',
            },
            { type: 'partRef', props: { label: 'the collar’s turned edge', regionId: 'demo_r1' } },
            { type: 'paragraph', content: 'Below is the custom block, rendered by our own React component.' },
        ],
    });

    return (
        <div className="bnlab">
            <header className="bnlab-bar">
                <span className="bnlab-kicker">BlockNote · Editor Path B · Phase 0 spike</span>
                <nav className="bnlab-actions">
                    <button className="bnlab-btn" onClick={toggleTheme}>
                        {theme === 'dark' ? '☾ dark' : '☀ light'} · toggle
                    </button>
                </nav>
                <span className="bnlab-meta">custom block: partRef · slash: /part</span>
            </header>

            <div className="bnlab-canvas">
                <div className="bnlab-doc">
                    <BlockNoteView editor={editor} theme={theme} slashMenu={false}>
                        <SuggestionMenuController
                            triggerCharacter="/"
                            getItems={async (query) =>
                                filterSuggestionItems(
                                    [...getDefaultReactSlashMenuItems(editor), insertPartRefItem(editor)],
                                    query,
                                )
                            }
                        />
                    </BlockNoteView>
                </div>
            </div>
        </div>
    );
}
