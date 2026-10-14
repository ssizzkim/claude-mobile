# 자동화 타일 아이콘 — 토르크 관리 앱과 같은 토르크 블루 바탕에 흰 그림, 그림자·그라데이션 없는 평면.
# 새 기능은 여기에 그림 함수를 하나 더하고 공사관리.html TOOL_TILES 끝에 한 줄 더한다.
import math
import sys
from PIL import Image, ImageDraw

S = 1024
BLUE = (38, 42, 174, 255)          # #262AAE 토르크 블루
W = (255, 255, 255, 255)
LW = 44                             # 선 굵기


def tile():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((24, 24, S - 24, S - 24), 230, fill=BLUE)
    return img, d


def bank():
    img, d = tile()
    d.polygon([(512, 230), (232, 400), (792, 400)], fill=W)            # 지붕
    for x in (322, 442, 582, 702):                                     # 기둥 4개
        d.rectangle((x - 26, 440, x + 26, 680), fill=W)
    d.rectangle((222, 712, 802, 762), fill=W)                          # 바닥
    return img


def hometax():
    img, d = tile()
    d.rounded_rectangle((300, 210, 724, 814), 40, outline=W, width=LW)  # 문서
    for y in (370, 470, 570):
        d.line((390, y, 634, y), fill=W, width=LW)
    d.line((390, 670, 520, 670), fill=W, width=LW)
    return img


def gmail():
    img, d = tile()
    d.rounded_rectangle((260, 330, 764, 694), 36, outline=W, width=LW)  # 봉투
    d.line((278, 352, 512, 530), fill=W, width=LW)
    d.line((746, 352, 512, 530), fill=W, width=LW)
    cx, cy, r = 512, 512, 380                                           # 둘러싼 순환 화살표 2개
    for a0 in (200, 20):
        d.arc((cx - r, cy - r, cx + r, cy + r), a0, a0 + 130, fill=W, width=30)
        t = math.radians(a0 + 130)
        tip = (cx + r * math.cos(t), cy + r * math.sin(t))
        ang = t + math.pi / 2
        n = ang + math.pi / 2
        p1 = (tip[0] + 58 * math.cos(ang), tip[1] + 58 * math.sin(ang))
        p2 = (tip[0] + 44 * math.cos(n), tip[1] + 44 * math.sin(n))
        p3 = (tip[0] - 44 * math.cos(n), tip[1] - 44 * math.sin(n))
        d.polygon([p1, p2, p3], fill=W)
    return img


def daily():
    img, d = tile()
    d.rounded_rectangle((220, 260, 640, 560), 70, outline=W, width=LW)  # 말풍선 1
    d.polygon([(300, 540), (270, 650), (390, 556)], fill=W)
    d.rounded_rectangle((470, 470, 804, 720), 60, fill=W)               # 말풍선 2(채움)
    d.polygon([(720, 700), (760, 800), (640, 712)], fill=W)
    for x in (560, 637, 714):                                           # 점 세 개
        d.ellipse((x - 22, 573, x + 22, 617), fill=BLUE)
    return img


size = int(sys.argv[1]) if len(sys.argv) > 1 else 96
for name, fn in (("tile_bank", bank), ("tile_hometax", hometax), ("tile_gmail", gmail), ("tile_daily", daily)):
    fn().resize((size, size), Image.LANCZOS).save(f"{name}.png")
    print(f"{name}.png")
