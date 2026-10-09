"""Utilidades de geometría: primitivas de partida, biseles, flecos,
cortes (franjas y prefracturado), pivotes, conteo y revisión de mallas.

Convenciones: 1 unidad = 1 stud, Z arriba, frente del modelo hacia -Y.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector


# --- Escena y objetos --------------------------------------------------------

def collection(name):
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def obj_from_bmesh(name, bm, coll=None, loc=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    # matrix_world explícita: location sola no se refleja hasta actualizar el depsgraph
    obj.matrix_world = Matrix.Translation(loc)
    return link(obj, coll)


def empty(name, loc=(0, 0, 0), coll=None, size=0.25):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "PLAIN_AXES"
    e.empty_display_size = size
    e.matrix_world = Matrix.Translation(loc)
    return link(e, coll)


def clear_scene():
    """Escena vacía con unidades en metros = studs."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    return sc


# --- Primitivas (solo como punto de partida) --------------------------------

def sphere(name, radius=1.0, segments=32, rings=16, loc=(0, 0, 0), coll=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=radius)
    return obj_from_bmesh(name, bm, coll, loc)


def cone(name, r1=1.0, r2=0.0, depth=2.0, segments=24, loc=(0, 0, 0), coll=None, base_at_origin=True):
    """Cono o tronco a lo largo de +Z. Con base_at_origin la base queda en z=0."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=r1, radius2=r2, depth=depth)
    if base_at_origin:
        bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, depth / 2))
    return obj_from_bmesh(name, bm, coll, loc)


def cylinder(name, radius=1.0, depth=1.0, segments=24, loc=(0, 0, 0), coll=None, base_at_origin=False):
    return cone(name, radius, radius, depth, segments, loc, coll, base_at_origin)


def box(name, size=(1, 1, 1), loc=(0, 0, 0), coll=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    return obj_from_bmesh(name, bm, coll, loc)


def torus(name, major=1.0, minor=0.25, seg=32, minor_seg=12, loc=(0, 0, 0), coll=None):
    """Toro en el plano XY."""
    bm = bmesh.new()
    rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        ring = []
        for j in range(minor_seg):
            b = 2 * math.pi * j / minor_seg
            r = major + minor * math.cos(b)
            ring.append(bm.verts.new((r * math.cos(a), r * math.sin(a), minor * math.sin(b))))
        rings.append(ring)
    for i in range(seg):
        r0, r1 = rings[i], rings[(i + 1) % seg]
        for j in range(minor_seg):
            j1 = (j + 1) % minor_seg
            bm.faces.new((r0[j], r1[j], r1[j1], r0[j1]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bmesh(name, bm, coll, loc)


def lathe(name, profile, segments=32, loc=(0, 0, 0), coll=None):
    """Sólido de revolución alrededor de Z. profile: [(r, z), ...] de abajo arriba.
    Si el primer o último r es 0, el polo se cierra en un punto."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r <= 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / segments),
                                        r * math.sin(2 * math.pi * i / segments), z))
                          for i in range(segments)])
    for a, b in zip(rings[:-1], rings[1:]):
        if len(a) == 1 and len(b) == 1:
            continue
        for i in range(segments):
            i1 = (i + 1) % segments
            if len(a) == 1:
                bm.faces.new((a[0], b[i], b[i1]))
            elif len(b) == 1:
                bm.faces.new((a[i], b[0], a[i1]))
            else:
                bm.faces.new((a[i], b[i], b[i1], a[i1]))
    # tapas planas si los extremos no son polos
    if len(rings[0]) > 1:
        bm.faces.new(list(reversed(rings[0])))
    if len(rings[-1]) > 1:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bmesh(name, bm, coll, loc)


# --- Modificadores -----------------------------------------------------------

def bevel(obj, width=0.04, segments=2, angle=30.0, profile=0.5, harden=False):
    m = obj.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segments
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.profile = profile
    m.harden_normals = harden
    m.use_clamp_overlap = True
    return m


def subsurf(obj, levels=1):
    m = obj.modifiers.new("Subsurf", "SUBSURF")
    m.levels = levels
    m.render_levels = levels
    return m


def solidify(obj, thickness=0.02, offset=0.0):
    m = obj.modifiers.new("Solidify", "SOLIDIFY")
    m.thickness = thickness
    m.offset = offset
    m.use_even_offset = True
    return m


