# LumApps Customizations API — Consolidated documentation

Technical documentation for extending LumApps beyond its native capabilities (JavaScript and CSS). Official source: [lumapps.github.io/customizations-api-doc](https://lumapps.github.io/customizations-api-doc/).

---

## Table of contents

1. [Introduction and concepts](#introduction-and-concepts)
2. [Context and prerequisites](#context-and-prerequisites)
3. [Capabilities (overview)](#capabilities-overview)
4. [JavaScript Customizations API](#javascript-customizations-api)
5. [CSS Customizations API](#css-customizations-api)
6. [References](#references)

---

## Introduction and concepts

### Introduction

The Customizations API provides a framework for extending LumApps beyond its native capabilities. It is aimed at advanced users with a technical background. LumApps only provides support for the Customizations API base functionality; any code beyond what is described in this section is the code owner’s responsibility.

### Concept

The **Customizations API** is a frontend development kit that allows extending LumApps sites by:

- Adding **visual components** to predetermined placeholders in the product.
- Reacting to **events** to trigger actions.

Customization is done via **JavaScript** and **CSS**, which are core to the application and to this documentation.

### Context

On LumApps, sites and platforms can be heavily customized (logos, colors, layout, positioning). The **Customizations API** is a **last resort** option: consider it only when out-of-the-box options, the Marketplace, and specific configurations are not enough to achieve the desired result.

---

## Context and prerequisites

### Prerequisites

- Understand how LumApps works, its entities, and how they are managed.
- Have verified that the desired customization cannot be achieved via out-of-the-box functionality or Extensions.

For development:

- [Git](https://git-scm.com/) for versioning customizations.
- [Visual Studio Code](https://code.visualstudio.com/) (or equivalent) for editing code.

---

## Capabilities (overview)

The API is split into two areas:

| Area | Description | Detailed documentation |
|------|-------------|-------------------------|
| **JavaScript Customizations API** | Adding components, disabling elements, changing text, reacting to events. | [JavaScript](#javascript-customizations-api) |
| **CSS Customizations API** | Changing visual style via CSS (supported anchors, best practices). | [CSS](#css-customizations-api) |

---

## JavaScript Customizations API

### Principles

- Standardize and officialize how JS and CSS customizations are added to the page.
- Provide an API that is agnostic to the framework used by LumApps while reusing patterns and components.
- Allow maintaining and controlling these customizations in a supported and maintainable way.

### Technical foundations

- Customizations are **JavaScript callbacks** executed once the application has loaded.
- They are injected into the page HTML and mounted on render. They are kept in memory while bundles and API calls load, then executed at the right time for each section.
- **Entry point**: `window.lumapps`, in particular **`window.lumapps.customize`**.

Minimal example: display a message above all pages:

```javascript
window.lumapps.customize(({ targets, components, render, placement, constants }) => {
    const { Message } = components;
    const { Kind } = constants;

    render({
        placement: placement.ABOVE,
        target: targets.PAGE,
        toRender: Message({
            className: 'general-message',
            kind: Kind.info,
            children: 'Message above all pages',
            hasBackground: true,
        }),
    });
});
```

- **targets**: areas of the page that can be customized (the “X” coordinate).
- **placement**: where to place the customization relative to the target (ABOVE, UNDER, LEFT, RIGHT, REPLACE).
- **components**: reusable components (Message, Button, etc.).
- **render**: function to render a component at a given `target` and `placement`.

---

### JavaScript API: `window.lumapps`

Functions available on `window.lumapps`:

| Function | Description |
|----------|-------------|
| `customize` | Registers a customization callback (see below). |
| `displayNotification` | Displays a notification. |
| `getInternalUrl` | Returns an internal LumApps URL. |
| `getCurrentContent` | Returns the content currently displayed (useful for contextual actions). |
| `disable` | Disables a component (e.g. `window.lumapps.disable('contribution-button')`). |
| `setText` | Changes the displayed text of a component (e.g. search box placeholder). |

---

### `window.lumapps.customize(callback, configuration)`

- **callback**: function called when the app mounts; it receives an object of parameters and returns nothing.
- **configuration** (optional):
  - `shouldRenderOnNavigation`: if `true`, the callback is re-executed on every navigation (use sparingly for performance).
  - `shouldUseCurrentContent`: set to `true` only if the customization uses `getCurrentContent()`; otherwise `false`.

#### Parameters passed to the callback

| Parameter | Description |
|-----------|-------------|
| `targets` | Available targets (PAGE, HEADER, SEARCH_BOX, CONTENT, WIDGET, etc.). |
| `placement` | ABOVE, UNDER, LEFT, RIGHT, REPLACE. |
| `components` | Components (Message, Button, Icon, Dropdown, etc.). |
| `constants` | Constants (Kind, Size, ColorPalette, Emphasis, Orientation, etc.). |
| `render` | Function to render a component: `render({ placement, target, toRender })`. |
| `session` | Session data (user, language, navigations, etc.). |
| `on` | Subscribe to events (NAVIGATION, SEARCH, WIDGET_RENDERED). |
| `pushEvent` | Emit custom events. |
| `getLatestEvents` | Retrieve latest events. |
| `state` | State management. |
| `api` | Axios instance for AJAX requests. |

*(Deprecated parameters `onNavigation`, `onWidgetRendered` must not be used for rendering.)*

#### Placements

| Placement | Description |
|-----------|-------------|
| `placement.ABOVE` | Above the target. |
| `placement.UNDER` | Below. |
| `placement.LEFT` | To the left. |
| `placement.RIGHT` | To the right. |
| `placement.REPLACE` | Replaces the target. |

Not all placements are compatible with all targets; see the [Capabilities](https://lumapps.github.io/customizations-api-doc/javascript/capabilities.html) documentation.

#### Targets — summary

**Components / zones:** APP, BOOKMARKS, BOOKMARKS_ITEMS, CONTRIBUTION_BUTTON, CONTRIBUTION_MENU, CONTEXTUAL_ACTIONS, FAVORITES, HEADER, LOGO, NAVIGATION, NAVIGATION_UI, NOTIFICATIONS_BUTTON, SEARCH_BOX, SEARCH_CUSTOM_METADATA, SEARCH_EXTENSION_RESULT, SEARCH_RESULT_ICON, SEARCH_TAB, SETTINGS, SETTINGS_BUTTON, STICKY_HEADER, SUB_NAVIGATION, SUB_NAVIGATION_UI, USER_CARD_FIELDS, USER_DROPDOWN_LINKS, USER_PROFILE_HEADER_FIELDS, USER_PROFILE_ORG_CHART, WIDGET.

**Pages:** COMMUNITY, CONTENT, CUSTOM_LIST, DIRECTORY, ERROR_PAGE, FEED, NOT_FOUND_PAGE, PAGE, PLAYLIST, PROFILE, SEARCH, SPACE, USER_DIRECTORY, USER_SETTINGS, VIDEO.

**Widget:** to target a specific widget: `target: \`${targets.WIDGET}-${widget-id}\`` or `target: \`${targets.WIDGET}-${identifier}\`` (identifier = “Style” field in the widget configuration).

---

### Components (overview)

Common components (detailed options on [JavaScript API](https://lumapps.github.io/customizations-api-doc/javascript/api.html)):

- **Message**: message with `kind` (info, warning, etc.), `children`, `hasBackground`, `className`.
- **Button**: `children`, `onClick`, `href`, `leftIcon` / `rightIcon`, `emphasis`, `size`, `aria-label`.
- **IconButton**: `icon`, `onClick`, `href`, `aria-label`.
- **Avatar**: `image`, `size`, `className`.
- **Badge**: `children`, `color`, `className`.
- **Bookmark**: `title`, `link`, `icon`.
- **ContextualAction**: for the contextual actions menu (content): `labelKey`, `icon`, `action` (function or `{ href, target }`), `tooltipLabelKey`.
- **Dropdown**, **DropdownSection**, **DropdownItem**: dropdown menus.
- **FlexBox**: flex layout, `children`, `orientation`, `gap`, `hAlign`, `vAlign`.
- **Link**, **ListItem**, **Icon**, **Chip**, **Dialog**, **RawHTML**, **Thumbnail**, etc.

Constants (`constants`) include: `Kind`, `Size`, `ColorPalette`, `Emphasis`, `Orientation`, etc.

---

### Detailed capabilities (JavaScript)

1. **Rendering and replacement**  
   Use `render({ placement, target, toRender })` (or `toRenderWithContext(context)` to decide based on page type).

2. **Disabling**  
   `window.lumapps.disable('target-id')` — e.g. `'contribution-button'`, `'bookmarks'`, `'search-box'`, `'navigation'`, `'navigation-ui'`, `'sticky-header'`, `'sub-navigation'`, `'favorites'`. Some disabling requires additional CSS (e.g. navigation).

3. **Changing text**  
   `window.lumapps.setText('search-box', { en: 'Explore', fr: 'Explorer', es: 'Explorar' })` — only for supported components (e.g. search box placeholder).

---

### JavaScript use cases (summary and examples)

- **Message above all pages**: `target: targets.PAGE`, `placement: placement.ABOVE`, `Message` component.
- **Message by page type**: `target: targets.PAGE`, `toRenderWithContext(context)` and check `context.type` (e.g. COMMUNITY, CONTENT, PLAYLIST, VIDEO).
- **Hide app launcher**: `window.lumapps.disable('bookmarks')`.
- **Add bookmarks**: `target: targets.BOOKMARKS_ITEMS`, `placement: placement.RIGHT`, `Bookmark` component.
- **Contextual action “Copy link”**: `target: targets.CONTEXTUAL_ACTIONS`, `placement: placement.UNDER`, `ContextualAction` with `action: () => { ... copy URL ... }` or `getCurrentContent()` to build a URL; if using `getCurrentContent()`, pass `{ shouldRenderOnNavigation: true }` as the second argument to `customize`.
- **Button or link in top bar**: `target: targets.SEARCH_BOX` (or LOGO, NOTIFICATIONS_BUTTON, etc.), `placement: placement.RIGHT`, `IconButton` or `Button` with `href` and `target: '_blank'`.
- **Links in contribution menu**: `target: targets.CONTRIBUTION_MENU`, `DropdownSection` + `DropdownItem`.
- **Badge next to logo for admins**: `target: targets.LOGO`, `placement: placement.RIGHT`, condition `session.user.isAdmin`, `Badge` component.
- **Hide navigation**: `window.lumapps.disable('navigation')` + CSS (e.g. `.inline-main-nav { display: none; }`, adjust padding / box-shadow).
- **Custom navigation**: `window.lumapps.disable('navigation-ui')` then `render` with `target: targets.NAVIGATION`, `placement: placement.REPLACE`, using `session.navigations.getCurrent()` (or `getParent()` if inheritance) for links.
- **Disable sticky header**: `window.lumapps.disable('sticky-header')` + CSS (e.g. `.header-top { position: initial !important; }`).
- **Customization on a widget**: `target: 'widget-<id>'` or `'widget-<identifier>'`, `placement: placement.ABOVE` / UNDER, component (e.g. `RawHTML`).
- **Side panel (side nav)**: `target: targets.APP`, `placement: placement.LEFT` or RIGHT, `FlexBox` with links (e.g. `Link` + `Thumbnail`).
- **Onboarding dialog**: `target: targets.APP`, `placement: placement.LEFT`, `Dialog` component with `isOpen`, `header`, `body`, `accept.onClick`; manage one-time display (e.g. localStorage).

Important limitations: use `DropdownSection` / `DropdownItem` in menus (settings, contribution), and `ContextualAction` / ListItem in contextual actions; avoid executing `render` from a callback (e.g. after click) — only at startup; do not use `setText` / `disable` inside `customize` (call them in plain JS if needed).

---

### Development and deployment (JavaScript)

- Customizations are added in **Head (HTML)** or via scripts injected in the admin (Style / Head).
- **Self-hosting**: possible but not officially supported; prefer grouping code in the Head or separating what is critical for first paint and caching it heavily.
- Comments in deployed code are not supported (size impact); minify code.
- Customizations **do not run on public sites/pages** (security).

---

### JavaScript FAQ

- **Multiple customizations same target/placement**: no; only one `render` per (target, placement) pair. For multiple elements, use a single `render` with a container component (e.g. FlexBox).
- **Remove a customization**: `render({ placement, target, toRender: null })`.
- **`render` from a callback (e.g. after click)**: not supported; only at startup.
- **DOM after RawHTML**: the DOM may not be available yet; use e.g. `setTimeout` to access elements (only with RawHTML, not supported for other components).
- Do not wrap in `DOMContentLoaded`; the API already handles execution timing.
- **Responsive navigation**: customizations on `NAVIGATION` do not affect the responsive version.

---

### JavaScript best practices

- Group customizations by configuration (e.g. one with `shouldRenderOnNavigation: true`, others without).
- Avoid external libraries when possible; otherwise (e.g. unpkg), load them before customizations (unsupported usage).
- Always use the Customizations API to modify markup; raw JS that touches the DOM is not supported and can hurt performance.
- Execute `disable` as early as possible to avoid display “flash”.
- Do not use `onNavigation` for `render`.

---

## CSS Customizations API

### Concept and principles

- Standardize how custom CSS is added to the page.
- Provide stable **anchors** (classes / IDs) to target supported areas.
- Any change outside these anchors is possible but **not guaranteed** between versions (markup may change).

### Overview

- CSS customizations allow changing the site’s appearance. This is an advanced option; you are responsible for the CSS code (possible side effects). LumApps does not maintain custom code; markup may change except for [supported anchors](https://lumapps.github.io/customizations-api-doc/css/api.html).

---

### Supported anchors (CSS)

Prefer these for stable customizations. Do not combine with HTML tags (e.g. avoid `div.header-top__logo`) so as not to depend on element type.

#### Top bar

| Zone | Class / anchor |
|------|-----------------|
| Entire header | `.header-top` |
| Max-width wrapper | `.header-top__wrapper` |
| Logo | `.header-top__logo` |
| Search box | `.header-top__search` |
| Contribution | `.header-top__contribution` |
| Favorites (directories) | `.header-top__directory-favorites` |
| Bookmarked apps | `.header-top__bookmarked-apps` |
| Notifications | `.header-top__notifications` |
| User settings | `.header-top__user-settings` |
| Settings | `.header-top__settings-menu` |

#### Navigation

- `.main-nav`
- `.main-nav__root`
- `.main-nav__wrapper`
- `.main-nav-item`

#### Page

- `#maincontent`

(The official doc may list other anchors; check [CSS API](https://lumapps.github.io/customizations-api-doc/css/api.html).)

---

### CSS use cases

- **Increase desktop width**: default 1128px; at desktop breakpoint (e.g. `min-width: 80em`) set `width` for `.header-top__wrapper`, `.main-nav__wrapper`, `#maincontent` (e.g. 1280px). Test with your templates and widgets.
- **Top bar icon background color**: e.g. `.header-top__bookmarked-apps { background-color: #2ba0fd; }` and `.header-top__bookmarked-apps .lumx-icon { color: white; }`.
- **Custom font**: `@font-face` then `html, body { font-family: 'CustomFont' !important; }`.

#### LumApps breakpoints

- wide: ≥ 1280px  
- desktop: ≥ 1024px and < 1280px  
- tablet: ≥ 480px and < 1024px  
- mobile: ≥ 350px and < 480px  
- small: < 350px  

---

### CSS best practices

- Do not customize in CSS what is already configurable in the UI (e.g. bar colors, navigation).
- Rely on **documented anchors**; everything else is unsupported and may change.
- Avoid selectors based on **HTML tags**; use only anchor classes/IDs.
- **Where to put CSS**:  
  - **Site theme**: for anything not in the first paint.  
  - **Head (HTML)**: for anything visible on first paint (top bar, viewport widgets) to reduce “blink”.
- Combine with **custom CSS classes** that LumApps allows on some elements (content rows/cells, widgets, slideshow, navigation links, etc.).

---

### CSS deployment

1. LumApps Admin → **Style** → **Style** tab → **Advanced** section.
2. **Site theme**: paste CSS there (recommended for production after minification).
3. **Head tag (HTML)**: for CSS critical to first paint if needed.
4. Save.

In production: aim for 2–5 KB of added CSS; minify (e.g. [minifier.org](https://www.minifier.org/)); version code in a repo rather than relying only on the Site theme field.

---

## References

- **Official Customizations API documentation**: [https://lumapps.github.io/customizations-api-doc/](https://lumapps.github.io/customizations-api-doc/)
- **JavaScript**: [Getting started](https://lumapps.github.io/customizations-api-doc/javascript.html), [API](https://lumapps.github.io/customizations-api-doc/javascript/api.html), [Capabilities](https://lumapps.github.io/customizations-api-doc/javascript/capabilities.html), [Use cases](https://lumapps.github.io/customizations-api-doc/javascript/use-cases.html), [Development](https://lumapps.github.io/customizations-api-doc/javascript/development-and-deployment.html), [FAQ](https://lumapps.github.io/customizations-api-doc/javascript/faq.html), [Best practices](https://lumapps.github.io/customizations-api-doc/javascript/best-pratices.html)
- **CSS**: [Overview](https://lumapps.github.io/customizations-api-doc/css.html), [API (anchors)](https://lumapps.github.io/customizations-api-doc/css/api.html), [Use cases](https://lumapps.github.io/customizations-api-doc/css/use-cases.html), [Best practices](https://lumapps.github.io/customizations-api-doc/css/best-practices.html), [Development and deployment](https://lumapps.github.io/customizations-api-doc/css/development-and-deployment.html)
- **LumApps Docs**: [https://docs.lumapps.com](https://docs.lumapps.com)
- **Layout and widget styling (local resource)**: `lumapps-layout-and-widget-styling.md`
