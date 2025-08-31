
# -*- coding: utf-8 -*-
import logging
from pathlib import Path

from fastapi import APIRouter
from langchain.prompts import ChatPromptTemplate

from api.dependencies.ik_api import IkApiDep
from common.mail_utils import get_mail, extract_unique_emails, remove_lines_starting_with_prefixes, clean_text
from models.request.mail import MailEventSuggestionRequest
from models.response.mail import EventResponse
from openai_clients import client_from_config

logger = logging.getLogger(__name__)

router = APIRouter(
        tags=["mail"],
        )

EVENT_PROMPT = ChatPromptTemplate([
    ("system", """You are a careful and ethical assistant specialized in analyzing the tone of email conversations. Your role is to detect any sign of disrespect, insults, threats, racism, anger, or emotional intensity in the messages.

Read the conversation carefully and respond in the SAME LANGUAGE as the email. If no issue is detected, answer with:  
"✅ Aucun contenu problématique détecté."

If you detect any concerning content, provide a clear and concise warning using the following format:  
"⚠️ ALERTE : [Type d'alerte]  
→ [Description brève du problème, sans exagération]"

Possible types of alerts:
- ⚠️ ALERTE : Ton agressif ou irrespectueux  
- ⚠️ ALERTE : Insultes ou langage dégradant  
- ⚠️ ALERTE : Menaces (directes ou implicites)  
- ⚠️ ALERTE : Contenu raciste, discriminatoire ou haineux  
- ⚠️ ALERTE : Client très en colère / frustration intense  
- ⚠️ ALERTE : Harcèlement ou pression excessive  

Be factual and avoid overreacting. Focus only on what is explicitly written."""),
    ("human", """Mail conversation: {text}

Analysis:""")
])

VALIDATION_PROMPT = ChatPromptTemplate([
    ("system", """You are a second-opinion ethical reviewer. Your role is to verify the tone analysis provided by the AI on an email conversation.

Check if:
- The alert is justified by the actual content (no overreaction)
- No serious issue was missed (no under-reaction)
- The language is neutral, factual, and proportional

Rules:
- If the analysis is correct and balanced, respond with: ```valid```
- If it's too harsh, too mild, or inaccurate, correct it and return the improved version between ```alert``` tags.
- Always respond in the SAME LANGUAGE as the original analysis.

Focus on real red flags:
- Insults, threats, racism, harassment, excessive anger
- Do not flag firm or direct tone unless it crosses into disrespect."""),
    ("human", """Original email: {text}

AI's tone analysis: {answer}

Verification:""")
])


event_client = client_from_config(model="qwen3", temprature=0.12, max_tokens=5000)
event_chain = EVENT_PROMPT | event_client.with_structured_output(EventResponse)

validation_prompt = client_from_config(model="mistral3", temprature=0.13, max_tokens=5000)
validation_chain = VALIDATION_PROMPT | validation_prompt


@router.post(
        "/mail/{mailbox_uuid}/folder/{folder_id}/thread/{thread_id}/event_suggestion",
        response_model=EventResponse,
        responses={400: {"description": "Bad Request"}},
        operation_id="event_suggestion",
        summary="Suggest an event",
        description=Path("common/docs/event_suggestion.md").read_text(),
        )
async def event_suggestion(
        mailbox_uuid: str,
        folder_id: str,
        thread_id: str,
        request: MailEventSuggestionRequest,
        ik_api: IkApiDep
        ) -> EventResponse:
    """

    Args:
        request:
        ik_api:

    Returns:

    """
    logger.info(f"Request for mailbox uuid: {mailbox_uuid}")
    mails = await get_mail(request.context_message_uid, ik_api, mailbox_uuid)
    email_sep = "\n---------------------------------------\n"
    text = ""
    emails = set()
    subject = None
    for mail in mails:
        if mail:
            date = mail.data.date.strftime("%A %d. %B %Y")
            from_item = mail.data.from_[0]
            from_display = f"{from_item.name} ({from_item.email})"
            to_cc_items = mail.data.to + mail.data.cc
            body = mail.data.body.value
            to_display = ", ".join([f"{r.name} ({r.email})" for r in to_cc_items])
            text += f"From: {from_display}\nTo: {to_display}\nDate: {date}\nE-mail: {body}{email_sep}"
            if subject is None:
                subject = mail.data.subject

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
    return EventResponse.correct_json(validation_result, result)
