// Shared data helpers for the Home bento tiles.
//
// Every tile is a small `useQuery` over endpoints that already exist — the posts
// list and the taste portfolio. We derive the editorial fields the tiles show
// (title, percept count, word count, "in progress") client-side from the post
// shape, so no backend change is needed and a future backfill just works.
import axios from 'axios';
import { API_URL } from '../../config/api';

const POSTS = `${API_URL}/api/v1/posts`;

// One recent-posts fetch feeds several tiles (Continue, Archive mosaic, Percepts,
// This week). Keyed by limit so callers share the cache.
export async function fetchRecentPosts(limit = 24) {
  const res = await axios.get(`${POSTS}?page=1&limit=${limit}`);
  return res.data?.posts ?? [];
}

// Exact archive size. With limit=1, total_pages === the true document count
// (ceil(n / 1) = n) — a one-row query that gives an honest "N images".
export async function fetchArchiveCount() {
  const res = await axios.get(`${POSTS}?page=1&limit=1`);
  return res.data?.total_pages ?? 0;
}

// --- deriving editorial fields from a post -------------------------------

// Pull readable text out of whatever `local_context` happens to be (string of
// HTML, an array of blocks, or a nested object) so the word count is honest.
function textOf(value) {
  if (!value) return '';
  if (typeof value === 'string') return value.replace(/<[^>]*>/g, ' ');
  if (Array.isArray(value)) return value.map(textOf).join(' ');
  if (typeof value === 'object') return Object.values(value).map(textOf).join(' ');
  return '';
}

export function wordCount(post) {
  const text = textOf(post?.local_context).trim();
  if (!text) return 0;
  return text.split(/\s+/).filter(Boolean).length;
}

export function percepts(post) {
  return Array.isArray(post?.region_annotations) ? post.region_annotations : [];
}

export function perceptCount(post) {
  return percepts(post).length;
}

export function perceptLabel(region) {
  return region?.label || region?.note || region?.name || 'a part';
}

// A reading has been *begun* once it carries marked parts or written context —
// those are the ones worth offering to resume.
export function isInProgress(post) {
  return perceptCount(post) > 0 || wordCount(post) > 0;
}

// Posts have no title field; compose the most human label available.
export function titleOf(post) {
  const tag = (post?.general_tags || []).find(Boolean);
  if (tag) return tag.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return post?.source_account || post?.instagram_handle || 'Untitled reading';
}

// "4 percepts · 240 words" — the progress line on a Continue tile.
export function progressLine(post) {
  const p = perceptCount(post);
  const w = wordCount(post);
  const parts = [];
  parts.push(`${p} ${p === 1 ? 'percept' : 'percepts'}`);
  if (w > 0) parts.push(`${w} ${w === 1 ? 'word' : 'words'}`);
  return parts.join(' · ');
}

// Was this post touched within the last `days`? (`updated_at` is an ISO string.)
export function updatedWithin(post, days = 7) {
  const ts = post?.updated_at;
  if (!ts) return false;
  const then = new Date(ts).getTime();
  if (Number.isNaN(then)) return false;
  return Date.now() - then <= days * 24 * 60 * 60 * 1000;
}
