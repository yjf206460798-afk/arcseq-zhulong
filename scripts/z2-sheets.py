"""Z2 交审拼图：python3 scripts/z2-sheets.py <交审目录>（scripts/z2-review.sh 的产物）。

  AB-c2-* / AB-c3-*      参考图 + A + B 同机位并排（大气形态对 C2，剑形态对 C3）
  OVERLAY-c2-* / c3-*    50% 叠图（A、B）
  BA-orbit               上一轮 → 本轮（B，固定四机位）
  FORMS-top / -oblique   两种形态并排（正交俯视 / 3/4 斜视）
  POSES-top / -oblique   化剑逐姿态（控件值 0 → 1）
  THUMB-forms            300 px 缩略图：大气形态 / 剑形态（A、B）
"""
import glob
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
FONT = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 26)
BG = (24, 28, 31)


def load(name):
    p = os.path.join(OUT, name)
    return Image.open(p).convert("RGB") if os.path.exists(p) else None


def labelled(im, text, width=None):
    if im is None:
        return None
    if width and im.width != width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    out = Image.new("RGB", (im.width, im.height + 40), BG)
    out.paste(im, (0, 40))
    ImageDraw.Draw(out).text((10, 6), text, fill=(220, 233, 235), font=FONT)
    return out


def stack(ims, vertical=True, gap=8):
    ims = [i for i in ims if i is not None]
    if not ims:
        return None
    if vertical:
        out = Image.new("RGB", (max(i.width for i in ims), sum(i.height for i in ims) + gap * (len(ims) - 1)), BG)
        y = 0
        for i in ims:
            out.paste(i, (0, y))
            y += i.height + gap
    else:
        out = Image.new("RGB", (sum(i.width for i in ims) + gap * (len(ims) - 1), max(i.height for i in ims)), BG)
        x = 0
        for i in ims:
            out.paste(i, (x, 0))
            x += i.width + gap
    return out


def grid(ims, cols):
    rows = [stack(ims[i:i + cols], vertical=False) for i in range(0, len(ims), cols)]
    return stack(rows)


def save(im, name, max_w=2400):
    if im is None:
        return
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(os.path.join(OUT, name), optimize=True)
    print("wrote", name, im.size)


VIEWS = {"top": "俯视", "side": "侧视", "front": "前视"}
for ref, form in (("c2", "C2 大气形态"), ("c3", "C3 剑形态")):
    for v, t in VIEWS.items():
        n = f"{ref}-{v}"
        vertical = v != "front"
        save(stack([labelled(load(f"REFERENCE-{n}.png"), f"REFERENCE · {form} {t}"), labelled(load(f"AFTER-{n}-A.png"), "A · 图纸模式"), labelled(load(f"AFTER-{n}-B.png"), "B · 金属质感（默认）")], vertical), f"AB-{n}.png")
        save(stack([labelled(load(f"OVERLAY-{n}-A.png"), f"50% 叠图 · A · {form} {t}"), labelled(load(f"OVERLAY-{n}-B.png"), "50% 叠图 · B")], vertical), f"OVERLAY-{n}.png")
# 上一轮 → 本轮（B）
rows = []
for d in ("030", "120", "210", "300"):
    rows.append(stack([labelled(load(f"BEFORE-B-lines-az{d}.png"), f"BEFORE · 方位 {d}°", 1100), labelled(load(f"AFTER-B-lines-az{d}.png"), f"AFTER（B）· 方位 {d}°", 1100)], vertical=False))
save(stack(rows), "BA-orbit.png")
# 剑形态四机位
rows = []
for d in ("030", "120", "210", "300"):
    rows.append(stack([labelled(load(f"AFTER-B-lines-az{d}.png"), f"大气形态 · 方位 {d}°", 1100), labelled(load(f"SWORD-B-lines-az{d}.png"), f"剑形态 · 方位 {d}°", 1100)], vertical=False))
save(stack(rows), "FORMS-orbit.png")


# 化剑逐姿态
def poses(kind):
    out = []
    for p in sorted(glob.glob(os.path.join(OUT, f"POSE-{kind}-*-lines-*.png")), key=lambda p: float(re.search(rf"POSE-{kind}-([0-9.]+)-", p).group(1))):
        t = float(re.search(rf"POSE-{kind}-([0-9.]+)-", p).group(1))
        out.append((t, Image.open(p).convert("RGB")))
    return out


for kind, label in (("top", "正交俯视"), ("oblique", "3/4 斜视")):
    ps = poses(kind)
    if ps:
        save(grid([labelled(im, f"化剑 {t:.2f} · {label}", 800) for t, im in ps], 3), f"POSES-{kind}.png")
        save(stack([labelled(ps[0][1], f"大气形态 · {label}", 1200), labelled(ps[-1][1], f"剑形态 · {label}", 1200)], vertical=False), f"FORMS-{kind}.png")
thumbs = []
for name, t in (("THUMB-atmo-A-lines-thumb300-az030.png", "大气 · A"), ("THUMB-atmo-B-lines-thumb300-az030.png", "大气 · B"), ("THUMB-sword-A-lines-thumb300-az030.png", "剑 · A"), ("THUMB-sword-B-lines-thumb300-az030.png", "剑 · B")):
    thumbs.append(labelled(load(name), t))
save(stack(thumbs, vertical=False), "THUMB-forms.png")
