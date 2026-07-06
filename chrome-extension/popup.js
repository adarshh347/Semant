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
    const { apiKey } = await chrome.storage.sync.get('apiKey');
    const headers = apiKey ? { 'X-API-Key': apiKey } : {};

    try {
        const response = await fetch('http://localhost:5007/api/v1/posts/?limit=1', { headers });
        if (response.ok) {
            statusEl.className = 'status connected';
            statusEl.textContent = '✓ Connected to Sharirasutra';
        } else if (response.status === 401) {
            statusEl.className = 'status disconnected';
            statusEl.textContent = '✗ Backend rejected the API key (401)';
        } else {
            throw new Error('Not OK');
        }
    } catch (error) {
        statusEl.className = 'status disconnected';
        statusEl.textContent = '✗ Backend not running (start with uvicorn)';
    }
}

// Check on popup open
checkConnection();
