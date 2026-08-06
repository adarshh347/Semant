import { createContext, useContext } from 'react';

/**
 * Semant Writer · W2 — the actions a node view may take.
 *
 * Node views reach the W1 loop through this context, and the context exposes EXACTLY the
 * operations W1 already owns: accept, dismiss, define an operator, inspect one. There is
 * deliberately no `commit`, no `write`, and no `saveScene` here — the canon has one owner,
 * and a node view that could reach it directly would be the second door §1 of the W2
 * directive forbids.
 */
export const WriterActionsContext = createContext({
  onAccept: async () => {},
  onDismiss: async () => {},
  onCreateOperator: async () => {},
  // W7 — read a passage against its own declared standard. Diagnoses; writes nothing.
  onReadAlignment: async () => null,
  onDecideFlag: async () => {},
  onInspectOperator: () => {},
  operators: [],
});

export function useWriterActions() {
  return useContext(WriterActionsContext);
}
