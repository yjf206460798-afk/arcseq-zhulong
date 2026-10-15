"""X0 拆图：X1 设定图的分色图 → 分类掩码 → 每个人像的连通块 → 米制标定 → 区域表 + 拆图叠图（WORKFLOW「拆图」）。

    .venv/bin/python blender/xianzhu/x0_split.py            # 写 refs/concept/X1_* 与 review/<日期>-X0-1/

不依赖 Blender，只用 Pillow + numpy。颜色按 IMAGE_PROMPTS「建模用图」C 表认（HSV 判别，色表不改）；
分色图的已知涂错（calib.json 的 color_errors）在这里按部位改判：领口绿 → 颈环、手套棕 → 手套、护膝棕 → 护膝。
"""
import csv
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec import LAYERS, PARTS, SEAMS  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
REF = os.path.join(ROOT, "refs", "concept")
SRC = os.path.join(REF, "X1_衔烛设定图.png")
SPLIT = os.path.join(REF, "X1_衔烛设定图_分色.png")
CALIB = os.path.join(REF, "X1_衔烛设定图_分色.calib.json")
FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"

# C 表：类别 → (中文, 叠图描边色)
CLASSES = {
    "fabric": ("服装面料", (200, 200, 200)),
    "bladder": ("抗荷气囊", (90, 200, 90)),
    "harness": ("挽具 / 扣", (255, 150, 40)),
    "scale": ("鳞甲", (70, 150, 255)),
    "helmet": ("盔壳", (190, 120, 255)),
    "visor_clear": ("透明面罩", (60, 230, 255)),
    "visor_gold": ("遮光面罩", (255, 220, 60)),
    "spine": ("脊线", (255, 60, 50)),
    "brown": ("脐带 / 靴 / 手套 / 护膝", (190, 130, 70)),
    "cooling": ("液冷管网", (170, 220, 255)),
    "skin": ("面部", (255, 255, 255)),
}
# 人像的标定高度：身高 1.74 m（头顶）+ 鞋底 0.03 + 盔顶 0.03（X1 头盔壳厚按此做）
FIG_H = 1.80


def hsv(a):
    mx, mn = a.max(2), a.min(2)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return h, s, mx


def classify(img):
    a = np.asarray(img.convert("RGB")).astype(float) / 255
    h, s, v = hsv(a)
    C = np.full(h.shape, "", dtype=object)
    sat = s > 0.25
    C[(s < 0.12) & (v > 0.45) & (v < 0.9)] = "fabric"
    C[(s < 0.08) & (v >= 0.9)] = "white"
    C[v < 0.42] = "line"
    C[sat & ((h < 12) | (h > 348)) & (s > 0.6) & (v > 0.5)] = "spine"
    C[sat & (h >= 15) & (h < 45) & (v <= 0.82) & (v > 0.25)] = "brown"
    C[sat & (h >= 18) & (h < 42) & (v > 0.82) & (s > 0.6)] = "harness"
    C[sat & (h >= 42) & (h < 64) & (v > 0.8)] = "visor_gold"
    C[sat & (h > 80) & (h < 150)] = "bladder"
    C[(h >= 178) & (h < 200) & (s >= 0.5) & (v > 0.8)] = "visor_clear"
    C[(h >= 178) & (h < 215) & (s > 0.12) & (s < 0.5) & (v > 0.7)] = "cooling"
    C[sat & (h >= 200) & (h < 228) & (s >= 0.45)] = "scale"
    C[sat & (h >= 240) & (h < 300)] = "helmet"
    return C


