import React, { useContext } from 'react';
import { createReactBlockSpec } from '@blocknote/react';
import { RegionStoreContext } from '../../state/regionStore';
import './partRefBlock.css';

/**
 * partRef — the /part BLOCK form (Chiasm, Phase 4b). Where the inline chip is prose
 * rhythm ("the [drape] holds the light"), this is *sustained attention*: an evidence
 * block that lifts the region out of the image and sets it in the writing — the
 * region crop + its label + who marked it.
 *
 * It stores REFERENCES, never copies: `regionId` / `perceptId` / `mentionId`. The
 * crop is resolved by reference — the block reads the store via context and cuts the
 * region's box out of the live image, so if the geometry later improves the evidence
 * follows. On-disk it round-trips as
 *   <div data-part-block data-inline-type="part-block" data-region-id data-region-ids
 *        data-percept-id data-mention-id data-origin data-label>label</div>
 * (toExternalHTML + parse), so the converter preserves every reference attr.
 *
 * createReactBlockSpec returns a FACTORY in BlockNote 0.51 — call partRefBlock().
 */

// Crop the region's normalized box out of the image into a fixed-height frame.
function RegionCrop({ box, src, label }) {
  if (!src || !box || !box.w || !box.h) {
    return <div className="bn-partref__crop bn-partref__crop--empty" aria-hidden />;
  }
  // Scale the image so the box fills the frame, then offset to the box's origin.
  const style = {
    backgroundImage: `url(${src})`,
    backgroundSize: `${100 / box.w}% ${100 / box.h}%`,
    backgroundPosition: `${(box.x / (1 - box.w || 1)) * 100}% ${(box.y / (1 - box.h || 1)) * 100}%`,
  };
  return <div className="bn-partref__crop" style={style} role="img" aria-label={`Region: ${label}`} />;
}

function PartRefBlock({ block }) {
  const { label, regionId, origin } = block.props;
  const store = useContext(RegionStoreContext);
  const region = store?.regionById?.(regionId) || null;
  const focused = !!store?.focusIds && store.focusIds.has(regionId);

  return (
    <div
      className={`bn-partref${focused ? ' is-focus' : ''}`}
      data-region-id={regionId || undefined}
      contentEditable={false}
      onMouseEnter={() => window.dispatchEvent(new CustomEvent('semant:region-hover', { detail: { regionIds: [regionId] } }))}
      onMouseLeave={() => window.dispatchEvent(new CustomEvent('semant:region-hover', { detail: { regionIds: [] } }))}
      onClick={() => window.dispatchEvent(new CustomEvent('semant:region-focus', { detail: { regionIds: [regionId] } }))}
    >
      <RegionCrop box={region?.box} src={store?.photoUrl} label={label} />
      <div className="bn-partref__body">
        <span className="bn-partref__kind">◈ part</span>
        <span className="bn-partref__label">{label}</span>
        {origin && origin !== 'human' && <span className="bn-partref__origin">{origin}</span>}
      </div>
    </div>
  );
}

// Shared markup builder so render's data-* and the on-disk HTML can't drift.
function partBlockAttrs({ regionId, perceptId, mentionId, origin, label }) {
  const a = {
    'data-part-block': '',
    'data-inline-type': 'part-block',
    'data-region-ids': regionId || '',
    'data-label': label || 'part',
  };
  if (regionId) a['data-region-id'] = regionId;
  if (perceptId) a['data-percept-id'] = perceptId;
  if (mentionId) a['data-mention-id'] = mentionId;
  if (origin) a['data-origin'] = origin;
  return a;
}

export const partRefBlock = createReactBlockSpec(
  {
    type: 'partRef',
    propSchema: {
      label: { default: 'a part' },
      regionId: { default: '' },
      perceptId: { default: '' },
      mentionId: { default: '' },
      origin: { default: 'human' },
    },
    content: 'none',
  },
  {
    render: (props) => <PartRefBlock block={props.block} />,
    toExternalHTML: (props) => {
      const p = props.block.props;
      return <div {...partBlockAttrs(p)}>{p.label}</div>;
    },
    parse: (el) =>
      el.hasAttribute('data-part-block')
        ? {
            regionId: el.getAttribute('data-region-id') || el.getAttribute('data-region-ids') || '',
            perceptId: el.getAttribute('data-percept-id') || '',
            mentionId: el.getAttribute('data-mention-id') || '',
            origin: el.getAttribute('data-origin') || 'human',
            label: el.getAttribute('data-label') || el.textContent || 'part',
          }
        : undefined,
  },
);
