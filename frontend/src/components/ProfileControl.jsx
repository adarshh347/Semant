import React, { useCallback, useEffect, useState } from 'react';
import { API_URL } from '../config/api';
import './ProfileControl.css';

/**
 * ProfileControl (VISION-C · C5) — the compact domain-profile control in the real curator
 * workflow. Auto proposes a multi-label profile with confidence + reason; the curator can
 * override by toggling profiles; the scheduled passes show ready/deferred/unavailable.
 * Changing the profile changes which specialist passes the next Dissect schedules
 * (selective scheduling) — not a model-control dashboard.
 */

const BASE = `${API_URL}/api/v1/posts`;
const SPECIALISTS = ['fashion', 'architecture', 'painting'];
// which capability each specialist's primary pass maps to (for the state pill)
const PASS_LABEL = {
  yolo11n_seg: 'YOLO', segformer_b0_ade: 'SegFormer-ADE', sam21_hiera_tiny: 'SAM',
  fashionpedia_r50fpn: 'Fashionpedia', segformer_clothes: 'Garments',
};

export default function ProfileControl({ postId, profile: seed, onProfile }) {
  const [profile, setProfile] = useState(seed || null);
  const [caps, setCaps] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => { setProfile(seed || null); }, [seed]);

  useEffect(() => {
    fetch(`${BASE}/vision/capabilities`)
      .then((r) => r.json())
      .then((d) => setCaps(Object.fromEntries((d.capabilities || []).map((c) => [c.name, c]))))
      .catch(() => {});
  }, []);

  const chosen = profile?.chosen || ['general'];

  const runAuto = useCallback(async () => {
    setBusy(true);
    try {
      const r = await fetch(`${BASE}/${postId}/domain-profile/propose`, { method: 'POST' });
      const d = await r.json();
      setProfile(d.domain_profile); onProfile?.(d.domain_profile);
    } catch { /* */ } finally { setBusy(false); }
  }, [postId, onProfile]);

  const override = useCallback(async (nextChosen) => {
    setBusy(true);
    try {
      const r = await fetch(`${BASE}/${postId}/domain-profile`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chosen: nextChosen }),
      });
      const d = await r.json();
      setProfile(d.domain_profile); onProfile?.(d.domain_profile);
    } catch { /* */ } finally { setBusy(false); }
  }, [postId, onProfile]);

  const toggle = (spec) => {
    const has = chosen.includes(spec);
    const next = has ? chosen.filter((c) => c !== spec) : [...chosen, spec];
    override(next.filter((c) => c !== 'general'));   // service re-adds general first
  };

  const passes = profile?.scheduled_passes || ['yolo11n_seg', 'sam21_hiera_tiny'];
  const reason = profile?.reason || '';
  const auto = profile?.user_overridden === false;

  const passState = (name) => caps[name]?.state || 'ready';

  return (
    <div className="pc" aria-label="Domain profile">
      <div className="pc-row">
        <span className="pc-eyebrow">Profile</span>
        <button className={`pc-chip pc-chip--general is-on`} disabled title="Always on — the cheap general pass">General</button>
        {SPECIALISTS.map((s) => (
          <button key={s} className={`pc-chip ${chosen.includes(s) ? 'is-on' : ''}`}
                  disabled={busy} aria-pressed={chosen.includes(s)}
                  onClick={() => toggle(s)}>{s[0].toUpperCase() + s.slice(1)}</button>
        ))}
        <button className={`pc-auto ${auto ? 'is-on' : ''}`} disabled={busy} onClick={runAuto}
                title="Auto-detect the domains">{busy ? '…' : 'Auto'}</button>
      </div>
      {reason && <p className="pc-reason" title={reason}>{auto ? reason : `${reason}`}</p>}
      <div className="pc-passes">
        {passes.map((p) => (
          <span key={p} className={`pc-pass pc-pass--${passState(p)}`}
                title={`${p} — ${passState(p)}${caps[p]?.reason ? ' · ' + caps[p].reason : ''}`}>
            {PASS_LABEL[p] || p}
            {passState(p) !== 'ready' && <em> · {passState(p)}</em>}
          </span>
        ))}
      </div>
    </div>
  );
}
