"""Create multi-size Windows icons from the generated master artwork."""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SIZES = [16, 24, 32, 48, 64, 128, 256]
MASTER = ASSETS / "app-master.png"


def load_master() -> Image.Image:
    image = Image.open(MASTER).convert("RGBA")
    # The generated artwork uses a near-black canvas outside its rounded tile.
    # Convert only that neutral edge canvas to transparency, keeping the deep
    # petroleum-green tile intact.
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if max(red, green, blue) <= 18:
                pixels[x, y] = (red, green, blue, 0)
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    master = load_master()
    images = [master.resize((size, size), Image.Resampling.LANCZOS) for size in SIZES]
    for size, image in zip(SIZES, images, strict=True):
        image.save(ASSETS / f"app-{size}.png")
    master.save(ASSETS / "app.ico", format="ICO", sizes=[(size, size) for size in SIZES])


if __name__ == "__main__":
    main()

