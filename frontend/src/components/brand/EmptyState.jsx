import { Link } from 'react-router-dom';
import RegionMotif from './RegionMotif';
import './states.css';

// A branded empty / error state — a DOOR, not a dead box. Leads with a
// hand-drawn plum region-mark motif, says what the room is for in Fraunces, and
// (almost always) points at the one next action. Honest by design: it never
// fakes a finished feature, and it carries no fabricated progress.
//
// Props:
//   motif   — RegionMotif variant (seed·stack·collect·infer·parts·portrait)
//   title   — the Fraunces headline
//   body    — a short muted line
//   action  — { to, label }  (router Link)  OR  { onClick, label }  (button)
//   tone    — 'default' | 'error'
//   compact — tighter padding for in-tile use (Home Continue tile)
export function EmptyState({ motif = 'seed', title, body, action, tone = 'default', compact = false }) {
  return (
    <div className={`semant-empty${compact ? ' semant-empty--compact' : ''}${tone === 'error' ? ' semant-empty--error' : ''}`} role="status">
      <RegionMotif variant={motif} size={compact ? 52 : 72} />
      {title && <h2 className="semant-empty__title">{title}</h2>}
      {body && <p className="semant-empty__body">{body}</p>}
      {action && action.to && (
        <Link to={action.to} className="semant-empty__action">
          {action.label} <span aria-hidden>→</span>
        </Link>
      )}
      {action && action.onClick && !action.to && (
        <button type="button" className="semant-empty__action" onClick={action.onClick}>
          {action.label} <span aria-hidden>→</span>
        </button>
      )}
    </div>
  );
}

export default EmptyState;
