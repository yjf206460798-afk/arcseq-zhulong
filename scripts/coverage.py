"""剖视填充度（复刻标准的硬指标）：在 K1 的机身轮廓内，模型非背景像素占比 ÷ 参考图同区域占比 ≥ 80%。

    python3 scripts/coverage.py <交审目录> [k1-cut-A k1-cut-B …]

输入是 overlay.mjs 的产物（REFERENCE-k1-cut.png 与 AFTER-<名>.png，同一裁剪框、已对齐到 K1 像素）。
掩膜：K1 自己的上下蒙皮线（blender/zl/interior.py 的 K1_TOP / K1_BOT）围成的机身轮廓，x 从机头尖到机头段末端（s 7.6）；
非背景：亮度比该图机身外背景的中位数高 14 级以上（0～255）。输出每张的占比、比值，以及一张掩膜可视化 COVERAGE-<名>.png。
"""
import ast
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1]
names = sys.argv[2:] or ["k1-cut-A", "k1-cut-B"]
src = open(os.path.join(ROOT, "blender", "zl", "interior.py"), encoding="utf8").read()
TOP = ast.literal_eval(re.search(r"K1_TOP = (\[.*?\])\n", src).group(1))
BOT = ast.literal_eval(re.search(r"K1_BOT = (\[.*?\])\n", src).group(1))
spec = json.load(open(os.path.join(OUT, "overlay-spec.json")))
crop = next(s for s in spec if s["refName"] == "k1-cut")["crop"]
X_END = 1696  # s 7.6（眼心 (97, 449)、220 px/m）


def mask_for(size):
    x0, y0 = crop[0], crop[1]
    poly = [(x - x0, y - y0) for x, y in TOP if x <= X_END] + [(X_END - x0, np.interp(X_END, *zip(*BOT)) - y0)] + [(x - x0, y - y0) for x, y in reversed(BOT) if x <= X_END]
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    return np.asarray(m) > 0


def share(path, mask):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    L = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]
    bg = float(np.median(L[~mask]))
    hit = (L > bg + 14) & mask
    return hit.sum() / mask.sum(), hit, bg


ref_path = os.path.join(OUT, "REFERENCE-k1-cut.png")
size = Image.open(ref_path).size
mask = mask_for(size)
ref_share, ref_hit, ref_bg = share(ref_path, mask)
lines = [f"K1 参考：机身轮廓内非背景 {ref_share:.1%}（背景亮度 {ref_bg:.0f}）"]
vis = []
for n in names:
    p = os.path.join(OUT, f"AFTER-{n}.png")
    if not os.path.exists(p):
        continue
    sh, hit, bg = share(p, mask)
    lines.append(f"{n}：{sh:.1%}（背景 {bg:.0f}）→ 比值 {sh / ref_share:.0%}（指标 ≥ 80%）")
    v = np.zeros(size[::-1] + (3,), np.uint8)
    v[mask] = (40, 40, 48)
    v[hit] = (220, 220, 220)
    v[ref_hit & ~hit] = (200, 60, 50)  # 参考图有、模型没有
    Image.fromarray(v).save(os.path.join(OUT, f"COVERAGE-{n}.png"))
open(os.path.join(OUT, "COVERAGE.txt"), "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