def label(mask):
    """4 连通标记（纯 numpy，两遍并查集）。返回 (标签图, 数量)。"""
    H, W = mask.shape
    lab = np.zeros((H, W), int)
    parent = [0]

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    n = 0
    for y in range(H):
        row = mask[y]
        for x in np.nonzero(row)[0]:
            up = lab[y - 1, x] if y else 0
            lf = lab[y, x - 1] if x else 0
            if up and lf:
                a, b = find(up), find(lf)
                lab[y, x] = min(a, b)
                parent[max(a, b)] = min(a, b)
            elif up or lf:
                lab[y, x] = up or lf
            else:
                n += 1
                parent.append(n)
                lab[y, x] = n
    m = np.array([find(i) for i in range(n + 1)])
    lab = m[lab]
    u = np.unique(lab[lab > 0])
    remap = np.zeros(n + 1, int)
    remap[u] = np.arange(1, len(u) + 1)
    return remap[lab], len(u)


def runs(profile, gap):
    """一维非零区间（间隔 ≥ gap 才分开）。"""
    idx = np.nonzero(profile)[0]
    if not len(idx):
        return []
    out, s, p = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - p > gap:
            out.append((s, p))
            s = i
        p = i
    out.append((s, p))
    return out


# 每个面板里的人像（从左到右）
FIGURES = {
    "soft": ["soft.front", "soft.side", "soft.back"],
    "armored": ["armored.front", "armored.side"],
    "helmet": ["helmet.open", "helmet.closed"],
    "helmet_wire": ["helmet.wire.front", "helmet.wire.side"],
    "exploded": ["layer1.cooling", "layer2.bladder", "layer3.restraint", "layer4.scale", "layer5.helmet"],
    "connector": ["umbilical.connector"],
}
STANDING = {"soft.front", "soft.side", "soft.back", "armored.front", "armored.side"}


