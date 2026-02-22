# LumApps Style and Theme — Global customization

The **style** (site theme) controls global appearance and behavior. You can customize not only CSS but also theme parameters (colors, nav, footer). **JavaScript** is injected via the instance **head**, not the style.

---

## Instance vs style: two different APIs

- **Instance (site)**  
  `GET _ah/api/lumsites/v1/instance/get?uid={instance_uid}`  
  Returns the site/instance object. Important fields:
  - **`style`**: the **style ID** (e.g. `"4028169471228830"`) — use it to fetch the theme via style/get.
  - **`head`**: HTML string where you add **JavaScript** (e.g. `"<script>var a=12;</script>"`).  
  **Do not** use `fields=head` when you need the style ID; that would restrict the response. Call instance/get without `fields` (or with fields that include `style`) to get the style ID, then call style/get for the theme.

- **Style (theme)**  
  `GET _ah/api/lumsites/v1/style/get?uid={style_uid}`  
  Returns the full **theme** object (stylesheets, properties, etc.). Get `style_uid` from the instance’s **`style`** field.

**Flow to get the theme:** 1) `instance/get?uid=instance_uid` → read `instance.style`; 2) `style/get?uid=instance.style` → theme object.

### When the site has no style yet (`instance.style` is null)

On some environments (e.g. beta), **`instance.style`** can be **null** for a new site. You can create a style via **`style/save`**:

1. **POST** to **`_ah/api/lumsites/v1/style/save`** with a payload **without** `id` or `uid`. The API creates the style and returns it with `id` and `uid` set.
2. **Required fields:** `customer`, `instance` (instance uid), `name` (e.g. `"sitestyle"` — **name is required**), `type` (e.g. `"global"`), `properties` (object with at least `primary`, `accent`, `colors`, `mainNav`, `search`, `top`), `stylesheets` (e.g. `[{ "kind": "root" }, { "content": "", "kind": "custom" }]`).
3. Then **link the instance** to the new style: **instance/save** with the instance object and `style` set to the returned style id.

Sending a style **with** an `id`/`uid` that does not exist returns **404** (update-only for that case). So to create: omit id/uid and include `name`.

### Instance response (excerpt)

When you call `instance/get?uid=...` (without `fields=head`), you get an object like:

- **`id`**, **`uid`**: instance id
- **`name`**, **`slug`**: site name and URL slug
- **`style`**: **style ID** (e.g. `"4028169471228830"`) → use with style/get to get the theme
- **`head`**: HTML string for scripts (e.g. `"<script>var a=12;</script>"`) — use this to add JavaScript

---

## Style object structure (style/get)

Example response:

```json
{
  "createdAt": "2026-02-21T23:26:15.974941+00:00",
  "createdBy": "4543584444818134",
  "customer": "7707798781338356",
  "id": "4028169471228830",
  "instance": "8035010586455967",
  "isDefault": false,
  "name": "sitestyle",
  "properties": {
    "accent": "#4CAF50",
    "colors": ["#FFFFFF", "#F44336", "#2196F3", "#000000", "transparent", "..."],
    "footer": {
      "en": "<div class=\"site-footer\"></div>"
    },
    "mainNav": {
      "backgroundColor": "#3F51B5",
      "fontColor": "#4CAF50",
      "fontSize": 12,
      "fontWeight": "normal",
      "iconColor": "#3F51B5",
      "iconSize": 12
    },
    "primary": "#2196F3",
    "search": {},
    "top": {
      "backgroundColor": "#F44336",
      "position": "content",
      "theme": "light"
    }
  },
  "status": "LIVE",
  "stylesheets": [
    {
      "content": ".ok{\n  padding:14px;\n}",
      "kind": "custom",
      "url": "https://storage.googleapis.com/..."
    }
  ],
  "type": "global",
  "uid": "4028169471228830",
  "updatedAt": "2026-02-22T11:46:50.456323+00:00",
  "updatedBy": "4543584444818134",
  "uuid": "b7d6f12e-0f7c-11f1-b52f-a2f019c7bff4"
}
```

---

## What you can customize

### 1. Theme CSS (style theme)

