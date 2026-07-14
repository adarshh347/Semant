import { QueryClient } from '@tanstack/react-query';

// Shared client for the app. Conservative defaults: data is fresh for 30s,
// no refetch-on-focus storm, one silent retry. Chiasm/editor state is NOT
// managed here — this is for server-cache reads (Gallery, Feed, …).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
