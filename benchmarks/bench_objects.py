# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare Blender's built-in object delete with Fast Delete.

Builds N parent empties, each with a parented mesh child, then deletes all
parents with each method and checks that the surviving children stayed put.

Usage (from the repository root):
    blender -b --factory-startup --python benchmarks/bench_objects.py -- fast_delete.py 5000
"""

import importlib.util
import sys
import time

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
addon_path = args[0]
N = int(args[1]) if len(args) > 1 else 5000

spec = importlib.util.spec_from_file_location("fast_delete", addon_path)
fast_delete = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fast_delete)
fast_delete.register()


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    coll = bpy.context.scene.collection
    mesh = bpy.data.meshes.new("m")
    parents = []
    for i in range(N):
        p = bpy.data.objects.new(f"P{i}", None)
        p.location = (i, 0, 0)
        coll.objects.link(p)
        c = bpy.data.objects.new(f"C{i}", mesh)
        c.parent = p
        c.location = (0, 1, 0)
        coll.objects.link(c)
        parents.append(p)
    bpy.context.view_layer.update()
    for p in parents:
        p.select_set(True)


build()
t = time.perf_counter()
bpy.ops.object.delete()
builtin = time.perf_counter() - t

build()
t = time.perf_counter()
bpy.ops.object.fast_delete('EXEC_DEFAULT')
fast = time.perf_counter() - t
bpy.context.view_layer.update()

child = bpy.data.objects["C7"]
print(f"{N} parents  built-in={builtin:.3f}s  fast={fast:.3f}s  speedup={builtin / fast:.1f}x")
print("objects left:", len(bpy.data.objects),
      "| C7 world position:", tuple(round(v, 3) for v in child.matrix_world.translation),
      "(expected (7.0, 1.0, 0.0))")

build()
bpy.ops.object.fast_delete('EXEC_DEFAULT', include_children=True)
print("include_children -> objects left:", len(bpy.data.objects), "meshes left:", len(bpy.data.meshes))
