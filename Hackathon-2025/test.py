async def get_message_from_inbox_by_index(app, thread_index=0, message_index=0, limit=5):
    """
    Retrieve a message from the inbox by thread and message index.
    Returns (message, mailbox_id, inbox_folder_id) or (None, None, None) if not found.
    """
    mailboxes = await m.list_mailboxes(app)
    if not mailboxes.data:
        print("No mailboxes found.")
        return None, None, None
    mailbox_id = mailboxes.data[0].uuid
    mail_folders = await m.list_mailboxes_folders(app, mailbox_id)
    inbox_folder = next((f for f in mail_folders.data if f.name.lower() == "inbox"), None)
    if not inbox_folder:
        print("Inbox folder not found.")
        return None, None, None
    emails_response = await m.list_mails(app, mailbox_id, inbox_folder.id, limit=limit)
    threads = emails_response.data.threads
    if thread_index >= len(threads):
        print(f"Thread index {thread_index} out of range.")
        return None, None, None
    thread = threads[thread_index]
    if message_index >= len(thread.messages):
        print(f"Message index {message_index} out of range in thread {thread_index}.")
        return None, None, None
    message = thread.messages[message_index]
    return message, mailbox_id, inbox_folder.id

async def get_all_messages_from_inbox(app, limit=5):
    """
    Retrieve all messages from all threads in the inbox.
    Returns a list of (message, thread_index, message_index, mailbox_id, inbox_folder_id).
    """
    mailboxes = await m.list_mailboxes(app)
    if not mailboxes.data:
        print("No mailboxes found.")
        return []
    mailbox_id = mailboxes.data[0].uuid
    mail_folders = await m.list_mailboxes_folders(app, mailbox_id)
    inbox_folder = next((f for f in mail_folders.data if f.name.lower() == "inbox"), None)
    if not inbox_folder:
        print("Inbox folder not found.")
        return []
    emails_response = await m.list_mails(app, mailbox_id, inbox_folder.id, limit=limit)
    threads = emails_response.data.threads
    all_messages = []
    for thread_idx, thread in enumerate(threads):
        for msg_idx, message in enumerate(thread.messages):
            all_messages.append((message, thread_idx, msg_idx, mailbox_id, inbox_folder.id))
    return all_messages


def get_message_id_from_resource(resource_url: str) -> str | None:
    """
    Extract the message id from a resource URL (the part after '/message/').
    Returns the id as a string, or None if not found.
    """
    import re
    match = re.search(r"/message/([^/]+)$", resource_url)
    if match:
        return match.group(1)
    return None

import asyncio
import common.constants as const
import common.ik_apis.mail as m
from common.ik_apis import IKApi


async def main():

    # assuming list_mailboxes expects an IKApi object, not just a token
    app = IKApi(const.IK_ACCESS_TOKEN)
    # Example: get the first message of the second thread (thread_index=1, message_index=0)
    message, mailbox_id, inbox_folder_id = await get_message_from_inbox_by_index(app, thread_index=1, message_index=0, limit=5)
    if not message:
        return
    print("Resource label:", message.resource)
    message_id = get_message_id_from_resource(message.resource)
    if message_id:
        print("Extracted message id:", message_id)
        # Get mail details using the extracted message id
        mail_details = await m.get_email(app, mailbox_id, inbox_folder_id, message_id)
        print("Mail details:", mail_details)
        # Send the mail details to Qwen3 (like event_suggestion)
        from common.openai_clients import client_from_config
        qwen_client = client_from_config(model="qwen3", temprature=0.6, max_tokens=5000)
        # You can customize the prompt as needed
        prompt = f"Analyze the following email details and summarize:\n{mail_details}"
        llm_response = await qwen_client.ainvoke(prompt)
        print("Qwen3 response:", llm_response.content)
    else:
        print("No message id found in resource URL.")



if __name__ == "__main__":
    asyncio.run(main())