def smooth(obj, angle=40.0):
    """Sombreado suave con bordes definidos por ángulo."""
    me = obj.data
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(angle))
    return obj


def apply_modifiers(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    new_me = bpy.data.meshes.new_from_object(ev)
    old = obj.data
    obj.modifiers.clear()
    obj.data = new_me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


# --- Transformaciones y pivotes ---------------------------------------------

def set_origin(obj, world_point):
    """Mueve el origen (pivote) de obj al punto dado, sin mover la geometría."""
    p_local = obj.matrix_world.inverted() @ Vector(world_point)
    obj.data.transform(Matrix.Translation(-p_local))
    obj.matrix_world = obj.matrix_world @ Matrix.Translation(p_local)
    return obj


def apply_transform(obj):
    """Hornea rotación y escala en la malla; conserva la posición."""
    loc = obj.matrix_world.translation.copy()
    obj.data.transform(Matrix.Translation(-loc) @ obj.matrix_world)
    obj.matrix_world = Matrix.Translation(loc)
    return obj


def transform_mesh(obj, matrix):
    obj.data.transform(matrix)
    obj.data.update()
    return obj


def look_rotation(direction, up=(0, 0, 1)):
    """Matriz 3x3 que lleva +Z local a 'direction'."""
    return Vector(direction).normalized().to_track_quat("Z", "Y").to_matrix()


def join(objs, name):
    target = objs[0]
    with bpy.context.temp_override(active_object=target, object=target,
                                   selected_objects=objs, selected_editable_objects=objs):
        bpy.ops.object.join()
    target.name = name
    target.data.name = name
    return target


def duplicate(obj, name, coll=None):
    d = obj.copy()
    d.data = obj.data.copy()
    d.name = name
    d.data.name = name
    for c in obj.users_collection[:1]:
        (coll or c).objects.link(d)
    return d


# --- Cortes: franjas y prefracturado ----------------------------------------

def _half(bm_src, co, no, keep_positive):
    bm = bm_src.copy()
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=co, plane_no=no,
                           clear_inner=keep_positive, clear_outer=not keep_positive)
    boundary = [e for e in bm.edges if e.is_boundary]
    if boundary:
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=boundary,
                                normal=Vector(no) if not keep_positive else -Vector(no))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def split_by_planes(obj, planes, prefix, coll=None, origin="center"):
    """Corta obj (sólido cerrado) con una lista de planos [(co, no)].
    Devuelve piezas cerradas que encajan exactamente, nombradas prefix_01…
    Las coordenadas de los planos están en el espacio local de obj."""
    bm0 = bmesh.new()
    bm0.from_mesh(obj.data)
    pieces = [bm0]
    for co, no in planes:
        nxt = []
        for bm in pieces:
            for keep in (True, False):
                h = _half(bm, co, no, keep)
                if len(h.faces) > 0:
                    nxt.append(h)
                else:
                    h.free()
            bm.free()
        pieces = nxt
    out = []
    for i, bm in enumerate(pieces, 1):
        name = f"{prefix}_{i:02d}"
        o = obj_from_bmesh(name, bm, coll or obj.users_collection[0])
        o.matrix_world = obj.matrix_world.copy()
        for m in obj.data.materials:
            o.data.materials.append(m)
        if origin == "center":
            set_origin(o, bbox_center([o]))
        out.append(o)
    return out


def bands(obj, z_cuts, prefix, coll=None):
    """Divide obj en franjas horizontales cerradas entre los z dados (locales).
    z_cuts: lista creciente con los cortes internos. Devuelve franjas de abajo arriba."""
    bm0 = bmesh.new()
    bm0.from_mesh(obj.data)
    edges = [-1e9] + list(z_cuts) + [1e9]
    out = []
    for i in range(len(edges) - 1):
        bm = bm0.copy()
        if edges[i] > -1e8:
            h = _half(bm, (0, 0, edges[i]), (0, 0, 1), True)
            bm.free()
            bm = h
        if edges[i + 1] < 1e8:
            h = _half(bm, (0, 0, edges[i + 1]), (0, 0, 1), False)
            bm.free()
            bm = h
        name = f"{prefix}_{i + 1:02d}"
        o = obj_from_bmesh(name, bm, coll or obj.users_collection[0])
        o.matrix_world = obj.matrix_world.copy()
        set_origin(o, bbox_center([o]))
        out.append(o)
    bm0.free()
    return out


