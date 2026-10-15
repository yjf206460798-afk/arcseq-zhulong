"""按 K1 零件表补建（WORKFLOW「拆图」第 4 步）：读 refs/layout/K1_驾驶舱侧剖.parts.csv，把“现有零件 = 缺”的行生成几何。

零件表由 scripts/k1-parts.py 从分色图自动拆出（作者 2026-10-15 确认）。站位 s、高度 z、长、高、粗、路径都是机体米制；
y 与宽只有一部分来自俯视小图，其余是推定 / 猜，这里再按截面内表面收进机身。每类的建法：
  · 箱体（盒）：kit box（面板凹缝、固定耳、四角螺栓、插头、小铭牌）；（罐）：kit tank，沿长边。
  · 机构（杆）：两端 + 粗 → 作动筒（长于 0.3 m）或撑杆（方管 + 两端耳环）；（支架）：小金属块 + 螺栓。
  · 结构（框 / 板）：只有一段的框 → 按 z 范围取内表面那几条边做框板；板 → 实心隔板。都是剖切件（切口画实心剖面）。
  · 管线：沿路径（s:z 折线）；同一连通管网取同一个 y（接零件的多数决；一个零件都不接的管网贴着远侧内壁走）；
    接零件 / 结构的一端是接头（套筒 + 法兰），接管网的一端是三通；长管每 0.4 m 一只卡箍；管件都是 8 边不倒角的轻量件。
接在“结构”上的管端做穿壁接头（法兰贴着最近的框或远侧内壁）。
"""
import csv
import math
import os
import zlib

from mathutils import Vector

from kit.parts import actuator, beam, box, cylinder, frame, hull, merge, pipe, tank

from .nose import S_END, S_FRONT, at

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(os.path.dirname(os.path.dirname(HERE)), "refs", "layout", "K1_驾驶舱侧剖.parts.csv")
X = Vector((1, 0, 0))
Y = Vector((0, 1, 0))
Z = Vector((0, 0, 1))


def rows():
    if not os.path.exists(CSV):
        return []
    with open(CSV, encoding="utf8") as f:
        return list(csv.DictReader(f))


def _f(r, k, d=0.0):
    try:
        return float(r[k])
    except (KeyError, ValueError):
        return d


def _path(r):
    return [tuple(map(float, q.split(":"))) for q in r["路径"].split(";") if q]


def _h(r, salt=""):
    return (zlib.crc32((r["编号"] + salt).encode()) & 0xFFFF) / 0xFFFF


