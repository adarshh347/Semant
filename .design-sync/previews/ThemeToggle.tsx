import React from 'react';
import { ThemeToggle } from 'frontend';

// ThemeToggle — a circular icon button that flips light/dark (Sun/Moon).
// Reads and writes the DS ThemeProvider context.
export const Default = () => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.75rem',
      padding: '0.75rem 1rem',
      borderRadius: 'var(--radius-md)',
      background: 'var(--surface)',
      border: '1px solid var(--line)',
    }}
  >
    <ThemeToggle />
    <span style={{ font: '600 0.875rem var(--font-sans)', color: 'var(--ink-muted)' }}>Toggle theme</span>
  </div>
);
