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

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class JSONRPCBase(BaseModel):
    jsonrpc: str = "2.0"

class JSONRPCErrorDetail(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None

class JSONRPCRequest(JSONRPCBase):
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
    id: Optional[Union[str, int]] = None

class JSONRPCResponse(JSONRPCBase):
    result: Any = Field(default_factory=dict)
    error: Optional[JSONRPCErrorDetail] = None
    id: Union[str, int, None] = None

class JSONRPCNotification(JSONRPCBase):
    method: str
    params: Optional[Union[Dict[str, Any], List[Any]]] = None
