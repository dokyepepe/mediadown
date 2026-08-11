"""Create deterministic multi-size Windows icons matching assets/app.svg."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw_icon(size: int) -> Image.Image:
    scale = size / 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    def box(values): return tuple(round(value * scale) for value in values)
    draw.rounded_rectangle(box((18, 18, 238, 238)), radius=round(38 * scale), fill="#2E8B57")
    arrow = [(116, 57), (140, 57), (140, 133), (168, 105), (185, 122), (128, 179), (71, 122), (88, 105), (116, 133)]
    draw.polygon([(round(x * scale), round(y * scale)) for x, y in arrow], fill="white")
    draw.rounded_rectangle(box((67, 190, 189, 205)), radius=max(1, round(7.5 * scale)), fill="white")
    play = [(177, 55), (212, 77), (177, 99)]
    draw.polygon([(round(x * scale), round(y * scale)) for x, y in play], fill="#DFF5E9")
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    images = [draw_icon(size) for size in SIZES]
    for size, image in zip(SIZES, images, strict=True):
        image.save(ASSETS / f"app-{size}.png")
    images[-1].save(ASSETS / "app.ico", format="ICO", sizes=[(size, size) for size in SIZES])


if __name__ == "__main__":
    main()