def main():
    calib = json.load(open(CALIB))
    src = Image.open(SRC).convert("RGB")
    sp = Image.open(SPLIT).convert("RGB")
    C = classify(sp)
    figure_px = C != "white"
    figs = []
    for panel, names in FIGURES.items():
        P = calib["panels"][panel]
        x0, y0, x1, y1 = P["region"]
        dx, dy = P["dx"], P["dy"]
        # 分色坐标 = 原图坐标 − (dx, dy)；面板框线向里收 6 px
        sx0, sy0, sx1, sy1 = x0 - dx + 6, y0 - dy + 6, x1 - dx - 6, y1 - dy - 6
        m = figure_px[sy0:sy1, sx0:sx1]
        lab, n = label(m)
        area = np.bincount(lab.ravel())
        boxes = []
        for k in range(1, n + 1):
            if area[k] > 800:
                ys, xs = np.nonzero(lab == k)
                boxes.append([sx0 + xs.min(), sy0 + ys.min(), sx0 + xs.max(), sy0 + ys.max(), lab == k])
        boxes.sort(key=lambda b: b[0])
        if panel == "exploded":
            # 四件分层服的手连在一起：按颈部那几行的列段定四个中心，取中点竖分；头盔与面罩两件合成第 5 层
            big, rest = boxes[0], boxes[1:]
            mk = big[4]
            rows = np.nonzero(mk.any(1))[0]
            neck = mk[rows.min():rows.min() + int(0.06 * (rows.max() - rows.min()))].any(0)
            cs = [(a + b) / 2 for a, b in runs(neck, 6)]
            cuts = [0] + [int((a + b) / 2) for a, b in zip(cs, cs[1:])] + [mk.shape[1]]
            split = []
            for a, b in zip(cuts, cuts[1:]):
                part = np.zeros_like(mk)
                part[:, a:b] = mk[:, a:b]
                ys, xs = np.nonzero(part)
                split.append([sx0 + xs.min(), sy0 + ys.min(), sx0 + xs.max(), sy0 + ys.max(), part])
            r0, r1 = rest[0], rest[1]
            split.append([min(r0[0], r1[0]), min(r0[1], r1[1]), max(r0[2], r1[2]), max(r0[3], r1[3]), r0[4] | r1[4]])
            boxes = split
        if len(boxes) != len(names):
            print(f"! {panel}: 找到 {len(boxes)} 件，预期 {len(names)}", file=sys.stderr)
        for name, (bx0, by0, bx1, by1, mk) in zip(names, boxes):
            full = np.zeros(C.shape, bool)
            full[sy0:sy1, sx0:sx1] = mk
            figs.append({"name": name, "panel": panel, "bbox_split": [int(bx0), int(by0), int(bx1), int(by1)], "dx": dx, "dy": dy, "_mask": full})
    # —— 每个人像：连通块（按类别）——
    regions = []
    for f in figs:
        bx0, by0, bx1, by1 = f["bbox_split"]
        sub = np.where(f["_mask"][by0:by1 + 1, bx0:bx1 + 1], C[by0:by1 + 1, bx0:bx1 + 1], "white")
        f["classes"] = {}
        for cls in CLASSES:
            m = sub == cls
            if m.sum() < 12:
                continue
            lab, n = label(m)
            comps = []
            for k in range(1, n + 1):
                ys, xs = np.nonzero(lab == k)
                if len(ys) < 12:
                    continue
                comps.append({"cls": cls, "area": int(len(ys)), "bbox": [int(bx0 + xs.min()), int(by0 + ys.min()), int(bx0 + xs.max()), int(by0 + ys.max())], "c": [round(float(bx0 + xs.mean()), 1), round(float(by0 + ys.mean()), 1)]})
            comps.sort(key=lambda c: -c["area"])
            f["classes"][cls] = int(m.sum())
            for c in comps:
                c["figure"] = f["name"]
                regions.append(c)
    # —— 米制标定（站姿人像）：盔顶 → 鞋底 = FIG_H；中线：正 / 背视取腿部质心，侧视取躯干质心 ——
    metric = {}
    for f in figs:
        if f["name"] not in STANDING:
            continue
        bx0, by0, bx1, by1 = f["bbox_split"]
        sub = (C[by0:by1 + 1, bx0:bx1 + 1] != "white")
        hpx = by1 - by0
        ppm = hpx / FIG_H
        rows_leg = sub[int(hpx * 0.6):int(hpx * 0.85)]
        rows_torso = sub[int(hpx * 0.2):int(hpx * 0.45)]
        use = rows_torso if f["name"].endswith("side") else rows_leg
        ys, xs = np.nonzero(use)
        cx = bx0 + xs.mean()
        metric[f["name"]] = {"ground_y_split": int(by1), "top_y_split": int(by0), "axis_x_split": round(float(cx), 1), "px_per_m": round(ppm, 2),
                             "dx": f["dx"], "dy": f["dy"], "view": "front" if f["name"].endswith("front") else ("back" if f["name"].endswith("back") else "side(+左侧)")}
    # 地标（米，离地；正视）
    def to_m(name, x, y):
        M = metric[name]
        return round((x - M["axis_x_split"]) / M["px_per_m"], 3), round((M["ground_y_split"] - y) / M["px_per_m"], 3)

    landmarks = {}
    for name in metric:
        M = metric[name]
        f = next(g for g in figs if g["name"] == name)
        bx0, by0, bx1, by1 = f["bbox_split"]
        sub = C[by0:by1 + 1, bx0:bx1 + 1]
        L = {}
        hc = [r for r in regions if r["figure"] == name and r["cls"] == "helmet"]
        if hc:
            L["helmet_bottom_z"] = to_m(name, 0, max(hc, key=lambda r: r["area"])["bbox"][3])[1]
        # 腰带：挽具最宽的一行（躯干段）
        H = by1 - by0
        hw = (sub == "harness").sum(1)
        band = slice(int(H * 0.25), int(H * 0.5))
        if hw[band].max() > 0:
            r = band.start + int(np.argmax(hw[band]))
            L["belt_z"] = to_m(name, 0, by0 + r)[1]
        # 胯：正 / 背视中线一列从下往上第一次碰到人像
        if not name.endswith("side"):
            cxl = int(round(M["axis_x_split"])) - bx0
            colm = (sub[:, max(cxl - 1, 0):cxl + 2] != "white").any(1)
            ys = np.nonzero(colm[int(H * 0.3):])[0]
            if len(ys):
                # 从脚往上：最后一段连续非人像的上端
                empty = np.nonzero(~colm)[0]
                empty = empty[empty > H * 0.35]
                if len(empty):
                    L["crotch_z"] = to_m(name, 0, by0 + empty.min() - 1)[1]
            # 肩宽：躯干上部（离地 1.30～1.50 m）最宽处
            wmax = 0
            for y in range(H):
                z = (M["ground_y_split"] - (by0 + y)) / M["px_per_m"]
                if 1.30 < z < 1.50:
                    xs = np.nonzero(sub[y] != "white")[0]
                    if len(xs):
                        wmax = max(wmax, xs.max() - xs.min())
            L["shoulder_width"] = round(wmax / M["px_per_m"], 3)
        # 护膝、靴口、手套（棕色块，按位置判）
        for r in regions:
            if r["figure"] != name or r["cls"] != "brown":
                continue
            x, z = to_m(name, *r["c"])
            ztop = to_m(name, 0, r["bbox"][1])[1]
            zbot = to_m(name, 0, r["bbox"][3])[1]
            if zbot < 0.03 and r["area"] > 300:
                L.setdefault("boot_top_z", []).append(ztop)
            elif 0.35 < z < 0.65 and r["area"] > 150:
                L.setdefault("kneepad_c", []).append([x, z])
            elif 0.7 < z < 1.0 and r["area"] > 150:
                L.setdefault("glove_c", []).append([x, z])
        landmarks[name] = L
    # —— 区域的米制坐标 ——
    for r in regions:
        if r["figure"] in metric:
            x0_, z1_ = to_m(r["figure"], r["bbox"][0], r["bbox"][1])
            x1_, z0_ = to_m(r["figure"], r["bbox"][2], r["bbox"][3])
            r["m"] = {"x": [x0_, x1_], "z": [z0_, z1_]}
    for f in figs:
        f.pop("_mask")
    out = {"image": "X1_衔烛设定图_分色.png", "classes": {k: v[0] for k, v in CLASSES.items()}, "fig_height_m": FIG_H,
           "note": "坐标为分色图像素；原图坐标 = 分色 + (dx, dy)。米制：x 为离人像中线（正视：观者右为 +，即着装者左侧为 +；背视相反；侧视人像朝左，+x 向后），z 离地。棕色块按位置改判（靴 / 护膝 / 手套 / 脐带），见 parts.csv。",
           "figures": figs, "metric": metric, "landmarks": landmarks, "regions": regions}
    with open(os.path.join(REF, "X1_衔烛设定图_分色.regions.json"), "w") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    # calib.json 的米制一项
    calib["metric"] = {"fig_height_m": FIG_H, "rule": "站姿人像盔顶 → 鞋底 = 1.80 m（身高 1.74 + 鞋底 0.03 + 盔顶 0.03）；像素/米按人像分别取。分色坐标，原图坐标 = 分色 + 面板 (dx, dy)",
                       "figures": metric, "landmarks_m": landmarks}
    with open(CALIB, "w") as fp:
        json.dump(calib, fp, ensure_ascii=False, indent=1)
    overlay(src, figs, regions, metric)
    rows = match(regions, metric)
    write_csv(rows)
    write_md(rows, landmarks)
    zones(src, figs, regions, metric, C)
    print(json.dumps({k: v for k, v in landmarks.items()}, ensure_ascii=False, indent=1))
    print(f"{len(figs)} figures · {len(regions)} regions")


