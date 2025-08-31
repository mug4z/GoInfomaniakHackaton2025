# -*- coding: utf-8 -*-
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(
    tags=["base"],
)


@router.get("/ping", response_class=PlainTextResponse)
def ping() -> Literal["pong"]:
    """
    An endpoint to test the api is up and running, returns pong if ok.
    """
    return "pong"
