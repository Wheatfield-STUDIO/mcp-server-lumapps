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

"""Well-known OAuth metadata for Copilot Studio discovery."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.oauth_metadata import (
    authorization_server_metadata,
    protected_resource_metadata,
)

router = APIRouter()

_CACHE = {"Cache-Control": "public, max-age=300"}


@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
async def oauth_protected_resource(request: Request):
    """RFC 9728 metadata. Copilot fetches the ``/mcp`` path form for this server."""
    document = protected_resource_metadata(request)
    if document is None:
        raise HTTPException(status_code=404, detail="OAuth discovery is not configured")
    return JSONResponse(content=document, headers=_CACHE)


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    """Authorization-server metadata with Entra authorize and token URLs."""
    document = authorization_server_metadata()
    if document is None:
        raise HTTPException(status_code=404, detail="OAuth discovery is not configured")
    return JSONResponse(content=document, headers=_CACHE)
