# -*- coding: utf-8 -*-
from fastapi import FastAPI

from .routers import mail, ping

description = """Hackathon demo API"""

summary = """Hackathon demo API"""
app = FastAPI(
        title="Hackathon 2025",
        description=description,
        summary=summary,
        version="0.0.1",
        terms_of_service="https://infomaniak.com/ai/terms/",
        contact={
            "name": "Infomaniak",
            "url":  "https://infomaniak.com",
            },
        )

app.include_router(ping.router)
app.include_router(mail.router)
