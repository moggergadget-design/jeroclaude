"""Maniquí de escala con medidas de un personaje R15 de Roblox (≈5.2 studs).

Medidas del cuerpo por defecto (bloques clásicos): piernas 1×1×2, torso 2×1×2,
brazos 1×1×2 y cabeza ≈1.2. Origen entre los pies, mirando a -Y.
Solo es utilería de render: nunca se exporta.
"""
from . import geo, materials

HEIGHT = 5.2
EYE_HEIGHT = 4.6


def build(loc=(0, 0, 0), name="Mannequin_R15"):
    coll = geo.collection("RIG_Mannequin")
    body = materials.get("matte", "mannequin", name="RIG_mannequin")
    accent = materials.get("matte", "mannequin_accent", name="RIG_mannequin_accent")
    parts = []

    def block(n, size, center, mat, bev=0.12):
        o = geo.box(f"{name}_{n}", size, center, coll)
        geo.bevel(o, bev, 3, angle=60)
        geo.smooth(o, 60)
        materials.assign(o, mat)
        parts.append(o)
        return o

    gap = 0.03
    block("LeftLeg", (0.98, 0.98, 2 - gap), (-0.5, 0, 1.0), body)
    block("RightLeg", (0.98, 0.98, 2 - gap), (0.5, 0, 1.0), body)
    block("Torso", (2.0, 1.0, 2 - gap), (0, 0, 3.0), body)
    block("LeftArm", (0.96, 0.96, 2 - gap), (-1.5, 0, 3.0), body)
    block("RightArm", (0.96, 0.96, 2 - gap), (1.5, 0, 3.0), body)
    head = geo.cylinder(f"{name}_Head", 0.6, 1.2, 32, (0, 0, 4.6), coll)
    geo.bevel(head, 0.25, 4, angle=60)
    geo.smooth(head, 60)
    materials.assign(head, body)
    parts.append(head)
    # visera para ver hacia dónde mira (-Y)
    visor = geo.box(f"{name}_Visor", (0.7, 0.1, 0.22), (0, -0.6, 4.72), coll)
    geo.bevel(visor, 0.04, 2)
    materials.assign(visor, accent)
    parts.append(visor)

    root = geo.empty(name, loc, coll)
    for p in parts:
        p.parent = root
    return root, parts
