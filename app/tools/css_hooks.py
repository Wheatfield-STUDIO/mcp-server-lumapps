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

"""CSS skin token ↔ live DOM class. Proven on content-list / directory."""


def skin_bridge_line(css_class: str) -> str:
    """One line: /blocks keeps the token; live CSS targets the prefixed class."""
    token = (css_class or "").strip()
    return f"skin: .{token} → .widget--{token}"


SKIN_BRIDGE_LEGEND = (
    "skin: .{cssClass} → .widget--{cssClass}  "
    "(/blocks stays the token; CSS targets the prefixed class; proven content-list / directory). "
    "Do not pick one at random. properties.widgetClass does not appear in /blocks — other/legacy."
)
