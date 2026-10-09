"""Orquestador común para cada build.py.

Uso desde un build.py:
    from lib import pipeline
    args = pipeline.args()
    ... construir piezas ...
    pipeline.run("asset_id", objs, args, pivot="rope_ring", budget=8000, ...)

Argumentos de línea de comandos (después de --):
    --version vNNN     versión a renderizar (obligatoria)
    --render LISTA     all | studio,game,silhouette,scale,far50,turntable,icon,states | none
    --quick            muestras bajas para iterar
    --approve          exporta y congela en exports/approved/<id>/
"""
import argparse
import json
import os
import sys

import bpy

from . import ROOT, export, geo, render

ALL_MODES = ["studio", "game", "silhouette", "scale", "far50", "turntable", "states"]


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    p.add_argument("--render", default="all")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--approve", action="store_true")
    a = p.parse_args(argv)
    a.modes = ALL_MODES if a.render == "all" else ([] if a.render == "none" else a.render.split(","))
    return a


def colors_used(objs):
    found = set()
    for o in objs:
        if o.type != "MESH":
            continue
        for m in o.data.materials:
            if m and "hex" in m:
                found.add(m["hex"])
        for k in ("color_off", "color_on"):
            if k in o:
                found.add(o[k])
    return sorted(found)


def run(asset_id, objs, a, *, pivot, budget=None, attachments=None, states=None,
        state_shots=None, floor=True, scale_place="ground", detail_point=None,
        detail_zoom=2.6, hero="studio_34", extra_manifest=None, textures=(),
        budget_debris=None):
    out_dir = os.path.join(ROOT, "renders", asset_id, a.version)
    os.makedirs(out_dir, exist_ok=True)
    meshes = [o for o in objs if o.type == "MESH"]

    # revisión técnica de cada pieza
    piece_list = []
    for o in sorted(meshes, key=lambda o: o.name):
        mats = [m for m in o.data.materials if m]
        piece_list.append({
            "name": o.name, "tris": geo.tris(o), "role": o.get("role", "static"),
            "color": mats[0].get("hex", "") if mats else "",
            "roblox_material": o.get("roblox_material", mats[0].get("roblox_material", "") if mats else ""),
            "mesh": geo.mesh_report(o),
        })

    # FBX de comprobación (no aprobado)
    fbx_path = os.path.join(out_dir, "fbx_check", f"{asset_id}.fbx")
    export.export_fbx(meshes, fbx_path)
    fbx_report = export.validate_fbx(fbx_path, meshes)

    files, times = {}, {}
    if a.modes:
        sess = render.Session(ROOT, asset_id, a.version, objs, quick=a.quick, floor=floor,
                              scale_place=scale_place, detail_point=detail_point,
                              detail_zoom=detail_zoom)
        modes = list(a.modes)
        if "states" in modes:
            modes.remove("states")
            if state_shots:
                sess.states(state_shots)
        files, times = sess.run(modes)

    # metadatos para la hoja y la galería
    meta_path = os.path.join(out_dir, "meta.json")
    prev = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            prev = json.load(f)
    merged_files = dict(prev.get("files", {}))
    merged_files.update(files)
    merged_times = dict(prev.get("times", {}))
    merged_times.update(times)
    review_path = os.path.join(out_dir, "review.json")
    checklist = []
    if os.path.exists(review_path):
        with open(review_path) as f:
            checklist = json.load(f).get("checklist", [])
    meta = {
        "asset_id": asset_id,
        "version": a.version,
        "hero": hero,
        "files": merged_files,
        "times": merged_times,
        "tris_total": sum(p["tris"] for p in piece_list),
        "budget": budget,
        "budget_debris": budget_debris,
        "pieces": len(piece_list),
        "colors": len(colors_used(objs)),
        "color_list": colors_used(objs),
        "dims": list(geo.dims([o for o in meshes if not o.get("visible") == "only_on_break"]) if meshes else []),
        "piece_list": piece_list,
        "fbx_check": fbx_report,
        "checks_ok": fbx_report.get("ok") and all(p["mesh"]["ok"] for p in piece_list),
        "checklist": checklist,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    man = export.manifest(asset_id, a.version, meshes, pivot, attachments, states,
                          icon=f"icons/{asset_id}_512.png", extra=extra_manifest)
    with open(os.path.join(out_dir, "manifest.preview.json"), "w") as f:
        json.dump(man, f, indent=2, ensure_ascii=False)

    if a.approve:
        out, rep = export.approve(ROOT, asset_id, a.version, meshes, man, textures)
        print(f"[approve] {asset_id} {a.version} -> {out} {rep}")

    print(f"[done] {asset_id} {a.version}: {meta['tris_total']} tris, {meta['pieces']} piezas, "
          f"FBX {'OK' if fbx_report.get('ok') else fbx_report}")
    return meta
