# Rebuild contact-sheet.png from svg/*.svg: `env -u VIRTUAL_ENV uv run --with pillow python build.py` (needs rsvg-convert on PATH)
import io
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
COLUMNS = 5
BACKGROUND = (244, 246, 250, 255)
INK = (26, 32, 51, 255)


def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def render(svg: Path, size: int) -> Image.Image:
    png = subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), str(svg)], capture_output=True, check=True
    ).stdout
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main() -> None:
    svgs = sorted((ROOT / "svg").glob("*.svg"))
    rows = -(-len(svgs) // COLUMNS)
    sheet = Image.new("RGBA", (1800, 420 * rows), BACKGROUND)
    draw = ImageDraw.Draw(sheet)
    font = load_font(22)
    for i, svg in enumerate(svgs):
        letter, slug = svg.stem.split("-", 1)
        x, y = 52 + 360 * (i % COLUMNS), 40 + 420 * (i // COLUMNS)
        sheet.alpha_composite(render(svg, 256), (x, y))
        sheet.alpha_composite(render(svg, 64), (x + 8, y + 270))
        sheet.alpha_composite(render(svg, 32), (x + 96, y + 286))
        sheet.alpha_composite(render(svg, 16), (x + 152, y + 294))
        draw.text((x + 8, y + 346), f"{letter} · {slug.replace('-', ' ')}", font=font, fill=INK)
        png = ROOT / "png" / f"{svg.stem}-512.png"
        if not png.exists():  # a concept's PNG is written once, delete it to render it again
            render(svg, 512).save(png)
    sheet.convert("RGB").save(ROOT / "contact-sheet.png", optimize=True)


if __name__ == "__main__":
    main()
