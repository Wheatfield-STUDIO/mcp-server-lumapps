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

"""Fail-closed email allowlist for LumApps tool impersonation (API key and OIDC)."""

from typing import Optional, Set

from app.core.config import settings


class AllowlistError(Exception):
    """Raised when a tool call is blocked by MCP_ALLOWED_USER_EMAILS. message is safe for clients."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def parse_allowed_user_emails(raw: Optional[str]) -> Set[str]:
    """Split a comma-separated env value into a lowercase email set. Empty/unset → empty set."""
    if not raw or not str(raw).strip():
        return set()
    return {part.strip().lower() for part in str(raw).split(",") if part.strip()}


def allowed_user_emails() -> Set[str]:
    return parse_allowed_user_emails(getattr(settings, "MCP_ALLOWED_USER_EMAILS", None))


def is_user_email_allowed(email: Optional[str], allowed: Optional[Set[str]] = None) -> bool:
    """Case-insensitive membership. Empty allowlist or missing email → False (fail closed)."""
    emails = allowed if allowed is not None else allowed_user_emails()
    if not emails:
        return False
    if not email or not str(email).strip():
        return False
    return str(email).strip().lower() in emails


def require_allowed_user_email(email: Optional[str]) -> str:
    """
    Return the stripped email if it is on MCP_ALLOWED_USER_EMAILS.
    Empty/unset allowlist denies every impersonation (API key and OIDC).
    """
    allowed = allowed_user_emails()
    if not allowed:
        raise AllowlistError(
            "LumApps tool calls are disabled because MCP_ALLOWED_USER_EMAILS is empty. "
            "The server administrator must set a comma-separated allowlist."
        )
    if not is_user_email_allowed(email, allowed):
        raise AllowlistError(
            "This user is not permitted to call LumApps tools."
        )
    return str(email).strip()
