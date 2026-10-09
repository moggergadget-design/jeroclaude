"""Rig de render fijo de BREAK A PIÑATA.

Modos: studio (front, 34, side, top, detail), game, silhouette, scale, far50,
turntable, icon y states (estados de llenado/daño definidos por el asset).

Todo con Cycles por CPU y transformación de vista Standard (ver docs/pipeline.md).
Todo lo que crea el rig lleva el prefijo RIG_ y se borra entre modos.
"""
import json
import math
import os
import shutil
import subprocess
import time

import bpy
from mathutils import Vector

from . import geo, mannequin, palette, post

SAMPLES = {"final": 128, "quick": 32}

# Luz de referencia (sección 3): sol cálido arriba a la izquierda a ~40°.
KEY_ELEVATION = 40.0
KEY_AZIMUTH_LEFT = 45.0  # grados hacia la izquierda de la cámara

# Colores de luz (no son colores de asset: viven aquí, en el rig)
LIGHT = {
    "studio_key": "#FFF3E2", "studio_fill": "#DCE6FF", "studio_rim": "#FFFFFF",
    "game_sun": "#FFD9A6", "game_rim": "#FFC7DD",
}

ROBLOX_FOV_V = 70.0  # campo de visión vertical por defecto de la cámara de Roblox


# --- Motor -----------------------------------------------------------------------

def setup_engine(res=(1024, 1024), samples=128, transparent=False, denoise=True):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    cy.samples = samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = denoise
    cy.denoiser = "OPENIMAGEDENOISE"
    cy.max_bounces = 8
    cy.transmission_bounces = 8
    cy.transparent_max_bounces = 8
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = 1.0
    cy.film_transparent_glass = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.use_persistent_data = True
    vs = sc.view_settings
    vs.view_transform = "Standard"
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0
    sc.display_settings.display_device = "sRGB"
    im = sc.render.image_settings
    im.file_format = "PNG"
    im.color_mode = "RGBA"
    im.color_depth = "8"
    im.compression = 30
    return sc


def clear_rig():
    for o in list(bpy.data.objects):
        if o.name.startswith("RIG_") and not o.name.startswith("RIG_Mannequin"):
            bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.lights, bpy.data.cameras):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def show_mannequin(show, loc=None):
    root = bpy.data.objects.get("Mannequin_R15")
    if show and not root:
        root, _ = mannequin.build()
    if not root:
        return None
    if loc is not None:
        root.location = loc
    for o in [root] + list(root.children):
        o.hide_render = not show
        o.hide_viewport = not show
    return root


# --- Cámara y encuadre --------------------------------------------------------

def _dir(azimuth, elevation):
    """Vector desde el objeto hacia la cámara. azimuth 0 = frente (-Y),
    positivo = la cámara gira hacia la derecha del objeto visto de frente (+X)."""
    a, e = math.radians(azimuth), math.radians(elevation)
    return Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


def camera(name="RIG_Camera", lens=50.0, fov_v=None, res=None):
    cam_data = bpy.data.cameras.new(name)
    cam_data.sensor_fit = "VERTICAL" if fov_v else "AUTO"
    if fov_v:
        cam_data.angle_y = math.radians(fov_v)
    else:
        cam_data.lens = lens
    cam_data.clip_start = 0.05
    cam_data.clip_end = 2000
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def aim(cam, target, direction, distance):
    target = Vector(target)
    cam.location = target + direction.normalized() * distance
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()


def _fov(cam):
    sc = bpy.context.scene
    aspect = sc.render.resolution_x / sc.render.resolution_y
    d = cam.data
    if d.sensor_fit == "VERTICAL":
        fv = d.angle_y
        fh = 2 * math.atan(math.tan(fv / 2) * aspect)
    else:
        f = 2 * math.atan(d.sensor_width / (2 * d.lens))
        if aspect >= 1:
            fh, fv = f, 2 * math.atan(math.tan(f / 2) / aspect)
        else:
            fv, fh = f, 2 * math.atan(math.tan(f / 2) * aspect)
    return fh, fv


