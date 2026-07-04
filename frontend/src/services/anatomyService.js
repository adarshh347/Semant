/**
 * Anatomy Catalog service — API layer for the scaled anatomy category profile.
 * Talks to /api/v1/anatomy endpoints.
 */
import { API_URL } from '../config/api';

const BASE = `${API_URL}/api/v1/anatomy`;

/**
 * Fetch the full aggregated category profile.
 * @param {Object} opts - { tag, handle, minOccurrences }
 */
export async function fetchCategories({ tag, handle, minOccurrences } = {}) {
    const params = new URLSearchParams();
    if (tag) params.set('tag', tag);
    if (handle) params.set('handle', handle);
    if (minOccurrences) params.set('min_occurrences', minOccurrences);
    const res = await fetch(`${BASE}/categories?${params}`);
    if (!res.ok) throw new Error('Failed to fetch categories');
    return res.json();
}

/**
 * Fetch top-N most-affecting categories.
 */
export async function fetchTopCategories(n = 10, tag = null) {
    const params = new URLSearchParams({ n });
    if (tag) params.set('tag', tag);
    const res = await fetch(`${BASE}/categories/top?${params}`);
    if (!res.ok) throw new Error('Failed to fetch top categories');
    return res.json();
}

/**
 * Fetch all images containing a specific category + label.
 */
export async function fetchCategoryImages(category, label, limit = 50) {
    const params = new URLSearchParams({ limit });
    const res = await fetch(`${BASE}/categories/${encodeURIComponent(category)}/${encodeURIComponent(label)}/images?${params}`);
    if (!res.ok) throw new Error('Failed to fetch category images');
    return res.json();
}

/**
 * Trigger LLM insight synthesis (POST).
 */
export async function synthesizeInsights(tag = null, handle = null) {
    const params = new URLSearchParams();
    if (tag) params.set('tag', tag);
    if (handle) params.set('handle', handle);
    const res = await fetch(`${BASE}/synthesize?${params}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to synthesize insights');
    return res.json();
}

/**
 * Fetch cached insights (GET).
 */
export async function fetchInsights(tag = null, handle = null) {
    const params = new URLSearchParams();
    if (tag) params.set('tag', tag);
    if (handle) params.set('handle', handle);
    const res = await fetch(`${BASE}/insights?${params}`);
    if (!res.ok) throw new Error('Failed to fetch insights');
    return res.json();
}
