// ⌘K command palette (cmdk), mounted in the app shell (App.jsx).
// Surfaces routes + the demoted Tools (Research / Unconceal / Anatomy / Motive)
// + basic verbs. Open with ⌘K / Ctrl+K, or dispatch `semant:open-command`
// (the NavBar trigger does this). Themed to plum v1.3 in CommandPalette.css.
import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command } from 'cmdk';
import {
  Images, BookOpen, Palette, User, Home,
  Microscope, Eye, ScanSearch, Sparkles,
  Upload, SunMoon, ArrowRight, Keyboard,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import './CommandPalette.css';

// Primary destinations — mirrors NavBar PRIMARY_LINKS.
const NAVIGATE = [
  { to: '/gallery', label: 'Gallery', hint: 'Browse the collection', icon: <Images size={16} /> },
  { to: '/feed', label: 'Read', hint: 'Latest stories', icon: <BookOpen size={16} /> },
  { to: '/atelier', label: 'Atelier', hint: 'The per-image workspace', icon: <Palette size={16} /> },
  { to: '/you', label: 'You', hint: 'Highlights & epics', icon: <User size={16} /> },
  { to: '/', label: 'Home', hint: 'The bento dashboard', icon: <Home size={16} /> },
];

// Demoted tooling — mirrors NavBar TOOLS_LINKS (the ones that "move under ⌘K").
const TOOLS = [
  { to: '/research', label: 'Research', hint: 'Research agent', icon: <Microscope size={16} /> },
  { to: '/unconceal', label: 'Unconceal', hint: 'Aletheia queue', icon: <Eye size={16} /> },
  { to: '/anatomy', label: 'Anatomy', hint: 'Name parts of an image', icon: <ScanSearch size={16} /> },
  { to: '/motive', label: 'Motive', hint: 'The why behind the work', icon: <Sparkles size={16} /> },
];

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();

  // ⌘K / Ctrl+K toggles; external trigger opens.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    const onOpen = () => setOpen(true);
    document.addEventListener('keydown', onKey);
    window.addEventListener('semant:open-command', onOpen);
    return () => {
      document.removeEventListener('keydown', onKey);
      window.removeEventListener('semant:open-command', onOpen);
    };
  }, []);

  const run = useCallback((fn) => {
    setOpen(false);
    // Defer so the dialog can unmount before navigation/side-effects.
    requestAnimationFrame(() => fn());
  }, []);

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      className="cmdk-dialog"
      shouldFilter
    >
      <Command.Input placeholder="Search routes, tools, actions…" />
      <Command.List>
        <Command.Empty>No results.</Command.Empty>

        <Command.Group heading="Navigate">
          {NAVIGATE.map((item) => (
            <Command.Item
              key={item.to}
              value={`${item.label} ${item.hint}`}
              onSelect={() => run(() => navigate(item.to))}
            >
              <span className="cmdk-item-icon">{item.icon}</span>
              <span className="cmdk-item-label">{item.label}</span>
              <span className="cmdk-item-hint">{item.hint}</span>
              <ArrowRight className="cmdk-item-go" size={14} />
            </Command.Item>
          ))}
        </Command.Group>

        <Command.Group heading="Tools">
          {TOOLS.map((item) => (
            <Command.Item
              key={item.to}
              value={`${item.label} ${item.hint}`}
              onSelect={() => run(() => navigate(item.to))}
            >
              <span className="cmdk-item-icon">{item.icon}</span>
              <span className="cmdk-item-label">{item.label}</span>
              <span className="cmdk-item-hint">{item.hint}</span>
              <ArrowRight className="cmdk-item-go" size={14} />
            </Command.Item>
          ))}
        </Command.Group>

        <Command.Group heading="Actions">
          <Command.Item
            value="Upload image new add archive"
            onSelect={() => run(() => window.dispatchEvent(new CustomEvent('semant:open-upload')))}
          >
            <span className="cmdk-item-icon"><Upload size={16} /></span>
            <span className="cmdk-item-label">Upload an image</span>
            <span className="cmdk-item-hint">Add to the archive</span>
          </Command.Item>
          <Command.Item
            value="Toggle theme dark light appearance"
            onSelect={() => run(() => toggleTheme())}
          >
            <span className="cmdk-item-icon"><SunMoon size={16} /></span>
            <span className="cmdk-item-label">Toggle theme</span>
            <span className="cmdk-item-hint">{theme === 'dark' ? 'Switch to light' : 'Switch to dark'}</span>
          </Command.Item>
          <Command.Item
            value="Keyboard shortcuts help keys hotkeys"
            onSelect={() => run(() => window.dispatchEvent(new CustomEvent('semant:open-shortcuts')))}
          >
            <span className="cmdk-item-icon"><Keyboard size={16} /></span>
            <span className="cmdk-item-label">Keyboard shortcuts</span>
            <span className="cmdk-item-hint">Press ?</span>
          </Command.Item>
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
