"""复刻样板交审拼图：A/B 与参考图并排、特写、目标帧与缩略图。python3 scripts/replica-sheets.py <交审目录>"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
FONT = ImageFont.truetype("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 26)
BG = (24, 28, 31)


def load(name):
    p = os.path.join(OUT, name)
    return Image.open(p).convert("RGB") if os.path.exists(p) else None


def labelled(im, text, width=None):
    if im is None:  # EXTERIOR_ONLY=1 时没有剖视 / 驾驶员图
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
        W = max(i.width for i in ims)
        out = Image.new("RGB", (W, sum(i.height for i in ims) + gap * (len(ims) - 1)), BG)
        y = 0
        for i in ims:
            out.paste(i, (0, y))
            y += i.height + gap
    else:
        H = max(i.height for i in ims)
        out = Image.new("RGB", (sum(i.width for i in ims) + gap * (len(ims) - 1), H), BG)
        x = 0
        for i in ims:
            out.paste(i, (x, 0))
            x += i.width + gap
    return out


def save(im, name, max_w=2400):
    if im is None:
        return
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im.save(os.path.join(OUT, name), optimize=True)
    print("wrote", name, im.size)


# A/B 与参考图并排（同一机位、同一取景）
for v, ref, vertical in (("c2-side", "C2 侧视", True), ("c2-top", "C2 俯视", True), ("c2-front", "C2 前视", False), ("k1-cut", "K1 侧剖", True)):
    rows = [labelled(load(f"REFERENCE-{v}.png"), f"REFERENCE · {ref}"), labelled(load(f"AFTER-{v}-A.png"), "A · 图纸模式（线条 + 五档明暗）"), labelled(load(f"AFTER-{v}-B.png"), "B · 金属质感（默认：PBR + 工作室环境光，线条降一级）")]
    save(stack(rows, vertical), f"AB-{v}.png")
    save(stack([labelled(load(f"OVERLAY-{v}-A.png"), "50% 叠图 · A"), labelled(load(f"OVERLAY-{v}-B.png"), "50% 叠图 · B")], vertical), f"OVERLAY-{v}.png")
# 机头尖三视图放大
rows = []
for v, t in (("c2-tip-top", "俯视"), ("c2-tip-side", "侧视"), ("c2-tip-front", "前视")):
    rows.append(stack([labelled(load(f"REFERENCE-{v}.png"), f"C2 {t}"), labelled(load(f"AFTER-{v}-A.png"), "A"), labelled(load(f"OVERLAY-{v}-A.png"), "50% 叠图")], vertical=False))
save(stack(rows), "AB-c2-tip.png")
# 1× / 4× / 12× 特写
tags = [("az030-1x", "1× 全景"), ("az030-4x-canopy", "4× 座舱与眉骨"), ("az060-4x-rcs", "4× 姿控喷口"), ("az030-12x-eye", "12× 光窗眼珠"), ("az060-12x-roller", "12× 滑轨滚轮座"), ("az060-4x-details", "4× 探头 / 静压孔 / 天线 / 姿控格栅 / 口盖"), ("az030-6x-hatch", "6× 屋面口盖（凹缝 + 紧固件）"), ("az090-4x-cockpit-cut", "4× 剖视座舱"), ("az100-7x-pilot", "7× 驾驶员（銜燭软态）"), ("az060-10x-pilot-front", "10× 头盔与胸前（眉骨、窄面罩、遮光面罩、颈环、「銜燭」）")]
for tag, t in tags:
    save(stack([labelled(load(f"CLOSE-A-lines-{tag}.png"), f"A · {t}", 1200), labelled(load(f"CLOSE-B-lines-{tag}.png"), f"B · {t}", 1200)], vertical=False), f"CLOSE-{tag}.png")
# A/B 3/4 斜视并排（外形通电 / 剖视）
rows = []
for tag, t in (("az030-ext", "3/4 斜视 · 外形（通电）"), ("az060-cut", "3/4 斜视 · 剖视")):
    rows.append(stack([labelled(load(f"OBLIQUE-A-lines-{tag}.png"), f"A · {t}", 1200), labelled(load(f"OBLIQUE-B-lines-{tag}.png"), f"B · {t}", 1200)], vertical=False))
save(stack(rows), "AB-oblique.png")
# 上一轮 → 本轮（B，默认画法）：四机位、斜视、特写、K1 侧剖（BEFORE-* 由 replica-review.sh 从 BEFORE_FROM 拷来）
rows = []
for d in ("030", "120", "210", "300"):
    rows.append(stack([labelled(load(f"BEFORE-lines-az{d}.png"), f"BEFORE · 方位 {d}°", 1100), labelled(load(f"AFTER-B-lines-az{d}.png"), f"AFTER（B）· 方位 {d}°", 1100)], vertical=False))
save(stack(rows), "BA-orbit.png")
pairs = [(f"BEFORE-CLOSE-B-lines-{tag}.png", f"CLOSE-B-lines-{tag}.png", t) for tag, t in tags] + [(f"BEFORE-OBLIQUE-B-lines-{tag}.png", f"OBLIQUE-B-lines-{tag}.png", t) for tag, t in (("az030-ext", "3/4 斜视 · 外形"), ("az060-cut", "3/4 斜视 · 剖视"))]
for a, b, t in pairs + [("BEFORE-AFTER-k1-cut-B.png", "AFTER-k1-cut-B.png", "K1 侧剖")]:
    if load(a) is not None:
        save(stack([labelled(load(a), f"BEFORE · {t}", 1200), labelled(load(b), f"AFTER · {t}", 1200)], vertical=False), "BA-" + b.replace("CLOSE-B-lines-", "").replace("OBLIQUE-B-lines-", "oblique-").replace("AFTER-", ""))
# 目标帧与缩略图
rows = []
for a, b, t in (("TARGET-1-parked-A-lines-az030.png", "TARGET-1-parked-B-lines-az030.png", "① 停机全景"), ("TARGET-2-nose-A.png", "TARGET-2-nose-B.png", "② 机头特写（电影画质）"), ("TARGET-3-orbit-A-lines-az330.png", "TARGET-3-orbit-B-lines-az330.png", "③ 入轨剪影")):
    rows.append(stack([labelled(load(a), f"A · {t}", 1100), labelled(load(b), f"B · {t}", 1100)], vertical=False))
save(stack(rows), "TARGETS.png")
thumbs = []
for name in ("TARGET-1-parked-A-lines-thumb300-az030.png", "TARGET-1-parked-B-lines-thumb300-az030.png", "TARGET-3-orbit-A-lines-thumb300-az330.png", "TARGET-3-orbit-B-lines-thumb300-az330.png"):
    im = load(name)
    if im is not None:
        thumbs.append(im)
save(stack(thumbs, vertical=False), "THUMB-feed.png")
