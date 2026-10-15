"""K1 分色建模图 → 零件表 + 拆图叠图（docs/WORKFLOW.md「拆图」第 2、3 步）。

    .venv/bin/python scripts/k1-parts.py [交审目录]      # 需要 bpy（取几何母版的截面与现有内部件）、numpy、pillow、scipy、scikit-image

输入：refs/layout/K1_驾驶舱侧剖_分色.png + .calib.json（分色图 → 原图像素，按轴分别缩放）、
      refs/layout/K1_驾驶舱侧剖.calib.json（原图像素 → 机体米制，见那里的说明）。
输出：refs/layout/K1_驾驶舱侧剖.parts.csv（零件表）；交审目录里 PARTS-overlay.png（全部零件叠回原图）、
      PARTS-split.png（八个类别分开）、PARTS-status.png（已建 / 缺），以及终端里的统计。

做法：分色图按色相分八类（灰结构、绿箱体、蓝管线、橙机构、紫座椅与人、青玻璃与屏、黄发光、棕起落架），黑描边把同色零件隔开；
每类找连通块 → 包围盒（管线另做：骨架 → 节点之间的分支 → 折线 + 半径，两端各查接在哪个零件上）；包围盒经 calib 换回原图像素，
再按 interior.py 的 k1 / kg / kc 映射到站位 s、高度 z；长、高按 220 px/m 量（不拉伸）。侧剖缺的 y、宽从俯视小图按站位取同色块的横向范围
（小图另行按三个锚点分段标定，比例不可靠 → 把握度“中”），取不到的按截面内表面推定（“猜”）。
列：长 / 宽 / 高是包围盒（米）；杆、框、梁、管另有“粗”（直径 / 厚）与“路径”（s:z;… 机体米制，杆是两端，管是折线）。
"""
import csv
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi
from skimage.morphology import skeletonize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "blender"))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "review", "20261015-Z1-parts")
os.makedirs(OUT, exist_ok=True)
LAYOUT = os.path.join(ROOT, "refs", "layout")
SEG = os.path.join(LAYOUT, "K1_驾驶舱侧剖_分色.png")
REF = os.path.join(LAYOUT, "K1_驾驶舱侧剖.png")
CSV = os.path.join(LAYOUT, "K1_驾驶舱侧剖.parts.csv")
CAL = json.load(open(os.path.join(LAYOUT, "K1_驾驶舱侧剖_分色.calib.json"), encoding="utf8"))
MET = json.load(open(os.path.join(LAYOUT, "K1_驾驶舱侧剖.calib.json"), encoding="utf8"))
T = CAL["transform_seg_to_ref"]
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

import bpy  # noqa: E402,F401

from zl import interior as I  # noqa: E402
from zl import nose as N  # noqa: E402
from zl.util import XN, reset  # noqa: E402


# —— 分色图 → 类别 ——————————————————————————————————————————————————————
# 类别：编码、名称、默认基本形、默认材质、画图颜色、最小面积（分色图像素）
CATS = {
    2: ("S", "结构", "板", "structure", (205, 205, 205), 0),
    3: ("G", "箱体", "盒", "avionics", (70, 210, 100), 40),
    4: ("B", "管线", "管", "pipe", (60, 150, 255), 30),
    5: ("O", "机构", "柱", "metal", (255, 150, 30), 30),
    6: ("P", "座椅与人", "人体", "suit", (190, 110, 240), 150),
    7: ("C", "玻璃与屏", "板", "glass", (60, 240, 240), 150),
    8: ("Y", "发光", "板", "glow", (255, 235, 40), 40),
    9: ("W", "起落架", "轮", "rubber", (170, 120, 70), 300),
}
MAIN_Y = 720  # 分色图里主剖面在这条线以上，以下是两张小图


def classify(im):
    im = im.astype(np.float32) / 255
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    mx, mn = im.max(-1), im.min(-1)
    d = np.maximum(mx - mn, 1e-6)
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    H = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    c = np.zeros(im.shape[:2], np.uint8)  # 0 白底
    c[(S < 0.18) & (mx <= 0.93) & (mx > 0.45)] = 2
    c[((mx <= 0.45) & (S < 0.35)) | (mx <= 0.25)] = 1  # 1 黑描边
    col = (S >= 0.3) & (mx > 0.25)
    c[col & (H >= 90) & (H < 165)] = 3
    c[col & (H >= 195) & (H < 240)] = 4
    c[col & (H >= 240) & (H < 320)] = 6
    c[col & (H >= 165) & (H < 195)] = 7
    c[col & (H >= 48) & (H < 75)] = 8
    c[col & (H >= 18) & (H < 48) & (mx > 0.75)] = 5
    c[col & (H >= 10) & (H < 48) & (mx <= 0.75)] = 9
    c[col & ((H < 10) | (H >= 320))] = 5
    return c


