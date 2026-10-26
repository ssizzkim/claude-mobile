# 「은행·홈택스」 앱 아이콘: 검은 바다에 물결이 치는 일러스트(둥근 사각형).
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 1024
rng = np.random.default_rng(7)
y, x = np.mgrid[0:S, 0:S].astype(np.float32) / S

# 물결 높이장: 물마루가 뾰족한 너울(ridged) 여러 겹 + 잔물결, 살짝 휘게
def waves(n, fmin, fmax, amp0, seed, ridged):
    r = np.random.default_rng(seed)
    out = np.zeros((S, S), np.float32)
    for _ in range(n):
        ang = np.pi / 2 + r.uniform(-0.22, 0.22)
        f = r.uniform(fmin, fmax)
        ph = r.uniform(0, 2 * np.pi)
        u = xw * np.cos(ang) + yw * np.sin(ang)
        w = np.sin(2 * np.pi * f * u + ph)
        if ridged:
            w = (1 - np.abs(w)) ** 2.5 * 2 - 1          # 뾰족한 물마루, 넓은 골
        out += amp0 * r.uniform(0.6, 1.0) * w
    return out

warp = (np.sin(2 * np.pi * (1.1 * x + 0.5 * y)) * 0.025
        + np.sin(2 * np.pi * (2.7 * x - 0.9 * y) + 1.0) * 0.012)
yp = y ** 1.5                                          # 원근: 위(먼 바다)일수록 촘촘
xw, yw = x + warp, yp + warp
h = waves(5, 3.0, 5.0, 1.0, 11, True) + waves(7, 9, 15, 0.3, 12, False) + waves(10, 22, 40, 0.07, 13, False)

gy, gx = np.gradient(h)
light = -(0.25 * gx + 1.0 * gy)                        # 먼 쪽(위)에서 오는 빛
light = light / (np.percentile(np.abs(light), 99.5) + 1e-6)
hn = (h - h.min()) / (h.max() - h.min())
crest = np.clip((hn - 0.72) / 0.28, 0, 1) ** 1.6      # 부서지는 물마루
near = 0.35 + 0.65 * y
val = 1.25 * (6 + near * (30 + 52 * np.tanh(1.8 * light)) + 175 * crest * near * np.clip(0.4 + light, 0, 1))
val = np.clip(val, 0, 255)

rgb = np.stack([val * 0.9, val * 0.95, val * 1.02], -1).clip(0, 255).astype(np.uint8)
sea = Image.fromarray(rgb, "RGB").filter(ImageFilter.GaussianBlur(0.7))

# 둥근 사각형으로 자르고 그림자
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(sh).rounded_rectangle((100, 120, 924, 944), 190, fill=(0, 0, 0, 120))
img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle((100, 100, 924, 924), 190, fill=255)
img.paste(sea.convert("RGBA"), (0, 0), mask)

out = Path(sys.argv[1] if len(sys.argv) > 1 else "icon.png")
img.save(out)
print(out)
