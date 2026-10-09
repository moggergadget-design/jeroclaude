"""Objeto de prueba del pipeline (NO es un diseño).

Ejercita la librería: materiales de cada tipo, franjas de llenado (bands),
pieza desprendible con pivote en la base, flecos con grosor, prefracturado,
horneado de textura, estados, exportación FBX con validación y todos los modos de render.

    bash tools/run.sh blender/assets/_test/test_pipeline/build.py --version v001
"""
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import bpy  # noqa: E402  (bpy primero: carga mathutils)
from mathutils import Matrix, Vector  # noqa: E402

from lib import geo, materials, palette, pipeline  # noqa: E402

A = pipeline.args()
geo.clear_scene()
coll = geo.collection("test_pipeline")
objs = []

# Base de madera pintada con biseles
base = geo.box("Base", (5.2, 2.2, 0.4), (0, 0, 0.2), coll)
geo.bevel(base, 0.12, 3)
geo.smooth(base, 40)
materials.assign(base, materials.get("wood_painted", "turquesa"))
objs.append(base)

# Núcleo esférico dividido en 6 franjas (prueba de FillStripe)
core = geo.sphere("CoreTmp", 0.9, 32, 16, (-1.2, 0, 1.45), coll)
stripes = geo.bands(core, [-0.6, -0.3, 0.0, 0.3, 0.6], "FillStripe", coll)
bpy.data.objects.remove(core)
cols = ["rosa", "naranja", "amarillo", "turquesa", "rosa", "naranja"]
for i, s in enumerate(stripes):
    on = palette.color(cols[i])
    off = palette.fill_off(on)
    lit = i < 3  # llenado al 50%
    materials.assign(s, materials.get("paper", on if lit else off))
    s["role"] = "fill_indicator"
    s["color_on"], s["color_off"] = on, off
    geo.smooth(s, 50)
    objs.append(s)

# Pico desprendible con pivote en su base y flecos con grosor en la punta
spike = geo.cone("Spike_01", 0.32, 0.06, 0.9, 20, coll=coll)
geo.bevel(spike, 0.03, 2, angle=50)
geo.smooth(spike, 50)
rot = Matrix.Rotation(math.radians(-60), 4, "Y")
spike.matrix_world = Matrix.Translation((-1.2 + 0.78, 0, 1.45 + 0.45)) @ rot
materials.assign(spike, materials.get("paper", "amarillo"))
spike["role"] = "detachable"
spike["pivot_name"] = "spike_base"
objs.append(spike)
fr = geo.fringe_ring("Fringe_01", count=14, radius=0.05, length=0.28, width=0.07,
                     thickness=0.014, droop=0.12, seed=3, coll=coll)
fr.matrix_world = spike.matrix_world @ Matrix.Translation((0, 0, 0.88)) @ Matrix.Rotation(math.radians(180), 4, "X")
geo.smooth(fr, 60)
materials.assign(fr, materials.get("paper", "rosa"))
objs.append(fr)

# Muestrario de materiales (dulce, plástico, metal, foil, vidrio, neón, barro)
kinds = [("candy", "rosa"), ("plastic", "sec_bottom"), ("metal_painted", "naranja"),
         ("gold", "coin_bottom"), ("glass", "gem_top"), ("neon", "premium_magenta"), ("clay", "clay")]
for i, (k, c) in enumerate(kinds):
    s = geo.sphere(f"Swatch_{k}", 0.24, 24, 12, (0.2 + i * 0.55, -0.45, 0.64), coll)
    geo.smooth(s, 80)
    materials.assign(s, materials.get(k, c))
    s["role"] = {"glass": "glass", "neon": "neon"}.get(k, "static")
    objs.append(s)

# Cubo con textura horneada (patrón procedural -> PNG 512)
tex_cube = geo.box("TexCube", (0.8, 0.8, 0.8), (1.6, 0.45, 0.85), coll)
geo.bevel(tex_cube, 0.08, 2)
geo.apply_modifiers(tex_cube)
geo.uv_smart(tex_cube)
proc = bpy.data.materials.new("proc_checker")
proc.use_nodes = True
nt = proc.node_tree
chk = nt.nodes.new("ShaderNodeTexChecker")
chk.inputs["Scale"].default_value = 6
chk.inputs["Color1"].default_value = palette.hex_lin("#FF5DA2")
chk.inputs["Color2"].default_value = palette.hex_lin("#FFF6E8")
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
materials.assign(tex_cube, proc)
out_dir = os.path.join(pipeline.ROOT, "renders", "test_pipeline", A.version)
png = materials.bake_basecolor(tex_cube, os.path.join(out_dir, "texcube_color.png"), 512)
materials.assign(tex_cube, materials.image_material("TexCube_mat", png, kind="candy"))
geo.smooth(tex_cube, 40)
objs.append(tex_cube)

# Prefracturado en 8 fragmentos (solo explosión)
frag_src = geo.sphere("FragTmp", 0.35, 24, 12, (2.15, -0.5, 0.75), coll)
c = Vector((2.15, -0.5, 0.75))
planes = [(c, Vector((1, 0.2, 0.1)).normalized()), (c, Vector((0.1, 1, -0.2)).normalized()),
          (c, Vector((-0.2, 0.1, 1)).normalized())]
local_planes = [(frag_src.matrix_world.inverted() @ co, no) for co, no in planes]
shards = geo.split_by_planes(frag_src, local_planes, "Shard", coll)
bpy.data.objects.remove(frag_src)
for s in shards:
    materials.assign(s, materials.get("paper", "lila"))
    s["role"] = "break_debris"
    s["visible"] = "only_on_break"
    geo.smooth(s, 40)
    objs.append(s)


def state_fill(n):
    def apply():
        prev = [(s, s.data.materials[0]) for s in stripes]
        for i, s in enumerate(stripes):
            s.data.materials[0] = materials.get("paper", s["color_on"] if i < n else s["color_off"])
        return lambda: [setattr_mat(o, m) for o, m in prev]
    return apply


def setattr_mat(o, m):
    o.data.materials[0] = m


def state_exploded():
    moved = []
    for s in shards:
        d = (s.matrix_world.translation - c).normalized() * 0.35
        s.location += d
        moved.append((s, d))
    return lambda: [setattr(s, "location", s.location - d) for s, d in moved]


pipeline.run(
    "test_pipeline", objs, A, pivot="base_center", budget=8000,
    attachments={"top": (-1.2, 0, 2.4)},
    states={"fill_steps": 6},
    state_shots=[("fill_000", state_fill(0)), ("fill_100", state_fill(6)), ("exploded", state_exploded)],
    detail_point=(-0.5, 0, 1.9), textures=[png],
)
