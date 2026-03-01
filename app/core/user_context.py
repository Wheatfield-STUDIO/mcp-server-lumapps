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

"""Request-scoped user identity from OIDC JWT claims."""

from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Context var set by auth layer; read by dispatcher/tools to resolve user_email.
current_user_context: ContextVar[Optional["UserContext"]] = ContextVar(
    "current_user_context", default=None
)


@dataclass(frozen=True)
class UserContext:
    """Verified user identity from OIDC token claims."""

    sub: str
    email: Optional[str]
    upn: Optional[str]
    issuer: str
    audience: Optional[str]
    scopes: List[str]
    raw_claims: Dict[str, Any]

    def resolved_email(self) -> str:
        """Email for LumApps token exchange: email claim, then upn, then sub if looks like email."""
        if self.email:
            return self.email
        if self.upn and "@" in self.upn:
            return self.upn
        if self.sub and "@" in self.sub:
            return self.sub
        return self.sub


def set_user_context(ctx: Optional[UserContext]) -> None:
    current_user_context.set(ctx)


def get_user_context() -> Optional[UserContext]:
    return current_user_context.get()