def overlay(src, figs, regions, metric):
    """拆图叠图：原图压暗 55%，每个区域按类别描轮廓（像素边界），人像框 + 米制刻度。"""
    base = Image.blend(src, Image.new("RGB", src.size, (0, 0, 0)), 0.45)
    sp = Image.open(SPLIT).convert("RGB")
    C = classify(sp)
    W, H = src.size
    ov = np.asarray(base).copy()
    for cls, (_, rgb) in CLASSES.items():
        if cls == "fabric":
            continue
        m = C == cls
        edge = m & ~(np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1))
        # 搬到原图坐标：按所在人像的 (dx, dy)
        for f in figs:
            bx0, by0, bx1, by1 = f["bbox_split"]
            e = np.zeros_like(edge)
            e[by0:by1 + 1, bx0:bx1 + 1] = edge[by0:by1 + 1, bx0:bx1 + 1]
            ys, xs = np.nonzero(e)
            ys, xs = ys + f["dy"], xs + f["dx"]
            ok = (ys >= 0) & (ys < H) & (xs >= 0) & (xs < W)
            ov[ys[ok], xs[ok]] = rgb
    img = Image.fromarray(ov)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 11)
    for f in figs:
        bx0, by0, bx1, by1 = f["bbox_split"]
        b = (bx0 + f["dx"], by0 + f["dy"], bx1 + f["dx"], by1 + f["dy"])
        d.rectangle(b, outline=(120, 140, 150))
        d.text((b[0], b[1] - 13), f["name"], fill=(220, 233, 235), font=font)
        if f["name"] in metric:
            M = metric[f["name"]]
            gy = M["ground_y_split"] + f["dy"]
            ax = M["axis_x_split"] + f["dx"]
            d.line((ax, b[1], ax, gy), fill=(123, 219, 236))
            for zm in np.arange(0, 1.81, 0.1):
                y = gy - zm * M["px_per_m"]
                w = 6 if round(zm * 10) % 5 == 0 else 3
                d.line((b[2] + 4, y, b[2] + 4 + w, y), fill=(123, 219, 236))
                if round(zm * 10) % 5 == 0:
                    d.text((b[2] + 12, y - 6), f"{zm:.1f}", fill=(123, 219, 236), font=font)
    # 图例
    y = H - 14 * (len(CLASSES) + 1) - 8
    d.rectangle((W - 220, y - 6, W - 8, H - 8), fill=(16, 21, 24), outline=(128, 153, 163))
    for k, (cls, (zh, rgb)) in enumerate(CLASSES.items()):
        d.rectangle((W - 210, y + 14 * k + 2, W - 198, y + 14 * k + 10), fill=rgb)
        d.text((W - 192, y + 14 * k), f"{cls} · {zh}", fill=(220, 233, 235), font=font)
    img.save(os.path.join(REF, "X1_拆图叠图.png"))


