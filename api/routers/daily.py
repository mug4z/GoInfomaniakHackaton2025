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
    ("system", """Tu es un assistant IA organisé et efficace, spécialisé dans le résumé des e-mails du jour.

Analyse les messages reçus au cours des dernières 24h et génère un résumé structuré au format JSON.

### 🔹 Champ `title`
- 5 à 10 mots maximum
- Résume le thème principal de la journée
- Exemple : "Réunion projet et devis à finaliser"

### 🔹 Champ `summary`
- 3 à 5 phrases max
- Clair, neutre, concis
- Inclus les décisions prises, les urgences, le contexte clé
- Écrit dans la **même langue** que les e-mails

### 🔹 Champ `date`
- Format ISO : `YYYY-MM-DD` (ex: 2025-08-30)
- C’est la date du résumé

### 🔹 Champ `emails`
- Liste **uniquement des adresses e-mail valides** (ex: `marc@infomaniak.com`)
- Récupérées depuis 'From', 'To', 'Cc'
- Interdit : y mettre du texte comme `"From: ..."` ou des sujets
- Ne **jamais inventer** une adresse
- Utilise **seulement** celles fournies dans : {emails}

### 🔹 Champ `action_items`
- Liste de **tâches concrètes** à faire
- Chaque tâche est une **chaîne de texte**
- Forme : verbe à l’impératif + contexte + échéance si possible
- Exemples :
  - "Répondre à Marc sur les specs techniques avant 17h"
  - "Envoyer le devis finalisé à Sophie"
  - "Valider le planning avec l'équipe"

### 🔹 Champ `topics`
- Liste de **mots-clés ou sujets** discutés
- Court, sans phrase
- Exemples : "Projet Q3", "Devis", "Réunion client", "Facture"

### 🔹 Règles strictes
- Ne **jamais utiliser** de markdown, ni ````json`, ni commentaires
- Ne **jamais inventer** d'information absente des e-mails
- Si aucun élément n’est trouvé → champs vides (liste vide, string vide)
- Réponds **uniquement avec un objet JSON valide**, rien d’autre."""),

    ("human", """Voici les e-mails du jour :

{text}

Résumé quotidien au format JSON :""")
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
