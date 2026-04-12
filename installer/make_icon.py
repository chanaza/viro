"""Generate viro.ico from the app's SVG logo."""
from PIL import Image, ImageDraw
import os

def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # Background rounded square
    r = s // 6
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=(79, 70, 229, 255))

    # Scale factor
    f = s / 32

    # Crosshair circle
    cx, cy = 9 * f, 9 * f
    cr = 5.5 * f
    lw = max(1, round(1.5 * f))
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], outline=(255, 255, 255, 255), width=lw)

    # Center dot
    dr = 1.8 * f
    d.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=(255, 255, 255, 255))

    # Crosshair lines
    d.line([(cx, 1 * f), (cx, 4.5 * f)], fill=(255, 255, 255, 255), width=lw)
    d.line([(cx, 13.5 * f), (cx, 17 * f)], fill=(255, 255, 255, 255), width=lw)
    d.line([(1 * f, cy), (4.5 * f, cy)], fill=(255, 255, 255, 255), width=lw)
    d.line([(13.5 * f, cy), (17 * f, cy)], fill=(255, 255, 255, 255), width=lw)

    # Spark (lightning bolt) bottom-right
    spark = [
        (15 * f, 13 * f),
        (16.5 * f, 14.5 * f),
        (15.9 * f, 14.75 * f),
        (16.15 * f, 16 * f),
        (15.05 * f, 15.1 * f),
        (14.55 * f, 16 * f),
        (14.35 * f, 14.65 * f),
        (13.6 * f, 14.45 * f),
    ]
    d.polygon(spark, fill=(255, 255, 255, 255))

    return img


sizes = [16, 32, 48, 64, 128, 256]
images = [make_icon(s) for s in sizes]

out = os.path.join(os.path.dirname(__file__), "viro.ico")
images[0].save(out, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
print(f"Saved: {out}")
