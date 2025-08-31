# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from ik_apis import IKApi

# Need to send to login ik
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

IKToken = Annotated[str, Depends(oauth2_scheme)]


async def ik_api_dependency(token: IKToken):
    return IKApi(token)


IkApiDep = Annotated[IKApi, Depends(ik_api_dependency)]
