// Background service worker for the extension

import {storageGet, storageSet} from "./shared/chrome.js";

// ---- Configuration ----
const CONFIG = {
    API_BASE_URL: "http://localhost:8000",
    MAIL_API_URL: "https://mail.infomaniak.com/api",
    URL_PATTERN: /https:\/\/mail\.infomaniak\.com\/api\/mail\/([a-f0-9-]+)\//,
};

// ---- Lifecycle ----
chrome.runtime.onInstalled.addListener(() => {
    console.info("Extension installed");
});

// ---- Mailbox ID capture from network requests ----
/**
 * Extracts and stores mailbox ID from request URLs
 * @param {chrome.webRequest.WebRequestCompletedDetails} details
 */
async function captureMailboxId(details) {
    const match = details.url.match(CONFIG.URL_PATTERN);
    if (!match) return;

    const mailboxId = match[1];
    try {
        const {mailboxIds = []} = await storageGet({mailboxIds: []});
        const unique = new Set(mailboxIds);
        unique.add(mailboxId);
        await storageSet({mailboxIds: [...unique]});
    } catch (error) {
        console.error("Failed to store mailbox ID:", error);
    }
}

// Narrow the observed URLs to the mail API domain for efficiency
chrome.webRequest.onCompleted.addListener(captureMailboxId, {
    urls: ["https://mail.infomaniak.com/api/*"],
});

// ---- Auth & requests ----
/**
 * Retrieves API token from storage
 * @returns {Promise<string>}
 */
async function getApiToken() {
    const {apiToken} = await storageGet("apiToken");
    if (!apiToken) throw new Error("API Token is not set.");
    return apiToken;
}

/**
 * Makes an authenticated API request
 * @param {string} url
 * @param {RequestInit} options
 * @returns {Promise<any>}
 */
async function makeAuthenticatedRequest(url, options = {}) {
    const token = await getApiToken();

    const response = await fetch(url, {
        ...options, headers: {
            "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(options.headers || {}),
        }, credentials: "omit",
    });

    if (!response.ok) {
        throw new Error(`Request failed: ${response.status} ${response.statusText}`);
    }

    return response.json();
}

/**
 * Calls the event suggestion endpoint
 * @param {string} mailboxId
 * @param {string} folderId
 * @param {string} threadId
 * @param {string[]} context
 * @returns {Promise<any>}
 */
function getEventSuggestion(mailboxId, folderId, threadId, context) {
    const url = `${CONFIG.API_BASE_URL}/mail/${mailboxId}/folder/${folderId}/thread/${threadId}/event_suggestion`;
    return makeAuthenticatedRequest(url, {
        method: "POST", body: JSON.stringify({context_message_uid: context}),
    });
}

/**
 * Orchestrates the event workflow API calls
 * @param {string} mailboxId
 * @param {string} folderId
 * @param {string} threadId
 * @param {string[]} context
 * @returns {Promise<any>}
 */
async function processEventWorkflow(mailboxId, folderId, threadId, context) {
    try {
        return await getEventSuggestion(mailboxId, folderId, threadId, context);
    } catch (error) {
        console.error("API Call Error:", error);
        return {error: error.message};
    }
}
//this this
// ---- Message handling from content scripts ----
chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
    if (request?.action !== "callApi") return false;

    try {
        const payload = request.payload || {};
        const {mailboxId, folderId, threadId, context} = payload;

        if (!mailboxId || !folderId || !threadId || !Array.isArray(context)) {
            sendResponse({error: "Invalid payload"});
            return true;
        }

        processEventWorkflow(mailboxId, folderId, threadId, context)
            .then(sendResponse)
            .catch((error) => {
                console.error("Request error:", error);
                sendResponse({error: error.message});
            });

        return true; // async response
    } catch (e) {
        console.error("Unexpected error:", e);
        sendResponse({error: String(e)});
        return true;
    }
});