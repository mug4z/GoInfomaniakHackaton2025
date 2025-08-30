// Popup script for managing API token and previewing parsed message data

import {queryActiveTab, sendMessageToTab, storageGet, storageSet,} from "./shared/chrome.js";
import {parseMailPattern} from "./shared/mail.js";


// ---- DOM references ----
const tokenInput = document.getElementById("tokenInput");
const saveButton = document.getElementById("saveTokenButton");
const contentOutput = document.getElementById("content");
const urlsOutput = document.getElementById("urls");
const showContentButton = document.getElementById("showContent");

// ---- Token persistence ----
async function loadSavedToken() {
    try {
        const {apiToken} = await storageGet("apiToken");
        if (apiToken) tokenInput.value = apiToken;
    } catch (e) {
        console.warn("Failed to load token:", e);
    }
}

async function saveApiToken() {
    const tokenValue = tokenInput.value.trim();

    if (!tokenValue) {
        alert("Please enter a valid token.");
        return;
    }

    try {
        await storageSet({apiToken: tokenValue});
        alert("Token saved successfully!");
    } catch (e) {
        alert(`Error saving token: ${e.message || String(e)}`);
    }
}

/**
 * Display URL for the last thread using mailbox ID from storage
 * @param {{folderThreads: {threadId: string, folderId: string}[]}} parsedData
 */
async function displayUrlForLastThread(parsedData) {
    const folderThreads = parsedData.folderThreads || [];

    if (folderThreads.length === 0) {
        urlsOutput.textContent = "No thread found.";
        return;
    }

    try {
        const {mailboxIds = []} = await storageGet({mailboxIds: []});
        if (mailboxIds.length === 0) {
            urlsOutput.textContent = "No mailbox ID found.";
            return;
        }

        const mailboxId = mailboxIds[0];
        const lastThread = folderThreads[folderThreads.length - 1];
        urlsOutput.textContent = `/mail/${mailboxId}/folder/${lastThread.folderId}/thread/${lastThread.threadId}/event_suggestion`;
    } catch (e) {
        urlsOutput.textContent = `Error reading mailbox IDs: ${e.message || String(e)}`;
    }
}

async function fetchAndDisplayMessageContent() {
    contentOutput.textContent = "Loading…";
    urlsOutput.textContent = "";

    try {
        const tabs = await queryActiveTab();
        if (!tabs.length) {
            contentOutput.textContent = "No active tab found.";
            return;
        }

        const response = await sendMessageToTab(tabs[0].id, {action: "extractMessageItems"});

        if (response && response.success) {
            const parsedContent = parseMailPattern(response.data);
            contentOutput.textContent = JSON.stringify(parsedContent, null, 2);
            await displayUrlForLastThread(parsedContent);
        } else {
            contentOutput.textContent = "Failed to extract message items: " + (response?.error || "Unknown error");
        }
    } catch (e) {
        contentOutput.textContent = `Error: ${e.message || String(e)}`;
    }
}

// ---- Event Listeners ----
document.addEventListener("DOMContentLoaded", loadSavedToken, {once: true});
saveButton.addEventListener("click", () => void saveApiToken());
showContentButton.addEventListener("click", () => void fetchAndDisplayMessageContent());