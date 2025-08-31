# -*- coding: utf-8 -*-
import datetime
import json
import logging
import re
from typing import List, Optional

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field, ValidationError, validator, conlist

logger = logging.getLogger()


class EventResponse(BaseModel):
    """Relevant information to set a new event"""

    emails: List[str] = Field(..., description=(
        "List of relevant participants e-mails found in the 'From' and 'To' fields before every e-mail content"), )
    title: str = Field(..., description="Title of the event based on the objectives described in the conversation", )
    description: str = Field(..., description="Short description of the event objective")
    date: str = Field(..., description="Date of the event formatted as YYYY-MM-DD")
    # Provide default values for the validation model to get the format if the first model dont find the value
    start_time: Optional[str] = Field(default="10:00", description="Start time of the event formatted as HH:MM")
    duration: Optional[int] = Field(default=60, description="Duration of the event in minutes")
    whole_day: Optional[bool] = Field(default=False,
                                      description="Boolean indicating if the event should last the entire day.", )

    @classmethod
    def _parse_duration(cls, duration_value, fallback_duration):
        """Parse duration value with default fallback to 60 minutes (1 hour)."""
        if duration_value is None:
            return fallback_duration if fallback_duration is not None else 60

        try:
            # Extract digits from the duration value
            duration_str = "".join(filter(str.isdigit, str(duration_value)))
            if not duration_str:
                return 60  # Default to 1 hour if no digits found

            duration_int = int(duration_str)
            # Validate that duration is reasonable (between 1 minute and 24 hours)
            if duration_int < 1 or duration_int > 1440:
                return 60  # Default to 1 hour for invalid ranges

            return duration_int
        except (ValueError, TypeError):
            return 60  # Default to 1 hour for any parsing errors

    @classmethod
    def correct_json(cls, validator_string: AIMessage, first_answer: "EventResponse"):
        if "```valid```" in validator_string.content.lower():
            return first_answer
        try:
            # Extract JSON from between triple backticks if present
            json_pattern = re.search(r"```(?:json)?\s*([\s\S]*?)```", validator_string.content)
            if json_pattern:
                # Use the content between backticks
                cleaned_json = json_pattern.group(1).strip()
            else:
                # If no backticks found, just clean up the raw string
                cleaned_json = re.sub(r"json\n", "", validator_string.strip())

            # Parse JSON
            data = json.loads(cleaned_json)

            # Create a new instance with values from the JSON or fallback to first_answer
            return cls(emails=data.get("emails", first_answer.emails), title=data.get("title", first_answer.title),
                       description=data.get("description", first_answer.description),
                       date=data.get("date", first_answer.date),
                       start_time=data.get("start_time", first_answer.start_time),
                       duration=cls._parse_duration(data.get("duration"), first_answer.duration),
                       whole_day=data.get("whole_day", first_answer.whole_day), )
        except (json.JSONDecodeError, AttributeError, KeyError, TypeError, ValidationError,) as e:
            # If JSON is invalid or missing required fields, return the first_answer
            logger.error(f"Error parsing JSON: {e}. Using fallback values.")
            return first_answer


class DailyResponse(BaseModel):
    """
    Résumé quotidien structuré, actionnable, intégrable.
    """
    title: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="Thème principal de la journée (ex: 'Validation projet et préparation réunion')"
    )

    summary: str = Field(
        ...,
        max_length=500,
        description="Résumé clair des échanges, décisions, contexte. Max 350 mots. Même langue que les e-mails."
    )

    date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date du résumé : YYYY-MM-DD"
    )

    emails: List[str] = Field(
        default_factory=list,
        description="Adresses uniques des expéditeurs et destinataires clés."
    )

    action_items: List[str] = Field(
        default_factory=list,
        description="Liste de tâches concrètes à faire (ex: 'Répondre à Marc avant 18h')"
    )

    topics: List[str] = Field(
        default_factory=list,
        description="Mots-clés ou sujets discutés (ex: 'Projet Q3', 'Facture', 'Recrutement')"
    )

    # Validation
    @validator("emails", each_item=True)
    def validate_email(cls, v):
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
            raise ValueError(f"Email invalide : {v}")
        return v

    @validator("date")
    def validate_date(cls, v):
        from datetime import datetime
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date invalide : doit être YYYY-MM-DD")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Réunion projet et validation devis",
                "summary": "Échanges avec Marc et Sophie sur le devis Q3. Accord verbal donné. En attente de version finale. Sophie propose un point technique mercredi.",
                "date": "2025-08-30",
                "emails": ["marc@infomaniak.com", "sophie@exemple.ch"],
                "action_items": [
                    "Répondre à Marc avec les questions techniques",
                    "Envoyer le devis finalisé à Sophie avant 17h"
                ],
                "topics": ["Projet Q3", "Devis", "Réunion"]
            }
        }

    @classmethod
    def correct_json(cls, validator_string: AIMessage, first_answer: "DailyResponse") -> "DailyResponse":
        """
        Valide et corrige la sortie du LLM.
        - Si '```valid```', retourne la réponse initiale.
        - Sinon, extrait le JSON corrigé entre ```json ... ``` et met à jour.
        """

        if "```valid```" in validator_string.content:
            return first_answer

        try:
            json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", validator_string.content)
            if not json_match:
                logger.warning("Aucun bloc JSON trouvé dans la réponse du validateur.")
                return first_answer

            cleaned_json = json_match.group(1).strip()

            data = json.loads(cleaned_json)

            return cls(
                emails=data.get("emails", first_answer.emails),
                title=data.get("title", first_answer.title),
                summary=data.get("summary", first_answer.summary),
                date=data.get("date", first_answer.date),
                action_items=data.get("action_items", first_answer.action_items),
                topics=data.get("topics", first_answer.topics)
            )

        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Erreur de parsing JSON dans correct_json : {e}")
            return first_answer

        except Exception as e:
            logger.error(f"Erreur inattendue dans correct_json : {e}")
            return first_answer


class MailBox(BaseModel):
    uuid: str
    email: str
    mailbox: str


class MailBoxResponse(BaseModel):
    data: list[MailBox]
    result: str


class EmailAddress(BaseModel):
    email: str
    name: str


class ThreadMessageBody(BaseModel):
    type: str
    value: str


class ThreadMessage(BaseModel):
    uid: str
    msg_id: str
    date: datetime.datetime
    subject: str
    from_: list[EmailAddress] = Field(alias="from")
    to: list[EmailAddress]
    cc: list[EmailAddress]
    bcc: list[EmailAddress]
    priority: str
    resource: str  # url
    download_resource: str  # url
    has_attachments: bool
    seen: bool
    forwarded: bool
    answered: bool
    flagged: bool
    preview: str
    body: Optional[ThreadMessageBody] = None

    @property
    def message_id(self) -> str:
        """Extract message ID from UID."""
        return self.uid.split("@")[0] if "@" in self.uid else self.uid

class Thread(BaseModel):
    uid: str
    from_: list[EmailAddress] = Field(alias="from")
    to: list[EmailAddress]
    cc: list[EmailAddress]
    bcc: list[EmailAddress]
    date: datetime.datetime
    subject: str
    messages: list[ThreadMessage]


class ListEmailsResponseData(BaseModel):
    messages_count: int
    threads: list[Thread] = Field(default_factory=list)


class ListEmailsResponse(BaseModel):
    data: ListEmailsResponseData
    result: str


class MailFolder(BaseModel):
    id: str
    name: str


class MailFolderResponse(BaseModel):
    data: list[MailFolder]
    result: str

class GetEmailResponse(BaseModel):
    data: ThreadMessage
    result: str