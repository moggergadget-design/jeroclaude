"""Materiales con nombre a partir de la paleta.

Cada material guarda en propiedades personalizadas el hex y el material de
Roblox previsto, para que export.py escriba el manifiesto sin adivinar.
"""
import os

import bpy

from . import palette

# kind -> (ajustes del Principled BSDF, material de Roblox)
KINDS = {
    # dulce: plástico liso con capa brillante
    "candy":         (dict(roughness=0.16, coat=0.6, coat_rough=0.05, specular=0.6), "SmoothPlastic"),
    # juguete de plástico, algo menos brillante que el dulce
    "plastic":       (dict(roughness=0.30, coat=0.25, coat_rough=0.12, specular=0.5), "SmoothPlastic"),
    # papel de china: mate con un poco de brillo de tela
    "paper":         (dict(roughness=0.82, sheen=0.35, sheen_rough=0.4, specular=0.25), "SmoothPlastic"),
    # papel maché pintado
    "papermache":    (dict(roughness=0.62, specular=0.35), "SmoothPlastic"),
    # madera pintada (laca satinada)
    "wood_painted":  (dict(roughness=0.42, coat=0.2, coat_rough=0.2, specular=0.45), "Wood"),
    # madera vista
    "wood_raw":      (dict(roughness=0.65, specular=0.3), "Wood"),
    # metal pintado
    "metal_painted": (dict(roughness=0.32, metallic=0.25, coat=0.3, coat_rough=0.1, specular=0.5), "SmoothPlastic"),
    # metal o papel metálico
    "foil":          (dict(roughness=0.22, metallic=1.0, specular=0.5), "Foil"),
    "gold":          (dict(roughness=0.18, metallic=1.0, specular=0.5), "Foil"),
    # vidrio o caramelo transparente
    "glass":         (dict(roughness=0.04, transmission=1.0, ior=1.45, specular=0.5), "Glass"),
    # neón: emisivo
    "neon":          (dict(roughness=0.4, emission=3.0), "Neon"),
    # barro
    "clay":          (dict(roughness=0.78, specular=0.3), "SmoothPlastic"),
    # maniquí y utilería del render (no se exporta)
    "matte":         (dict(roughness=0.55, specular=0.35), "SmoothPlastic"),
}


def _bsdf(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def _set(bsdf, name, value):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value


def get(kind, hex_or_name, name=None, alpha=1.0):
    """Devuelve (y cachea) el material <kind>_<HEX>."""
    if kind not in KINDS:
        raise KeyError(f"Tipo de material desconocido: {kind}")
    hex_str = palette.color(hex_or_name)
    mat_name = name or f"{kind}_{hex_str.lstrip('#')}"
    mat = bpy.data.materials.get(mat_name)
    if mat:
        return mat
    params, roblox = KINDS[kind]
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    b = _bsdf(mat)
    col = palette.hex_lin(hex_str)
    _set(b, "Base Color", col)
    _set(b, "Roughness", params.get("roughness", 0.5))
    _set(b, "Metallic", params.get("metallic", 0.0))
    _set(b, "Specular IOR Level", params.get("specular", 0.5))
    _set(b, "Coat Weight", params.get("coat", 0.0))
    _set(b, "Coat Roughness", params.get("coat_rough", 0.03))
    _set(b, "Sheen Weight", params.get("sheen", 0.0))
    _set(b, "Sheen Roughness", params.get("sheen_rough", 0.5))
    if "transmission" in params:
        _set(b, "Transmission Weight", params["transmission"])
        _set(b, "IOR", params.get("ior", 1.45))
    if "emission" in params:
        _set(b, "Emission Color", col)
        _set(b, "Emission Strength", params["emission"])
    if alpha < 1.0:
        _set(b, "Alpha", alpha)
    mat.diffuse_color = col  # color en el visor
    mat["hex"] = hex_str
    mat["kind"] = kind
    mat["roblox_material"] = roblox
    if alpha < 1.0:
        mat["roblox_transparency"] = round(1.0 - alpha, 3)
    return mat


def image_material(name, png_path, kind="paper", roblox=None):
    """Material con textura de color (PNG ya horneado)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    b = _bsdf(mat)
    params, default_roblox = KINDS[kind]
    _set(b, "Roughness", params.get("roughness", 0.5))
    _set(b, "Metallic", params.get("metallic", 0.0))
    _set(b, "Specular IOR Level", params.get("specular", 0.5))
    _set(b, "Coat Weight", params.get("coat", 0.0))
    _set(b, "Sheen Weight", params.get("sheen", 0.0))
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.abspath(png_path), check_existing=True)
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    mat["kind"] = kind
    mat["texture"] = os.path.basename(png_path)
    mat["roblox_material"] = roblox or default_roblox
    return mat


def assign(obj, mat, slot=0):
    me = obj.data
    while len(me.materials) <= slot:
        me.materials.append(None)
    me.materials[slot] = mat
    return obj


def piece_colors(obj):
    """Hex de todos los materiales de una pieza."""
    return [m["hex"] for m in obj.data.materials if m and "hex" in m]


def bake_basecolor(obj, out_png, size=512, margin=8):
    """Hornea el color base (procedural) de obj a un PNG con Cycles.

    obj necesita UVs. Usa el pase DIFFUSE solo-color para que la luz no
    quede pintada en la textura.
    """
    scene = bpy.context.scene
    prev_engine = scene.render.engine
    scene.render.engine = "CYCLES"
    img = bpy.data.images.new(os.path.basename(out_png), size, size, alpha=False)
    nodes_added = []
    for mat in obj.data.materials:
        if not mat:
            continue
        n = mat.node_tree.nodes.new("ShaderNodeTexImage")
        n.image = img
        mat.node_tree.nodes.active = n
        nodes_added.append((mat, n))
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bake = scene.render.bake
    bake.use_pass_direct = False
    bake.use_pass_indirect = False
    bake.use_pass_color = True
    bake.margin = margin
    bpy.ops.object.bake(type="DIFFUSE")
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    img.filepath_raw = os.path.abspath(out_png)
    img.file_format = "PNG"
    img.save()
    for mat, n in nodes_added:
        mat.node_tree.nodes.remove(n)
    scene.render.engine = prev_engine
    return out_png
