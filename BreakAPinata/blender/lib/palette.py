"""Paleta oficial de BREAK A PIÑATA.

Ningún asset define colores sueltos: todos salen de aquí por nombre.
Los hex son sRGB; Blender necesita valores lineales (hex_lin).
"""
import colorsys


def hex_to_srgb(hex_str):
    h = hex_str.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_lin(hex_str, alpha=1.0):
    """Hex sRGB -> RGBA lineal para Blender."""
    r, g, b = (srgb_to_linear(c) for c in hex_to_srgb(hex_str))
    return (r, g, b, alpha)


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def adjust(hex_str, sat=1.0, val=1.0, hue_shift=0.0):
    """Ajusta saturación y valor en HSV (multiplicadores)."""
    r, g, b = hex_to_srgb(hex_str)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h = (h + hue_shift) % 1.0
    return rgb_to_hex(colorsys.hsv_to_rgb(h, min(1, s * sat), min(1, v * val)))


def fill_off(hex_str):
    """Estado apagado de un indicador de llenado: desaturado y más oscuro."""
    return adjust(hex_str, sat=0.55, val=0.62)


def mix(hex_a, hex_b, t):
    a, b = hex_to_srgb(hex_a), hex_to_srgb(hex_b)
    return rgb_to_hex(tuple(x + (y - x) * t for x, y in zip(a, b)))


# --- Mundo -----------------------------------------------------------------
WORLD = {
    "sky_top": "#9FD8FF",
    "sky_horizon": "#FFD6E8",
    "grass": "#8EDB7A",
    "cantera": "#F6D7A7",
    "rosa": "#FF5DA2",        # rosa mexicano
    "turquesa": "#3FD0C9",
    "amarillo": "#FFD23F",
    "naranja": "#FF9F43",
    "lila": "#B18CFF",
    "jacaranda": "#A77BFF",
}
FACADES = ["rosa", "turquesa", "amarillo", "naranja", "lila"]

# --- Interfaz ----------------------------------------------------------------
UI = {
    "panel_top": "#4B2496", "panel_bottom": "#2D145C",
    "cream_top": "#FFF6E8", "cream_bottom": "#FFE3C2",
    "outline": "#1E0B40",
    "buy_top": "#5BF0A5", "buy_bottom": "#1FBF6E", "buy_border": "#0B5E36",
    "sec_top": "#6CC8FF", "sec_bottom": "#2E8BFF", "sec_border": "#12408A",
    "close_top": "#FF7A8A", "close_bottom": "#E8344E", "close_border": "#6E0F1F",
    "coin_top": "#FFE066", "coin_bottom": "#FFB000",
    "gem_top": "#7CF7FF", "gem_bottom": "#2BB8FF",
    "aguinaldo_top": "#FF8FA3", "aguinaldo_bottom": "#FF4F6D",
    "premium_magenta": "#FF4FD8", "premium_violet": "#9B5CFF",
    "disabled_top": "#9AA0B5", "disabled_bottom": "#6B7085",
}

# --- Rarezas -----------------------------------------------------------------
RARITY = {
    "common": "#C9D3E3",
    "uncommon": "#7BE495",
    "rare": "#4FA9FF",
    "epic": "#B061FF",
    "mythic": ["#FF4FD8", "#FFD84F", "#4FFFE0", "#9B5CFF"],
}

# --- Colores de apoyo (derivados, justificados en las fichas) ---------------
SUPPORT = {
    "studio_bg": "#ECE8F4",
    "mannequin": "#B8BCCB",
    "mannequin_accent": "#8C91A6",
    "wood_raw": "#C98A55",      # madera vista (cantos, palitos)
    "clay": "#D9774A",          # barro de macetas
    "metal_tip": "#D7DCE6",     # metal pintado claro
    "gold_drop": "#FFD84F",     # gota sorpresa
    "rope": "#E9D6B0",          # cuerda de ixtle
    "white": "#FFFFFF",
}


def color(name):
    """Busca un color por nombre en todas las tablas; acepta también '#RRGGBB'."""
    if name.startswith("#"):
        return name.upper()
    for table in (WORLD, UI, SUPPORT):
        if name in table:
            return table[name]
    if name in RARITY and isinstance(RARITY[name], str):
        return RARITY[name]
    raise KeyError(f"Color '{name}' no está en la paleta")
