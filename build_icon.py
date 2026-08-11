"""Generate the MK Pizza & Ice Bar Windows icon used by the EXE and installer."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
OUT = ASSETS / "mk_pizza.ico"

sizes = [16, 24, 32, 48, 64, 128, 256]
images = []
for size in sizes:
    im = Image.new("RGBA", (size, size), (15, 23, 42, 255))
    d = ImageDraw.Draw(im)
    margin = max(1, size // 12)
    d.rounded_rectangle((margin, margin, size-margin-1, size-margin-1), radius=max(2, size//7), fill=(37, 99, 235, 255))
    # Bold MK mark; use a common Windows font when available, otherwise Pillow default.
    font = None
    for fp in (
        r"C:\\Windows\\Fonts\\segoeuib.ttf",
        r"C:\\Windows\\Fonts\\arialbd.ttf",
    ):
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, max(8, int(size * 0.43)))
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()
    text = "MK"
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2]-box[0], box[3]-box[1]
    d.text(((size-tw)/2, (size-th)/2-box[1]), text, fill="white", font=font)
    images.append(im)

images[0].save(OUT, format="ICO", sizes=[(s, s) for s in sizes], append_images=images[1:])
print(f"Created {OUT}")
