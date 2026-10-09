"""Exportación FBX para Roblox, validación por reimportación y manifest.json.

Ajustes (documentación oficial de Roblox, ver docs/pipeline.md):
  Apply Scalings = FBX Unit Scale, Forward = Z, Up = Y, sin hojas de hueso,
  sin animación horneada, modificadores aplicados, texturas copiadas e incrustadas.
Conversión de coordenadas Blender -> Roblox: (x, y, z) -> (-x, z, y).
El frente del modelo (-Y en Blender) queda como -Z (LookVector) en Roblox.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys

import bpy

from . import geo, materials

FBX_SETTINGS = dict(
    apply_scale_options="FBX_SCALE_UNITS",
    global_scale=1.0,
    axis_forward="Z",
    axis_up="Y",
    use_mesh_modifiers=True,
    mesh_smooth_type="FACE",
    use_tspace=False,
    add_leaf_bones=False,
    bake_anim=False,
    path_mode="COPY",
    embed_textures=True,
    object_types={"MESH"},
)


def to_roblox(v):
    x, y, z = v
    return [round(-x, 4), round(z, 4), round(y, 4)]


def export_fbx(objs, fbx_path):
    os.makedirs(os.path.dirname(fbx_path), exist_ok=True)
    meshes = [o for o in objs if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.hide_set(False)
        o.hide_viewport = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.export_scene.fbx(filepath=fbx_path, use_selection=True, **FBX_SETTINGS)
    return fbx_path


def expected(objs):
    out = {}
    for o in objs:
        if o.type != "MESH":
            continue
        out[o.name] = {"tris": geo.tris(o), "dims": list(geo.dims([o]))}
    return out


def validate_fbx(fbx_path, objs, tol=2e-3):
    """Reimporta el FBX en un proceso limpio y compara piezas, nombres,
    triángulos y medidas con la escena original."""
    exp = expected(objs)
    checker = os.path.join(os.path.dirname(__file__), "fbx_check.py")
    res = subprocess.run([sys.executable, checker, "--", fbx_path],
                         capture_output=True, text=True)
    line = [l for l in res.stdout.splitlines() if l.startswith("FBXCHECK ")]
    if not line:
        return {"ok": False, "error": res.stderr[-2000:]}
    got = json.loads(line[-1][9:])
    problems = []
    missing = sorted(set(exp) - set(got))
    extra = sorted(set(got) - set(exp))
    if missing:
        problems.append(f"faltan piezas: {missing}")
    if extra:
        problems.append(f"piezas de más: {extra}")
    for n in sorted(set(exp) & set(got)):
        if exp[n]["tris"] != got[n]["tris"]:
            problems.append(f"{n}: tris {exp[n]['tris']} -> {got[n]['tris']}")
        if any(abs(a - b) > tol for a, b in zip(exp[n]["dims"], got[n]["dims"])):
            problems.append(f"{n}: medidas {exp[n]['dims']} -> {got[n]['dims']}")
    total_exp = geo.dims(objs)
    return {
        "ok": not problems,
        "pieces_expected": len(exp),
        "pieces_found": len(got),
        "problems": problems,
        "dims_total": list(total_exp),
    }


def manifest(asset_id, version, objs, pivot, attachments=None, states=None,
             icon=None, approved_on=None, extra=None):
    """Construye el manifest.json a partir de las propiedades de cada pieza:
    role, pivot_name, visible, color_off/color_on y del material (hex, roblox_material)."""
    pieces = []
    for o in sorted((o for o in objs if o.type == "MESH"), key=lambda o: o.name):
        mats = [m for m in o.data.materials if m]
        m0 = mats[0] if mats else None
        p = {
            "name": o.name,
            "tris": geo.tris(o),
            "role": o.get("role", "static"),
            "roblox_material": o.get("roblox_material", m0.get("roblox_material") if m0 else "SmoothPlastic"),
            "pivot": o.get("pivot_name", "center"),
            "pivot_blender": [round(c, 4) for c in o.matrix_world.translation],
            "pivot_roblox": to_roblox(o.matrix_world.translation),
        }
        if m0 is not None and "hex" in m0:
            p["color"] = m0["hex"]
        if len(mats) > 1:
            p["colors"] = [m.get("hex", m.name) for m in mats]
        for key in ("color_off", "color_on", "visible", "emit", "transparency"):
            if key in o:
                p[key] = o[key]
        tex = [m["texture"] for m in mats if "texture" in m]
        if tex:
            p["texture"] = tex[0] if len(tex) == 1 else tex
        pieces.append(p)
    data = {
        "asset_id": asset_id,
        "version": version,
        "approved_on": approved_on,
        "units": "studs",
        "blender_up": "Z",
        "front": "-Y",
        "roblox_axes": "Blender (x,y,z) -> Roblox (-x,z,y); frente -Y -> -Z (LookVector)",
        "dimensions": list(geo.dims(objs)),
        "pivot": pivot,
        "fbx": f"{asset_id}.fbx",
        "tris_total": sum(p["tris"] for p in pieces),
        "pieces": pieces,
        "attachments": {k: [round(c, 4) for c in v] for k, v in (attachments or {}).items()},
        "attachments_roblox": {k: to_roblox(v) for k, v in (attachments or {}).items()},
        "states": states or {},
        "icon": icon,
    }
    if extra:
        data.update(extra)
    return data


def approve(root, asset_id, version, objs, manifest_data, textures=()):
    """Exporta lo aprobado a exports/approved/<id>/ y congela el .blend."""
    out = os.path.join(root, "exports", "approved", asset_id)
    os.makedirs(out, exist_ok=True)
    fbx = export_fbx(objs, os.path.join(out, f"{asset_id}.fbx"))
    report = validate_fbx(fbx, objs)
    if not report["ok"]:
        raise RuntimeError(f"FBX no válido: {report}")
    for t in textures:
        shutil.copy2(t, out)
    manifest_data["approved_on"] = manifest_data.get("approved_on") or datetime.date.today().isoformat()
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, f"{asset_id}_{version}.blend"), copy=True)
    return out, report
