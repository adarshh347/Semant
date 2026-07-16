// The shortcuts sheet — opened by `?` (or a command-palette action). Reuses the
// plum Radix dialog; lists the same navigation sequences GlobalShortcuts binds,
// plus ⌘K and Esc, so the reference can't drift from the bindings.
import { useEffect, useState } from 'react';
import { Dialog, DialogContent } from './ui';
import { GOTO_SHORTCUTS } from './GlobalShortcuts';
import './ShortcutsDialog.css';

// Render "g h" as two <kbd> chips, "⌘ K" likewise.
function Keys({ combo }) {
  return (
    <span className="sc-keys">
      {combo.split(' ').map((k, i) => (
        <kbd key={i} className="sc-kbd">{k}</kbd>
      ))}
    </span>
  );
}

const GLOBAL = [
  ['⌘ K', 'Command palette · search'],
  ['?', 'This shortcuts sheet'],
  ['Esc', 'Close a dialog or menu'],
];

export default function ShortcutsDialog() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener('semant:open-shortcuts', onOpen);
    return () => window.removeEventListener('semant:open-shortcuts', onOpen);
  }, []);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent title="Keyboard shortcuts" description="Move around Semant without the mouse." size="sm">
        <div className="sc-group">
          <span className="eyebrow sc-group-label">Go to</span>
          <ul className="sc-list">
            {GOTO_SHORTCUTS.map(([combo, label]) => (
              <li key={combo} className="sc-row">
                <span className="sc-label">{label}</span>
                <Keys combo={combo} />
              </li>
            ))}
          </ul>
        </div>
        <div className="sc-group">
          <span className="eyebrow sc-group-label">Global</span>
          <ul className="sc-list">
            {GLOBAL.map(([combo, label]) => (
              <li key={combo} className="sc-row">
                <span className="sc-label">{label}</span>
                <Keys combo={combo} />
              </li>
            ))}
          </ul>
        </div>
      </DialogContent>
    </Dialog>
  );
}
