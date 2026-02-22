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

from typing import Callable, Dict, Any, Awaitable
from app.jsonrpc.models import JSONRPCRequest, JSONRPCResponse, JSONRPCErrorDetail
from app.jsonrpc.errors import JSONRPCCodes, MCPResourceNotFoundError
import logging

logger = logging.getLogger(__name__)

class JSONRPCDispatcher:
    def __init__(self):
        self.methods: Dict[str, Callable[..., Awaitable[Any]]] = {}

    def register(self, name: str):
        def decorator(func: Callable[..., Awaitable[Any]]):
            self.methods[name] = func
            return func
        return decorator

    async def dispatch(self, request: JSONRPCRequest) -> JSONRPCResponse:
        if request.method not in self.methods:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCErrorDetail(
                    code=JSONRPCCodes.METHOD_NOT_FOUND,
                    message=f"Method '{request.method}' not found"
                )
            )

        try:
            result = await self.methods[request.method](request.params)
            return JSONRPCResponse(id=request.id, result=result)
        except MCPResourceNotFoundError as e:
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCErrorDetail(
                    code=JSONRPCCodes.RESOURCE_NOT_FOUND,
                    message=e.message,
                    data={"uri": e.uri} if e.uri is not None else None,
                ),
            )
        except Exception as e:
            logger.exception(f"Error dispatching method {request.method}")
            return JSONRPCResponse(
                id=request.id,
                error=JSONRPCErrorDetail(
                    code=JSONRPCCodes.INTERNAL_ERROR,
                    message=str(e)
                )
            )

dispatcher = JSONRPCDispatcher()
