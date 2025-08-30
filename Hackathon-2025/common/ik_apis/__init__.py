# -*- coding: utf-8 -*-
import os


class IKApi:
    API_URL = os.getenv("IK_API_URL", "https://api.infomaniak.com")

    def __init__(self, token: str):
        self.token = token

    @property
    def security_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
        }
