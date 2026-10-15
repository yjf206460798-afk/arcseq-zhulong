"""静态版式样图（docs/PAGE_LAYOUT.md，Z2）：python3 scripts/layout-sample.py <样图目录>

目录里放 layout.html；本脚本从当前构建（dist/index.html = B、dist/drawing.html = A）截出它要的图：
  img/hero.png       中栏模型（B，方位 30°）+ callouts.js（五个编号引线的地标点在图上的像素位置，__arcseq.project 量）
  img/t-*.png        右栏三视图（A 图纸模式的正交侧 / 正 / 顶视，裁到模型外廓）
  img/v-*.png        左栏视图按钮的小缩略图
  img/d-*.png        右栏特写入口（驾驶舱、化剑关节、鳞片瓦）
再用 drive.mjs 截桌面（1440×900）与手机（390×844）两张：LAYOUT-desktop.png、LAYOUT-mobile.png。
云端截图前 export CHROME_PATH="$PWD/scripts/chrome.sh"。
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1])
IMG = os.path.join(OUT, "img")
TMP = os.path.join(OUT, ".tmp")
os.makedirs(IMG, exist_ok=True)
os.makedirs(TMP, exist_ok=True)
DRIVE = os.path.join(ROOT, ".claude/skills/anatomy/scripts/drive.mjs")


def drive(page, actions, *extra):
    f = os.path.join(TMP, "actions.json")
    json.dump(actions, open(f, "w"))
    r = subprocess.run(["timeout", "-k", "5", "300", "node", DRIVE, page, "--actions", f, *extra], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(r.stderr or r.stdout)
    return [json.loads(l[6:]) for l in r.stdout.splitlines() if l.startswith("eval: ")]


def shot(page, path, view, pre=None, scale=2):
    acts = [["wait", 500]] + ([["eval", pre]] if pre else []) + [["eval", f"__arcseq.resolution({scale})"], ["eval", view], ["wait", 300], ["shot", path, ".af-stage", scale]]
    drive(os.path.join(ROOT, page), acts, "--height", "1000")


def autocrop(src, dst, pad=12, bg_tol=10, width=None):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im).astype(int)
    bg = np.median(np.concatenate([a[8, :], a[-8, :], a[:, 8], a[:, -8]]), axis=0)
    m = np.abs(a - bg).max(-1) > bg_tol
    m[:, :6] = m[:, -6:] = False
    m[:6, :] = m[-6:, :] = False
    ys, xs = np.nonzero(m)
    box = (max(xs.min() - pad, 0), max(ys.min() - pad, 0), min(xs.max() + pad, im.width), min(ys.max() + pad, im.height))
    im = im.crop(box)
    if width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dst)


B, A = "dist/index.html", "dist/drawing.html"
# 中栏：B 方位 30°；五个编号引线挂在地标点上（模型坐标，x = 9.5 − s）
pts = {"烛光窗（眼）": [9.17, 0, 1.66], "眉骨与座舱": [3.6, 0, 2.9], "烛心": [-4.6, 0, 2.88], "化剑关节": [-0.16, 1.4, 2.2], "喷口与塞锥": [-8.6, 0.0, 1.9]}
hero = os.path.join(IMG, "hero.png")
acts = [["wait", 500], ["eval", "__arcseq.resolution(2)"], ["eval", "__arcseq.view(30, 'lines')"], ["wait", 300],
        ["eval", f"JSON.stringify({json.dumps(list(pts.values()))}.map((p) => __arcseq.project(p)))"], ["shot", hero, ".af-stage", 2]]
proj = json.loads(drive(os.path.join(ROOT, B), acts, "--height", "1000")[-1])
W, H = Image.open(hero).size
offsets = [(-260, -120), (-200, -170), (120, -190), (220, 120), (150, 140)]
callouts = []
for (name, _), (x, y), (dx, dy) in zip(pts.items(), proj, offsets):
    X, Y = x * 2, y * 2
    callouts.append({"text": name, "at": [round(X), round(Y)], "label": [round(X + dx), round(Y + dy)]})
open(os.path.join(OUT, "callouts.js"), "w").write(f"window.HERO_SIZE = [{W}, {H}];\nwindow.CALLOUTS = {json.dumps(callouts, ensure_ascii=False)};\n")
# 右栏三视图（A）与左栏视图按钮
for name, view in (("side", "__arcseq.view(90, 'lines', 0)"), ("front", "__arcseq.view(0, 'lines', 0)"), ("top", "__arcseq.view(90, 'lines', 90)"), ("iso", "__arcseq.view(30, 'lines', 30)")):
    raw = os.path.join(TMP, f"{name}.png")
    shot(A, raw, view)
    if name != "iso":
        autocrop(raw, os.path.join(IMG, f"t-{name}.png"), width=560)
    autocrop(raw, os.path.join(IMG, f"v-{name}.png"), width=120)
# 特写入口
shot(B, os.path.join(TMP, "hub.png"), "__arcseq.view(40, 'lines', 35);__arcseq.focus('wing.pivot.l', 5)", pre="__arcseq.set('sword', 0.5)")
for name, src in (("cockpit", "review/20261015-Z1-replica4/CLOSE-B-lines-az090-4x-cockpit-cut.png"), ("scales", "review/20261015-Z1-replica4/CLOSE-B-lines-az060-4x-details.png"), ("hub", os.path.join(TMP, "hub.png"))):
    im = Image.open(os.path.join(ROOT, src)).convert("RGB")
    w, h = im.size
    im = im.crop((int(w * 0.2), int(h * 0.25), int(w * 0.8), int(h * 0.75))).resize((320, round(320 * 0.5 * h / (0.6 * w))), Image.LANCZOS)
    im.save(os.path.join(IMG, f"d-{name}.png"))
# 桌面与手机两张
page = os.path.join(OUT, "layout.html")
drive(page, [["wait", 800], ["shot", os.path.join(OUT, "LAYOUT-desktop.png"), ".sheet", 1]], "--width", "1440", "--height", "900")
drive(page, [["wait", 800], ["shot", os.path.join(OUT, "LAYOUT-mobile.png"), ".sheet", 2]], "--width", "390", "--height", "844")
print("ok", callouts)