LAYER_RGB = {"L1": (170, 220, 255), "L2": (100, 220, 110), "L3": (255, 160, 60), "L4": (80, 160, 255), "L5": (200, 140, 255)}


def match(regions, metric):
    """自动连通块 → 区域表零件：块中心落在零件某视图的匹配框内（框 x0 ≥ 0 时按 |x| 比，左右件都认）。"""
    for r in regions:
        r["part"] = None
        M = metric.get(r["figure"])
        if not M or r["area"] < 100 or r["cls"] == "fabric":
            continue
        x = (r["c"][0] - M["axis_x_split"]) / M["px_per_m"]
        z = (M["ground_y_split"] - r["c"][1]) / M["px_per_m"]
        for P in PARTS:
            v = P["views"].get(r["figure"])
            if not v or v[0] != r["cls"]:
                continue
            xx = abs(x) if v[1] >= 0 else x
            if v[1] <= xx <= v[2] and v[3] <= z <= v[4]:
                r["part"] = P["id"]
                break
    rows = []
    for P in PARTS:
        hits = [r for r in regions if r.get("part") == P["id"]]
        zs = [r["m"]["z"] for r in hits]
        meas = (min(a for a, _ in zs), max(b for _, b in zs)) if zs else None
        px = ["%s:%d,%d,%d,%d" % (r["figure"], r["bbox"][0], r["bbox"][1], r["bbox"][2], r["bbox"][3]) for r in hits]
        rows.append({**{k: P[k] for k in ("id", "layer", "name", "cls", "seg", "how", "adopt", "conf")},
                     "z0": P["z"][0], "z1": P["z"][1], "az": "" if P["az"] is None else "%d～%d" % P["az"],
                     "z_measured": "" if meas is None else "%.3f～%.3f" % meas, "n_blocks": len(hits), "blocks_px": " ".join(px)})
    return rows