def seg2ref(x, y):
    return T["sx"] * x + T["bx"], T["sy"] * y + T["by"]


# —— 原图像素 ↔ 机体（与 interior.py 同一套映射） ——————————————————————————————
PX = MET["px_per_m"]
FLOOR = I.K1_FLOOR
COCKPIT_X = MET["zones"]["cockpit_x"]
GEAR_X = MET["zones"]["gear_x"]


def mapper_for(x, y):
    if x >= COCKPIT_X[0] and y < FLOOR + 8:
        return "kc"
    if x >= GEAR_X and y >= FLOOR:
        return "kg"
    return "k1"


MAP = {"k1": I.k1, "kg": I.kg, "kc": I.kc}


def to_body(x, y, m=None):
    m = m or mapper_for(x, y)
    p = MAP[m](x, y)
    return XN - p.x, p.z, m


def from_body(s, z):
    """机体 (s, z) → 原图像素：三种映射各求一遍，取区域规则自洽的那个。"""
    x = I.K1_EYE[0] + (s - N.EYE["s"]) * PX
    t, b = I._interp(I.K1_TOP, x), I._interp(I.K1_BOT, x)
    zk, zt = I.keel(s), N.top_profile(s)
    cands = {
        "k1": b - (z - zk) / max(1e-6, zt - zk) * (b - t),
        "kg": b - (z - zk) / max(1e-6, I.Z_GEAR - zk) * (b - FLOOR),
        "kc": I.K1_EYE[1] - (z - N.Z_TIP - N.EYE["z"] - I.LIFT) * PX,
    }
    for m in ("kc", "kg", "k1"):
        if mapper_for(x, cands[m]) == m:
            return x, cands[m]
    return x, cands["k1"]


# —— 区段（按原图 x）——————————————————————————————————————————————————————
ZONES = [(0, 150, "①光窗"), (150, 345, "②传感器舱"), (345, 511, "③姿控舱"), (511, 700, "④航电前段"), (700, 911, "④航电机柜"), (911, 1090, "⑤⑥眉骨下"), (1090, 1640, "座舱"), (1640, 1800, "座舱后")]


def zone_of(x, y):
    if x >= GEAR_X and y >= FLOOR + 4:
        return "⑭起落架舱" if x < 1460 else "座舱下后舱"
    return next(z for x0, x1, z in ZONES if x0 <= x < x1)


def nearest_frame(s):
    return min(I.FRAME_S, key=lambda f: abs(f - s))


# —— 俯视小图（取 y 与宽）——————————————————————————————————————————————————
TOPV = MET["top_inset"]


def inset_x(x_seg_main):
    """主剖面分色图 x → 俯视小图分色图 x（三个锚点分段线性）。"""
    a = TOPV["anchors_main_inset_seg_x"]
    xs, ys = zip(*a)
    return float(np.interp(x_seg_main, xs, ys, left=None, right=None))


def lateral(cls, k, x0, x1):
    """俯视小图里，主剖面 x0～x1（分色图像素）对应列上类别 k 的横向范围 → (y 中心, 半宽) 以小图当地机身半宽为单位；没有就 None。"""
    box = TOPV["box_seg"]
    yc = TOPV["centerline_seg_y"]
    a, b = int(inset_x(x0)), int(math.ceil(inset_x(x1)))
    a, b = max(a, box[0]), min(b, box[2])
    if b <= a:
        return None
    sub = cls[box[1]:box[3], a:b]
    hit = np.where((sub == k).any(axis=1))[0]
    body = np.where((sub != 0).any(axis=1))[0]
    if len(hit) < 3 or len(body) < 3:
        return None
    half = max(yc - (box[1] + body.min()), (box[1] + body.max()) - yc)
    lo, hi = box[1] + hit.min(), box[1] + hit.max()
    # 小图 y 向下 = 机体右侧（−y）：俯视、机头朝左
    return ((yc - (lo + hi) / 2) / half, (hi - lo) / 2 / half)


