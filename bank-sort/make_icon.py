# 「은행·홈택스」 앱 아이콘: 남색 바탕에 흰 은행 건물, 노란 세금계산서 한 장.
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
# 은행 건물(왼쪽 위)
d.polygon([(210, 400), (470, 250), (730, 400)], fill=W)           # 지붕
d.rectangle((230, 410, 710, 445), fill=W)                         # 처마
for x in (265, 365, 465, 565, 665):                               # 기둥
    d.rectangle((x - 22, 465, x + 22, 690), fill=W)
d.rectangle((215, 705, 725, 750), fill=W)                         # 기단
# 세금계산서(오른쪽 아래, 노란 종이)
paper = Image.new("RGBA", (S, S), (0, 0, 0, 0))
pd = ImageDraw.Draw(paper)
pd.rounded_rectangle((560, 520, 840, 860), 26, fill=(255, 210, 70, 255), outline=(255, 255, 255, 255), width=14)
for y in (600, 660, 720):
    pd.rounded_rectangle((610, y, 790, y + 22), 11, fill=(120, 80, 0, 255))
pd.rounded_rectangle((610, 780, 720, 802), 11, fill=(120, 80, 0, 255))
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle((572, 540, 852, 880), 26, fill=(0, 0, 0, 120))
img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
img.alpha_composite(paper)

out = Path(sys.argv[1] if len(sys.argv) > 1 else "icon.png")
img.save(out)
print(out)
