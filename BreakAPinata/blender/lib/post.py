"""Post-proceso con Pillow: fondo de estudio, gradación de juego (bloom suave y
saturación como Roblox), silueta, GIF e iconos con contorno."""
from PIL import Image, ImageChops, ImageEnhance, ImageFilter

from . import palette


def _rgb(hex_str):
    return tuple(int(round(c * 255)) for c in palette.hex_to_srgb(hex_str))


def composite_bg(raw, out, bg_hex):
    im = Image.open(raw).convert("RGBA")
    bg = Image.new("RGBA", im.size, _rgb(bg_hex) + (255,))
    Image.alpha_composite(bg, im).convert("RGB").save(out, optimize=True)
    return out


def game_grade(raw, out, saturation=1.10, bloom=0.22, threshold=200):
    """Aproxima la post-producción prevista en Roblox: Bloom suave y saturación +10%."""
    im = Image.open(raw).convert("RGB")
    im = ImageEnhance.Color(im).enhance(saturation)
    lum = im.convert("L").point(lambda v: 255 if v > threshold else int(v * v / (threshold * 4)))
    bright = Image.composite(im, Image.new("RGB", im.size, (0, 0, 0)), lum)
    radius = max(4, im.width // 90)
    glow = bright.filter(ImageFilter.GaussianBlur(radius))
    glow = ImageEnhance.Brightness(glow).enhance(bloom)
    im = ImageChops.add(im, glow)
    im.save(out, optimize=True)
    return out


def silhouette(raw, out):
    a = Image.open(raw).convert("RGBA").getchannel("A")
    white = Image.new("L", a.size, 255)
    black = Image.new("L", a.size, 0)
    Image.composite(black, white, a).convert("RGB").save(out, optimize=True)
    return out


def make_gif(frames, out, ms=90, size=None):
    ims = [Image.open(f).convert("RGB") for f in frames]
    if size:
        ims = [i.resize(size, Image.LANCZOS) for i in ims]
    pal = [i.quantize(colors=200, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for i in ims]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=ms, loop=0, optimize=True)
    return out


def icon_finish(raw, out, outline_px=6, outline_hex=None):
    """Contorno de 6 px en #1E0B40 alrededor de la silueta y sombra suave debajo."""
    outline_hex = outline_hex or palette.UI["outline"]
    im = Image.open(raw).convert("RGBA")
    a = im.getchannel("A")
    hard = a.point(lambda v: 255 if v > 24 else 0)
    dil = hard
    for _ in range(outline_px):
        dil = dil.filter(ImageFilter.MaxFilter(3))
    dil = dil.filter(ImageFilter.GaussianBlur(0.8))
    col = _rgb(outline_hex)
    outline = Image.new("RGBA", im.size, col + (0,))
    outline.putalpha(dil)
    shadow_a = dil.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.35))
    shadow = Image.new("RGBA", im.size, col + (0,))
    shadow.putalpha(shadow_a)
    shifted = Image.new("RGBA", im.size, (0, 0, 0, 0))
    shifted.paste(shadow, (0, max(4, im.height // 64)))
    canvas = Image.new("RGBA", im.size, (0, 0, 0, 0))
    canvas = Image.alpha_composite(canvas, shifted)
    canvas = Image.alpha_composite(canvas, outline)
    canvas = Image.alpha_composite(canvas, im)
    canvas.save(out, optimize=True)
    return out
