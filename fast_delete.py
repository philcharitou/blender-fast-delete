# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Fast Delete",
    "author": "Phil Charitou",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > Object menu / Right-click menu, Outliner > Right-click (or F3 search)",
    "description": "Delete thousands of objects and whole collection hierarchies in one batch instead of one at a time",
    "category": "Object",
}

import time

import bpy
from bpy.props import BoolProperty, StringProperty

NAME_SEP = "\x1f"


def build_children_map():
    children = {}
    for ob in bpy.data.objects:
        parent = ob.parent
        if parent is not None:
            children.setdefault(parent.as_pointer(), []).append(ob)
    return children


def collect_with_descendants(objects, children_map):
    result = {ob.as_pointer(): ob for ob in objects}
    stack = list(objects)
    while stack:
        ob = stack.pop()
        for child in children_map.get(ob.as_pointer(), ()):
            key = child.as_pointer()
            if key not in result:
                result[key] = child
                stack.append(child)
    return result


def batch_delete(doomed_objects, children_map, extra_ids=(), keep_child_transforms=True, purge_data=True):
    """Remove objects (dict pointer -> Object) plus any extra IDs in one pass.

    Returns (objects_removed, data_blocks_purged).
    """
    # Handle children that stay behind but lose their parent
    survivors = []
    if keep_child_transforms:
        for key in doomed_objects:
            for child in children_map.get(key, ()):
                if child.as_pointer() not in doomed_objects:
                    survivors.append((child, child.matrix_world.copy()))

    data_blocks = set()
    if purge_data:
        data_blocks = {ob.data for ob in doomed_objects.values() if ob.data is not None}

    bpy.data.batch_remove(list(doomed_objects.values()) + list(extra_ids))

    for child, matrix in survivors:
        child.matrix_world = matrix

    orphans = [d for d in data_blocks if d.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)

    return len(doomed_objects), len(orphans)


def ensure_object_mode(context):
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


