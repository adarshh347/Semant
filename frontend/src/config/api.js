// API Configuration
// In production (Vercel), this will use the environment variable
// In development, it will fall back to localhost
export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5008';
