export function parseMailPattern(content) {
    console.log("Parsing mail pattern");
  const mailPattern = /mail-(\d+)@([a-zA-Z0-9-]+)/g;
  const context_message_uid = [];
  const folderThreads = [];
  let match;

  while ((match = mailPattern.exec(content)) !== null) {
    const [, threadId, folderId] = match;
    context_message_uid.push(`${threadId}@${folderId}`);
    folderThreads.push({ threadId, folderId });
  }

  return { context_message_uid, folderThreads };
}