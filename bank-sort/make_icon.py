# 「은행·홈택스」 앱 아이콘: 남색 바탕 가운데 흰 은행 건물.
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
# 그림자
sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle((100, 120, 924, 944), 190, fill=(0, 0, 0, 110))
img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)))
# 바탕(위→아래 남색 그라데이션)
bg = Image.new("RGBA", (S, S))
d = ImageDraw.Draw(bg)
for y in range(S):
    t = y / S
    d.line([(0, y), (S, y)], fill=(int(36 + 10 * t), int(92 - 30 * t), int(150 - 45 * t), 255))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((100, 100, 924, 924), 190, fill=255)
img.paste(bg, (0, 0), mask)

d = ImageDraw.Draw(img)
W = (255, 255, 255, 255)
# 은행 건물(가운데)
d.polygon([(252, 412), (512, 262), (772, 412)], fill=W)           # 지붕
d.rectangle((272, 422, 752, 457), fill=W)                         # 처마
for x in (307, 407, 507, 607, 707):                               # 기둥
    d.rectangle((x + 5 - 22, 477, x + 5 + 22, 702), fill=W)
d.rectangle((257, 717, 767, 762), fill=W)                         # 기단

out = Path(sys.argv[1] if len(sys.argv) > 1 else "icon.png")
img.save(out)
print(out)
