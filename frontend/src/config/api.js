// API Configuration
// In production (Vercel), this will use the environment variable
// In development, it will fall back to localhost
import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5008';

// Optional API key. When the backend has API_KEY set, every /api/v1/* request
// must carry a matching X-API-Key header. Leave VITE_API_KEY unset for local
// dev against a backend with no key configured.
const API_KEY = import.meta.env.VITE_API_KEY;

if (API_KEY) {
  // Covers every axios request (most of the app).
  axios.defaults.headers.common['X-API-Key'] = API_KEY;

  // Parts of the app use the raw fetch() API instead of axios. Patch fetch
  // once, here, to inject the key on requests aimed at our backend so we don't
  // have to touch each call site. Requests to other hosts (e.g. Cloudinary)
  // are left untouched.
  const originalFetch = window.fetch.bind(window);
  window.fetch = (input, init = {}) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.startsWith(API_URL)) {
      const headers = new Headers(
        init.headers || (typeof input !== 'string' && input ? input.headers : undefined)
      );
      if (!headers.has('X-API-Key')) headers.set('X-API-Key', API_KEY);
      init = { ...init, headers };
    }
    return originalFetch(input, init);
  };
}
