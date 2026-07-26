import React, { useState } from 'react';
import { Sparkles } from 'lucide-react';
import useOrchestrate from './useOrchestrate';
import './OrchestrationBar.css';

/**
 * OrchestrationBar (CIRCUIT-001 SURFACE-001) — the intention affordance.
 *
 * "what do you want to do?" → the Director plans + executes → the resolved plan is shown (including
 * the steps that were REFUSED or could not run, with their reason — a partial plan is never
 * hidden) → the produced suggestions land in the existing SuggestionReview for supervised
 * Accept/Dismiss. This component builds NO review surface of its own; it reuses the one every
 * producer feeds.
 */

const STATUS_WORD = {
  ok: 'ran', empty: 'found nothing', unavailable: 'unavailable',
  skipped: 'skipped', error: 'error',
};

export default function OrchestrationBar({ postId, store }) {
  const [intention, setIntention] = useState('');
  const { status, error, plan, provenance, orchestrate } = useOrchestrate(postId, store);

  const run = () => { if (intention.trim() && status !== 'loading') orchestrate(intention); };

  const lineage = provenance?.lineage || [];
  const statusFor = (stepId) => (lineage.find((r) => r.step_id === stepId) || {}).status;
  const ran = plan?.steps || [];
  const refused = plan?.refused || [];
  const emptyPlan = plan && ran.length === 0;

  return (
    <div className="orch-bar" aria-label="Orchestrate">
      <span className="diff-eyebrow"><Sparkles size={12} /> Orchestrate</span>
      <div className="orch-input-row">
        <input
          className="orch-input" type="text" value={intention} aria-label="Intention"
          placeholder="what do you want to do?"
          onChange={(e) => setIntention(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') run(); }}
        />
        <button type="button" className="orch-run" onClick={run}
          disabled={status === 'loading' || !intention.trim()}>
          {status === 'loading' ? '…' : 'Run'}
        </button>
      </div>

      {status === 'error' && (
        <div className="orch-note orch-note--err">Couldn't orchestrate{error ? ` — ${error}` : ''}.</div>
      )}

      {plan && (
        <div className="orch-plan" aria-label="Plan">
          {/* an intention that matched nothing says why, plainly */}
          {emptyPlan && (plan.notes || []).length > 0 && (
            <div className="orch-note">{plan.notes[0]}</div>
          )}
          {ran.map((s) => {
            const st = statusFor(s.step_id) || 'planned';
            return (
              <div key={s.step_id} className={`orch-step is-${st}`}>
                <span className="orch-step-name">{s.actuator}</span>
                <span className="orch-step-status">{STATUS_WORD[st] || 'planned'}</span>
              </div>
            );
          })}
          {/* refused steps are shown, never dropped — with the exact reason */}
          {refused.map((r) => (
            <div key={r.step_id || r.actuator} className="orch-step is-refused">
              <span className="orch-step-name">{r.actuator}</span>
              <span className="orch-step-status" title={r.detail}>refused — {r.detail}</span>
            </div>
          ))}
        </div>
      )}

      {status === 'ready' && (
        <div className="orch-note">Suggestions are in review — accept or dismiss each below.</div>
      )}
      {status === 'empty' && !emptyPlan && (
        <div className="orch-note">The plan ran, but nothing here to suggest.</div>
      )}
    </div>
  );
}