def build(acc, I):
    """I：interior 模块（collect、half_width、inner_ring、FRAME_S、P、PC……）。返回补了多少件。"""
    table = rows()
    by_id = {r["编号"]: r for r in table}
    # 座舱里驾驶员身前身下的机构（侧杆、油门、脚蹬、座椅连杆）按真人尺寸手工建（interior.cockpit / seat_and_pilot），
    # K1 画的是另一个比例的人，不照表补，否则会和手建的那套重复
    hand = lambda r: r["类别"] == "机构" and r["区段"] == "座舱" and _f(r, "站位s") < 6.6  # noqa: E731
    todo = [r for r in table if r["现有零件"] == "缺" and r["把握度"] != "忽略" and not hand(r) and S_FRONT + 0.06 < _f(r, "站位s") < S_END - 0.05]
    n0 = len(acc)
    placed = {}  # 编号 → 实际放的 y（管线接零件时取它）
    for r in sorted(todo, key=lambda r: r["类别"] != "管线", reverse=True):
        cat, shape = r["类别"], r["基本形"]
        try:
            if cat == "箱体":
                y = _box(acc, I, r)
            elif cat == "机构" and shape == "杆":
                y = _rod(acc, I, r)
            elif cat == "机构":
                y = _bracket(acc, I, r)
            elif cat == "结构":
                y = _structure(acc, I, r)
            elif cat == "管线":
                continue
            else:
                y = None
            if y is not None:
                placed[r["编号"]] = y
        except ValueError as e:
            print("  零件表跳过", r["编号"], e)
    # 管网：同一连通管网的分支取同一个 y（接零件的分支多数决，没有就按网号散开），汇合处一只三通
    nets = {}
    for r in table:
        if r["类别"] == "管线":
            nets.setdefault(r.get("管网", r["编号"]), []).append(r)
    net_y = {}
    for nid, members in nets.items():
        ys = []
        for r in members:
            for e in (e.strip() for e in r["固定在"].split("↔")):
                if e in placed:
                    ys.append(placed[e])
                elif e in by_id and by_id[e]["y来源"] == "俯视小图":
                    ys.append(float(by_id[e]["y"]))
        # 没接任何零件的管网（K1 里画在内壁上、两端进壁 / 框的管）：贴着远侧内壁走（y = None）
        net_y[nid] = sorted(ys)[len(ys) // 2] if ys else None
    for r in todo:
        if r["类别"] == "管线":
            _pipe(acc, I, r, net_y[r.get("管网", r["编号"])])
    return len(acc) - n0


def _name(r):
    return "int.k1." + r["编号"][3:].lower()


def _inside_y(I, s, z, y, half):
    """把 y 收进 (s, z) 处的内表面（留 half + 1 cm）；那里没有空间时返回 None。"""
    hw = I.half_width(s, z)
    if hw <= half + 0.01:
        return None
    lim = hw - half - 0.01
    return max(-lim, min(lim, y))


def _box(acc, I, r):
    s, z = _f(r, "站位s"), _f(r, "z")
    L, W, H = max(0.04, _f(r, "长L")), max(0.04, _f(r, "宽W")), max(0.04, _f(r, "高H"))
    if r["基本形"] == "罐":
        rr = min(H, W) / 2 if L >= H else min(L, W) / 2
        along = X if L >= H else Z
        half = (L if L >= H else H) / 2 - rr * 0.1
        y = _inside_y(I, s, z, _f(r, "y"), rr) if r["y来源"] == "俯视小图" else _inside_y(I, s, z, -0.05, rr)
        if y is None:
            raise ValueError("罐放不下")
        c = at(s, y, z)
        I.collect(acc, tank(_name(r), c + along * half, c - along * half, rr, bands=2, props=I.P))
        return y
    # 宽：不超过表里的宽，也不超过四角处内表面的两倍；y 收进去
    for _ in range(6):
        w = I.fit(s - L / 2, s + L / 2, z - H / 2, z + H / 2, W)
        hw = min(I.half_width(ss, zz) for ss in (s - L / 2, s + L / 2) for zz in (z - H / 2, z + H / 2))
        if hw > 0.03:
            break
        L, H = L * 0.88, H * 0.88
    else:
        raise ValueError("箱放不下")
    y = _f(r, "y") if r["y来源"] == "俯视小图" else -(_h(r) * 0.12)
    y = max(-(hw - w / 2 - 0.005), min(hw - w / 2 - 0.005, y)) if hw > w / 2 + 0.005 else 0.0
    big = L > 0.14 and H > 0.1
    I.collect(acc, box(_name(r), at(s, y, z), (L, w, H), face="+y", panel=L > 0.08 and H > 0.07, handles=L > 0.22, plugs=min(3, int(L / 0.07)) if H > 0.08 else 0,
                       label=big, corner_bolts=True, split=1 if L > 0.32 else 0, grille=2 if big and _h(r, "g") > 0.6 else 0, props=I.P, material="avionics"))
    return y


def _ends(r):
    (s0, z0), (s1, z1) = _path(r)[:2]
    return (s0, z0), (s1, z1)


def _rod(acc, I, r):
    (s0, z0), (s1, z1) = _ends(r)
    th = min(0.06, max(0.014, _f(r, "粗", 0.02)))
    y = _f(r, "y") if r["y来源"] == "俯视小图" else -0.06 - 0.1 * _h(r)
    ys = [_inside_y(I, s, z, y, th) for s, z in ((s0, z0), (s1, z1))]
    if any(v is None for v in ys):
        raise ValueError("杆端出了机身")
    y = min(ys, key=abs)
    a, b = at(s0, y, z0), at(s1, y, z1)
    L = (b - a).length
    if L > 0.3 and th > 0.02:
        I.collect(acc, actuator(_name(r), a, b, th / 2, ext=0.35 + 0.3 * _h(r), props=I.P))
    else:
        d = (b - a).normalized()
        up = Y if abs(d.dot(Y)) < 0.9 else Z
        I.collect(acc, beam(_name(r), a + d * th * 0.6, b - d * th * 0.6, th * 0.9, th * 0.7, up, kind="box", material="metal", props=I.P))
        for k, p in enumerate((a, b)):
            I.collect(acc, cylinder(f"{_name(r)}.eye{k}", p - Y * th * 0.45, p + Y * th * 0.45, th * 0.6, 12, "metal", I.P, bevel=0.001))
    return y


def _bracket(acc, I, r):
    s, z = _f(r, "站位s"), _f(r, "z")
    L, H = min(0.12, max(0.02, _f(r, "长L"))), min(0.12, max(0.02, _f(r, "高H")))
    W = 0.035
    y = _f(r, "y") if r["y来源"] == "俯视小图" else -0.04 - 0.12 * _h(r)
    y = _inside_y(I, s, z, y, W / 2 + 0.01)
    if y is None:
        raise ValueError("支架放不下")
    I.collect(acc, box(_name(r), at(s, y, z), (L, W, H), material="metal", face="+y", panel=False, handles=False, plugs=0, ears=False, corner_bolts=min(L, H) > 0.05, props=I.P))
    return y


def _structure(acc, I, r):
    s, z, H = _f(r, "站位s"), _f(r, "z"), _f(r, "高H")
    z0, z1 = z - H / 2, z + H / 2
    ring_ = list(reversed(I.inner_ring(s)))
    if r["基本形"] == "梁":
        (s0, za), (s1, zb) = _ends(r)
        hw = min(I.half_width(s0, za), I.half_width(s1, zb))
        if hw < 0.05:
            raise ValueError("梁放不下")
        I.collect(acc, beam(_name(r), at(s0, -hw + 0.03, za), at(s1, -hw + 0.03, zb), 0.04, 0.05, Z, kind="channel", props=I.P, holes=int(abs(s1 - s0) / 0.15)))
        return 0.0
    if r["基本形"] == "板":
        # 实心隔板：内表面多边形在 z0～z1 之间的那一段（凸），厚 2 cm，剖切件
        pts = _clip_z(ring_, z0, z1)
        if len(pts) < 3:
            raise ValueError("板不在截面里")
        pts = [p + X * d for p in pts for d in (-0.01, 0.01)]
        I.collect(acc, hull(_name(r), pts, "structure", I.PC, bevel=0.004))
        return 0.0
    # 框：只要 z 范围碰到的那几条边（reversed 顺序：[−R1, −R2, −R3, R3, R2, R1, R0]，边 k 连 k → k+1）
    skip = set()
    for k in range(len(ring_)):
        a, b = ring_[k], ring_[(k + 1) % len(ring_)]
        if max(a.z, b.z) < z0 - 0.02 or min(a.z, b.z) > z1 + 0.02:
            skip.add(k)
    if len(skip) == len(ring_):
        raise ValueError("框不在截面里")
    I.collect(acc, frame(_name(r), ring_, depth=0.025, width=0.045, material="structure", props=I.PC, skip=skip))
    return 0.0


def _rdp3(P, eps):
    """三维折线 Ramer–Douglas–Peucker 简化。"""
    if len(P) < 3:
        return P
    a, b = P[0], P[-1]
    ab = b - a
    L = ab.length or 1e-9
    d = [((p - a).cross(ab)).length / L for p in P[1:-1]]
    i = max(range(len(d)), key=d.__getitem__) + 1
    if d[i - 1] > eps:
        return _rdp3(P[: i + 1], eps)[:-1] + _rdp3(P[i:], eps)
    return [a, b]


def _clip_z(poly, z0, z1):
    """凸多边形（同一 x）按 z0 ≤ z ≤ z1 裁剪（Sutherland–Hodgman，两条水平线）。"""
    def cut(P, inside, at_z):
        out = []
        for k in range(len(P)):
            a, b = P[k], P[(k + 1) % len(P)]
            ia, ib = inside(a), inside(b)
            if ia:
                out.append(a)
            if ia != ib and abs(b.z - a.z) > 1e-9:
                t = (at_z - a.z) / (b.z - a.z)
                out.append(a.lerp(b, t))
        return out
    P = cut(list(poly), lambda p: p.z >= z0, z0)
    return cut(P, lambda p: p.z <= z1, z1) if P else P


def _pipe(acc, I, r, y):
    pts = _path(r)
    if len(pts) < 2:
        return
    rad = min(0.028, max(0.005, _f(r, "粗", 0.016) / 2))
    ends = [e.strip() for e in r["固定在"].split("↔")]
    if y is None:
        rad = min(rad, 0.016)  # 壁上的管细一些（K1 里是成束的细管）
    yv = -1.0 if y is None else y  # 贴壁：收进内表面时会停在远侧壁前
    P3 = []
    for s, z in pts:
        if not (S_FRONT + 0.03 < s < S_END - 0.01):
            continue
        yy = _inside_y(I, s, z, yv, rad + 0.006)
        if yy is None:
            # 贴着蒙皮的管：往里收 2 cm 再试
            zc = (I.keel(s) + I.top_profile(s)) / 2 if hasattr(I, "top_profile") else z
            z = z + (zc - z) * 0.15
            yy = _inside_y(I, s, z, yv, rad + 0.006)
            if yy is None:
                continue
        P3.append(at(s, yy, z))
    # 去掉重合点
    Q = [P3[0]] if P3 else []
    for p in P3[1:]:
        if (p - Q[-1]).length > 0.012:
            Q.append(p)
    if len(Q) < 2 or sum((b - a).length for a, b in zip(Q, Q[1:])) < 0.05:
        return
    Q = _rdp3(Q, 0.008)  # 分色图骨架的锯齿折点去掉（8 mm 以内），面数也省下来
    name = _name(r)
    mat = "cable" if r["材质"] == "cable" else "pipe"
    I.collect(acc, pipe(name, Q, rad, bend=min(0.05, rad * 3), sides=8 if rad > 0.012 else 6, material=mat, props=I.P))
    # 两端：接零件、接结构的一端是接头（沿端段方向）；接管网的一端是三通（短横管）
    # 管件做轻量的（8 边、不倒角）：接头 = 套筒 + 法兰，三通 = 短横管，卡箍 = 扁环——这一类件数多，面数要省
    fits = []
    for k, (p, q) in enumerate(((Q[0], Q[1]), (Q[-1], Q[-2]))):
        d = (p - q).normalized()
        if ends[min(k, len(ends) - 1)] == "管网":
            side = d.cross(Y).normalized() if abs(d.dot(Y)) < 0.9 else X
            fits.append(cylinder(f"{name}.tee{k}", p - side * rad * 1.6, p + side * rad * 1.6, rad * 1.3, 8, "metal", I.P, bevel=0.0))
        else:
            fits.append(cylinder(f"{name}.fit{k}", p - d * 0.03, p - d * 0.006, rad * 1.3, 8, "metal", I.P, bevel=0.0))
            fits.append(cylinder(f"{name}.flange{k}", p - d * 0.006, p, rad * 1.7, 8, "metal", I.P, bevel=0.0))
    # 卡箍每 0.4 m
    L = sum((b - a).length for a, b in zip(Q, Q[1:]))
    for j in range(1, int(L / 0.4) + 1):
        f = j * 0.4
        for a, b in zip(Q, Q[1:]):
            seg = (b - a).length
            if f <= seg:
                c, d = a.lerp(b, f / seg), (b - a).normalized()
                fits.append(cylinder(f"{name}.clip{j}", c - d * 0.006, c + d * 0.006, rad * 1.25, 8, "metal", I.P, bevel=0.0))
                break
            f -= seg
    I.collect(acc, merge(f"{name}.fittings", fits, material="metal", props={**I.P, "lineLevel": "secondary"}))