def frame(cam, objs, direction, fill=0.8, target=None):
    """Coloca la cámara en 'direction' para que objs ocupen 'fill' del cuadro."""
    lo, hi = geo.world_bbox(objs)
    center = Vector(target) if target is not None else (lo + hi) / 2
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    fwd = -direction.normalized()
    right = fwd.cross(Vector((0, 0, 1)))
    if right.length < 1e-4:
        right = Vector((1, 0, 0))
    right.normalize()
    up = right.cross(fwd).normalized()
    fh, fv = _fov(cam)
    th, tv = math.tan(fh / 2) * fill, math.tan(fv / 2) * fill
    dist = 0.0
    for c in corners:
        rel = c - center
        depth = rel.dot(-fwd)  # hacia la cámara
        dist = max(dist, depth + abs(rel.dot(right)) / th, depth + abs(rel.dot(up)) / tv)
    aim(cam, center, direction, dist)
    return center, dist


# --- Luces y mundo -------------------------------------------------------------

def sun(name, direction_to_light, strength, color_hex, angle=8.0):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = strength
    ld.color = palette.hex_lin(color_hex)[:3]
    ld.angle = math.radians(angle)
    o = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = direction_to_light.normalized().to_track_quat("Z", "Y").to_euler()
    return o


def _light_dir(cam_dir, az_left, elevation):
    """Dirección hacia la luz relativa a la cámara: az_left grados a la
    izquierda de la cámara (vista desde la cámara) y 'elevation' sobre el horizonte."""
    h = Vector((cam_dir.x, cam_dir.y, 0))
    if h.length < 1e-4:
        h = Vector((0, -1, 0))
    h.normalize()
    left = Vector((0, 0, 1)).cross(h).normalized() * -1  # izquierda vista desde la cámara
    a = math.radians(az_left)
    hd = (h * math.cos(a) + left * math.sin(a)).normalized()
    e = math.radians(elevation)
    return Vector((hd.x * math.cos(e), hd.y * math.cos(e), math.sin(e)))


