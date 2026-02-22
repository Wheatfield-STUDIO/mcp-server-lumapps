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

"""Search the LumApps directory for people (Directory pillar)."""

from typing import Any, Dict, List, Optional, Tuple

from app.services.lumapps_auth import lumapps_auth
from app.services.lumapps_client import lumapps_client
import logging

logger = logging.getLogger(__name__)


def _platform_directory_field_mapping(content: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Dict[str, str], List[str]]:
    """
    Parse platform user directory content. Returns (directory_uid, site_id, uuid_to_label, searchable_uuids).
    searchable_uuids: all components that are displayInFilter or displayInList and type inputText/metadata
    (no widget). Adapts to any tenant: Information, Job Description, Title, Skills, Department, etc.
    """
    uid = content.get("uid") or content.get("id")
    if not uid:
        return None, None, {}, []
    site_id = content.get("instance")
    components = (content.get("template") or {}).get("components") or []
    uuid_to_label: Dict[str, str] = {}
    searchable_uuids: List[str] = []
    for comp in components:
        c_uid = comp.get("uuid")
        if not c_uid or comp.get("type") == "widget":
            continue
        props = comp.get("properties") or {}
        if not props.get("displayInFilter", True) and not props.get("displayInList", True):
            continue
        comp_type = comp.get("type") or ""
        if comp_type not in ("inputText", "metadata"):
            continue
        title = (comp.get("title") or {}).get("en") or (comp.get("title") or {}).get("fr") or ""
        if title:
            uuid_to_label[c_uid] = title
        searchable_uuids.append(c_uid)
    return uid, site_id, uuid_to_label, searchable_uuids

TOOL_NAME = "find_person"

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": "Search the LumApps directory for people (experts, colleagues). Use to find who is responsible for a topic, or an expert (e.g. RSE, React).",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query: role, topic, name, or expertise (e.g. 'responsable RSE', 'expert React')."},
            "user_email": {"type": "string", "description": "The email of the current user (from session context)."},
            "limit": {"type": "integer", "description": "Max number of people to return. Defaults to 10."},
        },
        "required": ["query", "user_email"],
    },
}


async def handle(arguments: Dict[str, Any]) -> Dict[str, Any]:
    query = arguments.get("query")
    user_email = arguments.get("user_email")
    limit = arguments.get("limit", 10)
    if not query:
        raise ValueError("Missing 'query' argument")
    if not user_email:
        raise ValueError("Missing 'user_email' argument")

    logger.info(f"Executing find_person for {user_email} with query: {query}")
    token = await lumapps_auth.get_token(user_email=user_email)

    try:
        platform_content = await lumapps_client.get_platform_user_directory(token=token)
        dir_uid, site_id, uuid_to_label, searchable_uuids = _platform_directory_field_mapping(platform_content)
        if not dir_uid or not searchable_uuids:
            return {"content": [{"type": "text", "text": "No matching people found in the LumApps directory for this query."}]}

        seen_ids: Dict[str, Tuple[Dict[str, Any], set]] = {}
        for field_uuid in searchable_uuids:
            try:
                by_dir = await lumapps_client.users_by_directory(
                    directory_uid=dir_uid,
                    token=token,
                    max_results=min(limit, 100),
                    lang="en",
                    site_id=site_id,
                    search_criteria={field_uuid: query},
                )
                items = by_dir.get("items") or []
                field_label = uuid_to_label.get(field_uuid) or field_uuid
                for u in items:
                    uid = u.get("id")
                    if not uid:
                        continue
                    if uid not in seen_ids:
                        seen_ids[uid] = (u, set())
                    seen_ids[uid][1].add(field_label)
            except Exception as e:
                logger.debug("Search on field %s failed: %s", uuid_to_label.get(field_uuid, field_uuid), e)

        if not seen_ids:
            return {"content": [{"type": "text", "text": "No matching people found in the LumApps directory for this query."}]}

        ordered = sorted(seen_ids.items(), key=lambda x: (-len(x[1][1]), (x[1][0].get("fullName") or "")))
        lines = ["I found the following people in the LumApps directory:\n"]
        for _uid, (u, matched_in) in ordered[:limit]:
            name = u.get("fullName") or (f"{u.get('firstName') or ''} {u.get('lastName') or ''}".strip()) or "Unknown"
            email = u.get("email") or ""
            line = f"- **{name}**"
            if email:
                line += f" — {email}"
            if u.get("jobTitle"):
                line += f" — {u['jobTitle']}"
            if u.get("locationName"):
                line += f" — {u['locationName']}"
            if matched_in:
                line += f" — _Found via:_ {', '.join(sorted(matched_in))}"
            for pf in u.get("profileFields") or []:
                val = (pf.get("value") or {}).get("value") or (pf.get("value") or {}).get("translations", {}).get("en")
                if val:
                    title = (pf.get("title") or {}).get("value") or (pf.get("title") or {}).get("translations", {}).get("en") or "Profile"
                    line += f" — {title}: {val}"
            lines.append(line + "\n")
        return {"content": [{"type": "text", "text": "".join(lines)}]}
    except Exception as e:
        logger.debug("Platform directory or users/by-directory failed: %s", e)

    return {"content": [{"type": "text", "text": "No matching people found in the LumApps directory for this query."}]}
