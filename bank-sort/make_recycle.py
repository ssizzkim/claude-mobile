# 지메일 정리 루틴 버튼용 재활용 마크(초록 원 안에 흰 ♻).
import sys
from PIL import Image, ImageDraw, ImageFont

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse((8, 8, S - 8, S - 8), fill=(46, 160, 90, 255))
for path in ("/System/Library/Fonts/Apple Symbols.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"):
    try:
        font = ImageFont.truetype(path, 190); break
    except OSError:
        font = None
d.text((S / 2, S / 2 + 14), "♻", font=font, fill=(255, 255, 255, 255), anchor="mm")
size = int(sys.argv[2]) if len(sys.argv) > 2 else 64
img.resize((size, size), Image.LANCZOS).save(sys.argv[1] if len(sys.argv) > 1 else "recycle.png")
