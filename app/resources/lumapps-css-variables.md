# LumApps CSS Variables — Reference

Consolidated documentation of CSS variables exposed by LumApps for theming and customization. Use them in the **Site theme** field in the Custom code panel (as custom CSS).

---

## How to use variables

**Prerequisite**: You must master principles of CSS.

If a variable is too vague and you need a more specific variable (e.g. variable applying only to broadcast emails), contact your LumApps representative.

The design system default theme acts as a starting point. Variables have default values (for example `--lumx-metadata-border-radius` is set to `0px`). From there, variable values can be modified to define how styles deviate from the default. To do so, you must inject variable values in the **Site theme** field in the **Custom code** panel (as regular custom CSS code).

Example: to modify the metadata component radius, inject `--lumx-metadata-border-radius: 16px;` as follows:

```css
:root {
  --lumx-metadata-border-radius: 16px;
}
```

This technique is suited for minor changes to the default theme. If more changes have to be done, use the dedicated Figma file and plugin instead.

### Figma file and plugin

LumApps CSS generator plugin helps customize LumApps right in the design tool Figma and then automatically generates variables to be used in the product. The plugin works with a specific Figma file thought of as a style guide. Use it as a starting point for new projects or for styles migration: going from hard-to-maintain custom CSS to safe CSS variables.