def world_color(hex_str, strength, camera_hex=None):
    """Mundo uniforme; camera_hex cambia lo que ve la cámara sin cambiar la luz."""
    w = bpy.data.worlds.get("RIG_World") or bpy.data.worlds.new("RIG_World")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg_light = nt.nodes.new("ShaderNodeBackground")
    bg_light.inputs["Color"].default_value = palette.hex_lin(hex_str)
    bg_light.inputs["Strength"].default_value = strength
    if camera_hex:
        bg_cam = nt.nodes.new("ShaderNodeBackground")
        bg_cam.inputs["Color"].default_value = palette.hex_lin(camera_hex)
        lp = nt.nodes.new("ShaderNodeLightPath")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(bg_light.outputs[0], mix.inputs[1])
        nt.links.new(bg_cam.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        nt.links.new(bg_light.outputs[0], out.inputs[0])
    bpy.context.scene.world = w
    return w


def world_sky(light_strength=0.55):
    """Cielo en degradado vertical #9FD8FF (arriba) -> #FFD6E8 (horizonte).
    La cámara lo ve a intensidad 1; la luz ambiental se atenúa."""
    w = bpy.data.worlds.get("RIG_World") or bpy.data.worlds.new("RIG_World")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
    cr = ramp.color_ramp
    cr.interpolation = "EASE"
    cr.elements[0].position = 0.0
    cr.elements[0].color = palette.hex_lin(palette.WORLD["sky_horizon"])
    cr.elements[1].position = 0.45
    cr.elements[1].color = palette.hex_lin(palette.WORLD["sky_top"])
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_light = nt.nodes.new("ShaderNodeBackground")
    bg_light.inputs["Strength"].default_value = light_strength
    nt.links.new(ramp.outputs["Color"], bg_cam.inputs["Color"])
    nt.links.new(ramp.outputs["Color"], bg_light.inputs["Color"])
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg_light.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    bpy.context.scene.world = w
    return w


def rig_studio(cam_dir):
    sun("RIG_Key", _light_dir(cam_dir, KEY_AZIMUTH_LEFT, KEY_ELEVATION), 2.9, LIGHT["studio_key"], 12)
    sun("RIG_Fill", _light_dir(cam_dir, -60, 15), 0.7, LIGHT["studio_fill"], 30)
    sun("RIG_Rim", _light_dir(cam_dir, 160, 35), 2.2, LIGHT["studio_rim"], 6)
    world_color(palette.SUPPORT["studio_bg"], 0.45)


def rig_game(cam_dir):
    sun("RIG_Sun", _light_dir(cam_dir, KEY_AZIMUTH_LEFT, KEY_ELEVATION), 3.4, LIGHT["game_sun"], 4)
    sun("RIG_Rim", _light_dir(cam_dir, 165, 25), 1.6, LIGHT["game_rim"], 6)
    world_sky(0.6)


def catcher(z, size=200):
    o = geo.box("RIG_Catcher", (size, size, 0.01), (0, 0, z - 0.005))
    o.is_shadow_catcher = True
    return o


def ground(z=0.0, size=600):
    from . import materials
    g = geo.box("RIG_Ground", (size, size, 0.2), (0, 0, z - 0.1))
    materials.assign(g, materials.get("matte", "grass", name="RIG_grass"))
    plaza = geo.cylinder("RIG_Plaza", 9.0, 0.06, 64, (0, 0, z + 0.0))
    materials.assign(plaza, materials.get("matte", "cantera", name="RIG_cantera"))
    return g


# --- Render -------------------------------------------------------------------------

def _render(path):
    sc = bpy.context.scene
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return round(time.time() - t, 1)


class Session:
    """Una sesión de renders para un asset y una versión."""

    def __init__(self, root, asset_id, version, objs, quick=False, floor=True,
                 scale_place="ground", detail_point=None, detail_zoom=2.6):
        self.root = root
        self.asset_id = asset_id
        self.version = version
        self.objs = objs
        self.quick = quick
        self.floor = floor
        self.scale_place = scale_place
        self.detail_point = detail_point
        self.detail_zoom = detail_zoom
        self.out = os.path.join(root, "renders", asset_id, version)
        self.tmp = os.path.join(self.out, "_tmp")
        os.makedirs(self.tmp, exist_ok=True)
        self.times = {}
        self.files = {}
        self.turn = None

    @property
    def samples(self):
        return SAMPLES["quick" if self.quick else "final"]

    def visible(self):
        return [o for o in self.objs if o.type == "MESH" and not o.hide_render]

    def _base(self, res, transparent):
        clear_rig()
        setup_engine(res, self.samples, transparent)

    def _save(self, key, path, secs):
        self.files[key] = os.path.relpath(path, self.root)
        self.times[key] = secs

    # -- estudio neutro
    def studio(self, views=("front", "34", "side", "top", "detail"), prefix="studio", res=(1024, 1024)):
        angles = {"front": (0, 8), "34": (35, 18), "side": (90, 8), "top": (0, 89), "detail": (35, 18)}
        for v in views:
            self._base(res, True)
            show_mannequin(False)
            az, el = angles[v]
            d = _dir(az, el)
            cam = camera()
            if v == "detail":
                lo, hi = geo.world_bbox(self.visible())
                pt = Vector(self.detail_point) if self.detail_point else (lo + hi) / 2
                _, dist = frame(cam, self.visible(), d)
                aim(cam, pt, d, dist / self.detail_zoom)
            else:
                frame(cam, self.visible(), d, fill=0.82)
            rig_studio(d)
            if self.floor:
                lo, _ = geo.world_bbox(self.visible())
                catcher(lo.z)
            raw = os.path.join(self.tmp, f"{prefix}_{v}_raw.png")
            secs = _render(raw)
            path = os.path.join(self.out, f"{prefix}_{v}.png")
            post.composite_bg(raw, path, palette.SUPPORT["studio_bg"])
            self._save(f"{prefix}_{v}", path, secs)

    # -- toma de juego
    def game(self, res=(1920, 1080), az=28, el=6, fill=0.55, fov_v=None, name="game"):
        self._base(res, False)
        show_mannequin(False)
        d = _dir(az, el)
        cam = camera(lens=40, fov_v=fov_v)
        lo, _ = geo.world_bbox(self.visible())
        frame(cam, self.visible(), d, fill=fill)
        rig_game(d)
        ground(lo.z if self.floor else 0.0)
        raw = os.path.join(self.tmp, f"{name}_raw.png")
        secs = _render(raw)
        path = os.path.join(self.out, f"{name}.png")
        post.game_grade(raw, path)
        self._save(name, path, secs)

    # -- silueta negro sobre blanco
    def silhouette(self, res=(1024, 1024)):
        self._base(res, True)
        bpy.context.scene.cycles.samples = 8
        bpy.context.scene.cycles.use_denoising = False
        show_mannequin(False)
        d = _dir(35, 18)
        cam = camera()
        frame(cam, self.visible(), d, fill=0.82)
        world_color("#FFFFFF", 1.0)
        raw = os.path.join(self.tmp, "silhouette_raw.png")
        secs = _render(raw)
        path = os.path.join(self.out, "silhouette.png")
        post.silhouette(raw, path)
        self._save("silhouette", path, secs)

    def _place_root(self):
        """Empty raíz para mover/girar el asset entero sin tocar sus piezas."""
        if self.turn:
            return self.turn
        e = bpy.data.objects.new("TURN_Root", None)
        bpy.context.scene.collection.objects.link(e)
        for o in self.objs:
            if o.parent is None:
                o.parent = e
        self.turn = e
        return e

    # -- escala junto al maniquí R15
    def scale(self, res=(1024, 1024)):
        self._base(res, True)
        root = self._place_root()
        lo, hi = geo.world_bbox(self.visible())
        if self.scale_place == "hang":
            root.location = (0, 0, 5.5 - (lo.z + hi.z) / 2)  # centro a 5.5 studs
        else:
            root.location = (0, 0, -lo.z)
        bpy.context.view_layer.update()
        lo, hi = geo.world_bbox(self.visible())
        man_x = lo.x - 0.6 - 1.0 - 0.6  # a la izquierda vista de frente
        man_root = show_mannequin(True, (man_x, 0, 0))
        both = self.visible() + [c for c in man_root.children if c.type == "MESH"]
        d = _dir(20, 10)
        cam = camera()
        frame(cam, both, d, fill=0.85)
        rig_studio(d)
        catcher(0.0)
        raw = os.path.join(self.tmp, "scale_raw.png")
        secs = _render(raw)
        path = os.path.join(self.out, "scale.png")
        post.composite_bg(raw, path, palette.SUPPORT["studio_bg"])
        root.location = (0, 0, 0)
        show_mannequin(False)
        bpy.context.view_layer.update()
        self._save("scale", path, secs)

    # -- a 50 studs con la cámara de Roblox
    def far50(self, res=(1920, 1080)):
        self._base(res, False)
        root = self._place_root()
        lo, hi = geo.world_bbox(self.visible())
        if self.scale_place == "hang":
            root.location = (0, 0, 5.5 - (lo.z + hi.z) / 2)
        else:
            root.location = (0, 0, -lo.z)
        bpy.context.view_layer.update()
        lo, hi = geo.world_bbox(self.visible())
        center = (lo + hi) / 2
        cam = camera(fov_v=ROBLOX_FOV_V)
        cam.location = Vector((center.x + 50 * math.sin(math.radians(20)), -50 * math.cos(math.radians(20)), 9.0))
        look = (center - cam.location)
        cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
        man_root = show_mannequin(True, (center.x + 4.0, center.y - 6.0, 0))
        rig_game(cam.location - center)
        ground(0.0)
        raw = os.path.join(self.tmp, "far50_raw.png")
        secs = _render(raw)
        path = os.path.join(self.out, "far50.png")
        post.game_grade(raw, path)
        root.location = (0, 0, 0)
        show_mannequin(False)
        bpy.context.view_layer.update()
        self._save("far50", path, secs)

    # -- giro de 360° en 24 cuadros
    def turntable(self, frames=24, res=(512, 512)):
        self._base(res, True)
        bpy.context.scene.cycles.samples = max(16, self.samples // 3)
        root = self._place_root()
        show_mannequin(False)
        d = _dir(25, 15)
        cam = camera()
        # encuadre que cubra todas las orientaciones
        lo, hi = geo.world_bbox(self.visible())
        c = (lo + hi) / 2
        r = max(Vector((hi.x - c.x, hi.y - c.y, 0)).length, 0.01)
        fake = [Vector((c.x + r, c.y + r, hi.z)), Vector((c.x - r, c.y - r, lo.z))]
        helper = geo.box("RIG_Bounds", (2 * r, 2 * r, hi.z - lo.z), c)
        helper.hide_render = True
        frame(cam, [helper], d, fill=0.85)
        rig_studio(d)
        if self.floor:
            catcher(lo.z)
        fdir = os.path.join(self.out, "turntable_frames")
        os.makedirs(fdir, exist_ok=True)
        t0 = time.time()
        paths = []
        for i in range(frames):
            root.rotation_euler = (0, 0, 2 * math.pi * i / frames)
            bpy.context.view_layer.update()
            raw = os.path.join(fdir, f"raw_{i:02d}.png")
            _render(raw)
            p = os.path.join(fdir, f"f_{i:02d}.png")
            post.composite_bg(raw, p, palette.SUPPORT["studio_bg"])
            paths.append(p)
        root.rotation_euler = (0, 0, 0)
        bpy.context.view_layer.update()
        gif = os.path.join(self.out, "turntable.gif")
        post.make_gif(paths, gif)
        self._save("turntable", gif, round(time.time() - t0, 1))
        if shutil.which("ffmpeg"):
            mp4 = os.path.join(self.out, "turntable.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "12", "-i",
                            os.path.join(fdir, "f_%02d.png"), "-pix_fmt", "yuv420p",
                            "-vf", "scale=512:512", mp4], check=False)
            if os.path.exists(mp4):
                self.files["turntable_mp4"] = os.path.relpath(mp4, self.root)

    # -- icono 512 transparente
    def icon(self, out_path=None, res=(512, 512)):
        self._base(res, True)
        show_mannequin(False)
        d = _dir(30, 20)
        cam = camera()
        frame(cam, self.visible(), d, fill=0.80)
        sun("RIG_Key", _light_dir(d, KEY_AZIMUTH_LEFT, 45), 3.0, LIGHT["studio_key"], 12)
        sun("RIG_Rim", _light_dir(d, 160, 35), 2.6, LIGHT["studio_rim"], 6)
        world_color(palette.SUPPORT["studio_bg"], 0.5)
        raw = os.path.join(self.tmp, "icon_raw.png")
        secs = _render(raw)
        path = out_path or os.path.join(self.out, "icon.png")
        post.icon_finish(raw, path)
        self._save("icon", path, secs)

    # -- estados (llenado, daño, explotada) definidos por el asset
    def states(self, states, view=(35, 18), res=(768, 768)):
        """states: lista de (nombre, función que aplica el estado y devuelve la que lo revierte)."""
        for name, apply_fn in states:
            undo = apply_fn()
            bpy.context.view_layer.update()
            self._base(res, True)
            show_mannequin(False)
            d = _dir(*view)
            cam = camera()
            frame(cam, self.visible(), d, fill=0.82)
            rig_studio(d)
            raw = os.path.join(self.tmp, f"state_{name}_raw.png")
            secs = _render(raw)
            path = os.path.join(self.out, f"state_{name}.png")
            post.composite_bg(raw, path, palette.SUPPORT["studio_bg"])
            self._save(f"state_{name}", path, secs)
            if undo:
                undo()
            bpy.context.view_layer.update()

    def run(self, modes):
        order = ["studio", "game", "silhouette", "scale", "far50", "turntable", "icon"]
        for m in order:
            if m in modes:
                print(f"[render] {self.asset_id} {self.version}: {m}")
                getattr(self, m)()
        if self.turn:
            for o in list(self.turn.children):
                mw = o.matrix_world.copy()
                o.parent = None
                o.matrix_world = mw
            bpy.data.objects.remove(self.turn)
            self.turn = None
        clear_rig()
        return self.files, self.times
