import React from 'react';
import { createReactInlineContentSpec } from '@blocknote/react';

/**
 * regionRef — the inline chip that references the image, ported to BlockNote
 * (Editor Path B, Phase 3). It replaces main's TipTap `regionRef` mark while
 * keeping the SAME on-disk shape, so nothing downstream has to change:
 *
 *   <span data-region-ref data-ref-kind="part|lens" data-region-ids="…"
 *         data-label="…" class="ref-chip ref-chip--part">label</span>
 *
 * That markup is what the read view (plain HTML via dangerouslySetInnerHTML) and
 * the link machinery (`blockRegionIds` regex on `data-region-ids`) both read — so
 * by emitting it verbatim from `render` and matching it in `parse`, the chip:
 *   - round-trips losslessly through the converter (no data loss on edit+save),
 *   - lights up the same regions in the read view as before,
 *   - still resolves for region↔story highlighting.
 *
 * `parse` matches on `data-region-ref`, so it reads BOTH main's legacy chips
 * (no BlockNote marker) and BlockNote's own re-serialisation.
 *
 * Interaction (hover previews, click highlights the region) is dispatched as DOM
 * CustomEvents so the chip stays decoupled from the region store — PostDetailPage
 * listens and forwards to `regionStore` (hover/focus).
 */

const emit = (name, regionIds) =>
  window.dispatchEvent(
    new CustomEvent(name, { detail: { regionIds: (regionIds || '').split(',').filter(Boolean) } }),
  );

export const regionRefInline = createReactInlineContentSpec(
  {
    type: 'regionRef',
    propSchema: {
      refKind: { default: 'part' },
      regionIds: { default: '' },
      label: { default: '' },
    },
    content: 'none',
  },
  {
    render: (props) => {
      const { refKind, regionIds, label } = props.inlineContent.props;
      return (
        <span
          data-region-ref=""
          data-ref-kind={refKind}
          data-region-ids={regionIds}
          data-label={label}
          className={`ref-chip ref-chip--${refKind}`}
          contentEditable={false}
          onMouseEnter={() => emit('semant:region-hover', regionIds)}
          onMouseLeave={() => emit('semant:region-hover', '')}
          onClick={() => emit('semant:region-focus', regionIds)}
        >
          {label}
        </span>
      );
    },
    // Save exactly main's markup (ref-chip class + data-region-ref), NOT BlockNote's
    // node-view wrapper — so the read view (plain HTML) styles and lights the chip
    // identically. Without this, blocksToHTMLLossy emits .bn-inline-content-section
    // and the read-view chip loses its styling.
    toExternalHTML: (props) => {
      const { refKind, regionIds, label } = props.inlineContent.props;
      return (
        <span
          data-region-ref=""
          data-ref-kind={refKind}
          data-region-ids={regionIds}
          data-label={label}
          className={`ref-chip ref-chip--${refKind}`}
        >
          {label}
        </span>
      );
    },
    // Match main's stored markup (and BlockNote's own re-serialisation) so existing
    // chips survive the first edit instead of flattening to dead text.
    parse: (el) =>
      el.hasAttribute('data-region-ref')
        ? {
            refKind: el.getAttribute('data-ref-kind') || 'part',
            regionIds: el.getAttribute('data-region-ids') || '',
            label: el.getAttribute('data-label') || el.textContent || '',
          }
        : undefined,
  },
);
