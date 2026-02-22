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


def format_api_error(exc: BaseException, max_body: int = 600) -> str:
    """Extract a clear message from API errors (HTTPStatusError or RetryError wrapping it)."""
    cause = exc
    if isinstance(exc, RetryError) and getattr(exc, "last_attempt", None):
        attempt = exc.last_attempt
        if getattr(attempt, "failed", False) and getattr(attempt, "outcome", None):
            cause = attempt.outcome.exception() or exc
    if isinstance(cause, httpx.HTTPStatusError):
        r = cause.response
        body = (r.text or "")[:max_body]
        if body:
            return f"HTTP {r.status_code} {r.reason_phrase}: {body}"
        return f"HTTP {r.status_code} {r.reason_phrase}"
    return str(exc)
