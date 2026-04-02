# Sidebar Tab Search - Blender Add-on
# Copyright (C) 2025 McKaa
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

bl_info = {
    "name": "Sidebar Tab Search v2",
    "author": "McKaa (Powered by Antigravity)",
    "version": (2, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Header",
    "description": "Deep text search for Sidebar (N-Panel) tabs, panels, properties, and buttons.",
    "warning": "",
    "doc_url": "",
    "tracker_url": "https://github.com/Code-Garvi/sidebar-tab-search-blender-addon",
    "support": "COMMUNITY",
    "category": "Interface",
}

import bpy
import time

# --- Deep Search Infrastructure ---

_SEARCH_CACHE = {"hash": None, "entries": []}
_SEARCH_CACHE_LAST_UPDATE = 0.0

class MockLayout:
    """Mock layout to capture text from panel draw methods without drawing."""
    def __init__(self):
        self.found_strings = set()
        self.use_property_split = False
        self.use_property_decorate = False
        self.active = True
        self.enabled = True
        self.alignment = 'EXPAND'
        self.scale_x = 1.0
        self.scale_y = 1.0

    def row(self, **kwargs): return self
    def column(self, **kwargs): return self
    def column_flow(self, **kwargs): return self
    def box(self): return self
    def split(self, **kwargs): return self
    def grid_flow(self, **kwargs): return self
    
    def prop(self, data, property, text=None, **kwargs):
        if text:
            self.found_strings.add(str(text))
        elif hasattr(data, "bl_rna"):
            try:
                prop_def = data.bl_rna.properties.get(str(property))
                if prop_def:
                    self.found_strings.add(str(prop_def.name))
            except: pass
        return self

    def prop_search(self, data, property, search_data, search_property, text="", **kwargs):
        if text:
            self.found_strings.add(str(text))
        elif hasattr(data, "bl_rna"):
            try:
                prop_def = data.bl_rna.properties.get(str(property))
                if prop_def:
                    self.found_strings.add(str(prop_def.name))
            except: pass
        return self

    def operator(self, operator, text=None, **kwargs):
        if text:
            self.found_strings.add(str(text))
        elif operator:
            try:
                name = str(operator).split(".")[-1].replace("_", " ").title()
                self.found_strings.add(name)
            except: pass
        return self

    def label(self, text="", **kwargs):
        if text: self.found_strings.add(str(text))
        return self
    
    def menu(self, menu, text="", **kwargs):
        if text: self.found_strings.add(str(text))
        return self
        
    def template_ID(self, data, property, new="", open="", unlink="", text="", **kwargs):
        if text: self.found_strings.add(str(text))
        return self

    def __getattr__(self, attr):
        return lambda *args, **kwargs: self

class MockPanel:
    def __init__(self, layout, panel_class):
        self.layout = layout
        self._panel_class = panel_class

    def __getattr__(self, attr):
        return getattr(self._panel_class, attr)

# Property group storing the search query
class SEARCHTABS_PG_properties(bpy.types.PropertyGroup):
    search_query: bpy.props.StringProperty(
        name="Search Tab",
        description="Type to search sidebar tabs",
        default="",
        options={'TEXTEDIT_UPDATE'}  # Update on every keystroke or after confirmation
    )

# Operator to switch sidebar category
class SEARCHTABS_OT_switch_tab(bpy.types.Operator):
    """Switch to selected sidebar tab"""
    bl_idname = "searchtabs.switch_tab"
    bl_label = "Switch Tab"
    
    category_name: bpy.props.StringProperty()
    target_panel_label: bpy.props.StringProperty(default="")

    def execute(self, context):
        # 1. Make sure the sidebar is visible
        if context.space_data and context.space_data.type == 'VIEW_3D':
            # If the sidebar is hidden, show it
            if not context.space_data.show_region_ui:
                context.space_data.show_region_ui = True

        # 2. Try to find the 'UI' region (Sidebar) in the active area
        sidebar_region = None
        for region in context.area.regions:
            if region.type == 'UI':
                sidebar_region = region
                break
        
        if sidebar_region:
            try:
                # Get list of available categories in current context
                available_categories = []
                for panel in bpy.types.Panel.__subclasses__():
                    if (hasattr(panel, 'bl_space_type') and panel.bl_space_type == 'VIEW_3D' and
                        hasattr(panel, 'bl_region_type') and panel.bl_region_type == 'UI' and
                        hasattr(panel, 'bl_category')):
                        
                        # Check if panel is available in current context
                        if hasattr(panel, 'poll'):
                            try:
                                if not panel.poll(context):
                                    continue
                            except Exception:
                                # If poll fails, skip this panel
                                continue
                        
                        # Check options for hidden headers
                        if hasattr(panel, 'bl_options'):
                           if 'HIDE_HEADER' in panel.bl_options:
                               continue

                        cat = panel.bl_category
                        if cat not in available_categories:
                            available_categories.append(cat)
                
                # Check if requested category is available
                if self.category_name not in available_categories:
                    self.report({'INFO'}, f"Tab '{self.category_name}' currently hidden")
                    return {'CANCELLED'}
                
                # Try to switch to the category
                try:
                    sidebar_region.active_panel_category = self.category_name
                except Exception as e:
                    # Catch the "enum not found" error specifically which happens when
                    # a category exists in theory (registered) but is hidden in practice.
                    error_str = str(e)
                    if "not found in" in error_str:
                        self.report({'INFO'}, f"Tab '{self.category_name}' is empty or unavailable")
                        return {'CANCELLED'}
                    else:
                        raise e # Re-raise other unexpected errors

                # Retry (often needed on first sidebar opening)
                if sidebar_region.active_panel_category != self.category_name:
                     try:
                        sidebar_region.active_panel_category = self.category_name
                     except Exception:
                         pass
                
                # Force region refresh
                sidebar_region.tag_redraw()
                
                # Try to scroll the view to the top
                with context.temp_override(area=context.area, region=sidebar_region):
                    try:
                        # Reset scroll to top
                        bpy.ops.view2d.scroll_up(deltas=100)
                    except Exception:
                        pass 

                return {'FINISHED'}
            except Exception as e:
                # If there's still an error, report it but don't crash
                self.report({'WARNING'}, f"Warning: {e}")
                return {'FINISHED'} # Return finished to not block the UI
        else:
            self.report({'WARNING'}, "Sidebar not found.")
            return {'CANCELLED'}

# Popover Panel (popup window)
class SEARCHTABS_PT_popover(bpy.types.Panel):
    """Creates a search popover panel"""
    bl_label = "Search Tabs"
    bl_idname = "SEARCHTABS_PT_popover"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 14 # Slightly wider window for long names

    def draw(self, context):
        global _SEARCH_CACHE
        layout = self.layout
        props = context.scene.searchtabs_props

        # Input field
        row = layout.row(align=True)
        row.prop(props, "search_query", text="", icon='VIEWZOOM')

        query = props.search_query.lower()

        # Collecting data: Category -> List of Panels (Labels)
        
        # Check cache validity (simple hash based on mode and active object)
        current_hash = hash(context.mode)
        if context.active_object:
            current_hash = hash((context.mode, context.active_object.name))
            
        if _SEARCH_CACHE["hash"] != current_hash:
            # Regenerate Index
            new_entries = []
            seen_categories = set()
            
            for panel in bpy.types.Panel.__subclasses__():
                if (hasattr(panel, 'bl_space_type') and panel.bl_space_type == 'VIEW_3D' and
                    hasattr(panel, 'bl_region_type') and panel.bl_region_type == 'UI' and
                    hasattr(panel, 'bl_category')):
                    
                    # Check poll
                    if hasattr(panel, 'poll'):
                        try:
                            if not panel.poll(context): continue
                        except: continue
                    
                    if hasattr(panel, 'bl_options') and 'HIDE_HEADER' in panel.bl_options:
                        continue

                    cat = panel.bl_category
                    if cat == " Search": continue

                    label = getattr(panel, 'bl_label', "")
                    
                    # 1. Add Category
                    if cat not in seen_categories:
                        new_entries.append({'search_text': cat.lower(), 'display': cat, 'cat': cat, 'is_main': True})
                        seen_categories.add(cat)
                    
                    # 2. Add Panel Header
                    if label and label != cat:
                        new_entries.append({
                            'search_text': f"{label} {cat}".lower(),
                            'display': f"{label} ({cat})",
                            'cat': cat,
                            'is_main': False
                        })
                        
                    # 3. Deep Search (Introspect Draw Method)
                    if hasattr(panel, 'draw'):
                        try:
                            mock_layout = MockLayout()
                            mock_panel = MockPanel(mock_layout, panel)
                            # Run the draw method
                            panel.draw(mock_panel, context)
                            
                            for text in mock_layout.found_strings:
                                if not text or text == label: continue
                                new_entries.append({
                                    'search_text': f"{text} {label} {cat}".lower(),
                                    'display': f"{text} ({label})",
                                    'cat': cat,
                                    'is_main': False
                                })
                        except Exception:
                            # Silently fail if a specific panel's draw logic crashes in mock context
                            pass

            _SEARCH_CACHE["entries"] = new_entries
            _SEARCH_CACHE["hash"] = current_hash
            
            global _SEARCH_CACHE_LAST_UPDATE
            now = time.time()
            if _SEARCH_CACHE_LAST_UPDATE == 0.0:
                print(f"Sidebar Tab Search: Cache initialized with {len(new_entries)} entries.")
            else:
                elapsed = now - _SEARCH_CACHE_LAST_UPDATE
                print(f"Sidebar Tab Search: Cache updated with {len(new_entries)} entries. Time since last update: {elapsed:.3f} seconds.")
            _SEARCH_CACHE_LAST_UPDATE = now
            
        entries = _SEARCH_CACHE["entries"]

        # Alphabetical sorting
        entries.sort(key=lambda x: x['display'])

        # Display
        col = layout.column(align=True)
        
        # Get limit from preferences
        limit = 25
        try:
            limit = context.preferences.addons[__name__].preferences.max_search_results
        except (KeyError, AttributeError):
            pass

        found_count = 0
        if len(query) >= 2:
            for entry in entries:
                if query in entry['search_text']:
                    found_count += 1
                    # Limit results to avoid clutter with short queries
                    if found_count > limit:
                        break
                    
                    icon = 'NODE' if entry['is_main'] else 'DOT'
                    op = col.operator("searchtabs.switch_tab", text=entry['display'], icon=icon)
                    op.category_name = entry['cat']
            
            if found_count == 0:
                col.label(text="No results")
        elif len(query) == 1:
            col.label(text="Type at least 2 characters...")
        else:
            col.label(text="Type to search...")
            # Show only main categories when empty
            main_cats = sorted([e for e in entries if e['is_main']], key=lambda x: x['display'])
            for entry in main_cats:
                op = col.operator("searchtabs.switch_tab", text=entry['display'], icon='NODE')
                op.category_name = entry['cat']

# Function to draw the icon in the header
def draw_header_icon(self, context):
    layout = self.layout
    layout.popover(panel="SEARCHTABS_PT_popover", text="N-Pannel Tabs", icon='VIEWZOOM')

# Addon Preferences
class SEARCHTABS_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    max_search_results: bpy.props.IntProperty(
        name="Max Search Results",
        description="Maximum number of displayed/found items",
        default=25,
        min=1,
        max=500
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "max_search_results")

# Registration
classes = (
    SEARCHTABS_PG_properties,
    SEARCHTABS_OT_switch_tab,
    SEARCHTABS_PT_popover,
    SEARCHTABS_AddonPreferences,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.searchtabs_props = bpy.props.PointerProperty(type=SEARCHTABS_PG_properties)
    
    # Add to 3D view header
    # First try to remove to avoid duplicates when reloading in the same session
    try:
        bpy.types.VIEW3D_HT_tool_header.remove(draw_header_icon)
    except ValueError:
        pass
    bpy.types.VIEW3D_HT_tool_header.append(draw_header_icon)

def unregister():
    # Remove from header
    try:
        bpy.types.VIEW3D_HT_tool_header.remove(draw_header_icon)
    except ValueError:
        pass
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.searchtabs_props

if __name__ == "__main__":
    register()
