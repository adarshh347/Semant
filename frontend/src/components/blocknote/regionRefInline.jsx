import React, { useContext } from 'react';
import { createReactInlineContentSpec } from '@blocknote/react';
import { RegionStoreContext } from '../../state/regionStore';

/**
 * regionRef — the inline chip that references the image, as a BlockNote custom
 * inline content (Editor Path B / Chiasm, Phase 3). It replaces main's TipTap
 * `regionRef` mark and carries the Mention-model reference identity in the markup:
 *
 *   <span data-region-ref data-inline-type="part|lens"
 *         data-region-ids="reg_1,reg_2" data-region-id="reg_1"
 *         data-percept-id="pct_creator_reg_1" data-mention-id="men_…"
 *         data-label="…" class="ref-chip ref-chip--part">label</span>
 *
 * These data-* attrs are treated as SEMANTIC, not incidental — the read view (plain
 * HTML via dangerouslySetInnerHTML), the link machinery (regex on `data-region-ids`),
 * and the Mention join all read them, so `blocksToHTMLLossy` must not drop them. The
 * converter's gated test asserts each survives import→export.
 *
 * Back-compat: `data-region-ref` + `data-ref-kind` + `data-region-ids` are still
 * emitted, and `parse` matches on `data-region-ref`, so main's legacy chips AND
 * BlockNote's own re-serialisation both reload as live chips (no flatten, no loss).
 *
 * Interaction (hover previews, click highlights the region) is dispatched as DOM
 * CustomEvents so the chip stays decoupled from the store — PostDetailPage listens.
 */

const emit = (name, regionIds) =>
  window.dispatchEvent(
    new CustomEvent(name, { detail: { regionIds: (regionIds || '').split(',').filter(Boolean) } }),
  );

// The full reference markup — one place, so render and toExternalHTML can't drift.
// Populated attrs only; a bare /part with no percept/mention yet just omits them.
function chipAttrs({ refKind, regionIds, perceptId, mentionId, label }) {
  const regionId = (regionIds || '').split(',').filter(Boolean)[0] || '';
  const a = {
    'data-region-ref': '',
    'data-ref-kind': refKind,        // legacy name (back-compat)
    'data-inline-type': refKind,     // canonical (Phase 3)
    'data-region-ids': regionIds,    // comma-joined; read view + link machinery
    'data-label': label,
    className: `ref-chip ref-chip--${refKind}`,
  };
  if (regionId) a['data-region-id'] = regionId;   // singular reference
  if (perceptId) a['data-percept-id'] = perceptId; // Mention: which percept
  if (mentionId) a['data-mention-id'] = mentionId; // Mention: the edge id
  return a;
}

// The editor-side chip. Reads the store via context so it lights ITSELF when its
// region is focused — React owns the class (nothing for an imperative toggle to
// wipe), keeping the highlight purely store-driven.
function RegionRefChip({ p }) {
  const store = useContext(RegionStoreContext);
  const ids = (p.regionIds || '').split(',').filter(Boolean);
  const focused = !!store?.focusIds && ids.some((id) => store.focusIds.has(id));
  const attrs = chipAttrs(p);
  return (
    <span
      {...attrs}
      className={`${attrs.className}${focused ? ' is-focus' : ''}`}
      contentEditable={false}
      role="button"
      tabIndex={0}
      aria-label={`Region reference: ${p.label}`}
      onMouseEnter={() => emit('semant:region-hover', p.regionIds)}
      onMouseLeave={() => emit('semant:region-hover', '')}
      // a11y: keyboard focus illuminates the region the same as hover.
      onFocus={() => emit('semant:region-hover', p.regionIds)}
      onBlur={() => emit('semant:region-hover', '')}
      onClick={() => emit('semant:region-focus', p.regionIds)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); emit('semant:region-focus', p.regionIds); } }}
    >
      {p.label}
    </span>
  );
}

export const regionRefInline = createReactInlineContentSpec(
  {
    type: 'regionRef',
    propSchema: {
      refKind: { default: 'part' },
      regionIds: { default: '' },
      perceptId: { default: '' },
      mentionId: { default: '' },
      label: { default: '' },
    },
    content: 'none',
  },
  {
    render: (props) => <RegionRefChip p={props.inlineContent.props} />,
    // Save exactly this markup (ref-chip + the data-* identity), NOT BlockNote's
    // node-view wrapper — so the read view styles and resolves the chip identically.
    toExternalHTML: (props) => {
      const p = props.inlineContent.props;
      return <span {...chipAttrs(p)}>{p.label}</span>;
    },
    // Read every reference attr back (new names first, legacy fallback), so both
    // main's legacy chips and BlockNote's re-serialisation reload losslessly.
    parse: (el) =>
      el.hasAttribute('data-region-ref')
        ? {
            refKind: el.getAttribute('data-inline-type') || el.getAttribute('data-ref-kind') || 'part',
            regionIds: el.getAttribute('data-region-ids') || el.getAttribute('data-region-id') || '',
            perceptId: el.getAttribute('data-percept-id') || '',
            mentionId: el.getAttribute('data-mention-id') || '',
            label: el.getAttribute('data-label') || el.textContent || '',
          }
        : undefined,
  },
);
