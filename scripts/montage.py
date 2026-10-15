"""交审拼图（PIL）：python3 scripts/montage.py <review 目录>

  ROUTE-three-way.png      Blender→网页 | 代码凸体→网页 | Cycles（同一机位 30°）
  ROUTE-closeups.png       两条网页路线的 4× 特写（眉骨与座舱、鳞片样片）上下对照
  QA-*.png                 四项质感的关 / 开对照
  THUMB-feed.png           三张目标帧缩到手机信息流卡片尺寸（300 px 宽），并排；下面一行是 1:1 放大看清不清楚
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

D = sys.argv[1]
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
BG = (16, 21, 24)
INK = (159, 176, 182)


def load(name):
    return Image.open(os.path.join(D, name)).convert("RGB")


def fit(im, w):
    return im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)


def labelled(ims, labels, w=760, gap=12, cols=None, size=18):
    cols = cols or len(ims)
    ims = [fit(i, w) for i in ims]
    h = max(i.height for i in ims)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w + (cols + 1) * gap, rows * (h + 34) + (rows + 1) * gap), BG)
    font = ImageFont.truetype(FONT, size)
    d = ImageDraw.Draw(sheet)
    for k, (im, lab) in enumerate(zip(ims, labels)):
        x = gap + (k % cols) * (w + gap)
        y = gap + (k // cols) * (h + 34 + gap)
        d.text((x, y), lab, fill=INK, font=font)
        sheet.paste(im, (x, y + 30))
    return sheet


def save(sheet, name):
    sheet.save(os.path.join(D, name), optimize=True)
    print("wrote", name)


save(labelled([load("ROUTE-glb-lines-az030.png"), load("ROUTE-hull-lines-az030.png"), load("CYCLES-hero-az030.png")], ["① Blender 脚本 → GLB → 网页引擎", "② 代码凸体（FIG.01 做法）→ 网页引擎", "③ 同一 Blender 源 → Cycles 渲染"], w=620), "ROUTE-three-way.png")
save(labelled([load("ROUTE-glb-lines-az030-brow4x.png"), load("ROUTE-hull-lines-az030-brow4x.png"), load("ROUTE-glb-lines-az075-belly4x.png"), load("ROUTE-hull-lines-az075-belly4x.png")], ["① Blender：眉骨并进机身（布尔），AO、铆钉、涂装", "② 凸体：眉骨贴面坐落，无 AO / 贴图", "① Blender：鳞片样片 + 其余机腹的贴图鳞片缝", "② 凸体：鳞片样片（每片一个凸包），机腹无细节"], w=620, cols=2), "ROUTE-closeups.png")
save(labelled([load("QA-ao-off-volume-az030-canopy3x.png"), load("QA-ao-on-volume-az030-canopy3x.png")], ["AO 关", "AO 开（顶点 AO + 贴图 AO）"], w=620), "QA-ao.png")
save(labelled([load("QA-detail-off-lines-az300-side4x.png"), load("QA-detail-on-lines-az300-side4x.png")], ["细节贴图 关", "细节贴图 开（铆钉、机号、鳞片缝）"], w=620), "QA-detail.png")
save(labelled([load("QA-glow-off-lines-az030.png"), load("QA-glow-on-lines-az030.png")], ["未通电", "通电：只有烛光窗与朱红棱线发光"], w=620), "QA-glow.png")
targets = [("TARGET-1-parked-lines-az030.png", "① 停机全景"), ("TARGET-2-nose.png", "② 机头特写（电影画质）"), ("TARGET-3-orbit-lines-az330.png", "③ 入轨剪影")]
ims = [load(f) for f, _ in targets]
thumbs = [fit(i, 300) for i in ims]
save(labelled(thumbs, [f"{l} · 300 px" for _, l in targets], w=300, size=13), "THUMB-feed.png")
