"""Generate a modern blue app logo/icon for S2P.

Squircle badge with a diagonal blue gradient, a white S-parameter waveform
motif, and the "S2P" wordmark. Renders a high-res PNG + a multi-size .ico for
the exe/window icon.
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(OUT_DIR, exist_ok=True)
N = 1024
WORDMARK = "ChipLens"


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(size, c0, c1):
    """Diagonal (top-left -> bottom-right) gradient as an RGB array."""
    y, x = np.mgrid[0:size, 0:size]
    t = (x + y) / (2.0 * (size - 1))
    arr = np.zeros((size, size, 3), np.uint8)
    for i in range(3):
        arr[..., i] = (c0[i] + (c1[i] - c0[i]) * t).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def squircle_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def load_font(px, bold=True):
    for name in (("segoeuib.ttf" if bold else "segoeui.ttf"),
                 ("arialbd.ttf" if bold else "arial.ttf")):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def build():
    # --- badge: blue gradient inside a squircle, subtle top highlight ---
    deep = (0x8E, 0x0B, 0x14)      # deep crimson
    sky = (0xF0, 0x39, 0x3E)       # vivid red
    base = gradient(N, deep, sky).convert("RGBA")

    # soft radial highlight top-centre for depth
    hi = Image.new("L", (N, N), 0)
    hd = ImageDraw.Draw(hi)
    hd.ellipse([N * 0.05, -N * 0.35, N * 0.95, N * 0.55], fill=70)
    hi = hi.filter(ImageFilter.GaussianBlur(N * 0.08))
    white = Image.new("RGBA", (N, N), (255, 255, 255, 255))
    base = Image.composite(white, base, hi.point(lambda v: int(v * 0.5)))

    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    img.paste(base, (0, 0), squircle_mask(N, int(N * 0.22)))

    # --- S-parameter waveform: a decaying sine sweeping across the badge ---
    wave = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wave)
    cy = N * 0.34
    pts = []
    for px in range(int(N * 0.14), int(N * 0.86)):
        u = (px - N * 0.14) / (N * 0.72)
        amp = N * 0.10 * (1.0 - 0.55 * u)             # gentle decay -> S-param roll-off
        py = cy + amp * math.sin(u * math.pi * 3.1)
        pts.append((px, py))
    wd.line(pts, fill=(255, 255, 255, 235), width=int(N * 0.026), joint="curve")
    # glow
    wave = Image.alpha_composite(wave.filter(ImageFilter.GaussianBlur(6)), wave)
    img = Image.alpha_composite(img, wave)

    # (re)bind the drawing context to the CURRENT image — alpha_composite above
    # returned a NEW object, so a context bound earlier would draw into nowhere.
    draw = ImageDraw.Draw(img)

    # --- wordmark: auto-fit the product name under the waveform ---
    name = WORDMARK
    target_w = N * 0.80
    size = int(N * 0.20)
    f = load_font(size)
    while draw.textlength(name, font=f) > target_w and size > 24:
        size -= 4
        f = load_font(size)
    w = draw.textlength(name, font=f)
    x = (N - w) / 2
    txt_y = N * 0.56
    sh = (0, 0, 0, 90)  # soft shadow
    for dx, dy, col in ((4, 5, sh), (0, 0, (255, 255, 255, 255))):
        draw.text((x + dx, txt_y + dy), name, font=f, fill=col)

    png = os.path.join(OUT_DIR, "chiplens_logo.png")
    img.save(png)
    # icon set
    ico = os.path.join(OUT_DIR, "chiplens.ico")
    img.save(ico, sizes=[(256, 256), (128, 128), (64, 64), (48, 48),
                         (32, 32), (16, 16)])
    # small preview
    img.resize((256, 256), Image.LANCZOS).save(
        os.path.join(OUT_DIR, "chiplens_logo_256.png"))
    print("saved:", png)
    print("saved:", ico)


if __name__ == "__main__":
    build()
