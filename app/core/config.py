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

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    MCP_API_KEY: str
    MCP_PUBLIC_URL: Optional[str] = None

    LUMAPPS_CLIENT_ID: Optional[str] = None
    LUMAPPS_CLIENT_SECRET: Optional[str] = None
    # Aliases for read app (preferred in K8s/enterprise); take precedence over LUMAPPS_CLIENT_ID/SECRET when set
    LUMAPPS_READ_CLIENT_ID: Optional[str] = None
    LUMAPPS_READ_CLIENT_SECRET: Optional[str] = None
    # Admin app (all.admin): required for modification tools unless using LUMAPPS_ACCESS_TOKEN
    LUMAPPS_ADMIN_CLIENT_ID: Optional[str] = None
    LUMAPPS_ADMIN_CLIENT_SECRET: Optional[str] = None
    LUMAPPS_ACCESS_TOKEN: Optional[str] = None
    LUMAPPS_ORG_ID: str
    LUMAPPS_HAUSSMANN_CELL: str = "https://sites.lumapps.com"
    SITE_BASE_URL: str = "https://sites.lumapps.com"
    # Optional: user directory module id (content/list type=user_directory) to enrich find_person with full profile (e.g. jobDescription)
    LUMAPPS_USER_DIRECTORY_ID: Optional[str] = None

    LOG_LEVEL: str = "INFO"
    MAX_SEARCH_RESULTS: int = 5

    @model_validator(mode="after")
    def check_lumapps_auth(self):
        if self.LUMAPPS_ACCESS_TOKEN:
            return self
        read_id = self.LUMAPPS_READ_CLIENT_ID or self.LUMAPPS_CLIENT_ID
        read_secret = self.LUMAPPS_READ_CLIENT_SECRET or self.LUMAPPS_CLIENT_SECRET
        if not read_id or not read_secret:
            raise ValueError(
                "Either LUMAPPS_ACCESS_TOKEN or both read credentials "
                "(LUMAPPS_READ_CLIENT_ID/SECRET or LUMAPPS_CLIENT_ID/LUMAPPS_CLIENT_SECRET) must be set"
            )
        return self

    def get_read_client_id(self) -> Optional[str]:
        """Effective read app client ID (LUMAPPS_READ_CLIENT_ID preferred, else LUMAPPS_CLIENT_ID)."""
        return self.LUMAPPS_READ_CLIENT_ID or self.LUMAPPS_CLIENT_ID

    def get_read_client_secret(self) -> Optional[str]:
        """Effective read app client secret (LUMAPPS_READ_CLIENT_SECRET preferred, else LUMAPPS_CLIENT_SECRET)."""
        return self.LUMAPPS_READ_CLIENT_SECRET or self.LUMAPPS_CLIENT_SECRET

    def has_admin_credentials(self) -> bool:
        """True if admin OAuth app is configured (for modification tools). When using LUMAPPS_ACCESS_TOKEN, that token is used for both read and admin."""
        if self.LUMAPPS_ACCESS_TOKEN:
            return True
        return bool(self.LUMAPPS_ADMIN_CLIENT_ID and self.LUMAPPS_ADMIN_CLIENT_SECRET)


settings = Settings()
