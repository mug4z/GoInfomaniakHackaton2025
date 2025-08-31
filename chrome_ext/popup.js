// Popup script for managing API token and previewing parsed message data

import {queryActiveTab, sendMessageToTab, storageGet, storageSet,} from "./shared/chrome.js";
import {parseMailPattern} from "./shared/mail.js";

// ---- DOM references ----
const tokenInput = document.getElementById("tokenInput");
const saveButton = document.getElementById("saveTokenButton");
const contentOutput = document.getElementById("content");
const showDailyButton = document.getElementById("showDaily");

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
 * @param {JSON} data 
 * @returns {string}
 */
function jsonToSummaryHTML(data) {
    const escape = (text) => {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    };

    const formatDate = (isoDate) => {
        const options = { year: 'numeric', month: 'long', day: 'numeric' };
        return new Date(isoDate).toLocaleDateString('fr-FR', options);
    };

    const labels = {
        title: "Titre",
        summary: "Résumé",
        date: "Date",
        emails: "Adresses e-mail",
        action_items: "Actions à faire",
        topics: "Sujets"
    };

    const order = ["title", "summary", "date", "emails", "action_items", "topics"];

    let html = `
        <div class="euria-daily-summary" style="
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            overflow: hidden;
            max-width: 800px;
            margin: 20px auto;
        ">
    `;

    for (const key of order) {
        if (!(key in data)) continue;

        const value = data[key];
        const label = labels[key];

        if (!value || (Array.isArray(value) && value.length === 0)) continue;

        let content = "";

        if (key === "title") {
            html += `<div style="background:#2c5282; color:white; padding:20px; font-size:1.6em; font-weight:600;">${escape(value)}</div>`;
            continue;
        } else if (key === "date") {
            content = `<em>${formatDate(value)}</em>`;
        } else if (Array.isArray(value)) {
            const items = value.map(item => `<li style="
                background: #f7fafc;
                border-left: 4px solid #63b3ed;
                padding: 8px 12px;
                margin-bottom: 6px;
                border-radius: 4px;
                font-size: 0.95em;
            ">${escape(item)}</li>`).join("");
            content = `<ul style="padding-left: 20px; margin: 8px 0;">${items}</ul>`;
        } else {
            content = `<p style="margin: 8px 0; color: #4a5568; line-height: 1.6;">${escape(value)}</p>`;
        }

        html += `
            <div style="padding: 24px; border-bottom: 1px solid #e2e8f0;">
                <h3 style="
                    color: #2d3748;
                    margin-bottom: 12px;
                    font-size: 1.1em;
                    border-bottom: 2px solid #e2e8f0;
                    display: inline-block;
                    padding-bottom: 4px;
                ">${label}</h3>
                ${content}
            </div>
        `;
    }

    html += `</div>`;

    return html;
}

/**
 * Display URL for the last thread using mailbox ID from storage
 * @param {{folderThreads: {threadId: string, folderId: string}[]}} parsedData
 */
async function showDaily(parsedData) {
    const folderThreads = parsedData.folderThreads || [];

    if (folderThreads.length === 0) {
        contentOutput.textContent = "No thread found.";
        return ;
    };

    try {
        const {mailboxIds = []} = await storageGet({mailboxIds: []});
        if (mailboxIds.length === 0) {
            contentOutput.textContent = "No mailbox ID found.";
            return ;
        };

        const mailboxId = mailboxIds[0];
        const lastThread = folderThreads[folderThreads.length - 1];
        
        const {apiToken} = await storageGet("apiToken");
        if (!apiToken) {
            throw new Error("API Token is not set.");
        };
            
        const response = await fetch(`http://localhost:8000/daily/${mailboxId}/folder/${lastThread.folderId}/message`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${apiToken}`,
            },
            credentials: "omit"
        });

        const json = await response.json();

        const win = window.open("", "_blank", "width=600,height=400");

        if (win) {
            win.document.write(`
                <!DOCTYPE html>
                <html lang="fr">
                <head>
                    <meta charset="UTF-8" />
                    <title>Texte reçu</title>
                    <style>
                        body { font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; }
                        pre { background: #f4f4f4; padding: 15px; border-radius: 5px; overflow: auto; }
                    </style>
                </head>
                <body>
                    <h2>Summary</h2>
                    ${jsonToSummaryHTML(json)} 
                </body>
                </html>
            `);
            contentOutput.textContent = "Emails successfully processed"
            win.document.close();
        } else {
            console.warn("Impossible d'ouvrir la fenêtre (bloquée par le bloqueur de popups ?)");
        };

    } catch (e) {
        contentOutput.textContent = `Error: ${e.message || String(e)}`;
    }
}

async function fetchAndShowDaily() {
    contentOutput.textContent = "Loading…";

    try {
        const tabs = await queryActiveTab();
        if (!tabs.length) {
            contentOutput.textContent = "No active tab found.";
            return;
        };
        
        try {
            await chrome.scripting.executeScript({
                target: { tabId: tabs[0].id },
                files: ["content_script.js"] 
            });
            console.log("Content script injected");
        } catch (e) {
            console.warn("Script already injected or failed:", e);
        }

        const response = await sendMessageToTab(tabs[0].id, {action: "extractMessageItems"});

        if (response && response.success) {
            const parsedContent = parseMailPattern(response.data);
            await showDaily(parsedContent);
        } else {
            contentOutput.textContent = "Failed to process daily mails: " + (response?.error || "Unknown error");
        }
    } catch (e) {
        contentOutput.textContent = `Error: ${e.message || String(e)}`;
    }
}

// ---- Event Listeners ----
document.addEventListener("DOMContentLoaded", loadSavedToken, {once: true});
saveButton.addEventListener("click", () => void saveApiToken());
showDailyButton.addEventListener("click", async () => void await fetchAndShowDaily());