def frame_bars(c, min_run=50):
    """分色图里的竖框：两条相距 3～18 px、重叠 ≥ 40 px 的长竖直描边，中间至少 45% 是灰。"""
    cl = ndi.binary_closing(c == 1, structure=np.ones((7, 1)))
    H, W = c.shape
    runs = []
    for x in range(W):
        col = np.concatenate([[0], cl[:, x].astype(np.int8), [0]])
        d = np.diff(col)
        st, en = np.where(d == 1)[0], np.where(d == -1)[0]
        if len(st):
            k = int(np.argmax(en - st))
            runs.append((en[k] - st[k], st[k], en[k]))
        else:
            runs.append((0, 0, 0))
    groups = []
    for x in (x for x in range(W) if runs[x][0] >= min_run):
        if groups and x - groups[-1][-1] <= 2:
            groups[-1].append(x)
        else:
            groups.append([x])
    lines = [(int(np.mean(g)),) + max(runs[i] for i in g)[1:] for g in groups]
    out = []
    for (xa, a0, a1), (xb, b0, b1) in zip(lines, lines[1:]):
        y0, y1 = max(a0, b0), min(a1, b1)
        if 3 <= xb - xa <= 18 and y1 - y0 >= 40 and (c[y0:y1, xa + 1:xb] == 2).mean() >= 0.45:
            out.append((xa, xb + 1, y0, y1))
    return out


def iou_seg(a, b):
    return iou(a, b)


