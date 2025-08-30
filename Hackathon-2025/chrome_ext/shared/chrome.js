// shared/chrome.js
export const storageGet = (keys) =>
  new Promise((resolve, reject) => {
    try {
      chrome.storage.local.get(keys, (res) => {
        const err = chrome.runtime.lastError;
        if (err) return reject(err);
        resolve(res);
      });
    } catch (e) {
      reject(e);
    }
  });

export const storageSet = (obj) =>
  new Promise((resolve, reject) => {
    try {
      chrome.storage.local.set(obj, () => {
        const err = chrome.runtime.lastError;
        if (err) return reject(err);
        resolve();
      });
    } catch (e) {
      reject(e);
    }
  });

export const queryActiveTab = () =>
  new Promise((resolve, reject) => {
    try {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const err = chrome.runtime.lastError;
        if (err) return reject(err);
        resolve(tabs);
      });
    } catch (e) {
      reject(e);
    }
  });

export const sendMessageToTab = (tabId, message) =>
  new Promise((resolve, reject) => {
    try {
      chrome.tabs.sendMessage(tabId, message, (response) => {
        const err = chrome.runtime.lastError;
        if (err) return reject(err);
        resolve(response);
      });
    } catch (e) {
      reject(e);
    }
  });