"""Trim and scale the rendered brand images to the Home Assistant brand sizes."""

import sys

from PIL import Image

src, dst = sys.argv[1], sys.argv[2]


def trim(img: Image.Image) -> Image.Image:
    return img.crop(img.getchannel("A").getbbox())


def square(img: Image.Image, size: int) -> Image.Image:
    img = trim(img)
    scale = size / max(img.size)
    img = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
    return canvas


def height(img: Image.Image, h: int) -> Image.Image:
    img = trim(img)
    return img.resize((round(img.width * h / img.height), h), Image.LANCZOS)


icon = Image.open(f"{src}/icon_src.png").convert("RGBA")
logo = Image.open(f"{src}/logo_src.png").convert("RGBA")
dark = Image.open(f"{src}/dark_logo_src.png").convert("RGBA")
outputs = {
    "icon.png": square(icon, 256),
    "icon@2x.png": square(icon, 512),
    "logo.png": height(logo, 128),
    "logo@2x.png": height(logo, 256),
    "dark_logo.png": height(dark, 128),
    "dark_logo@2x.png": height(dark, 256),
}
for name, img in outputs.items():
    img.save(f"{dst}/{name}", optimize=True)
    print(name, img.size)
