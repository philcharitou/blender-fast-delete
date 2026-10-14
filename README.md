# Fast Delete for Blender

Deletes thousands of objects, or whole collection hierarchies, in seconds instead of minutes.

Blender's built-in delete removes objects one at a time. Each removal scans the whole file to clear references to that object, so the time grows with the square of the object count. In big scenes with lots of parenting, a single delete can freeze Blender for minutes or longer. Fast Delete removes the whole selection in one pass.

## Benchmarks

Run headless in Blender 5.1 on Windows. The scripts are in [`benchmarks/`](benchmarks/).

| Test | Built-in | Fast Delete | Speedup |
|---|---|---|---|
| 5,000 parent empties (each with a mesh child), delete all parents | 11.0 s | 1.3 s | ~9x |
| 221 nested collections holding 10,000 objects, delete the top collection | 32.1 s | 0.6 s | ~50x |

## Features

**Fast Delete** (objects)
- Deletes the selected objects in one batch.
- **Include Children:** also deletes everything parented below the selection.
- **Keep Child Transforms:** children that aren't deleted stay where they are when their parent goes. On by default.
- **Remove Orphaned Data:** also removes meshes, curves and other data that nothing uses after the delete. On by default.

**Fast Delete Hierarchy** (collections)
- Deletes the selected collections, every collection inside them, and their objects.
- **Keep Objects Linked Elsewhere:** objects that are also in a collection you aren't deleting are kept. On by default.
- **Include Parented Children:** also deletes children of deleted objects, even if they're in other collections.
- **Keep Child Transforms** and **Remove Orphaned Data**, as above.

Both operators support undo and the redo panel, each one reports how many items it removed and how long it took.

## Installation

1. Download [`fast_delete.py`](fast_delete.py).
2. In Blender, open **Edit → Preferences → Add-ons**.
3. Open the **▾** menu at the top right and choose **Install from Disk…** (called **Install…** in Blender 4.1 and earlier).
4. Select `fast_delete.py` and tick the checkbox to enable **Fast Delete**.

## Notes

- **Deletes from every scene.** Like Blender's **Delete Globally** (Shift+X), deleted objects are removed from every scene in the file, not just the current one.
- **Compatibility.** Tested on Blender 5.1. It only uses APIs that have been around since Blender 3.0, so older versions should work but haven't been tested.

## Running the benchmarks

From the repository root:

```bash
blender -b --factory-startup --python benchmarks/bench_objects.py -- fast_delete.py 5000
```

```bash
blender -b --factory-startup --python benchmarks/bench_collections.py -- fast_delete.py
```

Each script builds a test scene, times the built-in method and Fast Delete, and checks the results.

## License

[GPL-3.0-or-later](LICENSE)
