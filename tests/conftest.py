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

"""Pytest fixtures. Set env before app import so Settings validate."""

import os

# Must set before any app import (app.main loads settings at import)
os.environ.setdefault("MCP_API_KEY", "test-mcp-api-key")
os.environ.setdefault("LUMAPPS_ORG_ID", "test-org-id")
os.environ.setdefault("LUMAPPS_READ_CLIENT_ID", "test-read-client-id")
os.environ.setdefault("LUMAPPS_READ_CLIENT_SECRET", "test-read-client-secret")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
