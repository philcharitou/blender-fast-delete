# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare deleting a large collection hierarchy the built-in way with Fast Delete Hierarchy.

Builds Root > 20 sub-collections > 10 leaf collections each, with 25
parent/child object pairs per leaf (10,000 objects in 221 collections).
One object is also linked outside the hierarchy, and one outside object is
parented into it, to check that both survive correctly.

Usage (from the repository root):
    blender -b --factory-startup --python benchmarks/bench_collections.py -- fast_delete.py
"""

import importlib.util
import sys
import time

import bpy

addon_path = sys.argv[sys.argv.index("--") + 1]
spec = importlib.util.spec_from_file_location("fast_delete", addon_path)
fast_delete = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fast_delete)
fast_delete.register()

N_SUB, N_LEAF, N_PAIRS = 20, 10, 25


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene_coll = bpy.context.scene.collection
    mesh = bpy.data.meshes.new("m")
    root = bpy.data.collections.new("Root")
    scene_coll.children.link(root)
    i = 0
    for s in range(N_SUB):
        sub = bpy.data.collections.new(f"Sub{s}")
        root.children.link(sub)
        for leaf_index in range(N_LEAF):
            leaf = bpy.data.collections.new(f"Leaf{s}_{leaf_index}")
            sub.children.link(leaf)
            for _ in range(N_PAIRS):
                p = bpy.data.objects.new(f"P{i}", None)
                p.location = (i, 0, 0)
                c = bpy.data.objects.new(f"C{i}", mesh)
                c.parent = p
                c.location = (0, 1, 0)
                leaf.objects.link(p)
                leaf.objects.link(c)
                i += 1
    # Inside the hierarchy but also linked outside it: should survive.
    scene_coll.objects.link(bpy.data.objects["P0"])
    # Outside the hierarchy, parented to an object inside it: should keep its position.
    outside = bpy.data.objects.new("Outside", None)
    outside.parent = bpy.data.objects["P5"]
    outside.location = (0, 0, 3)
    scene_coll.objects.link(outside)
    bpy.context.view_layer.update()
    return root


root = build()
total = len(bpy.data.objects)
t = time.perf_counter()
for ob in root.all_objects:
    ob.select_set(True)
bpy.ops.object.delete()
for coll in list(bpy.data.collections):
    bpy.data.collections.remove(coll)
builtin = time.perf_counter() - t

build()
t = time.perf_counter()
bpy.ops.outliner.fast_delete_collections('EXEC_DEFAULT', collection_names="Root")
fast = time.perf_counter() - t
bpy.context.view_layer.update()

n_colls = 1 + N_SUB + N_SUB * N_LEAF
print(f"{total} objects in {n_colls} collections  built-in={builtin:.3f}s  fast={fast:.3f}s  speedup={builtin / fast:.1f}x")
print("collections left:", len(bpy.data.collections),
      "| objects left:", sorted(o.name for o in bpy.data.objects), "(expected ['Outside', 'P0'])")
outside = bpy.data.objects["Outside"]
print("Outside world position:", tuple(round(v, 3) for v in outside.matrix_world.translation),
      "(expected (5.0, 0.0, 3.0))")
