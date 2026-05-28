"""Generate viro.ico — bold 'V' monogram on indigo rounded square, multi-size."""
from PIL import Image, ImageDraw, ImageFont
import io, os, struct


def make_image(size):
    SCALE = 4
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    r = s // 5
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=(79, 70, 229, 255))

    font = None
    font_size = int(s * 0.68)
    for path in [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\verdanab.ttf",
    ]:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, font_size)
                break
            except Exception:
                pass

    if font:
        bbox = d.textbbox((0, 0), "V", font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (s - tw) / 2 - bbox[0]
        y = (s - th) / 2 - bbox[1] - s * 0.03
        d.text((x, y), "V", font=font, fill=(255, 255, 255, 255))
    else:
        lw = max(2, s // 10)
        d.line([(s * 0.18, s * 0.18), (s // 2, s * 0.78)], fill="white", width=lw)
        d.line([(s // 2, s * 0.78), (s * 0.82, s * 0.18)], fill="white", width=lw)

    return img.resize((size, size), Image.LANCZOS)


def image_to_png_bytes(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_ico(sizes):
    """Manually build a valid multi-size ICO from PNG chunks."""
    images = [make_image(s) for s in sizes]
    pngs = [image_to_png_bytes(img) for img in images]
    n = len(sizes)
    header = struct.pack("<HHH", 0, 1, n)
    offset = 6 + n * 16
    directory = b""
    for s, png in zip(sizes, pngs):
        w = s if s < 256 else 0
        h = s if s < 256 else 0
        directory += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png), offset)
        offset += len(png)
    return header + directory + b"".join(pngs)


out = os.path.join(os.path.dirname(__file__), "viro.ico")
with open(out, "wb") as f:
    f.write(build_ico([16, 24, 32, 48, 64, 128, 256]))
print(f"Saved: {out} with 7 sizes")