# --- Flecos de papel --------------------------------------------------------

def fringe_ring(name, count=24, radius=0.3, length=0.35, width=0.06, thickness=0.012,
                droop=0.25, curl=0.15, seed=1, segments=4, coll=None):
    """Anillo de tiras de papel con grosor, en el plano XY, saliendo hacia afuera.
    droop: cuánto caen las puntas (studs); curl: ondulación aleatoria.
    El origen está en el centro del anillo."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    for k in range(count):
        a = 2 * math.pi * (k + rnd.uniform(-0.2, 0.2)) / count
        L = length * rnd.uniform(0.85, 1.12)
        tw = rnd.uniform(-0.6, 0.6)  # giro de la tira
        dr = droop * rnd.uniform(0.7, 1.3)
        cu = curl * rnd.uniform(-1, 1)
        ring_prev = None
        for s in range(segments + 1):
            t = s / segments
            # posición a lo largo de la tira
            r = radius + L * t
            z = -dr * t * t
            side = cu * t * t
            cx, cy = r * math.cos(a), r * math.sin(a)
            # vector tangente (lateral) y normal de la tira
            tx, ty = -math.sin(a), math.cos(a)
            ang = tw * t
            wx, wy, wz = tx * math.cos(ang), ty * math.cos(ang), math.sin(ang)
            nx, ny, nz = -tx * math.sin(ang), -ty * math.sin(ang), math.cos(ang)
            cx += tx * side
            cy += ty * side
            hw = width * 0.5 * (1.0 - 0.25 * t)
            ht = thickness * 0.5
            ring = [bm.verts.new((cx + wx * sx * hw + nx * sz * ht,
                                  cy + wy * sx * hw + ny * sz * ht,
                                  z + wz * sx * hw + nz * sz * ht))
                    for sx, sz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            if ring_prev:
                for j in range(4):
                    j1 = (j + 1) % 4
                    bm.faces.new((ring_prev[j], ring[j], ring[j1], ring_prev[j1]))
            else:
                bm.faces.new(list(reversed(ring)))
            ring_prev = ring
        bm.faces.new(ring_prev)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return obj_from_bmesh(name, bm, coll)


# --- UVs -----------------------------------------------------------------------

def uv_smart(obj, angle=66.0, margin=0.02):
    vl = bpy.context.view_layer
    for o in vl.objects:
        o.select_set(False)
    obj.select_set(True)
    vl.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


# --- Medidas e inspección -----------------------------------------------------

def _eval_mesh(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    return ev, ev.to_mesh()


def tris(obj):
    if obj.type != "MESH":
        return 0
    ev, me = _eval_mesh(obj)
    n = sum(len(p.vertices) - 2 for p in me.polygons)
    ev.to_mesh_clear()
    return n


def world_bbox(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != "MESH":
            continue
        ev, me = _eval_mesh(o)
        mw = o.matrix_world
        for v in me.vertices:
            p = mw @ v.co
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
        ev.to_mesh_clear()
    return lo, hi


def bbox_center(objs):
    lo, hi = world_bbox(objs)
    return (lo + hi) / 2


def dims(objs):
    lo, hi = world_bbox(objs)
    return tuple(round(x, 3) for x in (hi - lo))


def mesh_report(obj):
    """Revisión técnica de la malla evaluada (lo que se exporta)."""
    ev, me = _eval_mesh(obj)
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    nonmanifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
    doubles = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=1e-5)["targetmap"])
    # normales: comparamos con las recalculadas hacia afuera
    before = [f.normal.copy() for f in bm.faces]
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    flipped = sum(1 for f, n in zip(bm.faces, before) if f.normal.dot(n) < 0)
    # volumen con signo: negativo = normales hacia adentro
    volume = bm.calc_volume(signed=True)
    bm.free()
    return {
        "open_edges": boundary,       # >0 = superficie abierta / plano de una cara
        "nonmanifold_edges": nonmanifold,
        "loose_verts": loose_verts,
        "degenerate_faces": degenerate,
        "duplicate_verts": doubles,
        "flipped_faces": flipped,
        "volume": round(volume, 4),
        "ok": boundary == 0 and nonmanifold == 0 and loose_verts == 0 and flipped == 0 and volume > 0,
    }
