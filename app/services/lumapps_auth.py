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

import httpx
import time
import asyncio
import base64
from typing import Literal, Dict, Any
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

Profile = Literal["read", "admin"]


class LumAppsAuthManager:
    """Obtains LumApps OAuth2 tokens. Read tools use the read app (all.read); admin tools use the admin app (all.admin) when configured."""

    def __init__(self):
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def _cache_key(self, user_email: str, profile: Profile) -> str:
        return f"{user_email}:{profile}"

    async def get_token(self, user_email: str, profile: Profile = "read") -> str:
        """
        Return a bearer token for the given user and profile.
        - profile "read": uses LUMAPPS_READ_CLIENT_ID/SECRET or LUMAPPS_CLIENT_ID/SECRET (all.read), or LUMAPPS_ACCESS_TOKEN.
        - profile "admin": uses LUMAPPS_ADMIN_CLIENT_ID/SECRET (all.admin) or LUMAPPS_ACCESS_TOKEN.
        """
        if settings.LUMAPPS_ACCESS_TOKEN:
            logger.debug("Using LUMAPPS_ACCESS_TOKEN override")
            return settings.LUMAPPS_ACCESS_TOKEN

        if profile == "admin" and not settings.has_admin_credentials():
            raise ValueError(
                "Admin tools require LUMAPPS_ADMIN_CLIENT_ID and LUMAPPS_ADMIN_CLIENT_SECRET "
                "(a second LumApps OAuth app with all.admin). See README for read vs admin credentials."
            )

        key = self._cache_key(user_email, profile)
        async with self._lock:
            cached = self._tokens.get(key)
            if cached and time.time() < cached["expires_at"] - 60:
                return cached["token"]
            return await self._refresh_token(user_email, profile)

    async def _refresh_token(self, user_email: str, profile: Profile) -> str:
        if profile == "read":
            client_id = settings.get_read_client_id()
            client_secret = settings.get_read_client_secret()
        else:
            client_id = settings.LUMAPPS_ADMIN_CLIENT_ID
            client_secret = settings.LUMAPPS_ADMIN_CLIENT_SECRET

        if not client_id or not client_secret:
            raise ValueError(
                f"LumApps {profile} credentials are required: set LUMAPPS_ADMIN_CLIENT_ID and LUMAPPS_ADMIN_CLIENT_SECRET for admin tools."
            )

        logger.info("Refreshing LumApps OAuth2 token (profile=%s)", profile)
        async with httpx.AsyncClient() as client:
            try:
                token_url = f"{settings.LUMAPPS_HAUSSMANN_CELL.rstrip('/')}/v2/organizations/{settings.LUMAPPS_ORG_ID}/application-token"
                auth_str = f"{client_id}:{client_secret}"
                auth_base64 = base64.b64encode(auth_str.encode("ascii")).decode("ascii")
                headers = {
                    "Authorization": f"Basic {auth_base64}",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                payload = {"grant_type": "client_credentials", "user_email": user_email}
                response = await client.post(token_url, headers=headers, data=payload, timeout=10.0)

                if response.status_code != 200:
                    logger.error("LumApps token error (%s): HTTP %s", profile, response.status_code)
                response.raise_for_status()
                data = response.json()
                token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                expires_at = time.time() + expires_in
                key = self._cache_key(user_email, profile)
                self._tokens[key] = {"token": token, "expires_at": expires_at}
                logger.info("LumApps token refreshed (profile=%s)", profile)
                return token
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "Failed to refresh LumApps token (profile=%s, HTTP %s)",
                    profile,
                    exc.response.status_code,
                )
                raise
            except Exception as exc:
                logger.error(
                    "Failed to refresh LumApps token (profile=%s, %s)",
                    profile,
                    type(exc).__name__,
                )
                raise


lumapps_auth = LumAppsAuthManager()
