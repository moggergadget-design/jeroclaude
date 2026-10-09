"""Hoja de revisión del lote (PNG) y galería review/index.html.

Se ejecuta con el Python del proyecto (no necesita bpy):
  .venv/bin/python -m blender.lib.sheet lote_00 v001 <id> <id> ...
Lee renders/<id>/<version>/meta.json de cada asset.
"""
import html
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FONTS = os.path.join(ROOT, "ui", "fonts")

C = {
    "bg": (45, 20, 92), "bg2": (75, 36, 150), "card": (255, 246, 232),
    "ink": (30, 11, 64), "muted": (110, 90, 140), "ok": (31, 191, 110), "bad": (232, 52, 78),
    "white": (255, 255, 255),
}


def font(kind, size):
    path = {"title": "LuckiestGuy-Regular.ttf", "body": "Fredoka-Variable.ttf"}[kind]
    try:
        f = ImageFont.truetype(os.path.join(FONTS, path), size)
        if kind == "body":
            try:
                f.set_variation_by_name("SemiBold")
            except Exception:
                pass
        return f
    except OSError:
        return ImageFont.truetype("DejaVuSans.ttf", size)


def load_meta(asset_id, version):
    p = os.path.join(ROOT, "renders", asset_id, version, "meta.json")
    with open(p) as f:
        return json.load(f)


def _gradient(w, h, top, bottom):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return im