# —— 骨架 → 管线分支 ——————————————————————————————————————————————————————
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def branches(mask):
    sk = skeletonize(mask)
    n = ndi.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode="constant") - 1
    node = sk & (n != 2)
    body = sk & ~node
    lab, nl = ndi.label(body, structure=np.ones((3, 3)))
    out = []
    pts_of = ndi.find_objects(lab)
    for i, sl in enumerate(pts_of, 1):
        ys, xs = np.where(lab[sl] == i)
        ys, xs = ys + sl[0].start, xs + sl[1].start
        P = set(zip(ys.tolist(), xs.tolist()))
        # 找一端（分支内只有一个邻居），沿着走
        def nbrs(p):
            return [(p[0] + dy, p[1] + dx) for dy, dx in NB if (p[0] + dy, p[1] + dx) in P]
        start = next((p for p in P if len(nbrs(p)) <= 1), next(iter(P)))
        path, seen = [start], {start}
        while True:
            nx = [q for q in nbrs(path[-1]) if q not in seen]
            if not nx:
                break
            path.append(nx[0])
            seen.add(nx[0])
        # 两端各外延到相邻的节点像素（让分支接上网络）
        for end in (0, -1):
            p = path[end]
            for dy, dx in NB:
                q = (p[0] + dy, p[1] + dx)
                if 0 <= q[0] < node.shape[0] and 0 <= q[1] < node.shape[1] and node[q]:
                    if end == 0:
                        path.insert(0, q)
                    else:
                        path.append(q)
                    break
        out.append(path)
    return out


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a, b = np.array(pts[0], float), np.array(pts[-1], float)
    ab = b - a
    L = np.hypot(*ab) or 1e-9
    d = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / L for p in pts[1:-1]]
    i = int(np.argmax(d)) + 1
    if d[i - 1] > eps:
        return rdp(pts[: i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [pts[0], pts[-1]]


# —— 现有内部件（几何母版）→ 原图像素框 ————————————————————————————————————
SUFFIX = (".panel", ".bolts", ".bolt", ".label", ".ear", ".plug", ".handle", ".grille", ".nut", ".clip", ".clamps", ".c0", ".c1", ".window", ".lens", ".ring", ".groove", ".foot", ".cap", ".eye0", ".eye1", ".gland", ".rod", ".barrel")


MAT_CAT = {"avionics": "箱体", "tank": "箱体", "panel": "箱体", "interior": "箱体", "pipe": "管线", "cable": "管线", "metal": "机构", "chrome": "机构", "structure": "结构",
           "suit": "座椅与人", "seat": "座椅与人", "helmet": "座椅与人", "glass": "玻璃与屏", "screen": "玻璃与屏", "vermilion": "发光", "rubber": "起落架"}
COMPAT = {"箱体": {"箱体"}, "管线": {"管线"}, "机构": {"机构", "结构"}, "结构": {"结构", "机构"}, "座椅与人": {"座椅与人", "机构", "起落架"}, "玻璃与屏": {"玻璃与屏", "箱体"}, "发光": {"发光", "箱体"}, "起落架": {"起落架", "机构"}}


def existing_parts():
    reset()
    pairs, _ = I.build()
    out = []
    for o, _ in pairs:
        name = o.name
        if name.startswith("int.k1.") or any(t in name[len("int."):] for t in SUFFIX) or name.startswith("int.frame.") or name.startswith("int.stringer") or name.startswith("int.harness.drop"):
            continue
        vs = np.array([tuple(v.co) for v in o.data.vertices])
        s = XN - vs[:, 0]
        if s.min() > N.S_END:
            continue
        sc, zc = (s.min() + s.max()) / 2, (vs[:, 2].min() + vs[:, 2].max()) / 2
        xc, yc = from_body(sc, zc)
        hw, hh = (s.max() - s.min()) * PX / 2, (vs[:, 2].max() - vs[:, 2].min()) * PX / 2
        mat = o.data.materials[0].name if o.data.materials else "interior"
        cat = MAT_CAT.get(mat, "机构")
        if cat == "管线":
            sel = vs[:: max(1, len(vs) // 400)]
            PIPE_PTS.extend((from_body(XN - v[0], v[2]), name) for v in sel)
        out.append((name, (xc - hw, yc - hh, xc + hw, yc + hh), cat))
    return out


PIPE_PTS = []


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def cover(a, b):
    """b 覆盖了 a 的几成。"""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = (a[2] - a[0]) * (a[3] - a[1])
    return ix * iy / area if area > 0 else 0.0


# —— 主流程 ——————————————————————————————————————————————————————————————
def main():
    seg = np.asarray(Image.open(SEG).convert("RGB"))
    cls = classify(seg)
    main_cls = cls.copy()
    main_cls[MAIN_Y:] = 0
    labels = {}
    rows = []
    counter = {}
    known = MET.get("known_errors", [])

    def new_id(code):
        counter[code] = counter.get(code, 0) + 1
        return f"K1-{code}{counter[code]:03d}"

    # 1. 块状零件：每类连通块（4 邻接，黑描边把同色零件隔开）
    for k, (code, cat, shape, mat, _, amin) in CATS.items():
        if k in (2, 4):
            continue
        lab, nl = ndi.label(main_cls == k)
        labels[k] = lab
        for i, sl in enumerate(ndi.find_objects(lab), 1):
            m = lab[sl] == i
            area = int(m.sum())
            if area < amin:
                continue
            ys, xs = np.where(m)
            ys, xs = ys + sl[0].start, xs + sl[1].start
            rows.append({"k": k, "seg": (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1), "area": area, "pts": (xs, ys), "label": i})
    # 结构：灰色连通块里细长的（框、梁、地板）；大片的是内壁 / 蒙皮，不进表
    lab, nl = ndi.label(main_cls == 2)
    labels[2] = lab
    for i, sl in enumerate(ndi.find_objects(lab), 1):
        m = lab[sl] == i
        area = int(m.sum())
        h, w = m.shape
        if area < 60 or area > 9000:
            continue
        if not (h >= 3.5 * w and h >= 30) and not (w >= 4 * h and w >= 50):
            continue
        # 横向的长条碰到白底的是蒙皮带（外轮廓），不进表；竖的是框（框脚贴着蒙皮带，蒙皮带只有几像素厚）
        if w >= 4 * h:
            grow = ndi.binary_dilation(lab[sl] == i, iterations=3)
            box = main_cls[sl]
            if (box[grow] == 0).any():
                continue
        ys, xs = np.where(m)
        ys, xs = ys + sl[0].start, xs + sl[1].start
        rows.append({"k": 2, "seg": (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1), "area": area, "pts": (xs, ys), "label": i})
    # 结构（补）：框常和内壁同色连成一片，按“成对的长竖直描边、中间是灰”再找一遍
    for x0, x1, y0, y1 in frame_bars(main_cls):
        box = (x0, y0, x1, y1)
        if any(r["k"] == 2 and iou_seg(r["seg"], box) > 0.2 for r in rows):
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        rows.append({"k": 2, "seg": box, "area": (x1 - x0) * (y1 - y0), "pts": (xs.ravel(), ys.ravel()), "label": -1})
    # 2. 管线：骨架分支
    blue = main_cls == 4
    labels[4] = ndi.label(blue)[0]
    dt = ndi.distance_transform_edt(blue)
    pipes = []
    for path in branches(blue):
        if len(path) < 10:
            continue
        r = float(np.median([dt[p] for p in path]))
        if r < 1.2:
            continue
        pipes.append((path, r))

    # 每个块状零件：原图像素框、机体坐标、形状
    ex = existing_parts()
    out = []
    for row in rows:
        k = row["k"]
        code, cat, shape, mat, _, _ = CATS[k]
        x0, y0, x1, y1 = row["seg"]
        X0, Y0 = seg2ref(x0, y0)
        X1, Y1 = seg2ref(x1, y1)
        xc, yc = (X0 + X1) / 2, (Y0 + Y1) / 2
        s, z, mp = to_body(xc, yc)
        L, H = (X1 - X0) / PX, (Y1 - Y0) / PX
        xs, ys = row["pts"]
        rec = {"类别": cat, "站位s": s, "z": z, "长L": L, "高H": H, "基本形": shape, "材质": mat, "映射": mp, "box": (X0, Y0, X1, Y1), "k": k, "row": row}
        # 细长件（机构 / 结构）：主轴方向与两端
        P = np.stack([T["sx"] * xs + T["bx"], T["sy"] * ys + T["by"]], 1)
        c = P.mean(0)
        u, sv, vt = np.linalg.svd(P - c, full_matrices=False)
        ax = vt[0]
        proj = (P - c) @ ax
        thick = (P - c) @ vt[1]
        aspect = (proj.max() - proj.min()) / max(1.0, thick.max() - thick.min())
        rec["aspect"] = aspect
        if k in (5, 2) and aspect > 3.5:
            a, b = c + ax * proj.min(), c + ax * proj.max()
            rec["ends"] = (a, b)
            rec["基本形"] = "杆" if k == 5 else ("框" if abs(ax[1]) > abs(ax[0]) else "梁")
            rec["粗"] = (thick.max() - thick.min()) / PX
            ea, eb = to_body(*a), to_body(*b)
            rec["路径"] = f"{ea[0]:.3f}:{ea[1]:.3f};{eb[0]:.3f}:{eb[1]:.3f}"
        elif k == 5:
            rec["基本形"] = "支架"
        elif k == 3:
            # 圆罐：两端是圆头——包围盒四个角（各 12%）几乎没有本色像素，而长边中段是满的
            m = labels[3][y0:y1, x0:x1] == row["label"]
            hh, ww = m.shape
            cy, cx = max(1, int(hh * 0.12)), max(1, int(ww * 0.12))
            corners = np.mean([m[:cy, :cx].mean(), m[:cy, -cx:].mean(), m[-cy:, :cx].mean(), m[-cy:, -cx:].mean()])
            mid = m[:, ww // 2 - cx // 2: ww // 2 + cx // 2 + 1].mean() if ww > hh else m[hh // 2 - cy // 2: hh // 2 + cy // 2 + 1, :].mean()
            rec["基本形"] = "罐" if corners < 0.25 and mid > 0.8 and aspect > 1.3 else "盒"
        out.append(rec)

    # 3. 名字、区段、y / 宽、固定在、现有零件、把握度
    struct = [r for r in out if r["k"] == 2]
    for k_ in ("S", "G", "O", "P", "C", "Y", "W"):
        pass
    for rec in sorted(out, key=lambda r: (list(CATS).index(r["k"]), r["box"][0])):
        k = rec["k"]
        code = CATS[k][0]
        rec["编号"] = new_id(code)
    for rec in out:
        X0, Y0, X1, Y1 = rec["box"]
        xc, yc = (X0 + X1) / 2, (Y0 + Y1) / 2
        rec["区段"] = zone_of(xc, yc)
        k = rec["k"]
        x0, y0, x1, y1 = rec["row"]["seg"]
        lat = lateral(cls, k, x0, x1) if k in (3, 6, 7, 5) else None
        s, z = rec["站位s"], rec["z"]
        hw = max(0.05, I.half_width(s, z, I.SKIN + 0.01))
        if lat and lat[1] > 0.02:
            rec["y"], rec["宽W"], rec["y来源"] = lat[0] * hw, min(2 * hw, 2 * lat[1] * hw), "俯视小图"
        else:
            if k == 2:
                rec["y"], rec["宽W"], rec["y来源"] = 0.0, 2 * hw, "推定（整圈框 / 横梁）"
            elif k in (4, 5):
                rec["y"], rec["宽W"], rec["y来源"] = 0.0, min(2 * hw, 0.06), "猜"
            else:
                rec["y"], rec["宽W"], rec["y来源"] = 0.0, min(2 * hw, max(rec["长L"], rec["高H"]) * 0.9), "推定（截面内表面）"
        # 现有零件：重叠最多的那个（原图像素框）
        best, bv = None, 0.0
        for name, b, c in ex:
            if c not in COMPAT[rec["类别"]]:
                continue
            v = iou(rec["box"], b)
            if v > bv:
                best, bv = name, v
        rec["现有零件"] = best if bv >= 0.2 else "缺"
        rec["重叠"] = bv
        if bv < 0.2:
            # 落在一个更大的现有零件里（座椅上的小机构、箱体上的小盒）：算并入
            area = (X1 - X0) * (Y1 - Y0)
            for name, b, c in ex:
                bw, bh = b[2] - b[0], b[3] - b[1]
                compact = max(bw, bh) <= 4 * max(1.0, min(bw, bh)) and bw * bh <= (0.9 * PX) ** 2  # 细长件（纵梁、线束）的包围盒不算“装在里面”
                if c in COMPAT[rec["类别"]] and compact and bw * bh >= area and cover(rec["box"], b) >= 0.7:
                    rec["现有零件"] = f"并入 {name}"
                    break
        if rec.get("基本形") == "框":
            f = nearest_frame(s)
            rec["现有零件"] = f"int.frame（s {f:.2f}）" if abs(f - s) < 0.07 else "缺"
        if k == 7 and rec["box"][1] < 330:
            rec["现有零件"] = "canopy.glass（外形件）"
        # 固定在：结构件 → 蒙皮；其余 → 碰到的灰色结构块，没有就最近的框
        if k == 2:
            rec["固定在"] = "蒙皮"
        else:
            hits = [r["编号"] for r in struct if r["box"][0] - 6 <= X1 and r["box"][2] + 6 >= X0 and r["box"][1] - 6 <= Y1 and r["box"][3] + 6 >= Y0]
            f = min(I.FRAME_S, key=lambda f: min(abs(f - (s - rec["长L"] / 2)), abs(f - (s + rec["长L"] / 2))))
            rec["固定在"] = (" ".join(hits[:2]) + f" / 框 s{f:.2f}") if hits else f"框 s{f:.2f}（推定，加托架）"
        conf = "高" if rec["row"]["area"] > 300 and k in (3, 6, 7, 9) else "中"
        if rec["y来源"] == "猜":
            conf = "中" if k in (5,) else conf
        for e in known:
            bx = e["ref_box"]
            if k == 5 and cover(bx, rec["box"]) > 0.6:
                rec["备注"] = e["note"]
                conf = "忽略"
        rec["把握度"] = conf
        rec["名称"] = name_of(rec)

    # 管线行
    INDEX.update({(r["k"], r["row"]["label"]): r["编号"] for r in out if r["row"]["label"] >= 0 and r["k"] != 2})
    prow = []
    net_of = labels[4]
    for path, r in pipes:
        P = [(seg2ref(x, y)) for y, x in path]
        simp = rdp([(round(x, 1), round(y, 1)) for x, y in P], 2.0)
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(simp, simp[1:]))
        if L < 16:  # 短于约 7 cm 的是骨架毛刺
            continue
        horiz = abs(simp[-1][0] - simp[0][0]) >= abs(simp[-1][1] - simp[0][1])
        rad = r * (T["sy"] if horiz else T["sx"]) / PX
        body = [to_body(x, y) for x, y in simp]
        xs = [p[0] for p in simp]
        ys = [p[1] for p in simp]
        X0, Y0, X1, Y1 = min(xs), min(ys), max(xs), max(ys)
        # 两端接在什么上：端点周围 7 px（分色图）里非蓝、非底、非描边的类别 → 那个零件
        ends = []
        for y, x in (path[0], path[-1]):
            ends.append(touch(main_cls, labels, out, x, y))
        sc = (body[0][0] + body[-1][0]) / 2
        zc = (body[0][1] + body[-1][1]) / 2
        rec = {"编号": None, "类别": "管线", "基本形": "管", "材质": "cable" if rad > 0.012 else "pipe", "站位s": sc, "z": zc, "长L": L / PX, "高H": (Y1 - Y0) / PX, "宽W": 2 * rad, "y": 0.0,
               "y来源": "猜", "box": (X0, Y0, X1, Y1), "k": 4, "半径": rad, "路径": ";".join(f"{s:.3f}:{z:.3f}" for s, z, _ in body), "固定在": " ↔ ".join(ends), "区段": zone_of((X0 + X1) / 2, (Y0 + Y1) / 2), "现有零件": "", "把握度": "中" if "悬空" not in " ".join(ends) else "猜",
               "网": f"N{int(max(net_of[p] for p in path)):03d}"}
        prow.append(rec)
    prow.sort(key=lambda r: r["box"][0])
    for rec in prow:
        rec["编号"] = new_id("B")
        rec["名称"] = f"{rec['区段']} 管 {rec['编号'][-3:]}"
    # 现有管线：K1 管的路径（每 3 px 取点）有六成以上落在某根现有管 8 px 以内，算已有
    from scipy.spatial import cKDTree

    tree = cKDTree(np.array([p for p, _ in PIPE_PTS]))
    owners = [n for _, n in PIPE_PTS]
    for rec in prow:
        pts = [tuple(map(float, q.split(":"))) for q in rec["路径"].split(";")]
        xy = [from_body(s, z) for s, z in pts]
        dense = []
        for a, b in zip(xy, xy[1:]):
            n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 3))
            dense += [(a[0] + (b[0] - a[0]) * t / n, a[1] + (b[1] - a[1]) * t / n) for t in range(n)]
        d, i = tree.query(np.array(dense))
        near = [owners[j] for dd, j in zip(d, i) if dd < 8]
        if len(near) >= 0.6 * len(dense):
            rec["现有零件"] = max(set(near), key=near.count)
        else:
            rec["现有零件"] = "缺"

    allrows = sorted(out, key=lambda r: r["编号"]) + prow
    write_csv(allrows)
    draw(allrows, cls)
    report(allrows)


def touch(main_cls, labels, out, x, y, R=7):
    """管端 (x, y)（分色图像素）周围 R 内最近的、进了零件表的零件；没有就看是不是结构 / 管网，都不是为悬空。
    （描边的抗锯齿会在色块交界生出零星的青、棕像素，不算零件。）"""
    h, w = main_cls.shape
    y0, x0 = max(0, y - R), max(0, x - R)
    win = main_cls[y0: min(h, y + R + 1), x0: min(w, x + R + 1)]
    best, bd = None, 1e9
    for k in (3, 5, 6, 7, 8, 9):
        lab = labels.get(k)
        if lab is None:
            continue
        for yy, xx in np.argwhere(win == k):
            li = lab[y0 + yy, x0 + xx]
            hit = INDEX.get((k, int(li)))
            if hit is None:
                continue
            d = (y0 + yy - y) ** 2 + (x0 + xx - x) ** 2
            if d < bd:
                best, bd = hit, d
    if best:
        return best
    if (win == 2).sum() > 4:
        return "结构"
    if (win == 4).sum() > 0:
        return "管网"
    return "悬空"


INDEX = {}


ROLE = {
    "②传感器舱": {"G": "传感器组 / 处理盒"},
    "③姿控舱": {"G": "推进剂罐"},
    "④航电前段": {"G": "航电主机箱 / 泵组"},
    "④航电机柜": {"G": "航电机柜"},
    "⑤⑥眉骨下": {"G": "眉骨下设备箱", "O": "遮光盾驱动"},
    "座舱": {"P": "驾驶员", "O": "座椅 / 操纵", "C": "屏幕墙 / 座舱盖", "Y": "红灯单元", "G": "座椅后设备"},
    "座舱后": {"G": "座舱后设备箱", "O": "座舱盖作动"},
    "⑭起落架舱": {"W": "前起落架轮", "O": "起落架收放", "G": "液压单元"},
    "座舱下后舱": {"G": "后设备舱"},
}


def name_of(r):
    code = r["编号"][3]
    role = ROLE.get(r["区段"], {}).get(code)
    base = role or {"S": "框" if r.get("基本形") == "框" else "梁", "G": "设备箱", "O": "机构", "P": "人体", "C": "玻璃 / 屏", "Y": "发光件", "W": "起落架", "B": "管"}[code]
    if code == "G" and r.get("基本形") == "罐":
        base = "罐"
    if code == "O" and r.get("基本形") == "杆":
        base = role + "（杆）" if role else "作动筒 / 撑杆"
    if code == "C":
        base = "座舱盖玻璃" if r["box"][1] < 330 else "屏幕墙 / 平视显示器"
    if code == "S":
        base = "框" if r.get("基本形") == "框" else "纵梁 / 地板梁"
    return f"{r['区段']} {base}"


COLS = ["编号", "名称", "类别", "区段", "站位s", "y", "z", "长L", "宽W", "高H", "粗", "基本形", "材质", "固定在", "现有零件", "来源图", "把握度", "y来源", "原图像素框", "路径", "管网", "备注"]


def write_csv(rows):
    with open(CSV, "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for r in rows:
            X0, Y0, X1, Y1 = r["box"]
            w.writerow([
                r["编号"], r["名称"], r["类别"], r["区段"], f"{r['站位s']:.3f}", f"{r['y']:.3f}", f"{r['z']:.3f}", f"{r['长L']:.3f}", f"{r['宽W']:.3f}", f"{r['高H']:.3f}", f"{r['粗']:.3f}" if r.get("粗") else (f"{2 * r['半径']:.3f}" if r.get("半径") else ""),
                r["基本形"], r["材质"], r["固定在"], r["现有零件"], "K1 分色" + ("+俯视小图" if r.get("y来源") == "俯视小图" else ""), r["把握度"], r["y来源"],
                f"{X0:.0f} {Y0:.0f} {X1:.0f} {Y1:.0f}", r.get("路径", ""), r.get("网", ""), r.get("备注", ""),
            ])


def draw(rows, cls):
    ref = Image.open(REF).convert("RGB")
    W, H = ref.size
    dark = Image.blend(ref, Image.new("RGB", ref.size, (8, 12, 16)), 0.55)
    font = ImageFont.truetype(FONT, 11)
    big = ImageFont.truetype(FONT, 22)
    COL = {CATS[k][1]: CATS[k][4] for k in CATS}

    def paint(img, subset, labels=True, colour=None):
        d = ImageDraw.Draw(img, "RGBA")
        for r in subset:
            c = colour(r) if colour else COL[r["类别"]]
            X0, Y0, X1, Y1 = r["box"]
            if r["类别"] == "管线":
                pts = [tuple(map(float, p.split(":"))) for p in r["路径"].split(";")]
                xy = [from_body(s, z) for s, z in pts]
                d.line(xy, fill=c + (230,), width=max(2, int(r["半径"] * PX * 2)))
                if labels and r["长L"] * PX > 45:
                    d.text((xy[len(xy) // 2][0] + 2, xy[len(xy) // 2][1] - 12), r["编号"][3:], fill=c + (255,), font=font)
            elif "ends" in r:
                (ax, ay), (bx, by) = r["ends"]
                d.line([(ax, ay), (bx, by)], fill=c + (230,), width=max(2, int(r.get("粗", 0.02) * PX)))
                if labels:
                    d.text(((ax + bx) / 2 + 3, (ay + by) / 2 - 12), r["编号"][3:], fill=c + (255,), font=font)
            else:
                d.rectangle([X0, Y0, X1, Y1], outline=c + (255,), width=2, fill=c + (40,))
                if labels:
                    d.text((X0 + 2, Y0 + 1), r["编号"][3:], fill=c + (255,), font=font)
        return img

    # 全部叠回原图
    img = paint(dark.copy(), [r for r in rows if r["把握度"] != "忽略"])
    d = ImageDraw.Draw(img)
    d.text((24, 20), f"K1 零件表（自动提取，{len(rows)} 行）叠回原图 · 框 = 包围盒，线 = 管 / 杆 · 编号见 parts.csv", fill=(230, 235, 238), font=big)
    x = 24
    for k in CATS:
        c = CATS[k][4]
        d.rectangle([x, 56, x + 14, 70], fill=c)
        d.text((x + 20, 53), CATS[k][1], fill=(220, 225, 228), font=ImageFont.truetype(FONT, 16))
        x += 120
    img.save(os.path.join(OUT, "PARTS-overlay.png"))
    # 分类别拆图（4 × 2），裁到主剖面
    crop = (20, 170, 1774, 660)
    tiles = []
    for k in CATS:
        cat = CATS[k][1]
        t = paint(dark.copy(), [r for r in rows if r["类别"] == cat and r["把握度"] != "忽略"]).crop(crop)
        d = ImageDraw.Draw(t)
        n = sum(1 for r in rows if r["类别"] == cat)
        d.text((12, 8), f"{cat} · {n}", fill=CATS[k][4], font=big)
        tiles.append(t)
    tw, th = tiles[0].size
    sheet = Image.new("RGB", (tw * 2, th * 4), (10, 14, 18))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * tw, (i // 2) * th))
    sheet.save(os.path.join(OUT, "PARTS-split.png"))
    # 已建 / 缺
    st = paint(dark.copy(), [r for r in rows if r["把握度"] != "忽略" and r["类别"] != "结构"], labels=False, colour=lambda r: (90, 200, 120) if r["现有零件"] != "缺" else (240, 70, 60))
    d = ImageDraw.Draw(st)
    d.text((24, 20), "绿 = 几何母版里已有对应零件 · 红 = 缺（按零件表补建）", fill=(230, 235, 238), font=big)
    st.save(os.path.join(OUT, "PARTS-status.png"))


def report(rows):
    from collections import Counter

    c = Counter(r["类别"] for r in rows)
    miss = Counter(r["类别"] for r in rows if r["现有零件"] == "缺" and r["把握度"] != "忽略")
    conf = Counter(r["把握度"] for r in rows)
    print(f"零件表 {len(rows)} 行 → {os.path.relpath(CSV, ROOT)}")
    for k in CATS:
        n = CATS[k][1]
        print(f"  {n}: {c[n]}（缺 {miss[n]}）")
    print("  把握度:", dict(conf))
    loose = [r["编号"] for r in rows if r["类别"] == "管线" and "悬空" in r["固定在"]]
    print(f"  管线两端有悬空的: {len(loose)}")


if __name__ == "__main__":
    main()
