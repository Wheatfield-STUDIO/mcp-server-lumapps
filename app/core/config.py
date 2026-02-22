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
        if not self.LUMAPPS_CLIENT_ID or not self.LUMAPPS_CLIENT_SECRET:
            raise ValueError(
                "Either LUMAPPS_ACCESS_TOKEN or both LUMAPPS_CLIENT_ID and LUMAPPS_CLIENT_SECRET must be set"
            )
        return self

    def has_admin_credentials(self) -> bool:
        """True if admin OAuth app is configured (for modification tools). When using LUMAPPS_ACCESS_TOKEN, that token is used for both read and admin."""
        if self.LUMAPPS_ACCESS_TOKEN:
            return True
        return bool(self.LUMAPPS_ADMIN_CLIENT_ID and self.LUMAPPS_ADMIN_CLIENT_SECRET)


settings = Settings()
