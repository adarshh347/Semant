// Default backend base URL. Keep in sync with content.js and frontend/.env.
const DEFAULT_BACKEND_URL = 'http://localhost:8000';

// Normalize a user-entered base (strip trailing slashes; blank → default).
function normalizeBase(value) {
    const v = (value || '').trim().replace(/\/+$/, '');
    return v || DEFAULT_BACKEND_URL;
}

async function getBackendBase() {
    const { backendUrl } = await chrome.storage.sync.get('backendUrl');
    return normalizeBase(backendUrl);
}

// --- Backend URL management -------------------------------------------------
const urlInput = document.getElementById('backendUrlInput');
const saveUrlBtn = document.getElementById('saveUrlBtn');

chrome.storage.sync.get('backendUrl', ({ backendUrl }) => {
    urlInput.value = backendUrl || DEFAULT_BACKEND_URL;
});

saveUrlBtn.addEventListener('click', () => {
    const backendUrl = normalizeBase(urlInput.value);
    urlInput.value = backendUrl;
    chrome.storage.sync.set({ backendUrl }, checkConnection);
});

// --- API key management -----------------------------------------------------
const keyInput = document.getElementById('apiKeyInput');
const saveKeyBtn = document.getElementById('saveKeyBtn');
const keyStatus = document.getElementById('keyStatus');

// Load any saved key into the input.
chrome.storage.sync.get('apiKey', ({ apiKey }) => {
    if (apiKey) keyInput.value = apiKey;
});

saveKeyBtn.addEventListener('click', () => {
    const apiKey = keyInput.value.trim();
    chrome.storage.sync.set({ apiKey }, () => {
        keyStatus.textContent = apiKey ? '✓ Key saved' : 'Key cleared';
        checkConnection();
    });
});

// --- Backend connection check ----------------------------------------------
async function checkConnection() {
    const statusEl = document.getElementById('status');
    const base = await getBackendBase();
    const { apiKey } = await chrome.storage.sync.get('apiKey');
    const headers = apiKey ? { 'X-API-Key': apiKey } : {};

    try {
        const response = await fetch(`${base}/api/v1/posts/?limit=1`, { headers });
        if (response.ok) {
            statusEl.className = 'status connected';
            statusEl.textContent = `✓ Connected (${base})`;
        } else if (response.status === 401) {
            statusEl.className = 'status disconnected';
            statusEl.textContent = '✗ Backend rejected the API key (401)';
        } else {
            throw new Error('Not OK');
        }
    } catch (error) {
        statusEl.className = 'status disconnected';
        statusEl.textContent = `✗ No backend at ${base}`;
    }
}

// Check on popup open
checkConnection();
