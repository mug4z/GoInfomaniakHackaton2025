# -*- coding: utf-8 -*-
import datetime
import logging
from pathlib import Path

from fastapi import APIRouter, Depends
from langchain.prompts import ChatPromptTemplate

from api.dependencies.ik_api import IkApiDep
from common.mail_utils import extract_unique_emails, remove_lines_starting_with_prefixes, clean_text
from models.response.mail import DailyResponse
from openai_clients import client_from_config
from common.ik_apis.mail import list_mails

logger = logging.getLogger(__name__)

router = APIRouter(
        tags=["daily"],
        )

WEEKLY_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an organized and efficient AI assistant specialized in summarizing daily emails.

Analyze the messages received over the past 24 hours and generate a structured summary in valid JSON format.

### 🔹 Field `title`
- Maximum 5 to 10 words
- Summarize the main theme of the day
- Example: "Project meeting and quote to finalize"

### 🔹 Field `summary`
- 3 to 5 sentences maximum
- Clear, neutral, and concise
- Include key decisions, urgent matters, and essential context
- Written in the **same language** as the emails

### 🔹 Field `date`
- ISO format: `YYYY-MM-DD` (e.g., 2025-08-30)
- This is the summary's date

### 🔹 Field `emails`
- List **only valid email addresses** (e.g., `marc@infomaniak.com`)
- Extracted from 'From', 'To', or 'Cc' fields
- Forbidden: including text like `"From: ..."` or email subjects
- Never invent an email address
- Use **only** those provided in: {emails}

### 🔹 Field `action_items`
- List of **concrete action items**
- Each item is a **text string**
- Format: imperative verb + context + deadline if available
- Examples:
  - "Reply to Marc on technical specs before 5 PM"
  - "Send finalized quote to Sophie"
  - "Confirm schedule with the team"

### 🔹 Field `topics`
- List of **keywords or topics** discussed
- Short phrases, no full sentences
- Examples: "Q3 Project", "Quote", "Client meeting", "Invoice"

### 🔹 Strict rules
- Never use markdown, not even ```json or comments
- Never invent information not present in the emails
- If no data is found → leave fields empty (empty list, empty string)
- Respond **exclusively with a valid JSON object**, nothing else."""),

    ("human", """Here are today's emails:

{text}

Daily summary in JSON format:""")
])

WEEKLY_SUMMARY_VALIDATION_PROMPT = ChatPromptTemplate([
    ("system", """You are a daily email summary validator. Your task is to verify the accuracy and completeness of the AI-generated daily summary against the original email content.

Check the following:
- Are the key events, tasks, and topics correctly reported?
- Are action items complete and correctly assigned?
- Are dates, times, and attendees accurate?
- Is any information hallucinated (e.g. people, meetings, tasks not in the emails)?

Respond in one of two ways:
- If the summary is **correct and complete**, return exactly: ```valid```
- If the summary is **incorrect or incomplete**, return a **rectified version as JSON** between ```json``` tags. Only include the fields that need correction.

Never add explanations outside the tags."""),
    
    ("human", """Original emails: {text}

AI daily summary: {answer}

Verification:""")
])

event_client = client_from_config(model="qwen3", temprature=0.12, max_tokens=5000)
event_chain = WEEKLY_SUMMARY_PROMPT | event_client.with_structured_output(DailyResponse)

validation_prompt = client_from_config(model="mistral3", temprature=0.13, max_tokens=5000)
validation_chain = WEEKLY_SUMMARY_VALIDATION_PROMPT | validation_prompt

@router.post(
        "/daily/{mailbox_id}/folder/{folder_id}/message",
        response_model=DailyResponse,
        responses={400: {"description": "Bad Request"}},
        operation_id="summary_emails",
        summary="Make a summary of all e-mails",
        description=Path("common/docs/summary_emails.md").read_text(),
        )
async def summary_emails(
        mailbox_id: str,
        folder_id: str,
        ik_api: IkApiDep
        ) -> DailyResponse:
    """
    Summarizes emails from the last 24 hours in a given folder.

    Args:
        mailbox_id (str): ID of the mailbox
        folder_id (str): ID of the folder (e.g. INBOX)
        ik_api (IkApiDep): Injected API client for Infomaniak

    Returns:
        DailyResponse: Structured summary including events and emails

    """
    logger.info(f"Request for mailbox id: {mailbox_id}")
    mails = await list_mails(
        ik_api,
        mailbox_id,
        folder_id,
        from_date=datetime.datetime.now() - datetime.timedelta(days=1),
        to_date=datetime.datetime.now()
    )

    email_sep = "\n---------------------------------------\n"
    text = ""
    emails = set()
    subject = None
    for thread in mails.data.threads:
        for message in thread.messages:
            if message:
                date = message.date.strftime("%A %d. %B %Y")
                from_item = message.from_[0]
                from_display = f"{from_item.name} ({from_item.email})"
                to_items = message.to or []
                cc_items = message.cc or []
                to_cc_items = to_items + cc_items
                body = message.preview
                to_display = ", ".join([f"{r.name} ({r.email})" for r in to_cc_items])
                text += f"From: {from_display}\nTo: {to_display}\nDate: {date}\nE-mail: {body}{email_sep}"
                if subject is None:
                    subject = message.subject

                # Update email list
                field_emails = [str(item.email) for item in [from_item] + to_cc_items]
                parsed_emails = extract_unique_emails(body)
                emails.update(field_emails + parsed_emails)

    text = f"Subject: {subject}\n\n{text}"
    text = remove_lines_starting_with_prefixes(text, [">"])
    text = clean_text(text)

    result = event_chain.invoke(
            {"emails": ", ".join(emails), "text": text}
            )

    # Validate output
    valid_emails = [email for email in result.emails if email in emails]
    if len(result.emails) != len(valid_emails):
        wrong_emails = [email for email in result.emails if email not in emails]
        result.emails = valid_emails
        logger.info(f"The following e-mails have been hallucinated and removed: {wrong_emails}")
    validation_result = validation_chain.invoke(
            {"answer": result, "text": text}
            )
    return DailyResponse.correct_json(validation_result, result)

