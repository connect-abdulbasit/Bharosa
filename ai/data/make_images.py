"""Deterministic synthetic ID-card-like photos for tests and for calibrating read_document's blur check.

Everything is fake: invented name, fake CNIC (starts 00000), noise instead of a face. Same arguments give the same bytes.
Usage:  from make_images import make_card;  jpeg = make_card(seed=1, blur=2.0)
"""
import io
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FAKE_LINES = ["IDENTITY CARD (FAKE)", "Name", "Muhammad Aslam", "Father Name", "Abdul Rehman", "CNIC", "00000-4210100-1",
              "Date of Birth", "01.01.1980", "Sahara Relief Programme"]


def _font(size):
    try:
        return ImageFont.load_default(size=size)  # Pillow 10.1+
    except TypeError:
        return ImageFont.load_default()


def make_cnic_card(seed=1, width=1100, height=700, name="Muhammad Aslam", father="Abdul Rehman", cnic="00000-4210100-1",
                   dob="12.03.1984", gender="M", blur=0.0, quality=92, specimen=False):
    """A fake CNIC-like card laid out for OCR: label above value, large type, a noise block instead of a face. Everything is invented
    (the number starts 00000). Same arguments give the same bytes."""
    rng = random.Random(seed)
    img = Image.new("L", (width, height), 238)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, width - 11, height - 11], outline=60, width=4)
    draw.rectangle([10, 10, width - 11, 110], fill=55)
    draw.text((40, 28), "IDENTITY CARD (FAKE)", fill=245, font=_font(52))
    pw, ph = int(width * 0.24), int(height * 0.42)
    if specimen:  # a plain frame instead of the noise block: noise next to the text only confuses OCR
        draw.rectangle([width - pw - 50, 150, width - 50, 150 + ph], outline=90, width=3)
    else:
        img.paste(Image.frombytes("L", (pw, ph), bytes(rng.randrange(70, 190) for _ in range(pw * ph))), (width - pw - 50, 150))
    label, value = _font(30), _font(46)
    y = 140
    for lab, val in (("Name", name), ("Father Name", father), ("Gender", gender), ("Identity Number", cnic), ("Date of Birth", dob)):
        draw.text((50, y), lab, fill=50 if specimen else 90, font=label)
        draw.text((50, y + 34), val, fill=15, font=value)
        y += 108
    if specimen:  # unmistakably not a real document: SPECIMEN across the card (kept clear of the text lines)
        draw.text((width - 420, height - 90), "SPECIMEN", fill=120, font=_font(60))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality)
    return out.getvalue()


def make_card(seed=1, width=1024, height=646, blur=0.0, brightness=1.0, contrast=1.0, quality=90, rotate=0):
    """A card-like JPEG. blur = Gaussian radius in px (0 sharp, ~1.5 soft, 3+ unreadable); brightness/contrast scale the pixels."""
    rng = random.Random(seed)
    img = Image.new("L", (width, height), 225)
    draw = ImageDraw.Draw(img)
    draw.rectangle([8, 8, width - 9, height - 9], outline=40, width=4)
    draw.rectangle([8, 8, width - 9, 90], fill=70)
    font, small = _font(int(height * 0.075)), _font(int(height * 0.055))
    draw.text((30, 20), FAKE_LINES[0], fill=240, font=font)
    pw, ph = int(width * 0.22), int(height * 0.42)
    noise = bytes(rng.randrange(70, 190) for _ in range(pw * ph))
    img.paste(Image.frombytes("L", (pw, ph), noise), (width - pw - 40, 120))
    y = 120
    for i, line in enumerate(FAKE_LINES[1:]):
        draw.text((40 + rng.randrange(0, 6), y), line, fill=30, font=small if i % 2 == 0 else font)
        y += int(height * 0.085)
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if contrast != 1.0 or brightness != 1.0:
        img = img.point(lambda p: max(0, min(255, int(((p - 128) * contrast + 128) * brightness))))
    if rotate:
        img = img.rotate(rotate, expand=True)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality)
    return out.getvalue()


if __name__ == "__main__":  # python ai/data/make_images.py  ->  ai/data/sample_id_specimen.jpg (sharp) and sample_id_specimen_blurry.jpg
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    for name, kw in (("sample_id_specimen.jpg", {}), ("sample_id_specimen_blurry.jpg", {"blur": 6.0})):
        with open(os.path.join(here, name), "wb") as f:
            f.write(make_cnic_card(seed=7, specimen=True, name="Fatima Noor", father="Noor Muhammad", cnic="00000-4210100-2", dob="01.07.1979", gender="F", **kw))
        print("wrote", name)