To access both the file and plugin, fill a request on this [form](https://docs.google.com/forms/d/e/1FAIpQLScwktgQG3BTN3OovFPKquBkeys7tnHCU9B-qFSYpwSK4T7T1g/viewform).

### Pitfalls — do not use

- **Shadow variables**: Only `--lumx-app-header-box-shadow` is documented. Do **not** use `--lumx-shadow-1`, `--lumx-shadow-2`, `--lumx-shadow-3`, `--lumx-shadow-4`, or `--lumx-shadow-5` (they do not exist).
- **Primary color tokens**: The design system uses `--lumx-color-primary-N`, `--lumx-color-primary-D1`, `--lumx-color-primary-D2`, `--lumx-color-primary-L2` … `--lumx-color-primary-L5`. Do **not** use `--lumx-color-primary-500`, `-600`, `-700` or other numeric suffixes (they do not exist).
- **Component class names**: This document lists **CSS variables** only. LumApps does not expose official class names here (e.g. `.lumx-button`, `.lumx-button--primary` do not exist in this reference). For theme-wide changes, use variables. For overrides that have no variable (e.g. button text-transform), prefer inspecting the site DOM or avoid inventing class names.

### Widget shadows (no CSS variable)

There is no CSS variable for widget shadows. By default LumApps applies `box-shadow: 0 2px 4px #00000024` to the selector below. To remove shadows from all site widgets, override with `box-shadow: none`:

```css
.widget:not(.widget--has-ungrouped-container-block) {
  box-shadow: none;
}
```

---

## App background and header

| Name | Value |
|------|-------|
| `--lumx-app-background` | var(--lumx-color-dark-L6) |
| `--lumx-app-background-alt` | var(--lumx-color-light-N) |

### App header

| Name | Value |
|------|-------|
| `--lumx-app-header-logo-height` | 32px |
| `--lumx-app-header-box-shadow` | 0 4px 4px 0 rgba(0, 0, 0, 0.12) |
| `--lumx-app-header-border-bottom-width` | 0 |
| `--lumx-app-header-border-bottom-color` | transparent |

---

## Text styles

### Custom text styles

| Name | Value |
|------|-------|
| `--lumx-typography-custom-title1-font-size` | 2.5rem |
| `--lumx-typography-custom-title1-font-weight` | 700 |
| `--lumx-typography-custom-title1-line-height` | 3.125rem |
| `--lumx-typography-custom-title2-font-size` | 1.875rem |
| `--lumx-typography-custom-title2-font-weight` | 700 |
| `--lumx-typography-custom-title2-line-height` | 2.5rem |
| `--lumx-typography-custom-title3-font-size` | 1.5rem |
| `--lumx-typography-custom-title3-font-weight` | 700 |
| `--lumx-typography-custom-title3-line-height` | 2rem |
| `--lumx-typography-custom-title4-font-size` | 1.25rem |
| `--lumx-typography-custom-title4-font-weight` | 700 |
| `--lumx-typography-custom-title4-line-height` | 1.875rem |
| `--lumx-typography-custom-title5-font-size` | 1rem |
| `--lumx-typography-custom-title5-font-weight` | 700 |
| `--lumx-typography-custom-title5-line-height` | 1.5rem |
| `--lumx-typography-custom-title6-font-size` | 0.875rem |
| `--lumx-typography-custom-title6-font-weight` | 700 |
| `--lumx-typography-custom-title6-line-height` | 1.25rem |
| `--lumx-typography-custom-intro-font-size` | 1.125rem |
| `--lumx-typography-custom-intro-font-weight` | 400 |
| `--lumx-typography-custom-intro-line-height` | 1.875rem |
| `--lumx-typography-custom-body-font-size` | 0.875rem |
| `--lumx-typography-custom-body-font-weight` | 400 |
| `--lumx-typography-custom-body-line-height` | 1.25rem |
| `--lumx-typography-custom-body-large-font-size` | 1rem |
| `--lumx-typography-custom-body-large-font-weight` | 400 |
| `--lumx-typography-custom-body-large-line-height` | 1.5rem |
| `--lumx-typography-custom-quote-font-size` | 1rem |
| `--lumx-typography-custom-quote-font-weight` | 400 |
| `--lumx-typography-custom-quote-line-height` | 1.5rem |
| `--lumx-typography-custom-publish-info-font-size` | 0.875rem |
| `--lumx-typography-custom-publish-info-font-weight` | 400 |
| `--lumx-typography-custom-publish-info-line-height` | 1.25rem |
| `--lumx-typography-custom-button-size-m-font-size` | 0.875rem |
| `--lumx-typography-custom-button-size-m-font-weight` | 700 |
| `--lumx-typography-custom-button-size-m-line-height` | 1.25rem |
| `--lumx-typography-custom-button-size-s-font-size` | 0.75rem |
| `--lumx-typography-custom-button-size-s-font-weight` | 700 |
| `--lumx-typography-custom-button-size-s-line-height` | normal |
| `--lumx-typography-custom-tag-font-size` | 0.875rem |
| `--lumx-typography-custom-tag-font-weight` | 400 |
| `--lumx-typography-custom-tag-line-height` | 1.25rem |
| `--lumx-typography-custom-metadata-font-size` | 0.875rem |
| `--lumx-typography-custom-metadata-font-weight` | 400 |
| `--lumx-typography-custom-metadata-line-height` | 1.25rem |

### Custom text styles attribution

- **--lumx-typography-custom-title1**: HTML widget: Heading 1 (`<h1>`), Article: Title, Title widget: Text
- **--lumx-typography-custom-title2**: HTML widget: Heading 2 (`<h2>`), Article: Heading 1
- **--lumx-typography-custom-title3**: HTML widget: Heading 3 (`<h3>`), Article: Heading 2, Community title widget: Text, Content list widget (cover view): Content title
- **--lumx-typography-custom-title4**: HTML widget: Heading 4 (`<h4>`), Content list widget (other than cover): Content title, Community list: Community title, Post list: Post title
- **--lumx-typography-custom-title5**: HTML widget: Heading 5 (`<h5>`), Directory entry: title, Email: Sender, File list: File name, Link: title, User list: Primary field (Name by default)
- **--lumx-typography-custom-title6**: HTML widget: Heading 6 (`<h6>`)
- **--lumx-typography-custom-intro**: Intro widget: Text
- **--lumx-typography-custom-body-large**: HTML widget: Normal text, Article: Normal text
- **--lumx-typography-custom-body**: Content list: excerpt, Post list: description, Email: title/snippet, Community list: content
- **--lumx-typography-custom-quote**: HTML: Block-quote, Article: Block-quote
- **--lumx-typography-custom-publish-info**: Content list: Publish date, Article: Date, Metadata: Publication date
- **--lumx-typography-custom-tag**: Tag component: label
- **--lumx-typography-custom-metadata**: Metadata component: label
- **--lumx-typography-custom-button-size-m**: Button (size m): label
- **--lumx-typography-custom-button-size-s**: Button (size s): label

### Default font

| Name | Value |
|------|-------|
| `--lumx-typography-font-family` | [desired font name] |
| `--lumx-typography-font-weight-regular` | [desired font weight for regular] |
| `--lumx-typography-font-weight-bold` | [desired font weight for bold] |

---

## Components (Button to Metadata)

### Button

| Name | Value |
|------|-------|
| `--lumx-button-border-radius` | 4px |
| `--lumx-button-emphasis-high-state-default-padding-horizontal` | 16px |
| `--lumx-button-emphasis-high-state-default-border-width` | 0px |
| `--lumx-button-emphasis-high-state-default-theme-light-background-color` | var(--lumx-color-primary-N) |
| `--lumx-button-emphasis-high-state-default-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-high-state-default-theme-light-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-high-state-default-theme-dark-background-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-high-state-default-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-high-state-default-theme-dark-color` | var(--lumx-color-primary-N) |
| `--lumx-button-emphasis-high-state-hover-padding-horizontal` | 16px |
| `--lumx-button-emphasis-high-state-hover-border-width` | 0px |
| `--lumx-button-emphasis-high-state-hover-theme-light-background-color` | var(--lumx-color-primary-D1) |
| `--lumx-button-emphasis-high-state-hover-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-high-state-hover-theme-light-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-high-state-hover-theme-dark-background-color` | var(--lumx-color-light-L1) |
| `--lumx-button-emphasis-high-state-hover-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-high-state-hover-theme-dark-color` | var(--lumx-color-primary-N) |
| `--lumx-button-emphasis-high-state-active-padding-horizontal` | 16px |
| `--lumx-button-emphasis-high-state-active-border-width` | 0px |
| `--lumx-button-emphasis-high-state-active-theme-light-background-color` | var(--lumx-color-primary-D2) |
| `--lumx-button-emphasis-high-state-active-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-high-state-active-theme-light-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-high-state-active-theme-dark-background-color` | var(--lumx-color-light-L2) |
| `--lumx-button-emphasis-high-state-active-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-high-state-active-theme-dark-color` | var(--lumx-color-primary-N) |
| `--lumx-button-emphasis-medium-state-default-padding-horizontal` | 16px |
| `--lumx-button-emphasis-medium-state-default-border-width` | 0px |
| `--lumx-button-emphasis-medium-state-default-theme-light-background-color` | var(--lumx-color-dark-L5) |
| `--lumx-button-emphasis-medium-state-default-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-medium-state-default-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-button-emphasis-medium-state-default-theme-dark-background-color` | var(--lumx-color-light-L5) |
| `--lumx-button-emphasis-medium-state-default-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-medium-state-default-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-medium-state-hover-padding-horizontal` | 16px |
| `--lumx-button-emphasis-medium-state-hover-border-width` | 0px |
| `--lumx-button-emphasis-medium-state-hover-theme-light-background-color` | var(--lumx-color-dark-L4) |
| `--lumx-button-emphasis-medium-state-hover-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-medium-state-hover-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-button-emphasis-medium-state-hover-theme-dark-background-color` | var(--lumx-color-light-L4) |
| `--lumx-button-emphasis-medium-state-hover-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-medium-state-hover-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-medium-state-active-padding-horizontal` | 16px |
| `--lumx-button-emphasis-medium-state-active-border-width` | 0px |
| `--lumx-button-emphasis-medium-state-active-theme-light-background-color` | var(--lumx-color-dark-L3) |
| `--lumx-button-emphasis-medium-state-active-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-medium-state-active-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-button-emphasis-medium-state-active-theme-dark-background-color` | var(--lumx-color-light-L3) |
| `--lumx-button-emphasis-medium-state-active-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-medium-state-active-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-low-state-default-padding-horizontal` | 8px |
| `--lumx-button-emphasis-low-state-default-border-width` | 0px |
| `--lumx-button-emphasis-low-state-default-theme-light-background-color` | transparent |
| `--lumx-button-emphasis-low-state-default-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-low-state-default-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-button-emphasis-low-state-default-theme-dark-background-color` | transparent |
| `--lumx-button-emphasis-low-state-default-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-low-state-default-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-low-state-hover-padding-horizontal` | 8px |
| `--lumx-button-emphasis-low-state-hover-border-width` | 0px |
| `--lumx-button-emphasis-low-state-hover-theme-light-background-color` | var(--lumx-color-dark-L5) |
| `--lumx-button-emphasis-low-state-hover-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-low-state-hover-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-button-emphasis-low-state-hover-theme-dark-background-color` | var(--lumx-color-light-L5) |
| `--lumx-button-emphasis-low-state-hover-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-low-state-hover-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-low-state-active-padding-horizontal` | 8px |
| `--lumx-button-emphasis-low-state-active-border-width` | 0px |
| `--lumx-button-emphasis-low-state-active-theme-light-background-color` | var(--lumx-color-dark-L4) |
| `--lumx-button-emphasis-low-state-active-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-low-state-active-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-button-emphasis-low-state-active-theme-dark-background-color` | var(--lumx-color-light-L4) |
| `--lumx-button-emphasis-low-state-active-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-low-state-active-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-selected-state-default-border-width` | 0px |
| `--lumx-button-emphasis-selected-state-default-theme-light-background-color` | var(--lumx-color-primary-L5) |
| `--lumx-button-emphasis-selected-state-default-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-selected-state-default-theme-light-color` | var(--lumx-color-primary-D2) |
| `--lumx-button-emphasis-selected-state-default-theme-dark-background-color` | var(--lumx-color-light-L3) |
| `--lumx-button-emphasis-selected-state-default-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-selected-state-default-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-selected-state-hover-border-width` | 0px |
| `--lumx-button-emphasis-selected-state-hover-theme-light-background-color` | var(--lumx-color-primary-L4) |
| `--lumx-button-emphasis-selected-state-hover-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-selected-state-hover-theme-light-color` | var(--lumx-color-primary-D2) |
| `--lumx-button-emphasis-selected-state-hover-theme-dark-background-color` | var(--lumx-color-light-L4) |
| `--lumx-button-emphasis-selected-state-hover-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-selected-state-hover-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-button-emphasis-selected-state-active-border-width` | 0px |
| `--lumx-button-emphasis-selected-state-active-theme-light-background-color` | var(--lumx-color-primary-L3) |
| `--lumx-button-emphasis-selected-state-active-theme-light-border-color` | transparent |
| `--lumx-button-emphasis-selected-state-active-theme-light-color` | var(--lumx-color-primary-D2) |
| `--lumx-button-emphasis-selected-state-active-theme-dark-background-color` | var(--lumx-color-light-L5) |
| `--lumx-button-emphasis-selected-state-active-theme-dark-border-color` | transparent |
| `--lumx-button-emphasis-selected-state-active-theme-dark-color` | var(--lumx-color-light-N) |

### Chips

| Name | Value |
|------|-------|
| `--lumx-chip-emphasis-selected-state-default-border-width` | 0px |
| `--lumx-chip-emphasis-selected-state-hover-border-width` | 0px |
| `--lumx-chip-emphasis-selected-state-active-border-width` | 0px |
| `--lumx-chip-emphasis-selected-state-default-theme-light-background-color` | var(--lumx-color-primary-L5) |
| `--lumx-chip-emphasis-selected-state-default-theme-dark-background-color` | var(--lumx-color-light-L3) |
| `--lumx-chip-emphasis-selected-state-hover-theme-light-background-color` | var(--lumx-color-primary-L4) |
| `--lumx-chip-emphasis-selected-state-hover-theme-dark-background-color` | var(--lumx-color-light-L4) |
| `--lumx-chip-emphasis-selected-state-active-theme-light-background-color` | var(--lumx-color-primary-L3) |
| `--lumx-chip-emphasis-selected-state-active-theme-dark-background` | var(--lumx-color-light-L5) |
| `--lumx-chip-emphasis-selected-state-default-theme-light-border-color` | transparent |
| `--lumx-chip-emphasis-selected-state-default-theme-dark-border-color` | transparent |
| `--lumx-chip-emphasis-selected-state-hover-theme-light-border-color` | transparent |
| `--lumx-chip-emphasis-selected-state-hover-theme-dark-border-color` | transparent |
| `--lumx-chip-emphasis-selected-state-active-theme-light-border-color` | transparent |
| `--lumx-chip-emphasis-selected-state-active-theme-dark-border-color` | transparent |

### Metadata

| Name | Value |
|------|-------|
| `--lumx-metadata-list-separator` | · |
| `--lumx-metadata-height` | 20px |
| `--lumx-metadata-border-radius` | 0px |
| `--lumx-metadata-state-default-padding-horizontal` | 0px |
| `--lumx-metadata-state-default-border-width` | 0px |
| `--lumx-metadata-state-default-theme-light-color` | var(--lumx-color-dark-L2) |
| `--lumx-metadata-state-default-theme-dark-color` | var(--lumx-color-light-L2) |
| `--lumx-metadata-state-hover-padding-horizontal` | 0px |
| `--lumx-metadata-state-hover-border-width` | 0px |
| `--lumx-metadata-state-hover-theme-light-color` | var(--lumx-color-dark-L1) |
| `--lumx-metadata-state-hover-theme-dark-color` | var(--lumx-color-light-L1) |
| `--lumx-metadata-state-active-padding-horizontal` | 0px |
| `--lumx-metadata-state-active-border-width` | 0px |
| `--lumx-metadata-state-active-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-metadata-state-active-theme-dark-color` | var(--lumx-color-light-N) |

---

## Components (Navigation to Text field & select)

### Navigation

| Name | Value |
|------|-------|
| `--lumx-navigation-item-padding-horizontal` | 8px |
| `--lumx-navigation-item-border-radius` | 4px |
| `--lumx-navigation-item-emphasis-low-state-default-border-top-width` | 0px |
| `--lumx-navigation-item-emphasis-low-state-default-border-right-width` | 0px |
| `--lumx-navigation-item-emphasis-low-state-default-border-bottom-width` | 0px |
| `--lumx-navigation-item-emphasis-low-state-default-border-left-width` | 0px |
| `--lumx-navigation-item-emphasis-low-state-default-theme-light-background-color` | transparent |
| `--lumx-navigation-item-emphasis-low-state-default-theme-light-border-color` | var(--lumx-color-dark-L5) |
| `--lumx-navigation-item-emphasis-low-state-default-theme-light-icon-color` | var(--lumx-color-dark-N) |
| `--lumx-navigation-item-emphasis-low-state-default-theme-light-label-color` | var(--lumx-color-dark-N) |
| `--lumx-navigation-item-emphasis-low-state-default-theme-light-chevron-background-color` | transparent |
| `--lumx-navigation-item-emphasis-low-state-default-theme-light-chevron-color` | var(--lumx-color-dark-N) |
| `--lumx-navigation-item-emphasis-low-state-default-theme-dark-background-color` | transparent |
| `--lumx-navigation-item-emphasis-low-state-default-theme-dark-border-color` | var(--lumx-color-light-L5) |
| `--lumx-navigation-item-emphasis-low-state-default-theme-dark-icon-color` | var(--lumx-color-light-N) |
| `--lumx-navigation-item-emphasis-low-state-default-theme-dark-label-color` | var(--lumx-color-light-N) |
| `--lumx-navigation-item-emphasis-low-state-default-theme-dark-chevron-background-color` | transparent |
| `--lumx-navigation-item-emphasis-low-state-default-theme-dark-chevron-color` | var(--lumx-color-light-N) |
| *(hover/active/selected variants follow same pattern; see full list in source)* |

### Side navigation

| Name | Value |
|------|-------|
| `--lumx-side-navigation-item-emphasis-selected-state-default-border-width` | 0px |
| `--lumx-side-navigation-item-emphasis-selected-state-default-theme-light-border-color` | transparent |
| `--lumx-side-navigation-item-emphasis-selected-state-default-theme-light-background-color` | var(--lumx-color-primary-L5) |
| `--lumx-side-navigation-item-emphasis-selected-state-hover-border-width` | 0px |
| `--lumx-side-navigation-item-emphasis-selected-state-hover-theme-light-border-color` | transparent |
| `--lumx-side-navigation-item-emphasis-selected-state-hover-theme-light-background-color` | var(--lumx-color-primary-L4) |
| `--lumx-side-navigation-item-emphasis-selected-state-active-border-width` | 0px |
| `--lumx-side-navigation-item-emphasis-selected-state-active-theme-light-border-color` | transparent |
| `--lumx-side-navigation-item-emphasis-selected-state-active-theme-light-background-color` | var(--lumx-color-primary-L3) |

### Tabs

| Name | Value |
|------|-------|
| `--lumx-tabs-link-border-radius` | 0px |
| `--lumx-tabs-link-emphasis-low-state-default-border-*-width` | 0/0/2px/0 (top, right, bottom, left) |
| `--lumx-tabs-link-emphasis-low-state-default-theme-light-background-color` | transparent |
| `--lumx-tabs-link-emphasis-low-state-default-theme-light-border-color` | var(--lumx-color-dark-L5) |
| `--lumx-tabs-link-emphasis-low-state-default-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-tabs-link-emphasis-low-state-default-theme-dark-*` | (mirror light theme) |
| *(hover/active/selected states: same structure with hover/active/selected in name)* |
| `--lumx-tabs-link-emphasis-selected-state-default-theme-light-border-color` | var(--lumx-color-primary-N) |
| `--lumx-tabs-link-emphasis-selected-state-default-theme-light-color` | var(--lumx-color-dark-N) |

### Tags

| Name | Value |
|------|-------|
| `--lumx-tag-list-separator` | · |
| `--lumx-tag-height` | 20px |
| `--lumx-tag-border-radius` | 0px |
| `--lumx-tag-state-default-padding-horizontal` | 0px |
| `--lumx-tag-state-default-border-width` | 0px |
| `--lumx-tag-state-default-theme-light-color` | var(--lumx-color-dark-L2) |
| `--lumx-tag-state-default-theme-dark-color` | var(--lumx-color-light-L2) |
| `--lumx-tag-state-hover-*` / `--lumx-tag-state-active-*` | (same pattern) |

### Text field & select

| Name | Value |
|------|-------|
| `--lumx-text-field-input-padding-horizontal` | 12px |
| `--lumx-text-field-input-border-radius` | 4px |
| `--lumx-text-field-state-default-input-border-*-width` | 1px (all sides) |
| `--lumx-text-field-state-default-theme-light-header-label-color` | var(--lumx-color-dark-N) |
| `--lumx-text-field-state-default-theme-light-input-background-color` | var(--lumx-color-dark-L6) |
| `--lumx-text-field-state-default-theme-light-input-border-color` | var(--lumx-color-dark-L4) |
| `--lumx-text-field-state-default-theme-light-input-content-color` | var(--lumx-color-dark-N) |
| `--lumx-text-field-state-default-theme-light-input-placeholder-color` | var(--lumx-color-dark-L2) |
| `--lumx-text-field-state-default-theme-dark-*` | (mirror) |
| `--lumx-text-field-state-hover-*` | (same structure, hover) |
| `--lumx-text-field-state-focus-input-border-*-width` | 2px (all sides) |
| `--lumx-text-field-state-focus-theme-light-input-border-color` | var(--lumx-color-primary-L2) |
| `--lumx-text-field-state-focus-theme-dark-input-border-color` | var(--lumx-color-light-L2) |

### Thumbnails

| Name | Value |
|------|-------|
| `--lumx-thumbnail-aspect-ratio` | x/x (e.g. 3/2, 16/9). Use with caution. |

---

## Widgets

### Community list

| Name | Value |
|------|-------|
| `--lumx-community-block-title-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-community-block-title-theme-dark-color` | var(--lumx-color-light-N) |

### Content list

| Name | Value |
|------|-------|
| `--lumx-content-block-title-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-content-block-title-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-content-block-title-text-transform` | none |

### Directory entries

| Name | Value |
|------|-------|
| `--lumx-directory-entry-block-orientation-h-thumbnail-size` | var(--lumx-size-m) |
| `--lumx-directory-entry-block-orientation-v-thumbnail-size` | var(--lumx-size-l) |
| `--lumx-directory-entry-block-title-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-directory-entry-block-title-theme-dark-color` | var(--lumx-color-light-N) |

### Header and footer

| Name | Value |
|------|-------|
| `--lumx-widget-header-font-family` | inherited font |
| `--lumx-widget-footer-font-family` | inherited font |

### Introduction

| Name | Value |
|------|-------|
| `--lumx-widget-intro-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-widget-intro-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-widget-intro-text-align` | left |
| `--lumx-widget-intro-alignment-h` | flex-start |

### Post list

| Name | Value |
|------|-------|
| `--lumx-post-block-title-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-post-block-title-theme-dark-color` | var(--lumx-color-light-N) |

### Title

| Name | Value |
|------|-------|
| `--lumx-widget-title-theme-light-color` | var(--lumx-color-dark-N) |
| `--lumx-widget-title-theme-dark-color` | var(--lumx-color-light-N) |
| `--lumx-widget-title-text-transform` | none |
| `--lumx-widget-title-text-align` | left |
| `--lumx-widget-title-alignment-h` | flex-start |
| `--lumx-widget-title-alignment-v` | flex-start |
