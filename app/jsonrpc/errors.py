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


class JSONRPCCodes:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    RATE_LIMIT_ERROR = -32000
    RESOURCE_NOT_FOUND = -32002


class MCPResourceNotFoundError(Exception):
    """Raised when a requested MCP resource URI is unknown or unreadable."""

    def __init__(self, message: str, uri: Optional[str] = None):
        self.message = message
        self.uri = uri
        super().__init__(message)
