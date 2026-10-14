# 버튼 타일 아이콘(일러스트풍: 그라데이션 바탕 + 입체 그림 + 부드러운 그림자).
# 새 기능은 여기에 그림 함수를 하나 더하고 buttons.py App.TILES 끝에 한 줄 더한다.
import math
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024                     # 크게 그리고 줄여서 가장자리를 매끄럽게
R = 230                      # 모서리 둥글기


def vgrad(c1, c2, size=(S, S)):
    """위→아래 그라데이션."""
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / (h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(c1, c2)) + (255,))
    return img


def tile(c1, c2):
    """둥근 사각형 바탕(그라데이션 + 위쪽 광택)."""
    bg = vgrad(c1, c2)
    gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(gloss).ellipse((-200, -620, S + 200, 430), fill=(255, 255, 255, 34))
    bg.alpha_composite(gloss.filter(ImageFilter.GaussianBlur(30)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24, 24, S - 24, S - 24), R, fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(bg, (0, 0), mask)
    return out, mask


def shadow_of(layer, offset=(0, 26), blur=26, alpha=110):
    a = layer.split()[3].point(lambda v: v * alpha // 255)
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.paste(sh, offset, sh)
    return out


def place(base, layer, mask, shadow=True):
    if shadow:
        base.alpha_composite(shadow_of(layer))
    base.alpha_composite(layer)
    clip = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    clip.paste(base, (0, 0), mask)
    return clip


# ------------------------------------------------------------------ 신한은행: 저녁 하늘의 은행 건물

def bank():
    base, mask = tile((70, 120, 200), (24, 44, 96))
    d = ImageDraw.Draw(base)
    for x, y, r in ((190, 210, 5), (300, 150, 4), (820, 190, 6), (740, 120, 3), (880, 300, 4)):   # 별
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 200))
    d.ellipse((150, 120, 290, 260), fill=(255, 236, 170, 255))            # 달
    d.ellipse((190, 105, 320, 235), fill=(54, 98, 172, 255))
    b = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(b)
    stone, dark, light = (246, 240, 228), (200, 190, 172), (255, 252, 244)
    bd.polygon([(512, 255), (205, 425), (819, 425)], fill=stone)          # 박공
    bd.polygon([(512, 255), (512, 425), (819, 425)], fill=dark)           # 그늘진 반쪽
    bd.polygon([(512, 315), (300, 405), (724, 405)], fill=(222, 212, 194))
    bd.ellipse((482, 345, 542, 395), fill=(210, 168, 70))                 # 금색 원판
    bd.rectangle((215, 425, 809, 470), fill=light)                        # 처마
    bd.rectangle((215, 455, 809, 470), fill=dark)
    for cx in (275, 393, 512, 631, 749):                                  # 기둥(왼쪽 밝고 오른쪽 그늘)
        bd.rectangle((cx - 34, 488, cx + 34, 720), fill=stone)
        bd.rectangle((cx + 6, 488, cx + 34, 720), fill=dark)
        bd.rectangle((cx - 44, 478, cx + 44, 494), fill=light)
        bd.rectangle((cx - 44, 716, cx + 44, 732), fill=light)
    bd.rectangle((190, 735, 834, 768), fill=light)                        # 계단
    bd.rectangle((160, 768, 864, 801), fill=stone)
    bd.rectangle((130, 801, 894, 834), fill=dark)
    return place(base, b, mask)


# ------------------------------------------------------------------ 홈택스: 겹친 세금계산서 + 도장

def invoice():
    base, mask = tile((255, 196, 84), (226, 120, 30))
    def paper(box, rot):
        p = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        pd = ImageDraw.Draw(p)
        x0, y0, x1, y1 = box
        pd.rounded_rectangle(box, 26, fill=(255, 253, 247))
        pd.polygon([(x1 - 120, y0), (x1, y0 + 120), (x1 - 120, y0 + 120)], fill=(232, 226, 212))   # 접힌 모서리
        pd.polygon([(x1 - 120, y0), (x1, y0), (x1, y0 + 120)], fill=(0, 0, 0, 0))
        pd.rectangle((x0 + 60, y0 + 70, x0 + 300, y0 + 110), fill=(70, 90, 130))                 # 제목
        for i, y in enumerate(range(y0 + 170, y1 - 120, 64)):
            pd.rounded_rectangle((x0 + 60, y, x1 - 60 - (110 if i % 3 == 2 else 0), y + 22), 11, fill=(214, 206, 190))
        pd.rectangle((x0 + 60, y1 - 110, x1 - 60, y1 - 106), fill=(214, 206, 190))
        return p.rotate(rot, resample=Image.BICUBIC, center=(512, 540))
    back = paper((270, 210, 770, 860), 9)
    front = paper((250, 190, 750, 840), -5)
    base = place(base, back, mask)
    base = place(base, front, mask)
    st = Image.new("RGBA", (S, S), (0, 0, 0, 0))                          # 빨간 도장
    sd = ImageDraw.Draw(st)
    sd.ellipse((560, 600, 820, 860), outline=(214, 40, 40, 235), width=26)
    sd.ellipse((600, 640, 780, 820), outline=(214, 40, 40, 200), width=10)
    sd.line((640, 735, 690, 785), fill=(214, 40, 40, 235), width=26)
    sd.line((688, 785, 760, 680), fill=(214, 40, 40, 235), width=26)
    st = st.rotate(-14, resample=Image.BICUBIC, center=(690, 730))
    return place(base, st, mask, shadow=False)


