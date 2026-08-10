import React, { useState } from 'react';
import PerceptionLab from './PerceptionLab';
import { TARGET_WIDTHS, widthBand } from './useContainerWidth';
import { createFixtureClient } from './clients/fixtureClient';
import { HARNESS_SCENARIOS } from './harnessScenarios';
import './perceptionLab.css';

/**
 * PERCEPTUAL-ORGANS-002 Lane E — the whole laboratory, at every width and in both themes, at once.
 *
 * WHY THIS EXISTS AS A COMPONENT AND NOT AS A CHECKLIST. The failures this build is asking about
 * are not "does it fit": they are "does the mask still land on the thing it measured when the pane
 * is 320px", and "is the difference between `refused` and `empty` still legible when the inspector
 * has collapsed under the stage". Neither survives being checked once by hand. Rendering every
 * width simultaneously means a regression at 430px is visible while you are looking at 1100px.
 *
 * The panes are `resize: horizontal`, so a person can drag past the named widths and watch the
 * band attribute change — the four numbers are where the build asks, not where the layout works.
 *
 * THE SCENARIOS ARE THE POINT. A harness that only showed a happy path would prove that a working
 * laboratory fits in a phone. The states below are the ones that are hard to render honestly when
 * space runs out: nothing found, everything found, an adapter that is not here, a refusal.
 */

export default function ResponsiveHarness({ widths = TARGET_WIDTHS }) {
    const [scenario, setScenario] = useState(HARNESS_SCENARIOS[0]);
    const [theme, setTheme] = useState('light');

    return (
        <div className="pl-harness" data-theme={theme} data-harness>
            <div className="pl-harness-bar">
                <span className="pl-kicker">Perception laboratory · responsive proof</span>
                <span className="pl-segmented" role="group" aria-label="Scenario">
                    {HARNESS_SCENARIOS.map((s) => (
                        <button key={s.key} type="button" className="pl-btn"
                            data-scenario={s.key} aria-pressed={scenario.key === s.key}
                            onClick={() => setScenario(s)}>
                            {s.label}
                        </button>
                    ))}
                </span>
                <span className="pl-segmented" role="group" aria-label="Theme">
                    <button type="button" className="pl-btn" data-theme-option="light"
                        aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>
                        Light
                    </button>
                    <button type="button" className="pl-btn" data-theme-option="dark"
                        aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>
                        Dark
                    </button>
                </span>
                <span className="pl-bar-spacer" />
                <span className="pl-chip">{widths.join(' · ')} px</span>
            </div>

            <p className="pl-panel-sub" data-scenario-why>{scenario.why}</p>

            <div className="pl-harness-grid">
                {widths.map((width) => (
                    <figure key={`${scenario.key}-${width}`} className="pl-harness-figure">
                        <figcaption className="pl-harness-caption">
                            <span className="pl-chip" data-expected-band={widthBand(width)}>
                                {width}px · {widthBand(width)}
                            </span>
                        </figcaption>
                        {/*
                          * The width comes from the STYLESHEET, keyed off this attribute — the
                          * four the build names each have a rule in `perceptionLab.css`. An
                          * inline `style` here would be one hardcoded value the design tokens do
                          * not govern, in the one file whose job is to prove they do.
                          */}
                        <div className="pl-harness-pane" data-harness-width={width}>
                            <PerceptionLab
                                key={`${scenario.key}-${width}-${theme}`}
                                client={createFixtureClient(scenario.options)} />
                        </div>
                    </figure>
                ))}
            </div>
        </div>
    );
}
