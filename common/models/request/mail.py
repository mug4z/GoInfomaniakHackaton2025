from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class MailEventSuggestionRequest(BaseModel):
    context_message_uid: List[str] = Field(..., description="Message uid of the thread, <msg id>@<folder id>")