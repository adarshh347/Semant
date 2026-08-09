import React from 'react';
import { STATUS_COPY } from './inquiryContract';

/**
 * INQUIRY WORKBENCH — one status, rendered as itself.
 *
 * Takes an `{value, known}` field straight from the contract, so the component cannot see a bare
 * string and cannot therefore invent a reading of one. Three cases, and the third is the one that
 * exists on purpose:
 *
 *   · a recognised status  → its own word and its own class
 *   · an ABSENT status     → "no status", never a default
 *   · an UNRECOGNISED one  → the word `unknown`, WITH the raw value beside it
 *
 * The last is the directive's "unknown fields and statuses are not coerced to successful
 * defaults", in pixels. A future backend's `attuned` must not be rounded to `interpretive`
 * because that is the nearest thing this client understands: it renders as unknown, the raw
 * string stays legible, and no stylesheet rule can accidentally give it a familiar treatment
 * because `iw-badge--unknown` is the only class it gets.
 *
 * `measured` and `visible` reach this component only from a backend evidence object. Nothing in
 * the surface derives them — see `isEvidenceGrade` — so there is no code path where a receipt's
 * confident-looking payload arrives here wearing one.
 */
export default function EpistemicBadge({ field, prefix = '' }) {
    if (!field || !field.value) {
        return (
            <span className="iw-badge iw-badge--absent"
                  title="nothing on this object says how it is held">
                {prefix}no status
            </span>
        );
    }

    if (!field.known) {
        return (
            <span className="iw-badge iw-badge--unknown"
                  data-raw={field.value}
                  title={`this client does not recognise "${field.value}"`}>
                {prefix}unknown: <span className="iw-badge-raw">{field.value}</span>
            </span>
        );
    }

    return (
        <span className={`iw-badge iw-badge--${field.value}`}
              data-status={field.value}
              title={STATUS_COPY[field.value] || field.value}>
            {prefix}{field.value}
        </span>
    );
}

/** A claim FORM — what kind of thing is being asserted. Not an epistemic status. */
export function KindBadge({ field }) {
    if (!field || !field.value) return null;
    if (!field.known) {
        return (
            <span className="iw-kind iw-kind--unknown" data-raw={field.value}>
                unknown kind: <span className="iw-badge-raw">{field.value}</span>
            </span>
        );
    }
    return (
        <span className="iw-kind" data-kind={field.value}>{field.value.replace(/_/g, ' ')}</span>
    );
}
