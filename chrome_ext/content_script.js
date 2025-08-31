// Email content script for Chrome extension
// Adds functionality to extract email information and integrate with calendar

(() => {
    console.log("Content script loaded");

    // Constants
    const CONFIG = {
        buttonId: "event_api_call",
        buttonHtml: `
      <button type="button" id="event_api_call" class="mat-focus-indicator mailFooter-button mat-raised-button mat-button-base ng-star-inserted">
        <span class="mat-button-wrapper">
          <div>
            <i class="icon icon-magic-wand-outline"></i>
            <p class="d-none d-lg-block d-xl-block threadContent--dateMail">Resume daily mails</p>
          </div>
        </span>
        <span class="mat-ripple mat-button-ripple"></span>
        <span class="mat-button-focus-overlay"></span>
      </button>
    `,
        calendarBaseUrl: "https://calendar.infomaniak.com/create",
        mailPattern: /mail-(\d+)@([a-zA-Z0-9-]+)/g,
        targetSelector: "mail-toolbar__right ng-star-inserted",
        messageItemSelector: "div.message-item",
    };

    // Storage for collected frame data (reserved for future multi-frame aggregation)
    const frameDataCollection = new Map();

    // ---- Chrome API helpers (Promise-based) ----
    const storageGet = (keys) => new Promise((resolve) => chrome.storage.local.get(keys, resolve));

    const runtimeSendMessage = (message) => new Promise((resolve) => chrome.runtime.sendMessage(message, resolve));

    // ---- DOM helpers ----
    const qsAll = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    // ---- Content extraction ----
    const getMessageItemContent = () => qsAll(CONFIG.messageItemSelector)
        .map((el) => el.className)
        .join(" ");

    // ---- Pattern parsing ----
    const extractEmailThreadInfo = (content) => {
        const formattedEmails = [];
        const folderThreads = [];
        let match;

        while ((match = CONFIG.mailPattern.exec(content)) !== null) {
            const [, threadId, folderId] = match;
            formattedEmails.push(`${threadId}@${folderId}`);
            folderThreads.push({threadId, folderId});
        }

        return {formattedEmails, folderThreads};
    };

    // ---- API orchestration ----
    const callApi = async (content) => {
        const {formattedEmails, folderThreads} = extractEmailThreadInfo(content);
        if (folderThreads.length === 0) return;

        const {mailboxIds = []} = await storageGet({mailboxIds: []});
        if (mailboxIds.length === 0) return;

        const mailboxId = mailboxIds[0];
        const lastThread = folderThreads[folderThreads.length - 1];

        const response = await runtimeSendMessage({
            action: "callApi", payload: {
                mailboxId, folderId: lastThread.folderId, threadId: lastThread.threadId, context: formattedEmails,
            },
        });

        handleApiResponse(response);
    };

    // ---- Response handling / Calendar URL building ----
    const handleApiResponse = (response) => {
        if (!response || response.error) {
            console.error("API call failed:", response?.error ?? "Unknown error");
            return;
        }

        const params = new URLSearchParams({ctz: "Europe/Zurich"});

        if (response.title) params.set("text", response.title);

        const emailsText = Array.isArray(response.emails) && response.emails.length ? `Participants:\n${response.emails.join("\n")}` : "";

        const mergedDescription = [response.description, emailsText]
            .filter(Boolean)
            .join("\n\n");

        if (mergedDescription) params.set("details", mergedDescription);

        if (response.date && response.start_time) {
            const start = parseDateTime(response.date, response.start_time);
            if (start) {
                const end = new Date(start);
                end.setMinutes(end.getMinutes() + (Number(response.duration) || 60));
                params.set("dates", `${formatAsCalendarDate(start)}/${formatAsCalendarDate(end)}`);
            }
        }

        const url = `${CONFIG.calendarBaseUrl}?${params.toString()}`;
        console.log("Opening calendar URL:", url);
        window.open(url, "_blank", "noopener,noreferrer");
    };

    const parseDateTime = (dateStr, timeStr) => {
        try {
            const [y, m, d] = dateStr.split("-").map(Number);
            const [hh, mm] = timeStr.split(":").map(Number);
            if (Number.isFinite(y) && Number.isFinite(m) && Number.isFinite(d) && Number.isFinite(hh) && Number.isFinite(mm)) {
                return new Date(y, m - 1, d, hh, mm);
            }
        } catch {
            /* noop */
        }
        return null;
    };

    const formatAsCalendarDate = (date) => date.toISOString().replace(/[-:]|\.\d{3}/g, "");

    // ---- Button insertion ----
    const insertButton = (targetDiv) => {
        if (!targetDiv || targetDiv.querySelector(`#${CONFIG.buttonId}`)) return;

        targetDiv.insertAdjacentHTML("beforeend", CONFIG.buttonHtml);

        const btn = targetDiv.querySelector(`#${CONFIG.buttonId}`);
        if (btn) {
            btn.addEventListener("click", () => {
                const content = getMessageItemContent();
                callApi(content).catch((err) => console.error("Failed to call API:", err));
            });
        }
    };

    // Observe for target container appearance and insert the button
    const observer = new MutationObserver(() => {
        const targetDiv = document.querySelector(CONFIG.targetSelector);
        if (targetDiv) {
            insertButton(targetDiv);
        }
    });

    // Start observing when DOM is ready
    const startObserving = () => {
        try {
            observer.observe(document.body, {
                childList: true, subtree: true,
            });

            // Attempt immediate insertion if already present
            const targetDiv = document.querySelector(CONFIG.targetSelector);
            if (targetDiv) insertButton(targetDiv);
        } catch (e) {
            console.warn("MutationObserver setup failed:", e);
        }
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", startObserving, {once: true});
    } else {
        startObserving();
    }

    // ---- Message handling (for popup or other scripts) ----
    chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
        if (request?.action === "extractMessageItems") {
            try {
                const data = getMessageItemContent();
                // Optional: store per-frame data if needed later
                frameDataCollection.set(performance.now(), data);
                sendResponse({success: true, data});
            } catch (error) {
                console.error("Extraction error:", error);
                sendResponse({success: false, error: String(error)});
            }
            return true; // async-safe
        }

        return false; // not handled
    });

})();