def write_csv(rows):
    keys = ["id", "layer", "name", "cls", "seg", "z0", "z1", "az", "z_measured", "n_blocks", "adopt", "conf", "how", "blocks_px"]
    head = {"id": "编号", "layer": "层", "name": "名称", "cls": "分色类别", "seg": "部位", "z0": "z0(m)", "z1": "z1(m)", "az": "方位(°)",
            "z_measured": "分色实测z(m)", "n_blocks": "匹配块数", "adopt": "采信", "conf": "把握度", "how": "做法", "blocks_px": "匹配块(分色像素 x0,y0,x1,y1)"}
    with open(os.path.join(REF, "X1_衔烛设定图_分色.parts.csv"), "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow([head[k] for k in keys])
        for r in rows:
            w.writerow([r[k] for k in keys])


def write_md(rows, landmarks):
    """分层与区域表（给作者看的一页）：由 spec.py + 实测生成，不手改。"""
    from spec import SCALE_ZONES
    L = ["# 銜燭 · 分层与区域表（X0 拆图，自动生成：`blender/xianzhu/x0_split.py`，数据源 `blender/xianzhu/spec.py`）", "",
         "坐标：人面朝 +x，+y 为着装者左手边，z 离地（米）。站姿高度按设定图米制标定（盔顶 → 鞋底 1.80 m）。"
         "方位 az：躯干 0 前 / +90 左 / 180 后；四肢 0 前 / +90 外侧 / −90 内侧。叠图：`X1_拆图叠图.png`（分色类别轮廓）、`X1_分层区域叠图.png`（零件框 + 接缝走向）。", "",
         "## 分层（由内到外）", "", "| 层 | 名称 | 覆盖 |", "|---|---|---|"]
    L += [f"| {a} | {b} | {c} |" for a, b, c in LAYERS]
    L += ["", "## 区域表", "", "| 编号 | 层 | 名称 | 部位 | z (m) | 方位 (°) | 分色实测 z | 采信 | 把握 | 做法 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| `{r['id']}` | {r['layer']} | {r['name']} | {r['seg']} | {r['z0']}～{r['z1']} | {r['az'] or '—'} | {r['z_measured'] or '—'} | {r['adopt']} | {r['conf']} | {r['how']} |")
    L += ["", "## 接缝线走向（软态外层，X1 做成服装低模的边环）", "", "| 编号 | 走向 | 做法 |", "|---|---|---|"]
    L += [f"| `{q['id']}` | {q['how']} | {q['kind']} |" for q in SEAMS]
    L += ["", "## 鳞片区（X2）", "", "、".join(f"`{z}`" for z in SCALE_ZONES) + "：鳞片尖朝下、前后错叠；躯干正面中线、关节内侧不覆盖（`scale.chest` 不采信）。", "",
          "## 站姿地标（分色实测，米）", "", "| 人像 | 盔底 | 腰带 | 胯 | 肩宽 | 靴口 | 护膝中心 | 手套中心 |", "|---|---|---|---|---|---|---|---|"]
    for k, v in landmarks.items():
        kp = v.get("kneepad_c", [[None, None]])
        gl = v.get("glove_c", [[None, None]])
        f = lambda q: "—" if q is None else f"{q:.2f}"  # noqa: E731
        L.append(f"| {k} | {f(v.get('helmet_bottom_z'))} | {f(v.get('belt_z'))} | {f(v.get('crotch_z'))} | {f(v.get('shoulder_width'))} | "
                 f"{f(min(v['boot_top_z']) if 'boot_top_z' in v else None)} | {f(kp[0][1])} | x {f(abs(gl[0][0]) if gl[0][0] is not None else None)}, z {f(gl[0][1])} |")
    with open(os.path.join(REF, "X1_分层与区域表.md"), "w") as fp:
        fp.write("\n".join(L) + "\n")


def zones(src, figs, regions, metric, C):
    """分层区域叠图：匹配到零件的块按层上色画框并标编号（不采信的画灰框打叉），软态三视图上画接缝线走向示意。"""
    img = Image.blend(src, Image.new("RGB", src.size, (0, 0, 0)), 0.5)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 10)
    lay = {P["id"]: P for P in PARTS}
    labelled = set()
    for r in regions:
        pid = r.get("part")
        if not pid:
            continue
        f = next(g for g in figs if g["name"] == r["figure"])
        b = (r["bbox"][0] + f["dx"], r["bbox"][1] + f["dy"], r["bbox"][2] + f["dx"], r["bbox"][3] + f["dy"])
        P = lay[pid]
        bad = P["adopt"].startswith("不采信")
        col = (140, 140, 140) if bad else LAYER_RGB[P["layer"]]
        d.rectangle(b, outline=col, width=1)
        if bad:
            d.line((b[0], b[1], b[2], b[3]), fill=col)
            d.line((b[0], b[3], b[2], b[1]), fill=col)
        key = (r["figure"], pid)
        if key not in labelled:
            labelled.add(key)
            d.text((b[2] + 2, b[1]), pid.split(".", 1)[1], fill=col, font=font)
    # 接缝线走向示意（软态正 / 背视）：水平缝取该行人像连续段，拉链为前中竖线
    rings = {"soft.front": [1.47, 1.10, 0.64, 0.46, 0.25], "soft.back": [1.47, 1.42, 1.10, 0.64, 0.46, 0.25]}
    for name, zs in rings.items():
        M = metric[name]
        f = next(g for g in figs if g["name"] == name)
        bx0, by0, bx1, by1 = f["bbox_split"]
        for zm in zs:
            y = int(round(M["ground_y_split"] - zm * M["px_per_m"]))
            row = C[y, bx0:bx1 + 1] != "white"
            for a, b in runs(row, 1):
                if b - a < 8:
                    continue
                d.line((bx0 + a + f["dx"], y + f["dy"], bx0 + b + f["dx"], y + f["dy"]), fill=(123, 219, 236), width=1)
        if name == "soft.front":
            ax = M["axis_x_split"] + f["dx"]
            d.line((ax, M["ground_y_split"] - 1.50 * M["px_per_m"] + f["dy"], ax, M["ground_y_split"] - 0.84 * M["px_per_m"] + f["dy"]), fill=(123, 219, 236), width=1)
    # 图例：层
    W, H = img.size
    y = H - 14 * (len(LAYERS) + 3) - 8
    d.rectangle((W - 330, y - 6, W - 8, H - 8), fill=(16, 21, 24), outline=(128, 153, 163))
    for k, (lid, zh, _) in enumerate(LAYERS):
        d.rectangle((W - 320, y + 14 * k + 2, W - 308, y + 14 * k + 10), fill=LAYER_RGB[lid])
        d.text((W - 302, y + 14 * k), f"{lid} {zh}", fill=(220, 233, 235), font=font)
    k = len(LAYERS)
    d.rectangle((W - 320, y + 14 * k + 2, W - 308, y + 14 * k + 10), outline=(140, 140, 140))
    d.text((W - 302, y + 14 * k), "不采信（DESIGN 9.1.1 / calib 取舍）", fill=(220, 233, 235), font=font)
    d.line((W - 320, y + 14 * (k + 1) + 6, W - 308, y + 14 * (k + 1) + 6), fill=(123, 219, 236))
    d.text((W - 302, y + 14 * (k + 1)), "接缝线走向（示意：领口 / 背育克 / 腰 / 膝上下 / 靴口 / 拉链）", fill=(220, 233, 235), font=font)
    img.save(os.path.join(REF, "X1_分层区域叠图.png"))


if __name__ == "__main__":
    main()
