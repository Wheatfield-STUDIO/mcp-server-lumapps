# Copyright 2026 Joffrey TREBOT (Wheatfield Studio)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="apiKey", auto_error=False)
api_key_query_token = APIKeyQuery(name="token", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

async def validate_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key",
        )
    if api_key != settings.MCP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key

def _get_bearer_key(credentials: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    if credentials and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None

async def validate_api_key_header_or_query(
    api_key_header_val: str = Security(api_key_header),
    api_key_query_val: str = Security(api_key_query),
    token_query_val: str = Security(api_key_query_token),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
):
    """Accept X-API-Key, Authorization: Bearer, or apiKey/token query params."""
    bearer_key = _get_bearer_key(bearer)
    api_key = api_key_header_val or api_key_query_val or token_query_val or bearer_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key (use X-API-Key, Authorization: Bearer, or ?apiKey= or ?token= query)",
        )
    if api_key != settings.MCP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key
