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

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from app.core.config import settings
from app.services.lumapps_auth import lumapps_auth
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _retryable_http_or_timeout(exc: BaseException) -> bool:
    """Retry only on server errors (5xx) or timeouts; do not retry on 4xx."""
    if isinstance(exc, httpx.ReadTimeout):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class LumAppsClient:
    def __init__(self):
        self.base_url = settings.LUMAPPS_HAUSSMANN_CELL
        self.org_id = settings.LUMAPPS_ORG_ID

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(_retryable_http_or_timeout),
    )
    async def _request(self, method: str, path: str, token: str, **kwargs) -> Dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        headers["Content-Type"] = "application/json"
        headers["lumapps-organization-id"] = self.org_id
        timeout = httpx.Timeout(30.0, connect=10.0)
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
            logger.info(f"Sending {method} to {url}")
            
            response = await client.request(method, url, headers=headers, **kwargs)
            
            if response.status_code == 429:
                logger.warning(f"Rate limited by LumApps API: {url}")
                response.raise_for_status()
            
            if response.status_code != 200:
                request_url = str(response.request.url)
                body_preview = (response.text or "")[:2000]
                logger.error(
                    "LumApps API error: %s %s | request=%s | response_body=%s",
                    response.status_code,
                    response.reason_phrase,
                    request_url,
                    body_preview,
                )
            
            response.raise_for_status()
            return response.json()

    async def search(self, query: str, token: str, limit: int = 5, lang: str = None) -> List[Dict[str, Any]]:
        path = "_ah/api/lumsites/v1/omnisearch/search"
        payload = {
            "query": query,
            "maxResults": limit,
        }
        if lang:
            payload["lang"] = lang
        extra_headers = {"X-Lumapps-Searchengine": "ns"}
        logger.info(f"Searching LumApps at {path} with payload: {payload}")
        data = await self._request("POST", path, token=token, json=payload, headers=extra_headers)
        logger.info(f"LumApps Search Result Count: {data.get('resultCountExact')}")
        
        items = data.get("items", [])
        logger.info(f"LumApps API returned {len(items)} items.")
        return items

    async def get_content(self, content_id: str, token: str, lang: str = None) -> Dict[str, Any]:
        """
        Get a single content (page) by uid. Returns the full content object.
        GET _ah/api/lumsites/v1/content/get?uid=...
        Response includes: id, uid, title, template (layout as template.components: rows/cells/widgets
        with uuid, widgetType, properties.style), instance, status, authorDetails, etc.
        For layout in v2 format (components + widgets[]) use get_content_layout instead.
        """
        path = "_ah/api/lumsites/v1/content/get"
        params = {"uid": content_id}
        if lang:
            params["lang"] = lang
        
        try:
            return await self._request("GET", path, token=token, params=params)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404 and lang:
                logger.warning(f"Content {content_id} not found in '{lang}', retrying without lang parameter")
                params.pop("lang")
                return await self._request("GET", path, token=token, params=params)
            raise e

    async def get_metadata(self, metadata_ids: List[str], token: str) -> List[Dict[str, Any]]:
        """
        Fetch metadata details for a list of IDs.
        Uses metadata/getMulti endpoint.
        """
        if not metadata_ids:
            return []
            
        path = "_ah/api/lumsites/v1/metadata/getMulti"
        params = [("ids", mid) for mid in metadata_ids]
        
        data = await self._request("GET", path, token=token, params=params)
        return data.get("items", [])

    async def list_content(
        self,
        site_uid: str,
        token: str,
        limit: int = 5,
        lang: str = None,
        order_by: str = "publicationDate",
        order_direction: str = "desc",
    ) -> List[Dict[str, Any]]:
        """
        List content (e.g. news) for a site, sorted by publication date.
        Used for listing site content (e.g. by publication date).
        """
        path = "_ah/api/lumsites/v1/content/list"
        params = {
            "siteId": site_uid,
            "maxResults": limit,
        }
        if lang:
            params["lang"] = lang
        if order_by:
            params["orderBy"] = order_by
        if order_direction:
            params["orderDirection"] = order_direction

        data = await self._request("GET", path, token=token, params=params)
        return data.get("items", [])

    async def get_user_profile(
        self,
        user_email: str,
        content_id: str,
        token: str,
        uid: str = None,
        lang: str = "en",
    ) -> Dict[str, Any]:
        """
        Get full user profile from the user directory (includes customProfile, jobDescription if present).
        GET _ah/api/lumsites/v1/user/directory/get — use email or uid, and contentId.
        """
        path = "_ah/api/lumsites/v1/user/directory/get"
        params = {"contentId": content_id}
        if uid:
            params["uid"] = uid
        else:
            params["email"] = user_email
        if lang:
            params["lang"] = lang
        return await self._request("GET", path, token=token, params=params)

    async def user_directory_list(
        self,
        content_id: str,
        token: str,
        query: str = None,
        max_results: int = 30,
        cursor: str = None,
        first_name: str = None,
        last_name: str = None,
        primary_email: str = None,
        status: str = "enabled",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Search user directory for profiles matching criteria. Returns full profile info
        (jobDescription, customProfile, etc.) in one call.
        POST _ah/api/lumsites/v1/user/directory/list
        Body: contentId (required), query, maxResults (1–100), cursor, firstName, lastName, primaryEmail, status, etc.
        """
        path = "_ah/api/lumsites/v1/user/directory/list"
        payload = {
            "contentId": content_id,
            "maxResults": min(max(1, max_results), 100),
            "status": status,
        }
        if query:
            payload["query"] = query
        if cursor:
            payload["cursor"] = cursor
        if first_name:
            payload["firstName"] = first_name
        if last_name:
            payload["lastName"] = last_name
        if primary_email:
            payload["primaryEmail"] = primary_email
        for k, v in kwargs.items():
            if v is not None and k not in payload:
                payload[k] = v
        return await self._request("POST", path, token=token, json=payload)

    async def get_platform_user_directory(self, token: str) -> Dict[str, Any]:
        """
        Get the main platform user directory content. Returns directory id (uid), instance (siteId),
        and template.components with field mapping (uuid -> title.en, boundMap.text e.g. jobDescription).
        GET _ah/api/lumsites/v1/content/platform-user-directory
        """
        path = "_ah/api/lumsites/v1/content/platform-user-directory"
        return await self._request("GET", path, token=token)

    async def users_by_directory(
        self,
        directory_uid: str,
        token: str,
        max_results: int = 20,
        lang: str = "en",
        site_id: str = None,
        search_criteria: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Search users in a directory by profile field criteria. Returns items with full profileFields
        (id, title, value) and contactFields. Adapts to any directory and its field mapping.
        GET v2/organizations/{org_id}/users/by-directory/{directory_uid}?maxResults=...&siteId=...&lang=...&searchCriteria[field_uuid]=value
        """
        path = f"v2/organizations/{self.org_id}/users/by-directory/{directory_uid}"
        params: Dict[str, Any] = {
            "maxResults": min(max(1, max_results), 100),
            "lang": lang,
        }
        if site_id:
            params["siteId"] = site_id
        if search_criteria:
            for field_uuid, value in search_criteria.items():
                if value is not None and str(value).strip():
                    params[f"searchCriteria[{field_uuid}]"] = str(value).strip()
        return await self._request("GET", path, token=token, params=params or None)

    async def post_to_feed(
        self,
        feed_uid: str,
        message: str,
        token: str,
        lang: str = None,
    ) -> Dict[str, Any]:
        """
        Post a short update/message to a LumApps space (feed/community).
        """
        path = "_ah/api/lumsites/v1/feed/post"
        payload = {
            "feedUid": feed_uid,
            "body": message,
        }
        if lang:
            payload["lang"] = lang
        return await self._request("POST", path, token=token, json=payload)

    async def get_content_layout(self, content_id: str, token: str) -> Dict[str, Any]:
        """
        Get the layout of a page (content): components tree and widgets with their styles (padding, margin, border, title text).
        GET v2/organizations/{org_id}/contents/{content_id}/layout
        """
        path = f"v2/organizations/{self.org_id}/contents/{content_id}/layout"
        return await self._request("GET", path, token=token)

    async def get_widget_blocks(
        self,
        widget_type: str,
        site_id: str,
        token: str,
        can_use_lang_fallback: bool = False,
        force_display: bool = True,
        body: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Load the block/settings for a widget type on a site.
        POST v2/organizations/{org_id}/widgets/{widget_type}/blocks?siteId=...&canUseLangFallback=...&forceDisplay=...
        Used to get current widget config (body.style, text, etc.) before or after editing.
        """
        path = f"v2/organizations/{self.org_id}/widgets/{widget_type}/blocks"
        params = {"siteId": site_id, "forceDisplay": str(force_display).lower()}
        if widget_type == "title":
            params["canUseLangFallback"] = str(can_use_lang_fallback).lower()
        return await self._request(
            "POST",
            path,
            token=token,
            params=params,
            json=body or {},
        )

    async def save_content(self, token: str, data: Dict[str, Any], send_notifications: bool = True) -> Dict[str, Any]:
        """
        Create or update a content (page). For update, send the full content object (e.g. from get_content).
        POST _ah/api/lumsites/v1/content/save
        Payload shape: same as get_content (id/uid, title, template with template.components for layout,
        instance, status, customContentType, etc.). Can set sendNotifications=false via params.
        """
        path = "_ah/api/lumsites/v1/content/save"
        params = {}
        if not send_notifications:
            params["sendNotifications"] = "false"
        return await self._request("POST", path, token=token, params=params or None, json=data)

    async def save_content_layout(self, content_id: str, token: str, layout: Dict[str, Any]) -> Dict[str, Any]:
        """
        Save (update) the layout of a page (v2 format: components + widgets[]).
        Tries POST (PUT returns 404 on this LumApps API).
        path: v2/organizations/{org_id}/contents/{content_id}/layout
        """
        path = f"v2/organizations/{self.org_id}/contents/{content_id}/layout"
        try:
            return await self._request("POST", path, token=token, json=layout)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise httpx.HTTPStatusError(
                    "Layout save failed (404). This API may require saving via content/save with full content.template.",
                    request=e.request,
                    response=e.response,
                ) from e
            raise

    async def instance_search(
        self,
        token: str,
        max_results: int = 30,
        cursor: str = None,
        name: str = None,
        ids: List[str] = None,
        parent: str = None,
        status: str = "LIVE",
        fields: str = None,
        sort_order: List[str] = None,
        consider_user_identity: bool = True,
        empty_parent: bool = None,
        user_favorites_only: bool = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Search/list LumApps sites (instances). Use for discovery or to let the user choose a site.
        POST _ah/api/lumsites/v1/instance/search
        Returns: { items: [{ id, uid, name, slug, parent, isDefaultInstance, createdAt, createdBy, metadata }], more, cursor }.
        """
        path = "_ah/api/lumsites/v1/instance/search"
        payload: Dict[str, Any] = {
            "maxResults": min(max(1, max_results), 100),
            "status": status,
            "considerUserIdentity": consider_user_identity,
        }
        if cursor:
            payload["cursor"] = cursor
        if name:
            payload["name"] = name
        if ids:
            payload["ids"] = ids
        if parent:
            payload["parent"] = parent
        if fields:
            payload["fields"] = fields
        if sort_order is not None:
            payload["sortOrder"] = sort_order
        if empty_parent is not None:
            payload["emptyParent"] = empty_parent
        if user_favorites_only is not None:
            payload["userFavoritesOnly"] = user_favorites_only
        for k, v in kwargs.items():
            if v is not None and k not in payload:
                payload[k] = v
        return await self._request("POST", path, token=token, json=payload)

    async def get_instance(self, instance_uid: str, token: str, fields: str = None) -> Dict[str, Any]:
        """
        Get a site (instance) by uid. Do not use fields=head when you need the style ID.
        Instance contains: id, uid, name, slug, style (style id), head (HTML for scripts), etc.
        """
        path = "_ah/api/lumsites/v1/instance/get"
        params = {"uid": instance_uid}
        if fields:
            params["fields"] = fields
        return await self._request("GET", path, token=token, params=params)

    async def save_instance(self, instance: Dict[str, Any], token: str) -> Dict[str, Any]:
        """
        Save the full instance (site). POST _ah/api/lumsites/v1/instance/save.
        When instance.style is null, the API may create a default style and return the instance with style set.
        Use this to "initialize" the style on a new site before fetching/updating the theme.
        """
        path = "_ah/api/lumsites/v1/instance/save"
        return await self._request("POST", path, token=token, json=instance)

    def _extract_style_id(self, data: Dict[str, Any]) -> Any:
        """Extract style id from instance, instance/save or style/save response (style id string or dict with id/uid)."""
        if not isinstance(data, dict):
            return None
        raw = data.get("style")
        if raw is None:
            inst = data.get("instance")
            if isinstance(inst, dict):
                raw = inst.get("style")
            # else: instance can be a string (instance id), no .get("style") on it
        if raw is not None:
            if isinstance(raw, str):
                return raw.strip() or None
            if isinstance(raw, dict):
                return raw.get("id") or raw.get("uid")
        # Response might be the style object itself (instance has "stylesheets": [] too — only treat as style when type is global)
        if isinstance(data, dict) and data.get("type") == "global":
            return data.get("id") or data.get("uid")
        return None

    # Default properties for creating a new style via style/save (no id/uid — API returns the created style with id).
    _DEFAULT_NEW_STYLE_PROPERTIES = {
        "accent": "#4CAF50",
        "colors": [
            "transparent", "#FFFFFF", "#F44336", "#E91E63", "#9C27B0", "#673AB7",
            "#3F51B5", "#2196F3", "#03A9F4", "#00BCD4", "#009688", "#4CAF50",
            "#8BC34A", "#CDDC39", "#FFEB3B", "#FFC107", "#FF9800", "#FF5722",
            "#795548", "#9E9E9E", "#607D8B", "#000000", "#212121", "#757575",
            "#BDBDBD", "#E0E0E0",
        ],
        "mainNav": {},
        "primary": "#2196F3",
        "search": {},
        "top": {"theme": "light", "position": "content"},
    }

    async def _create_and_link_style_for_instance(
        self, instance_id: str, instance: Dict[str, Any], token: str
    ) -> Any:
        """
        Create a new style via style/save (no id/uid); API returns the created style with id.
        Then link via instance/save with style=id. Returns style id or None.
        """
        if not isinstance(instance, dict):
            instance = await self.get_instance(instance_id, token=token)
        if not isinstance(instance, dict):
            return None
        customer = instance.get("customer") or self.org_id
        new_style = {
            "customer": customer,
            "instance": instance_id,
            "name": "sitestyle",
            "type": "global",
            "properties": dict(self._DEFAULT_NEW_STYLE_PROPERTIES),
            "stylesheets": [
                {"kind": "root"},
                {"content": "", "kind": "custom"},
            ],
        }
        try:
            saved = await self.save_style(new_style, token=token)
            style_id = self._extract_style_id(saved) if isinstance(saved, dict) else None
            if style_id:
                instance_updated = dict(instance)
                instance_updated["style"] = style_id
                try:
                    await self.save_instance(instance_updated, token=token)
                    logger.info("Created and linked style %s to instance %s.", style_id, instance_id)
                    return style_id
                except Exception as link_err:
                    logger.warning(
                        "Linking style %s to instance %s failed (%s); retrying with refetched instance.",
                        style_id, instance_id, link_err,
                    )
                    try:
                        instance_fresh = await self.get_instance(instance_id, token=token)
                        if not isinstance(instance_fresh, dict):
                            raise TypeError("get_instance did not return a dict")
                        instance_fresh["style"] = style_id
                        await self.save_instance(instance_fresh, token=token)
                        logger.info("Linked style %s to instance %s (after refetch).", style_id, instance_id)
                        return style_id
                    except Exception as retry_err:
                        logger.warning("Retry link failed: %s", retry_err)
                        raise
        except Exception as e:
            logger.warning("create style for instance %s failed: %s", instance_id, e)
        return None

    async def get_style_by_instance(self, instance_id: str, token: str) -> Dict[str, Any]:
        """
        Get style for a site. GET instance → if style is null, create via style/save and link via instance/save → GET style.
        Returns {"style": <style dict>} or {"style": None}.
        """
        instance = await self.get_instance(instance_id, token=token)
        style_id = self._extract_style_id(instance)
        if not style_id:
            # New site: create style (POST style/save without id), then link (POST instance/save with style=id)
            style_id = await self._create_and_link_style_for_instance(
                instance_id=instance_id, instance=instance, token=token
            )
        if not style_id:
            return {"style": None}
        path = "_ah/api/lumsites/v1/style/get"
        style_data = await self._request("GET", path, token=token, params={"uid": style_id})
        return {"style": style_data}

    async def save_style(self, style: Dict[str, Any], token: str) -> Dict[str, Any]:
        """
        Create or update a style. POST style/save.
        Without id/uid in body → create (API returns new style with id). With id → update.
        """
        path = "_ah/api/lumsites/v1/style/save"
        return await self._request("POST", path, token=token, json=style)


lumapps_client = LumAppsClient()
