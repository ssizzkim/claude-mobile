# 버튼 타일 아이콘(같은 모양의 둥근 사각형 + 흰 그림). 새 기능은 여기에 그림을 하나 더하고 buttons.py TILES 에 한 줄 더한다.
import sys
from PIL import Image, ImageDraw, ImageFont

S = 512


def base(color):
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((16, 16, S - 16, S - 16), 110, fill=color)
    return img


def bank():
    img = base((38, 84, 140, 255)); d = ImageDraw.Draw(img); W = "white"
    d.polygon([(116, 210), (256, 128), (396, 210)], fill=W)
    d.rectangle((126, 216, 386, 236), fill=W)
    for x in (154, 205, 256, 307, 358):
        d.rectangle((x - 13, 248, x + 13, 362), fill=W)
    d.rectangle((110, 372, 402, 396), fill=W)
    return img


def invoice():
    img = base((214, 150, 30, 255)); d = ImageDraw.Draw(img)
    d.rounded_rectangle((146, 106, 366, 406), 22, fill="white")
    for y in (170, 220, 270):
        d.rounded_rectangle((182, y, 330, y + 18), 9, fill=(214, 150, 30, 255))
    d.rounded_rectangle((182, 320, 270, 338), 9, fill=(214, 150, 30, 255))
    return img


def recycle():
    img = base((46, 160, 90, 255)); d = ImageDraw.Draw(img)
    font = ImageFont.truetype("/System/Library/Fonts/Apple Symbols.ttf", 360)
    d.text((S / 2, S / 2 + 26), "♻", font=font, fill="white", anchor="mm")
    return img


size = int(sys.argv[1]) if len(sys.argv) > 1 else 96
for name, fn in (("tile_bank", bank), ("tile_hometax", invoice), ("tile_gmail", recycle)):
    fn().resize((size, size), Image.LANCZOS).save(f"{name}.png")
    print(f"{name}.png")
