"""概念图分色图 → 米制剪影折线（Z2 几何母版的对位依据）。

    .venv/bin/python scripts/silhouettes.py [输出目录]

读 refs/concept/C2、C3 的分色图与 calib.json（分色坐标 → 原图坐标），每个视图：
  ① 按颜色分类（底白、黑描边、灰机身、浅绿主翼、深绿鸭翼 / 前缘条、蓝垂尾与翼尖鳍、深灰喷口与塞锥、青座舱盖、紫眉骨与滑轨、
     红棱线、橙进气 / 背条、黄光窗、棕鳞片区）；
  ② 换成米：C2 沿用 Z1 复刻样板的锚点（俯视 66.0 px/m、侧视 42.42 px/m、前视 46.67 px/m，机头尖为原点），
     C3 用同一机身全长（机头尖 → 塞锥尖）换算——机身在化剑中不变长；
  ③ 外轮廓（全部非底色，补洞后最大连通块）与各颜色区的轮廓，Douglas–Peucker 简化到 0.5 px。
坐标：俯视 (s, y)，s 自机头尖向后、y 向左舷为正（图上方是右舷）；侧视 (s, z)，z 向上、机头尖 z = 1.65（停机姿态）；
前视 (y, z)，y 向左舷为正（前视看向机头，图左是右舷）。
输出 refs/concept/C2_剪影.json、C3_剪影.json 与叠图 <输出目录>/SIL-C2.png、SIL-C3.png（原图上画回折线，核对用）。
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from skimage.measure import approximate_polygon, find_contours

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CON = os.path.join(ROOT, "refs", "concept")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "review", "silhouettes")
Z_TIP = 1.65

# 颜色类：HSV（h 0～360，s、v 0～1）判据
CLASSES = ["outline", "body", "wing", "canard", "tail", "nozzle", "canopy", "brow", "chine", "intake", "eye", "tiles"]


def classify(rgb):
    a = rgb.astype(np.float32) / 255.0
    mx, mn = a.max(-1), a.min(-1)
    v, s = mx, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, (g - b) / d % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    lab = np.full(rgb.shape[:2], -1, np.int16)  # -1 底色
    grey = s < 0.15
    lab[grey & (v < 0.2)] = 0  # outline
    lab[grey & (v >= 0.2) & (v < 0.55)] = 5  # nozzle / cone（深灰）
    lab[grey & (v >= 0.55) & (v < 0.94)] = 1  # body
    col = ~grey
    green = col & (h >= 90) & (h < 160)
    lab[green & (v >= 0.78)] = 2  # 浅绿主翼
    lab[green & (v < 0.78)] = 3  # 深绿：鸭翼、前缘条
    lab[col & (h >= 200) & (h < 235)] = 4  # 蓝：垂尾、翼尖鳍
    lab[col & (h >= 170) & (h < 200)] = 6  # 青：座舱盖
    lab[col & (h >= 260) & (h < 320)] = 7  # 紫：眉骨、滑轨
    lab[col & ((h >= 345) | (h < 12)) & (s > 0.5)] = 8  # 红棱线
    lab[col & (h >= 22) & (h < 45) & (v > 0.7) & (s > 0.5)] = 9  # 橙：进气、背条
    lab[col & (h >= 45) & (h < 70) & (s > 0.5)] = 10  # 黄：光窗
    lab[col & (h >= 12) & (h < 40) & (v <= 0.7)] = 11  # 棕：鳞片区
    return lab


def contours(mask, tol=0.5, min_area=30):
    """mask 的外轮廓（补洞后每个连通块一条），像素坐标 (x, y)。"""
    lab, n = ndimage.label(ndimage.binary_fill_holes(mask))
    out = []
    for k in range(1, n + 1):
        m = lab == k
        if m.sum() < min_area:
            continue
        cs = find_contours(np.pad(m, 1).astype(np.float32), 0.5)
        c = max(cs, key=len) - 1  # (row, col)
        c = approximate_polygon(c, tol)
        out.append([(float(x), float(y)) for y, x in c])
    return out


def sheet(name, calib, views, anchors):
    seg = np.asarray(Image.open(os.path.join(CON, calib["image"])).convert("RGB"))
    ref = Image.open(os.path.join(CON, calib["maps_to"])).convert("RGB")
    H, W = ref.height, ref.width
    lab_seg = classify(seg)
    data = {"source": calib["image"], "maps_to": calib["maps_to"], "views": {}}
    draw = ImageDraw.Draw(ref)
    palette = {"silhouette": (255, 60, 60), "wing": (90, 230, 110), "canard": (40, 160, 60), "tail": (60, 150, 255), "nozzle": (200, 200, 200), "canopy": (0, 240, 240), "brow": (180, 90, 220), "intake": (255, 160, 40), "tiles": (170, 110, 70), "eye": (255, 230, 0)}
    for view, (region, dx, dy) in views.items():
        # 分色坐标 → 原图坐标：x_ref = x_seg * sx + bx + dx …（C2 只有 sx；C3 每个视图一个平移）
        sx = calib.get("transform_seg_to_ref", {}).get("sx", 1.0)
        x0, y0, x1, y1 = region
        # 反向取样：每个原图像素回到分色图取类别（正向映射在 sx = 1.0007 时会漏掉一列，留下一道 1 px 的白缝）
        lab = np.full((H, W), -1, np.int16)
        yr, xr = np.mgrid[0:H, 0:W]
        xs = np.round((xr - dx) / sx).astype(int)
        ys = np.round(yr - dy).astype(int)
        ok = (xs >= 0) & (xs < seg.shape[1]) & (ys >= 0) & (ys < seg.shape[0])
        lab[ok] = lab_seg[ys[ok], xs[ok]]
        roi = np.full_like(lab, -1)
        roi[y0:y1, x0:x1] = lab[y0:y1, x0:x1]
        a = anchors[view]
        k, (px, py) = a["k"], a["origin"]

        def to_m(pts, view=view, k=k, px=px, py=py):
            if view == "top":
                return [[round((x - px) / k, 4), round((py - y) / k, 4)] for x, y in pts]  # 图上方 = 右舷 = −y
            if view == "side":
                return [[round((x - px) / k, 4), round(Z_TIP + (py - y) / k, 4)] for x, y in pts]
            return [[round((px - x) / k, 4), round(Z_TIP + (py - y) / k, 4)] for x, y in pts]  # 前视：图左 = 右舷 = −y

        sil = contours(roi >= 0)
        sil = max(sil, key=len) if sil else []
        rec = {"k_px_per_m": k, "origin_px": [px, py], "silhouette": to_m(sil), "classes": {}}
        for nm in ("wing", "canard", "tail", "nozzle", "canopy", "brow", "intake", "eye", "tiles"):
            polys = contours(roi == CLASSES.index(nm), min_area=40)
            if polys:
                rec["classes"][nm] = [to_m(p) for p in polys]
                for p in polys:
                    draw.line(p + p[:1], fill=palette[nm], width=1)
        # 红棱线：像素中心点（不是区域），按 s 排序
        ry, rx = np.nonzero(roi == CLASSES.index("chine"))
        if len(rx):
            pts = sorted(zip(rx.tolist(), ry.tolist()))
            rec["chine_points"] = to_m(pts[:: max(1, len(pts) // 400)])
        nb = (roi >= 0)
        bx = np.nonzero(nb.any(0))[0]
        by = np.nonzero(nb.any(1))[0]
        rec["extent_m"] = {"x_px": [int(bx.min()), int(bx.max())], "y_px": [int(by.min()), int(by.max())]}
        if view == "top":
            rec["extent_m"]["length_m"] = round((bx.max() - px) / k, 3)
            rec["extent_m"]["span_m"] = round((by.max() - by.min()) / k, 3)
        elif view == "side":
            rec["extent_m"]["length_m"] = round((bx.max() - px) / k, 3)
            rec["extent_m"]["z_m"] = [round(Z_TIP + (py - by.max()) / k, 3), round(Z_TIP + (py - by.min()) / k, 3)]
        else:
            rec["extent_m"]["span_m"] = round((bx.max() - bx.min()) / k, 3)
            rec["extent_m"]["z_m"] = [round(Z_TIP + (py - by.max()) / k, 3), round(Z_TIP + (py - by.min()) / k, 3)]
        if sil:
            draw.line(sil + sil[:1], fill=palette["silhouette"], width=2)
        data["views"][view] = rec
    return data, ref


def main():
    os.makedirs(OUT, exist_ok=True)
    c2 = json.load(open(os.path.join(CON, "C2_大气形态三视图_分色.calib.json"), encoding="utf8"))
    c3 = json.load(open(os.path.join(CON, "C3_剑形态三视图_分色.calib.json"), encoding="utf8"))
    # C2：Z1 复刻样板的锚点（scripts/replica-review.sh 叠图同一组）
    a2 = {"top": {"k": 66.0, "origin": (89.0, 390.5)}, "side": {"k": 42.42, "origin": (590.0, 929.5)}, "front": {"k": 46.67, "origin": (297.0, 923.7)}}
    v2 = {v: (r, 0, 0) for v, r in c2["views_px"].items()}
    d2, im2 = sheet("C2", c2, v2, a2)
    # C3：机头尖与塞锥尖按 C2 同一全长换算（全长取 C2 俯视量出的值）
    L = d2["views"]["top"]["extent_m"]["length_m"]
    v3 = {v: (spec["region"], spec["dx"], spec["dy"]) for v, spec in c3["views"].items()}
    a3 = {}
    seg3 = classify(np.asarray(Image.open(os.path.join(CON, c3["image"])).convert("RGB")))
    for v, (region, dx, dy) in v3.items():
        x0, y0, x1, y1 = region
        m = np.zeros(seg3.shape, bool)
        m[max(0, y0 - dy):y1 - dy, max(0, x0 - dx):x1 - dx] = True
        nb = (seg3 >= 0) & m
        xs = np.nonzero(nb.any(0))[0] + dx
        eye = np.nonzero((seg3 == CLASSES.index("eye")) & m)
        ey, ex = (eye[0].mean() + dy, eye[1].mean() + dx) if len(eye[0]) else (None, None)
        ys = np.nonzero(nb.any(1))[0] + dy
        if v == "front":
            # 前视：中线取横向外廓的中点（左右对称；光窗色块的重心偏右 ~0.15 m），高度取光窗中心；
            # 比例按俯视的翼展——C3 前视横向全宽 = 转平垂尾的跨度（俯视量）
            a3[v] = {"k": None, "origin": (float(xs.min() + xs.max()) / 2, ey)}
        elif v == "top":
            k = (xs.max() - xs.min()) / L
            a3[v] = {"k": float(k), "origin": (float(xs.min()), float(ys.min() + ys.max()) / 2)}  # 中线 = 外廓上下中点
        else:
            k = (xs.max() - xs.min()) / L
            a3[v] = {"k": float(k), "origin": (float(xs.min()), float(ey))}
    # 前视比例：取 C3 俯视的横向全宽（剑格）对齐前视全宽
    tmp, _ = sheet("C3", c3, {"top": v3["top"]}, {"top": a3["top"]})
    span_top = tmp["views"]["top"]["extent_m"]["span_m"]
    x0, y0, x1, y1 = v3["front"][0]
    m = np.zeros(seg3.shape, bool)
    m[max(0, y0 - v3["front"][2]):y1 - v3["front"][2], max(0, x0 - v3["front"][1]):x1 - v3["front"][1]] = True
    xs = np.nonzero(((seg3 >= 0) & m).any(0))[0]
    a3["front"]["k"] = float((xs.max() - xs.min()) / span_top)
    d3, im3 = sheet("C3", c3, v3, a3)
    for nm, d, im in (("C2", d2, im2), ("C3", d3, im3)):
        json.dump(d, open(os.path.join(CON, f"{nm}_剪影.json"), "w", encoding="utf8"), ensure_ascii=False, indent=0)
        im.save(os.path.join(OUT, f"SIL-{nm}.png"))
        for v, rec in d["views"].items():
            print(nm, v, "k", round(rec["k_px_per_m"], 3), rec["extent_m"], "classes", {c: len(p) for c, p in rec["classes"].items()})


if __name__ == "__main__":
    main()
