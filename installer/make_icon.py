"""Generate viro.ico — bold 'V' monogram on indigo rounded square."""
from PIL import Image, ImageDraw, ImageFont
import os


def make_icon(size):
    SCALE = 4
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Indigo rounded square background
    r = s // 5
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=(79, 70, 229, 255))

    # Bold "V" — try to load a system font, fall back to default
    font = None
    font_size = int(s * 0.68)
    candidates = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\verdanab.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                pass

    text = "V"
    if font:
        bbox = d.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = (s - tw) / 2 - bbox[0]
        y = (s - th) / 2 - bbox[1] - s * 0.03  # slight upward nudge
        d.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    else:
        # Fallback: draw a simple V shape with lines
        lw = max(2, s // 10)
        mid_x = s // 2
        top_y = s * 0.18
        bot_y = s * 0.78
        d.line([(s * 0.18, top_y), (mid_x, bot_y)], fill=(255, 255, 255, 255), width=lw)
        d.line([(mid_x, bot_y), (s * 0.82, top_y)], fill=(255, 255, 255, 255), width=lw)

    return img.resize((size, size), Image.LANCZOS)


sizes = [16, 24, 32, 48, 64, 128, 256]
images = [make_icon(s) for s in sizes]

out = os.path.join(os.path.dirname(__file__), "viro.ico")
images[0].save(out, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
print(f"Saved: {out}")
