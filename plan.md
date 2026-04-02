# Plan: Left-Align Tab Names in Popover

## Objective
Make the tab names in the popup left-aligned to allow for easier scanning by the first letter of the tab name.

## Key Files & Context
- `__init__.py`: The `SEARCHTABS_PT_popover` panel class draws the list of operators for the matching tabs.

## Implementation Steps
1. **Remove explicit left alignment on the column:** Currently, `col.alignment = 'LEFT'` shrinks the width of the buttons to only fit their text. Remove this line so the column uses the default `'EXPAND'` behavior, allowing the items to be full width (better for hover effects).
2. **Add `emboss=False` to the operators:** To achieve left-aligned text within a full-width clickable area, we set the `emboss` parameter to `False` on the operator buttons. This makes them look and act like standard left-aligned menu items.
    - Locate `op = col.operator("searchtabs.switch_tab", text=entry['display'], icon=icon)` and change it to `op = col.operator("searchtabs.switch_tab", text=entry['display'], icon=icon, emboss=False)`.
    - Locate `op = col.operator("searchtabs.switch_tab", text=entry['display'], icon='NODE')` and change it to `op = col.operator("searchtabs.switch_tab", text=entry['display'], icon='NODE', emboss=False)`.

## Verification & Testing
1. Reload the add-on in Blender.
2. Open the "N-Panel Tabs" popup.
3. Observe that the list of tabs (both when searching and when empty) are now left-aligned and span the full width of the popover.