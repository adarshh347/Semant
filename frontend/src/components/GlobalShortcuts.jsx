// App-wide keyboard shortcuts (OSS: react-hotkeys-hook). A GitHub-style `g`
// prefix for navigation, plus `?` for the shortcuts sheet. ⌘K (the command
// palette) is owned by CommandPalette; we don't redefine it here.
//
// Renders nothing — it just mounts the hotkeys. react-hotkeys-hook disables
// these while a form field is focused (its default), so typing never triggers
// navigation.
import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useHotkeys } from 'react-hotkeys-hook';

// Don't fire shortcuts while the user is typing.
function inFormField(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

// `g` then a letter, within the sequence window. Kept in one place so the help
// sheet can render the exact same list.
export const GOTO_SHORTCUTS = [
  ['g h', 'Home', '/home'],
  ['g g', 'Gallery', '/gallery'],
  ['g r', 'Read', '/feed'],
  ['g a', 'Atelier', '/atelier'],
  ['g y', 'You', '/you'],
];

const SEQ = { sequenceTimeoutMs: 1200 };

export default function GlobalShortcuts() {
  const navigate = useNavigate();

  // Navigation sequences (react-hotkeys-hook uses `>` as the sequence delimiter).
  useHotkeys('g>h', () => navigate('/home'), SEQ);
  useHotkeys('g>g', () => navigate('/gallery'), SEQ);
  useHotkeys('g>r', () => navigate('/feed'), SEQ);
  useHotkeys('g>a', () => navigate('/atelier'), SEQ);
  useHotkeys('g>y', () => navigate('/you'), SEQ);

  // `?` opens the shortcuts sheet. Bound natively rather than via useHotkeys:
  // the produced key is a shifted special char (event.key === '?'), which the
  // code-based hotkey matcher doesn't handle cleanly. A guarded keydown is
  // simpler and reliable, and skips typing in form fields.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== '?' || e.metaKey || e.ctrlKey || e.altKey) return;
      if (inFormField(e.target) || inFormField(document.activeElement)) return;
      e.preventDefault();
      window.dispatchEvent(new CustomEvent('semant:open-shortcuts'));
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  return null;
}
