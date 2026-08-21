import { createContext, useContext } from 'react';

/**
 * The inspector's context, in its own module.
 *
 * Split out for a mundane reason with a real consequence: a `.jsx` file that exports a hook
 * alongside its components loses fast refresh for the whole file, so every edit to the sidebar
 * would remount the workbench and drop the session being watched. The rule that enforces this
 * (`react-refresh/only-export-components`) is doing something for the person developing against a
 * live inquiry, not tidying imports.
 *
 * `null` outside a provider is a supported state, not a misuse — see `ImageRef`.
 */
export const InspectorContext = createContext(null);

export function useImageInspector() {
    return useContext(InspectorContext);
}
