"""Reimporta un FBX en una escena vacía e imprime piezas, triángulos y medidas.
Lo lanza export.validate_fbx en un proceso aparte para no ensuciar la escena."""
import json
import sys

import bpy
from mathutils import Vector

fbx = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
# mismos ejes que la exportación, para comparar en coordenadas de Blender
bpy.ops.import_scene.fbx(filepath=fbx, axis_forward="Z", axis_up="Y", use_custom_normals=True)
dg = bpy.context.evaluated_depsgraph_get()
out = {}
for o in bpy.context.scene.objects:
    if o.type != "MESH":
        continue
    me = o.evaluated_get(dg).to_mesh()
    pts = [o.matrix_world @ v.co for v in me.vertices]
    lo = Vector(map(min, *pts)) if len(pts) > 1 else pts[0]
    hi = Vector(map(max, *pts)) if len(pts) > 1 else pts[0]
    out[o.name] = {
        "tris": sum(len(p.vertices) - 2 for p in me.polygons),
        "dims": [round(x, 4) for x in (hi - lo)],
    }
print("FBXCHECK " + json.dumps(out))
