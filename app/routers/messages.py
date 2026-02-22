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

from fastapi import APIRouter, Depends, Request, Header
from app.core.security import validate_api_key_header_or_query
from app.jsonrpc.models import JSONRPCRequest, JSONRPCResponse
from app.jsonrpc.dispatcher import dispatcher
from app.routers.sse import sse_queues
from typing import Union, List, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/messages")
async def messages_endpoint(
    request: Request,
    rpc_request: Union[JSONRPCRequest, List[JSONRPCRequest]],
    api_key: str = Depends(validate_api_key_header_or_query),
    mcp_session_id: Optional[str] = Header(None, alias="mcp-session-id"),
):
    session_id = mcp_session_id or request.query_params.get("mcp-session-id")

    if isinstance(rpc_request, list):
        results = []
        for req in rpc_request:
            logger.info(f"Received Batch JSON-RPC request: {req.method}")
            results.append(await dispatcher.dispatch(req))
        if session_id and session_id in sse_queues:
            for resp in results:
                if resp is not None:
                    sse_queues[session_id].put_nowait(resp.model_dump_json())
            return None
        return results

    logger.info(f"Received JSON-RPC request: {rpc_request.method}")
    response = await dispatcher.dispatch(rpc_request)

    if session_id and session_id in sse_queues:
        if rpc_request.id is not None and response is not None:
            sse_queues[session_id].put_nowait(response.model_dump_json())
        return None

    if rpc_request.id is None:
        return None
    return response