def contact_sheet(lote, version, metas, out, cols=None, tile=520, title=None):
    n = len(metas)
    cols = cols or min(4, max(1, n))
    rows = (n + cols - 1) // cols
    pad, head, info_h = 28, 120, 150
    W = pad + cols * (tile + pad)
    H = head + rows * (tile + info_h + pad) + pad
    sheet = _gradient(W, H, C["bg2"], C["bg"])
    d = ImageDraw.Draw(sheet)
    d.text((pad, 26), title or f"BREAK A PIÑATA · {lote.upper()} · {version}", font=font("title", 52),
           fill=C["white"], stroke_width=3, stroke_fill=C["ink"])
    for i, m in enumerate(metas):
        r, c = divmod(i, cols)
        x = pad + c * (tile + pad)
        y = head + r * (tile + info_h + pad)
        d.rounded_rectangle([x, y, x + tile, y + tile + info_h], 22, fill=C["card"], outline=C["ink"], width=4)
        img_rel = m["files"].get(m.get("hero", "studio_34")) or next(iter(m["files"].values()))
        im = Image.open(os.path.join(ROOT, img_rel)).convert("RGB")
        im.thumbnail((tile - 24, tile - 24))
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], 16, fill=255)
        sheet.paste(im, (x + (tile - im.width) // 2, y + 12), mask)
        ty = y + tile + 4
        d.text((x + 18, ty), m["asset_id"], font=font("body", 30), fill=C["ink"])
        d.text((x + tile - 18, ty + 4), m["version"], font=font("body", 24), fill=C["muted"], anchor="ra")
        dims = " × ".join(f"{v:g}" for v in m["dims"])
        lines = [
            f"{m['tris_total']:,} tris  ·  {m['pieces']} piezas  ·  {m['colors']} colores",
            f"{dims} studs",
        ]
        budget = m.get("budget")
        if budget:
            lines[0] += f"  (máx {budget:,})"
        for k, line in enumerate(lines):
            d.text((x + 18, ty + 44 + k * 32), line, font=font("body", 23), fill=C["ink"])
        ok = m.get("checks_ok")
        if ok is not None:
            d.text((x + tile - 18, ty + 108), "técnica OK" if ok else "técnica: revisar",
                   font=font("body", 22), fill=C["ok"] if ok else C["bad"], anchor="ra")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.save(out, optimize=True)
    return out


def _rel(path_from_root):
    return os.path.relpath(os.path.join(ROOT, path_from_root), os.path.join(ROOT, "review"))


def gallery(lote, version, metas, sheet_path, out, notes=""):
    e = html.escape
    parts = [f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Revisión {e(lote)} {e(version)}</title>
<style>
:root{{--bg:#2D145C;--bg2:#4B2496;--card:#FFF6E8;--ink:#1E0B40;--muted:#6E5A8C;--ok:#1FBF6E;--bad:#E8344E}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Fredoka,system-ui,sans-serif;background:linear-gradient(#4B2496,#2D145C) fixed;color:var(--ink)}}
header{{padding:24px 16px;color:#fff;max-width:1200px;margin:auto}}h1{{margin:0 0 6px;font-size:34px;letter-spacing:.5px}}
main{{max-width:1200px;margin:auto;padding:0 16px 48px}}
.card{{background:var(--card);border:3px solid var(--ink);border-radius:18px;padding:16px;margin:0 0 22px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}}
.grid figure{{margin:0}}.grid img{{width:100%;border-radius:10px;border:2px solid #0002;display:block}}
figcaption{{font-size:13px;color:var(--muted);margin-top:3px}}
table{{border-collapse:collapse;font-size:14px;width:100%;margin-top:10px}}td,th{{border-bottom:1px solid #0001;padding:4px 6px;text-align:left}}
.ok{{color:var(--ok);font-weight:600}}.bad{{color:var(--bad);font-weight:600}}
.sheet{{width:100%;border-radius:14px;border:3px solid var(--ink)}}
ul.check{{padding-left:20px;margin:6px 0}}
</style></head><body><header><h1>BREAK A PIÑATA · {e(lote)} · {e(version)}</h1>
<div>{e(notes)}</div></header><main>
<div class="card"><h2>Hoja del lote</h2><img class="sheet" src="{e(_rel(sheet_path))}" alt="Hoja del lote"></div>"""]
    for m in metas:
        imgs = "".join(
            f'<figure><a href="{e(_rel(p))}"><img loading="lazy" src="{e(_rel(p))}" alt="{e(k)}"></a>'
            f'<figcaption>{e(k)}</figcaption></figure>'
            for k, p in m["files"].items() if p.endswith((".png", ".gif")))
        rows = "".join(
            f"<tr><td>{e(p['name'])}</td><td>{p['tris']}</td><td>{e(p.get('role', ''))}</td>"
            f"<td>{e(p.get('color', ''))}</td><td>{e(p.get('roblox_material', ''))}</td>"
            f"<td class=\"{'ok' if p['mesh']['ok'] else 'bad'}\">{'OK' if p['mesh']['ok'] else e(json.dumps(p['mesh']))}</td></tr>"
            for p in m["piece_list"])
        fbx = m.get("fbx_check") or {}
        fbx_txt = ("<span class='ok'>FBX validado</span>" if fbx.get("ok")
                   else f"<span class='bad'>FBX: {e(str(fbx.get('problems') or fbx.get('error') or 'sin validar'))}</span>")
        checklist = "".join(
            f"<li class=\"{'ok' if c['ok'] else 'bad'}\">{e(c['item'])}"
            f"{' — ' + e(c['note']) if c.get('note') else ''}</li>"
            for c in m.get("checklist", []))
        times = ", ".join(f"{k} {v}s" for k, v in m.get("times", {}).items())
        parts.append(f"""<div class="card" id="{e(m['asset_id'])}"><h2>{e(m['asset_id'])} <small>{e(m['version'])}</small></h2>
<p><b>{m['tris_total']:,}</b> triángulos · {m['pieces']} piezas · {m['colors']} colores ·
{' × '.join(f'{v:g}' for v in m['dims'])} studs · {fbx_txt}</p>
<div class="grid">{imgs}</div>
<table><tr><th>Pieza</th><th>Tris</th><th>Rol</th><th>Color</th><th>Roblox</th><th>Malla</th></tr>{rows}</table>
{'<h3>Checklist</h3><ul class="check">' + checklist + '</ul>' if checklist else ''}
<p style="font-size:12px;color:var(--muted)">Tiempos de render: {e(times)}</p></div>""")
    parts.append("</main></body></html>")
    with open(out, "w") as f:
        f.write("".join(parts))
    return out


def build(lote, version, ids, notes=""):
    metas = [load_meta(i, v) for i, v in ids]
    sheet = os.path.join(ROOT, "review", f"{lote}_{version}.png")
    contact_sheet(lote, version, metas, sheet)
    idx = os.path.join(ROOT, "review", "index.html")
    gallery(lote, version, metas, os.path.relpath(sheet, ROOT), idx, notes)
    return sheet, idx


if __name__ == "__main__":
    lote, version, *rest = sys.argv[1:]
    pairs = [(r.split(":")[0], r.split(":")[1] if ":" in r else version) for r in rest]
    print(build(lote, version, pairs))
