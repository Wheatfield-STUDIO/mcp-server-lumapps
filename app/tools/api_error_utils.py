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

"""Shared helpers for formatting API errors in tool responses."""

import httpx
from tenacity import RetryError

# Message returned when LumApps denies write (403/401) so we don't leak API details
PERMISSION_DENIED_MESSAGE = (
    "This action was denied by the platform. "
    "Global design and architecture changes require Site Administrator privileges for this site."
)


def is_permission_denied(exc: BaseException) -> bool:
    """True if the exception looks like an HTTP permission-denied (401/403)."""
    cause = exc
    if isinstance(exc, RetryError) and getattr(exc, "last_attempt", None):
        attempt = exc.last_attempt
        if getattr(attempt, "failed", False) and getattr(attempt, "outcome", None):
            cause = attempt.outcome.exception() or exc
    if isinstance(cause, httpx.HTTPStatusError):
        return cause.response.status_code in (401, 403)
    return False


def log_tool_failure(log, message: str, exc: BaseException) -> None:
    """Log a tool failure without the LumApps response body or the exception text."""
    cause = exc
    if isinstance(exc, RetryError) and getattr(exc, "last_attempt", None):
        attempt = exc.last_attempt
        if getattr(attempt, "failed", False) and getattr(attempt, "outcome", None):
            cause = attempt.outcome.exception() or exc
    if isinstance(cause, httpx.HTTPStatusError):
        log.error("%s (HTTP %s)", message, cause.response.status_code)
        return
    log.error("%s (%s)", message, type(cause).__name__)


def format_api_error(exc: BaseException, max_body: int = 600) -> str:
    """Status-only message. LumApps response bodies are not returned to the caller."""
    del max_body  # kept so existing callers that pass it do not break
    cause = exc
    if isinstance(exc, RetryError) and getattr(exc, "last_attempt", None):
        attempt = exc.last_attempt
        if getattr(attempt, "failed", False) and getattr(attempt, "outcome", None):
            cause = attempt.outcome.exception() or exc
    if isinstance(cause, httpx.HTTPStatusError):
        return f"The LumApps request failed (HTTP {cause.response.status_code})."
    return "The LumApps request failed."