class OBJECT_OT_fast_delete(bpy.types.Operator):
    """Delete selected objects in a single batch (much faster for large selections)"""
    bl_idname = "object.fast_delete"
    bl_label = "Fast Delete"
    bl_options = {'REGISTER', 'UNDO'}

    include_children: BoolProperty(
        name="Include Children",
        description="Also delete every descendant of the selected objects",
        default=False,
    )
    keep_child_transforms: BoolProperty(
        name="Keep Child Transforms",
        description="Children that survive keep their world-space position when their parent is deleted",
        default=True,
    )
    purge_data: BoolProperty(
        name="Remove Orphaned Data",
        description="Also remove meshes, curves, etc. left with no users by this delete",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        start = time.perf_counter()
        ensure_object_mode(context)

        selected = list(context.selected_objects)
        children_map = build_children_map()

        if self.include_children:
            doomed = collect_with_descendants(selected, children_map)
        else:
            doomed = {ob.as_pointer(): ob for ob in selected}

        count, purged = batch_delete(
            doomed, children_map,
            keep_child_transforms=self.keep_child_transforms and not self.include_children,
            purge_data=self.purge_data,
        )

        msg = f"Deleted {count} object(s)"
        if purged:
            msg += f" and {purged} data-block(s)"
        self.report({'INFO'}, f"{msg} in {time.perf_counter() - start:.3f}s")
        return {'FINISHED'}


class OUTLINER_OT_fast_delete_collections(bpy.types.Operator):
    """Delete the selected collections, all their child collections and the objects inside, in a single batch"""
    bl_idname = "outliner.fast_delete_collections"
    bl_label = "Fast Delete Hierarchy"
    bl_options = {'REGISTER', 'UNDO'}

    collection_names: StringProperty(
        name="Collections",
        description="Internal: names of the collections to delete (filled in from the Outliner selection)",
        options={'HIDDEN', 'SKIP_SAVE'},
    )
    keep_shared_objects: BoolProperty(
        name="Keep Objects Linked Elsewhere",
        description="Don't delete objects that are also in a collection outside the deleted hierarchy",
        default=True,
    )
    include_object_children: BoolProperty(
        name="Include Parented Children",
        description="Also delete objects parented to deleted objects, even if they live in other collections",
        default=False,
    )
    keep_child_transforms: BoolProperty(
        name="Keep Child Transforms",
        description="Surviving children keep their world-space position when their parent is deleted",
        default=True,
    )
    purge_data: BoolProperty(
        name="Remove Orphaned Data",
        description="Also remove meshes, curves, etc. left with no users by this delete",
        default=True,
    )

    @staticmethod
    def gather_from_context(context):
        selected = getattr(context, "selected_ids", None) or []
        colls = [i for i in selected if isinstance(i, bpy.types.Collection)]
        if not colls:
            layer_coll = context.view_layer.active_layer_collection
            if layer_coll and layer_coll.collection != context.scene.collection:
                colls = [layer_coll.collection]
        return colls

    @classmethod
    def poll(cls, context):
        # Only require that collections exist
        return bool(bpy.data.collections)

    def invoke(self, context, event):
        colls = self.gather_from_context(context)
        if not colls:
            self.report({'WARNING'}, "Select one or more collections in the Outliner")
            return {'CANCELLED'}
        self.collection_names = NAME_SEP.join(c.name for c in colls)
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        names = [n for n in self.collection_names.split(NAME_SEP) if n]
        label = names[0] if len(names) == 1 else f"{len(names)} collections"
        layout.label(text=f"Delete {label} and everything inside?", icon='OUTLINER_COLLECTION')
        layout.prop(self, "keep_shared_objects")
        layout.prop(self, "include_object_children")
        row = layout.row()
        row.active = not self.include_object_children
        row.prop(self, "keep_child_transforms")
        layout.prop(self, "purge_data")

    def execute(self, context):
        start = time.perf_counter()
        ensure_object_mode(context)

        if not self.collection_names:
            self.collection_names = NAME_SEP.join(c.name for c in self.gather_from_context(context))

        roots = [bpy.data.collections.get(n) for n in self.collection_names.split(NAME_SEP) if n]
        roots = [c for c in roots if c is not None]
        if not roots:
            self.report({'WARNING'}, "No collections to delete")
            return {'CANCELLED'}

        # Every collection in the hierarchy.
        doomed_colls = {}
        stack = list(roots)
        while stack:
            coll = stack.pop()
            key = coll.as_pointer()
            if key in doomed_colls:
                continue
            doomed_colls[key] = coll
            stack.extend(coll.children)

        # Every object directly inside those collections.
        doomed = {}
        for coll in doomed_colls.values():
            for ob in coll.objects:
                doomed[ob.as_pointer()] = ob

        if self.keep_shared_objects:
            # Built once: Object.users_collection scans every collection per call.
            linked_elsewhere = set()
            surviving_colls = [c for c in bpy.data.collections if c.as_pointer() not in doomed_colls]
            surviving_colls += [scene.collection for scene in bpy.data.scenes]
            for coll in surviving_colls:
                linked_elsewhere.update(ob.as_pointer() for ob in coll.objects)
            doomed = {key: ob for key, ob in doomed.items() if key not in linked_elsewhere}

        children_map = build_children_map()
        if self.include_object_children:
            doomed = collect_with_descendants(list(doomed.values()), children_map)

        count, purged = batch_delete(
            doomed, children_map,
            extra_ids=doomed_colls.values(),
            keep_child_transforms=self.keep_child_transforms and not self.include_object_children,
            purge_data=self.purge_data,
        )

        msg = f"Deleted {len(doomed_colls)} collection(s), {count} object(s)"
        if purged:
            msg += f" and {purged} data-block(s)"
        self.report({'INFO'}, f"{msg} in {time.perf_counter() - start:.3f}s")
        return {'FINISHED'}


def object_menu_func(self, context):
    self.layout.separator()
    self.layout.operator(OBJECT_OT_fast_delete.bl_idname, icon='TRASH')


def collection_menu_func(self, context):
    self.layout.separator()
    self.layout.operator(OUTLINER_OT_fast_delete_collections.bl_idname, icon='TRASH')


MENUS = (
    (bpy.types.VIEW3D_MT_object, object_menu_func),
    (bpy.types.VIEW3D_MT_object_context_menu, object_menu_func),
    (bpy.types.OUTLINER_MT_object, object_menu_func),
    (bpy.types.OUTLINER_MT_collection, collection_menu_func),
)

CLASSES = (
    OBJECT_OT_fast_delete,
    OUTLINER_OT_fast_delete_collections,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    for menu, func in MENUS:
        menu.append(func)


def unregister():
    for menu, func in MENUS:
        menu.remove(func)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
