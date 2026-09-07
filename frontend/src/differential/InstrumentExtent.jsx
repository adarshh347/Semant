import React, { useId } from 'react';
import { Minus, Plus } from 'lucide-react';
import {
    positionToValue, valueToPosition, stepUp, stepDown,
    extentLabel, extentShort, presetFor,
} from './instrumentScale';

/**
 * One control for "how much of the image does this mark cover" — shared by the
 * brush's radius and the boundary's band width, because they are the same kind
 * of quantity and deserve the same instrument.
 *
 * Kept visually and linguistically apart from the intensity registers beside it:
 *
 *     Size     — 4.5% of image width
 *     Register — 3 Structural
 *
 * They are orthogonal channels. Size is how much the mark covers; register is how
 * intensely it participates. A curator who reads them as one dial will paint a
 * broad stroke when they meant a dominant one.
 *
 * A neutral swatch renders the current extent beside the slider so a keyboard
 * user — who never has a pointer over the image, and so never sees the live
 * cursor preview — can still see what they are choosing.
 */
export default function InstrumentExtent({
    label = 'Size', value, onChange, range, presets = null,
    shortcutHint = '[ ]', swatchMax = 34,
}) {
    const id = useId();
    const pos = valueToPosition(value, range);

    // The swatch is proportional to the value across the range, floored so the
    // finest setting is still visible rather than vanishing to a dot.
    const px = Math.max(4, Math.round(swatchMax * (0.18 + 0.82 * pos)));

    return (
        <div className="diff-extent" role="group" aria-label={label}>
            <div className="diff-extent-head">
                <label className="diff-extent-label" htmlFor={id}>{label}</label>
                <output className="diff-extent-value" htmlFor={id}>{extentShort(value)}</output>
                <span className="diff-extent-keys" aria-hidden="true">{shortcutHint}</span>
            </div>

            <div className="diff-extent-row">
                <button type="button" className="diff-vp-btn"
                    onClick={() => onChange(stepDown(value, range))}
                    disabled={value <= range.min}
                    aria-label={`Decrease ${label.toLowerCase()}`} title={`Smaller ( [ )`}>
                    <Minus size={13} />
                </button>

                {/* The slider carries the real value in its ARIA text, not the 0..1
                    track position — "0.62" would tell a screen-reader user nothing
                    about the mark they are about to make. */}
                <input
                    id={id} type="range" className="diff-extent-slider"
                    min={0} max={1} step={0.001} value={pos}
                    onChange={(e) => onChange(positionToValue(Number(e.target.value), range))}
                    aria-valuetext={extentLabel(value)}
                />

                <button type="button" className="diff-vp-btn"
                    onClick={() => onChange(stepUp(value, range))}
                    disabled={value >= range.max}
                    aria-label={`Increase ${label.toLowerCase()}`} title={`Larger ( ] )`}>
                    <Plus size={13} />
                </button>

                <span className="diff-extent-swatch" aria-hidden="true"
                    style={{ width: px, height: px }} />
            </div>

            {presets && (
                <div className="diff-extent-presets" role="group" aria-label={`${label} presets`}>
                    {presets.map((p) => (
                        <button key={p.key} type="button"
                            className={`diff-extent-preset${presetFor(value, presets) === p.key ? ' on' : ''}`}
                            aria-pressed={presetFor(value, presets) === p.key}
                            onClick={() => onChange(p.value)}>{p.label}</button>
                    ))}
                </div>
            )}
        </div>
    );
}