- **Where**: `style.stylesheets[]` — each item has `content` (CSS string), `kind` (e.g. `"custom"`, `"global"`), and optionally `url`, `name`.
- **How**: Edit the `content` of the relevant stylesheet (e.g. the one with `kind: "global"` or the first custom one). Use LumApps CSS variables when possible (see resource **lumapps-css-variables**).
- This is the right place for design system CSS (primary color, shadows, border-radius, site background, etc.) and for **footer styling** (CSS that targets the footer markup you add in `properties.footer`).

### 2. Global parameters (properties)

- **Where**: `style.properties`.
- **Main fields**:
  - **`primary`**: Primary color (e.g. `"#2196F3"`).
  - **`accent`**: Accent color (e.g. `"#4CAF50"`).
  - **`colors`**: Palette array (hex + `"transparent"`).
  - **`mainNav`**: Nav bar (backgroundColor, fontColor, fontSize, fontWeight, iconColor, iconSize).
  - **`top`**: Top bar (backgroundColor, position, theme).
  - **`footer`**: Footer **HTML** per language (see below).
  - **`search`**: Search-related options.

You can change these to adjust the theme without touching CSS (e.g. switch primary/accent, nav colors).

### 3. Footer: HTML + CSS

- **HTML**: Set **`properties.footer`** to an object with locale keys and HTML strings. **Recommendation:** use **HTML only**, with no inline or embedded CSS; use **custom class names** (e.g. `site-footer`, `site-footer__inner`, `site-footer__nav`) to avoid conflicts with LumApps classes (LumApps may use names like `footer`). **Do not use the `<footer>` tag** — LumApps already wraps this content in a `<footer>` element, so use a `<div>` with a custom class, e.g.  
  `{ "en": "<div class=\"site-footer\">...</div>", "fr": "..." }`.  
  This is injected as the footer markup.
- **CSS**: Add the footer styles in the **theme stylesheet** (`stylesheets[].content`) via **update_global_css**, targeting the custom classes you used in the HTML (e.g. `.site-footer { ... }`, `.site-footer__inner`, `.site-footer__nav`). Keep footer markup and footer CSS separate: HTML here, styling in the style theme.

**Using MCP tools:** To add or change a footer: (1) use **update_site_global_settings** with `footer_html` or `footer_html_by_locale` for the footer HTML; (2) use **update_global_css** for the footer CSS (classes used in that HTML). To add JavaScript in the head (classic or Customizations API), use **update_site_global_settings** with `head_html`; for Customizations API scripts, see resource **lumapps-customizations-api** (uri: `lumapps://lumapps-mcp-server/customizations-api`).

### 4. Head (JavaScript)

- **Where**: On the **instance**, not the style. Use `GET instance/get?uid={instance_uid}&fields=head` to read/write the **`head`** field. It is an HTML string (e.g. `"<script>var a=12;</script>"`).
- **How**: Add your scripts in that head content (e.g. `<script>...</script>` or `<script src="..."></script>`). Do not put script logic in the theme CSS. To update the head you must save the instance (instance/save) with the modified `head` field.

---

## Saving changes: style/save

**One endpoint for create and update** — **`POST _ah/api/lumsites/v1/style/save`** returns **200** in both cases and the full style object in the response.

- **Create (no style yet):** Send a payload **without** `id` or `uid`: `customer`, `instance`, `name` (required), `type` (e.g. `"global"`), `properties`, `stylesheets`. The API creates the style and returns it with `id`, `uid`, `createdAt`, etc.
- **Update (existing style):** Send the **entire style object** from **style/get**, with your changes applied (e.g. `stylesheets[i].content`, `properties.primary`). Do not send only the updated fields. The API returns the saved style (same shape).

So: no id in body → create; id in body → update. Same request, same 200 on success.

---

## Summary

| Goal | Where | Save |
|------|--------|-----|
| Theme CSS (design system, footer styles) | `style.stylesheets[].content` | Full style → style/save |
| Global colors/nav/top | `style.properties` (primary, accent, mainNav, top) | Full style → style/save |
| Footer HTML | `style.properties.footer` (e.g. `{"en": "<div>...</div>"}`) | Full style → style/save |
| JavaScript | Instance **head** (instance/get → field `head`) | Instance save with updated head |
| Design system variables | Theme CSS in stylesheets + lumapps-css-variables resource | Full style → style/save |
