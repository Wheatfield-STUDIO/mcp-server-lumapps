# LumApps — Layout and Styling (rows, cells, widgets)

Consolidated documentation on editing layout (rows and cells), row/cell styles, and widget styling. Changes made in the UI do not overwrite any Custom CSS already applied.

---

## 1. Editing layout

You can change the general layout by editing content, a community, or the directory.

### Who can edit the layout

Permissions depend on the entity type. In general, global administrators and site administrators can edit any layout. For details on roles, see LumApps *User roles* documentation.

| Context | Layout edit permissions |
|---------|--------------------------|
| **Content** | Users with Create & Edit role on the content type, and users added as Editors in the content configuration. If the content was built with fixed widgets or a simple template, only administrators can change the layout (by disabling Simple mode). |
| **Communities** | Community administrators and users with Create & Edit role. |
| **Spaces** | Space administrators. |
| **Directory** | Users with Create & Edit role. |

### Rows and cells

- For row and cell design options, refer to LumApps *Designing options* documentation.
- **Constraint**: you cannot add more than **4 cells side by side** in a single row.

### Create a cell structure

1. Edit one of: a piece of content, a content-type list, a content-type template, a community or space, or a directory.
2. Click a cell to open its configuration in the sidebar.
3. In the **Global** section, enable **Cell structure**.

### Enable a sticky cell

1. Same as creating a cell structure (edit the content/community/space/directory, click the cell).
2. In the **Global** section, enable **Cell structure** and **Sticky cell**.

---

## 2. Row and cell style

Style settings apply to the **row** or **cell** (position and appearance). Changes do not overwrite existing Custom CSS.

### Spacing (margin and padding)

- **Margin** and **Padding** are editable for the row or cell.
- **Margin** fields accept negative values.
- A lock control lets you apply the same value to all directions.

### Border

- **Size** (pixels), **color** (picker), and **radius** (border radius) are configurable.
- Enter numeric values in the pixel fields and choose the color from the list.
- The lock lets you apply the same value to all directions.

### Background

- **Color**: click to select (color picker).
- **Image**: choose via the LumApps Media Picker.
- **Shadow**: set the background shadow.

---

## 3. Widget style

Each **part of a widget** can be customized via the widget style. Changes do not overwrite Custom CSS already applied.

### Editable sections

The widget style has several areas: **overall**, **content**, **header**, **footer**. Each editable area is clearly identified in the UI. When you select an area, a dropdown lets you choose and customize values.

In each area you can edit: **spacing**, **border**, **background**.

### Spacing

- **Margin** and **Padding** for the widget position.
- Negative values are allowed for margins.
- Lock to apply the same value to all directions.

### Border

- **Size**, **color**, and **radius** of the border.
- Enter values in pixels and choose the color from the list.
- Lock to apply the same value to all directions.

### Background

- **Color** (color picker), **image** (Media Picker), **shadow** (background shadow).

### Header and footer: icon and title position

- In the **header** and **footer** sections you can place the icon and title by drag and drop.
- Display options: **block** or **inline**.
- Then adjust **Margin** and **Padding** for the icon and title.

### Hover (footer only)

- In the **Footer** section, hover mode options let you change:
  - **color** (default and hover),
  - **icon position**,
  - **size**.

---

## 4. Developer resources

- **Customizations API**: technical documentation for LumApps customizations (JavaScript and CSS).  
  → See the consolidated resource **`lumapps-customizations-api.md`** in this folder.  
  Official documentation: [https://lumapps.github.io/customizations-api-doc/](https://lumapps.github.io/customizations-api-doc/)
- **LumApps Docs** : [https://docs.lumapps.com](https://docs.lumapps.com)