# ------------------------------------------------------------------ 지메일 정리: 재활용 화살표가 둘러싼 봉투

def gmail():
    base, mask = tile((96, 206, 132), (30, 128, 78))
    env = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ed = ImageDraw.Draw(env)
    x0, y0, x1, y1 = 300, 380, 724, 660
    ed.rounded_rectangle((x0, y0, x1, y1), 30, fill=(255, 255, 255))
    ed.polygon([(x0 + 8, y1 - 8), (512, 530), (x1 - 8, y1 - 8)], fill=(232, 238, 236))     # 아래 접힘
    ed.polygon([(x0 + 6, y0 + 10), (512, 560), (x1 - 6, y0 + 10)], fill=(214, 70, 60))     # 붉은 덮개(메일 느낌)
    ed.polygon([(x0 + 40, y0 + 10), (512, 520), (x1 - 40, y0 + 10)], fill=(236, 92, 78))
    base = place(base, env, mask)
    ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))                        # 순환 화살표 3개
    rd = ImageDraw.Draw(ring)
    cx, cy, r, w = 512, 520, 330, 46
    for k in range(3):
        a0 = k * 120 + 18
        a1 = a0 + 84
        rd.arc((cx - r, cy - r, cx + r, cy + r), a0, a1, fill=(255, 255, 255), width=w)
        t = math.radians(a1)
        tip = (cx + r * math.cos(t), cy + r * math.sin(t))
        ang = t + math.pi / 2                                              # 진행 방향
        p1 = (tip[0] + 62 * math.cos(ang), tip[1] + 62 * math.sin(ang))
        n = ang + math.pi / 2
        p2 = (tip[0] + 52 * math.cos(n), tip[1] + 52 * math.sin(n))
        p3 = (tip[0] - 52 * math.cos(n), tip[1] - 52 * math.sin(n))
        rd.polygon([p1, p2, p3], fill=(255, 255, 255))
    return place(base, ring, mask)


# ------------------------------------------------------------------ 오늘 정리: 문자·카톡 말풍선 + 메모

def daily():
    base, mask = tile((168, 120, 240), (96, 56, 184))
    def bubble(box, color, tail, dots):
        b = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        bd = ImageDraw.Draw(b)
        bd.rounded_rectangle(box, 90, fill=color)
        bd.polygon(tail, fill=color)
        x0, y0, x1, y1 = box
        cy = (y0 + y1) // 2
        for i in range(3):
            cx = x0 + (x1 - x0) * (i + 1) // 4
            bd.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=dots)
        return b
    yellow = bubble((150, 230, 600, 470), (254, 229, 0), [(220, 450), (200, 560), (320, 460)], (60, 50, 40))   # 카톡
    green = bubble((420, 470, 874, 710), (110, 220, 120), [(800, 690), (830, 800), (700, 700)], (255, 255, 255))  # 문자
    base = place(base, yellow, mask)
    base = place(base, green, mask)
    note = Image.new("RGBA", (S, S), (0, 0, 0, 0))                       # 정리 메모(체크)
    nd = ImageDraw.Draw(note)
    nd.rounded_rectangle((150, 560, 400, 850), 30, fill=(255, 255, 255))
    for i, y in enumerate((625, 705, 785)):
        nd.line((190, y, 220, y + 25), fill=(120, 80, 210), width=16)
        nd.line((218, y + 25, 262, y - 22), fill=(120, 80, 210), width=16)
        nd.rounded_rectangle((285, y - 6, 365, y + 12), 9, fill=(200, 190, 230))
    return place(base, note, mask)


size = int(sys.argv[1]) if len(sys.argv) > 1 else 96
for name, fn in (("tile_bank", bank), ("tile_hometax", invoice), ("tile_gmail", gmail), ("tile_daily", daily)):
    fn().resize((size, size), Image.LANCZOS).save(f"{name}.png")
    print(f"{name}.png")
