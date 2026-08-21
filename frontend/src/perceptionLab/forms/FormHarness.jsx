import React, { useState } from 'react';
import FormRendererLab from './FormRendererLab';
import { TARGET_WIDTHS } from '../useContainerWidth';
import { HARNESS_CASES } from './harnessCases';
import './forms.css';

/**
 * PERCEPTUAL-FORMS-001E — the responsive and dark-mode proof, as a page.
 *
 * FOUR WIDTHS IN ONE VIEWPORT. The laboratory keys its layout off the width of its own container,
 * not the window, so 1100 / 720 / 430 / 320 can be proved side by side without resizing anything —
 * and a person can drag a pane past a boundary and watch `data-w` change. That is a better proof
 * than four screenshots, because it shows the transition rather than the endpoints.
 *
 * Each pane is a full laboratory with its own state, so the narrow one can be driven while the
 * wide one sits at a different form. The screenshot script drives this page.
 */

export default function FormHarness({ initialCase = 0 }) {
    const [index, setIndex] = useState(initialCase);
    const scene = HARNESS_CASES[index] ?? HARNESS_CASES[0];

    return (
        <div className="pl-fm-harness" data-harness data-harness-case={scene.key}>
            <div className="pl-fm-bar">
                <span className="pl-fm-kicker">form renderer harness</span>
                <h1 className="pl-fm-title">{scene.label}</h1>
                <p className="pl-fm-question">{scene.why}</p>
            </div>
            <ul className="pl-fm-tabs" data-harness-picker={HARNESS_CASES.length}>
                {HARNESS_CASES.map((c, i) => (
                    <li key={c.key}>
                        <button type="button" className="pl-fm-tab" data-harness-option={c.key}
                            aria-pressed={i === index} onClick={() => setIndex(i)}>
                            {c.label}
                        </button>
                    </li>
                ))}
            </ul>

            <div className="pl-fm-harnessgrid">
                {TARGET_WIDTHS.map((width) => (
                    <figure key={width} className="pl-fm-harnessfig">
                        <figcaption className="pl-fm-harnesscap" data-harness-caption={width}>
                            {width}px
                        </figcaption>
                        <div className="pl-fm-harnesspane" data-harness-width={width}>
                            {/* KEYED BY THE CASE. `initialForm` and `initialView` are initial
                                state, so without a key React would keep the pane's own state and
                                switching case would change the caption and nothing else — which
                                is exactly the bug where a screenshot index and its captions
                                describe different pictures. */}
                            <FormRendererLab
                                key={scene.key}
                                initialForm={scene.form}
                                initialView={scene.view}
                                now={scene.at}
                            />
                        </div>
                    </figure>
                ))}
            </div>
        </div>
    );
}
