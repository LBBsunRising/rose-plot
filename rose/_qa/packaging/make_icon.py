"""Generate the RoseChart application icon (transparent, 1024px + ICO multi-size).

Programmatic fallback for the oil_ui_image path. Draws a modern flat
Nightingale rose chart: near-solid disc made of equal-angle rounded slices with
varied radii (petal silhouette), concentric deep-teal -> cyan colour bands,
thin chart separations, optional centre core / guide ring. No text, fully
transparent background. Supersampled + LANCZOS downscaled.

Run with the portable runtime:
    rose\\.venv\\python.exe rose\\_qa\\packaging\\make_icon.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE = Path(__file__).resolve().parents[2]          # rose/
ASSETS = BASE / "assets"
QA = BASE / "_qa" / "packaging"

CANVAS = 1024
CX = CY = 512.0
ART_R = 468.0                                       # max artwork radius (1024 space)

# ---------------------------------------------------------------- palettes
BANDS_DARK_LIGHT = [                                # centre deep -> rim cyan
    (0.00, (9, 58, 73)),
    (0.30, (11, 88, 108)),
    (0.58, (15, 127, 155)),
    (0.80, (39, 183, 207)),
    (1.00, (133, 240, 250)),
]
BANDS_LIGHT_DARK = [
    (0.00, (146, 242, 252)),
    (0.26, (52, 205, 227)),
    (0.55, (17, 138, 167)),
    (0.80, (9, 82, 101)),
    (1.00, (5, 48, 62)),
]
ACCENT_STOPS = [
    (0.00, (124, 39, 58)),
    (0.35, (205, 40, 80)),
    (0.72, (246, 89, 114)),
    (1.00, (255, 190, 196)),
]
HUB_STOPS = [(0.0, (15, 92, 111)), (0.62, (8, 51, 63)), (1.0, (5, 33, 42))]
HUB_RING = (132, 240, 252)

RADII = [0.92, 0.58, 0.80, 0.50, 0.88, 0.64, 0.965, 0.55, 0.84, 0.70]
RADII_9 = [0.92, 0.62, 0.82, 0.54, 0.95, 0.70, 0.58, 0.86, 0.74]
RADII_8 = [0.94, 0.64, 0.86, 0.56, 0.90, 0.70, 0.60, 0.82]
ACCENT_INDEX = 6


def _lut(stops) -> np.ndarray:
    pos = np.array([p for p, _ in stops], dtype=np.float32)
    cols = np.array([c for _, c in stops], dtype=np.float32)
    xs = np.linspace(0.0, 1.0, 1024)
    out = np.stack([np.interp(xs, pos, cols[:, i]) for i in range(3)], axis=1)
    return out.astype(np.uint8)


LUT_DL = _lut(BANDS_DARK_LIGHT)
LUT_LD = _lut(BANDS_LIGHT_DARK)
LUT_ACCENT = _lut(ACCENT_STOPS)
LUT_HUB = _lut(HUB_STOPS)


def _radial_layer(lut, mask, size, r_max, gain: float = 1.0):
    x = np.arange(size, dtype=np.float32)
    c = size / 2.0
    r = np.sqrt((x[None, :] - c) ** 2 + (x[:, None] - c) ** 2)
    t = np.clip(r / r_max, 0.0, 1.0)
    rgb = lut[(t * 1023).astype(np.int32)].astype(np.float32) * gain
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, mask]).astype(np.uint8), "RGBA")


def _arc_pts(cx, cy, r, a_from, a_to, steps):
    return [(cx + r * math.cos(a_from + (a_to - a_from) * k / steps),
             cy + r * math.sin(a_from + (a_to - a_from) * k / steps)) for k in range(steps + 1)]


def sector_mask(ang_center_deg, half_deg, r_out, rho=10.0, size=0, s=3):
    size = size or CANVAS * s
    cx = cy = size / 2.0
    scale = size / CANVAS
    r_out_px = r_out * scale
    rho_px = rho * scale
    a = math.radians(ang_center_deg)
    half = math.radians(half_deg)
    a0, a1 = a - half, a + half
    d = math.asin(min(0.99, rho_px / max(r_out_px - rho_px, 1.0)))
    oc_r = r_out_px - rho_px
    oc1 = (cx + oc_r * math.cos(a0 + d), cy + oc_r * math.sin(a0 + d))
    oc2 = (cx + oc_r * math.cos(a1 - d), cy + oc_r * math.sin(a1 - d))
    pts = [(cx, cy)]
    n0 = (math.cos(a0 + math.pi / 2), math.sin(a0 + math.pi / 2))
    f1 = (oc1[0] - rho_px * n0[0], oc1[1] - rho_px * n0[1])
    pts.append(f1)
    t1 = (cx + r_out_px * math.cos(a0 + d), cy + r_out_px * math.sin(a0 + d))
    ang_f = math.atan2(f1[1] - oc1[1], f1[0] - oc1[0])
    ang_t = math.atan2(t1[1] - oc1[1], t1[0] - oc1[0])
    if ang_f - ang_t > math.pi:
        ang_f -= 2 * math.pi
    elif ang_t - ang_f > math.pi:
        ang_t -= 2 * math.pi
    pts.extend(_arc_pts(oc1[0], oc1[1], rho_px, ang_f, ang_t, 8))
    pts.extend(_arc_pts(cx, cy, r_out_px, a0 + d, a1 - d, 30)[1:])
    t2 = (cx + r_out_px * math.cos(a1 - d), cy + r_out_px * math.sin(a1 - d))
    n1 = (math.cos(a1 + math.pi / 2), math.sin(a1 + math.pi / 2))
    f2 = (oc2[0] + rho_px * n1[0], oc2[1] + rho_px * n1[1])
    ang_t2 = math.atan2(t2[1] - oc2[1], t2[0] - oc2[0])
    ang_f2 = math.atan2(f2[1] - oc2[1], f2[0] - oc2[0])
    if ang_f2 - ang_t2 > math.pi:
        ang_f2 -= 2 * math.pi
    elif ang_t2 - ang_f2 > math.pi:
        ang_t2 -= 2 * math.pi
    pts.extend(_arc_pts(oc2[0], oc2[1], rho_px, ang_t2, ang_f2, 8)[1:])
    pts.append(f2)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)
    return np.array(mask)


def _gloss(canvas: Image.Image, union: np.ndarray, size: int,
           alpha: float = 50.0, shade: float = 26.0):
    x = np.arange(size, dtype=np.float32)
    dx = x[None, :] - size * 0.31
    dy = x[:, None] - size * 0.20
    glow = np.exp(-(dx * dx + dy * dy) / (2.0 * (size * 0.34) ** 2))
    hl = np.minimum((glow * alpha).astype(np.uint8), union)
    hi = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    hi.putalpha(Image.fromarray(hl))
    canvas.alpha_composite(hi)
    dx2 = x[None, :] - size * 0.74
    dy2 = x[:, None] - size * 0.86
    dark = np.exp(-(dx2 * dx2 + dy2 * dy2) / (2.0 * (size * 0.36) ** 2))
    sh = np.minimum((dark * shade).astype(np.uint8), union)
    di = Image.new("RGBA", (size, size), (4, 30, 40, 0))
    di.putalpha(Image.fromarray(sh))
    canvas.alpha_composite(di)


def draw_core(canvas: Image.Image, radius: float, s: int, size: int, ring: bool = True,
              style: str = "ring"):
    scale = size / CANVAS
    cxy = size / 2.0
    r = radius * scale
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([cxy - r, cxy - r, cxy + r, cxy + r], fill=255)
    canvas.alpha_composite(_radial_layer(LUT_HUB, np.array(mask), size, r))
    d = ImageDraw.Draw(canvas)
    if style == "ring":
        rr = r * 0.66
        d.ellipse([cxy - rr, cxy - rr, cxy + rr, cxy + rr],
                  outline=HUB_RING + (95,), width=max(1, int(2.6 * scale)))
    elif style == "dot":
        dr = r * 0.20
        d.ellipse([cxy - dr, cxy - dr, cxy + dr, cxy + dr],
                  fill=HUB_RING + (215,))
    elif style == "both":
        rr = r * 0.70
        d.ellipse([cxy - rr, cxy - rr, cxy + rr, cxy + rr],
                  outline=HUB_RING + (110,), width=max(1, int(3 * scale)))
        d.arc([cxy - r * 0.82, cxy - r * 0.82, cxy + r * 0.82, cxy + r * 0.82],
              start=198, end=322, fill=(180, 250, 255, 115), width=max(1, int(2.5 * scale)))


def draw_chart_lines(canvas: Image.Image, n: int, radii, union, size: int,
                     width_px: float = 3.0, alpha: int = 120, r_min: float = 40.0):
    scale = size / CANVAS
    cxy = size / 2.0
    step = 360.0 / n
    layer = Image.new("RGBA", (size, size), (5, 40, 51, 0))
    d = ImageDraw.Draw(layer)
    w = max(1, int(width_px * scale))
    for i in range(n):
        a = math.radians(-90.0 + (i + 0.5) * step)
        r_end = min(radii[i], radii[(i + 1) % n]) * ART_R * scale
        r0 = r_min * scale
        if r_end <= r0:
            continue
        d.line([cxy + math.cos(a) * r0, cxy + math.sin(a) * r0,
                cxy + math.cos(a) * r_end, cxy + math.sin(a) * r_end],
               fill=(5, 40, 51, alpha), width=w)
    la = np.array(layer.getchannel("A"))
    layer.putalpha(Image.fromarray(np.minimum(la, union)))
    canvas.alpha_composite(layer)


def render(n: int = 10, bands: str = "dl", gap_deg: float = 0.0, rho: float = 10.0,
           radii=None, hole: float = 0.0, core: float = 0.0, guide_ring: float = 0.0,
           accent: bool = False, s: int = 3, gloss: bool = True,
           chart_lines: bool = False, line_alpha: int = 120, tint: float = 0.0,
           rim: bool = False, core_style: str = "ring") -> Image.Image:
    size = CANVAS * s
    radii = radii or ({10: RADII, 9: RADII_9, 8: RADII_8}[n])
    step = 360.0 / n
    half = (step - gap_deg) / 2.0

    slices = []
    for i in range(n):
        ang = -90.0 + i * step
        r_out = radii[i] * ART_R
        slices.append((i, ang, r_out, sector_mask(ang, half, r_out, rho=rho, size=size, s=s)))
    union = np.maximum.reduce([sl[3] for sl in slices])

    # per-pixel fill: continuous colour bands, no seam artefacts between slices
    x = np.arange(size, dtype=np.float32)
    cxy_px = size / 2.0
    dx = x[None, :] - cxy_px
    dy = x[:, None] - cxy_px
    r_map = np.sqrt(dx * dx + dy * dy)
    ang_map = np.degrees(np.arctan2(dy, dx))
    idx = np.floor((((ang_map + 90.0) % 360.0) / step)).astype(np.int32) % n
    lut = LUT_DL if bands == "dl" else LUT_LD
    rgb = lut[(np.clip(r_map / (ART_R * s), 0.0, 1.0) * 1023).astype(np.int32)]
    if tint:
        gains = np.array([1.0 + (tint if i % 2 == 0 else -tint * 0.6) for i in range(n)],
                         dtype=np.float32)
        rgb = np.clip(rgb.astype(np.float32) * gains[idx][..., None], 0, 255).astype(np.uint8)
    if accent:
        acc_sel = (idx == ACCENT_INDEX)
        rgb[acc_sel] = LUT_ACCENT[(np.clip(r_map[acc_sel] / (ART_R * s), 0.0, 1.0) * 1023)
                                  .astype(np.int32)]
    canvas = Image.fromarray(np.dstack([rgb, union]).astype(np.uint8), "RGBA")

    if chart_lines:
        draw_chart_lines(canvas, n, radii, union, size, alpha=line_alpha)

    if gloss:
        _gloss(canvas, union, size)

    d = ImageDraw.Draw(canvas)
    scale = size / CANVAS
    cxy = size / 2.0

    if rim:
        eroded = Image.fromarray(union).filter(ImageFilter.MinFilter(9))
        rim_a = np.clip(np.array(Image.fromarray(union)).astype(np.int16) -
                        np.array(eroded).astype(np.int16), 0, 255).astype(np.uint8)
        rim_layer = Image.new("RGBA", (size, size), (139, 240, 250, 0))
        rim_layer.putalpha(Image.fromarray(rim_a))
        canvas.alpha_composite(rim_layer)

    if guide_ring > 0:
        rr = guide_ring * ART_R * scale
        ring_layer = Image.new("RGBA", (size, size), (255, 255, 255, 0))
        rd = ImageDraw.Draw(ring_layer)
        rd.ellipse([cxy - rr, cxy - rr, cxy + rr, cxy + rr],
                   outline=(190, 250, 255, 145), width=max(1, int(2.0 * scale)))
        ra = np.array(ring_layer.getchannel("A"))
        ring_layer.putalpha(Image.fromarray(np.minimum(ra, union)))
        canvas.alpha_composite(ring_layer)

    if hole > 0:
        hr = hole * scale
        d.ellipse([cxy - hr, cxy - hr, cxy + hr, cxy + hr], fill=(0, 0, 0, 0))
    if core > 0:
        draw_core(canvas, core, s, size, style=core_style)

    return canvas.resize((CANVAS, CANVAS), Image.LANCZOS)


def with_shadow(icon: Image.Image, strength: float = 0.26, blur: float = 16.0,
                offset: int = 12) -> Image.Image:
    alpha = icon.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    a = (np.array(alpha).astype(np.float32) * strength).clip(0, 255).astype(np.uint8)
    sh = np.zeros((CANVAS, CANVAS, 4), dtype=np.uint8)
    sh[..., 0], sh[..., 1], sh[..., 2] = 4, 34, 43
    sh[..., 3] = a
    shadow = Image.fromarray(sh, "RGBA")
    out = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    out.alpha_composite(shadow, dest=(0, offset))
    out.alpha_composite(icon)
    return out


VARIANTS = [
    ("1 solid chart+lines+core", dict(gap_deg=0.0, chart_lines=True, core=74.0)),
    ("2 solid chart+lines", dict(gap_deg=0.0, chart_lines=True)),
    ("3 solid +lines+core+tint", dict(gap_deg=0.0, chart_lines=True, core=74.0, tint=0.035)),
    ("4 solid +lines+core+guide", dict(gap_deg=0.0, chart_lines=True, core=74.0, guide_ring=0.62)),
    ("5 ring chart+lines+core", dict(gap_deg=0.0, chart_lines=True, hole=118.0, core=98.0)),
    ("6 8 slices +lines+core", dict(n=8, gap_deg=0.0, chart_lines=True, core=74.0)),
    ("7 solid +lines+core bright lines", dict(gap_deg=0.0, chart_lines=True, core=90.0,
                                              line_alpha=185)),
    ("8 smooth scallop + core", dict(gap_deg=0.0, core=74.0)),
]


def variant_sheet(path: Path, tile: int = 232):
    n = len(VARIANTS)
    cols = 4
    rows = (n + cols - 1) // cols
    pad = 13
    cell_h = tile + pad + 18
    sheet = Image.new("RGB", (cols * (tile + pad) + pad, 2 * rows * cell_h + pad), (13, 20, 36))
    d = ImageDraw.Draw(sheet)
    for r, bg in enumerate(((255, 255, 255), (13, 20, 36))):
        for c, (name, kw) in enumerate(VARIANTS):
            im = render(**kw)
            x0 = pad + (c % cols) * (tile + pad)
            y0 = pad + (r * rows + c // cols) * cell_h
            tile_img = Image.new("RGB", (tile, tile), bg)
            thumb = im.resize((tile - 22, tile - 22), Image.LANCZOS)
            tile_img.paste(thumb, (11, 11), thumb)
            sheet.paste(tile_img, (x0, y0))
            d.text((x0 + 2, y0 + tile + 2), name, fill=(203, 213, 225))
    sheet.save(path, "PNG")


def small_sheet(path: Path, bases):
    sizes = [16, 24, 32, 48, 64]
    mag = 3
    tile_h = 200
    sheet = Image.new("RGB", (len(sizes) * 200 + 20, len(bases) * 2 * (tile_h + 30) + 20),
                      (13, 20, 36))
    d = ImageDraw.Draw(sheet)
    for bi, (label, base) in enumerate(bases):
        for r, bg in enumerate(((255, 255, 255), (13, 20, 36))):
            for c, sz in enumerate(sizes):
                sm = base.resize((sz, sz), Image.LANCZOS)
                big = sm.resize((sz * mag, sz * mag), Image.NEAREST)
                x0 = 10 + c * 200
                y0 = 10 + (bi * 2 + r) * (tile_h + 30)
                tile = Image.new("RGB", (190, tile_h), bg)
                tile.paste(big, ((190 - big.width) // 2, (tile_h - big.height) // 2), big)
                sheet.paste(tile, (x0, y0))
                d.text((x0 + 4, y0 + tile_h - 12), f"{label} {sz}px", fill=(203, 213, 225))
    sheet.save(path, "PNG")


def ico_sheet(ico_path: Path, path: Path):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    im = Image.open(ico_path)
    frames = {}
    for sz in sizes:
        im.size = (sz, sz)
        frames[sz] = im.convert("RGBA").copy()
    cell = 250
    sheet = Image.new("RGB", (4 * (cell + 12) + 12, 2 * (cell + 12) + 12), (13, 20, 36))
    d = ImageDraw.Draw(sheet)
    for idx, sz in enumerate(sizes):
        fr = frames[sz]
        disp = fr.resize((sz * 3, sz * 3), Image.NEAREST) if sz * 3 <= cell - 20 else fr
        c, r = idx % 4, idx // 4
        x0, y0 = 12 + c * (cell + 12), 12 + r * (cell + 12)
        tile = Image.new("RGB", (cell, cell), (255, 255, 255))
        tile.paste(disp, ((cell - disp.width) // 2, (cell - disp.height) // 2), disp)
        sheet.paste(tile, (x0, y0))
        d.text((x0 + 4, y0 + 4), f"{sz}px", fill=(15, 23, 42))
    sheet.save(path, "PNG")


def save_deliverables(icon: Image.Image):
    ASSETS.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    icon.save(ASSETS / "icon_1024.png", "PNG")
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon_256.png", "PNG")
    icon.save(ASSETS / "icon.ico",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def final_candidates_sheet(path: Path, items, tile: int = 340):
    pad = 16
    rows = 2
    sheet = Image.new("RGB", (len(items) * (tile + pad) + pad, rows * (tile + pad + 18) + pad),
                      (13, 20, 36))
    d = ImageDraw.Draw(sheet)
    for r, bg in enumerate(((255, 255, 255), (13, 20, 36))):
        for c, (name, im) in enumerate(items):
            x0 = pad + c * (tile + pad)
            y0 = pad + r * (tile + pad + 18)
            tile_img = Image.new("RGB", (tile, tile), bg)
            thumb = im.resize((tile - 28, tile - 28), Image.LANCZOS)
            tile_img.paste(thumb, (14, 14), thumb)
            sheet.paste(tile_img, (x0, y0))
            d.text((x0 + 2, y0 + tile + 2), name, fill=(203, 213, 225))
    sheet.save(path, "PNG")


def main() -> int:
    QA.mkdir(parents=True, exist_ok=True)

    common = dict(gap_deg=0.0, chart_lines=True, line_alpha=105)
    final = render(core=84.0, core_style="dot", **common)
    save_deliverables(final)
    final.save(QA / "chosen_1024.png")
    ico_sheet(ASSETS / "icon.ico", QA / "icon_ico_sizes.png")
    small_sheet(QA / "icon_small_sizes.png",
                [("A dot", final),
                 ("B ring", render(core=84.0, core_style="ring", **common)),
                 ("C none", render(**common))])
    final_candidates_sheet(
        QA / "icon_final_candidates.png",
        [("A: core 84 dot", final),
         ("B: core 84 ring", render(core=84.0, core_style="ring", **common)),
         ("C: no core", render(**common)),
         ("D: core 84 both", render(core=84.0, core_style="both", **common))],
        tile=300,
    )
    for name in ("icon_1024.png", "icon_256.png", "icon.ico"):
        p = ASSETS / name
        print(f"deliverable {p}  {p.stat().st_size:,} bytes")
    print("ico sizes:", sorted(Image.open(ASSETS / "icon.ico").ico.sizes()))
    print("preview ->", QA / "icon_final_candidates.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
