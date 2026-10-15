"""烛龙机头段内部（对 refs/layout/K1 的机头部分叠图对位；剖视模式按需加载的模块）。

K1 → 机体坐标（refs/layout/README：K1 比例尺不可信，只取相对位置）：
  · 纵向：以光窗眼心对齐（K1 (97, 449) ↔ s 0.33），220 px/m——这样 K1 的眉骨前缘、座舱前壁、驾驶员臀部、头盔
    分别落在 s 3.9、4.84、6.15、6.5，与几何母版（C2）的眉骨、座舱盖前缘、座舱盖后部对得上。
  · 竖向（座舱以外）：按 K1 自己的上下蒙皮线之间的比例放进我们的截面（k1()）：C2 的机身比 K1 高约 16～20%，
    零件跟着截面走，不会穿出蒙皮；零件本身的尺寸按 220 px/m 量，不拉伸。
  · 起落架舱与座舱地板以下（kg()）：K1 的地板梁 ↔ 我们的舱顶 Z_GEAR，K1 的龙骨 ↔ 我们的龙骨。
  · 座舱（有意不同，README：K1 的座舱盖画低了）：驾驶员与座椅按真人尺寸做（大腿 0.55 m、头盔半径 0.135 m、
    椅背后倾 33°），臀点放在 K1 的臀点站位（s 6.15），整体高度让头盔顶离 C2 座舱盖内表面约 5 cm；
    座舱里其余设备按 kc()：均匀比例再抬高 LIFT。
剖视只从 +y 一侧看：舱壁、舱侧板只做远侧（y < 0）那一片当背景，近侧不做（否则挡住内部）。全部零件用 blender/kit。
"""
import math
import sys

import numpy as np

from mathutils import Vector

from kit.parts import actuator, beam, bolts, box, bracket, clamp, connector, cylinder, drum, ellipsoid, frame, hull, lathe, merge, pipe, pump, tank, valve

from . import k1table, pilot
from .nose import EYE, S_END, S_FLAT as S_FLAT_I, Z_TIP, at, ring, top_profile
from .util import XN, lerp

SKIN = 0.04  # 蒙皮厚（剖面带的宽，3～5 cm）
P = {"module": "interior", "lineLevel": "structure"}
PC = {**P, "cut": True, "section": "cap"}
SEAMS = []  # 内部模块的分割线（驾驶员服装接缝……）：build.py 写进 zhulong.json 的 interiorSeams  # 剖切面上被切开的内部件（屏幕墙、地板……K1 里近侧一半是剖掉的）

# —— K1 → 机体 ——————————————————————————————————————————————————————
K1_PX = 220.0
K1_EYE = (97.0, 449.0)
# K1 外蒙皮的上、下轮廓线（像素，量自 refs/layout/K1；上线在 1000～1450 是 K1 画低了的眉骨 / 座舱盖）
K1_TOP = [(57, 448), (150, 423), (300, 398), (400, 380), (500, 372.7), (600, 360.8), (700, 346.5), (800, 331.5), (900, 311.5), (1000, 300), (1100, 292), (1250, 278), (1350, 253), (1450, 222), (1550, 217), (1650, 209), (1774, 200)]
K1_BOT = [(57, 448), (100, 456), (150, 474), (300, 488), (400, 501.7), (500, 513.8), (600, 529), (700, 538.8), (800, 545), (900, 552.7), (1000, 568), (1100, 581.5), (1200, 584), (1300, 590), (1400, 596.7), (1500, 610), (1600, 618), (1774, 630)]
K1_FLOOR = 482.0  # K1 起落架舱顶（地板梁）
Z_GEAR = Z_TIP - 0.1  # 我们的起落架舱顶
LIFT = 0.2  # 座舱设备（kc）相对均匀比例的抬高
ZF = Z_TIP + 0.03  # 座舱地板面
SRP = (6.15, Z_TIP + 0.25)  # 座椅参考点（椅面与椅背交线中点）：s、z；头盔顶离座舱盖内表面留约 4 cm（build 时打印）
BACK = math.radians(30)  # 椅背后倾（R3 反馈：约 30°）
GRIPS = {"R": at(5.98, -0.33, Z_TIP + 0.68), "L": at(6.0, 0.33, Z_TIP + 0.65)}  # 侧杆（右）、油门（左）握把中心：1.74 m 驾驶员半躺时手够得着的位置


def _interp(tab, x):
    if x <= tab[0][0]:
        return tab[0][1]
    for (x0, y0), (x1, y1) in zip(tab, tab[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return tab[-1][1]


def ks(x):
    return EYE["s"] + (x - K1_EYE[0]) / K1_PX


def kl(px):
    """K1 像素长度 → 米。"""
    return px / K1_PX


def keel(s):
    return ring(s)["R3"][1]


def k1(x, y, dy=0.0):
    """K1 像素 → 机体点（座舱以外的设备）：竖向按 K1 上下蒙皮线之间的比例放进我们的截面。"""
    s = ks(x)
    t, b = _interp(K1_TOP, x), _interp(K1_BOT, x)
    f = (b - y) / (b - t)
    zk, zt = keel(s), top_profile(s)
    return at(s, dy, zk + f * (zt - zk))


def kg(x, y, dy=0.0):
    """起落架舱与座舱地板以下：K1 地板梁 ↔ Z_GEAR，K1 下蒙皮 ↔ 龙骨。"""
    s = ks(x)
    b = _interp(K1_BOT, x)
    f = (b - y) / (b - K1_FLOOR)
    zk = keel(s)
    return at(s, dy, zk + f * (Z_GEAR - zk))


def kc(x, y, dy=0.0):
    """座舱设备：均匀比例 + LIFT。"""
    return at(ks(x), dy, Z_TIP + EYE["z"] + (K1_EYE[1] - y) / K1_PX + LIFT)


def S(p):
    """机体点 → 站位 s。"""
    return XN - p.x


def half_width(s, z, inset=SKIN + 0.015):
    """站位 s、高度 z 处内表面的半宽（截面左半边折线 R0→R1→R2→R3→腹底）。"""
    R = ring(s)
    chain = [R["R0"], R["R1"], R["R2"], R["R3"]]
    if z <= R["R3"][1] + inset:
        return 0.0
    for (y0, z0), (y1, z1) in zip(chain, chain[1:]):
        lo, hi = min(z0, z1), max(z0, z1)
        if lo <= z <= hi and hi > lo:
            y = y0 + (y1 - y0) * (z - z0) / (z1 - z0)
            return max(0.0, y - inset)
    if z > R["R0"][1]:
        return 0.0
    return max(0.0, R["R2"][0] - inset)


def fit(s0, s1, z0, z1, want):
    """箱体宽（y 向）：不超过 want，也不超过这块空间四角处内表面宽度的两倍。"""
    hw = min(half_width(s, z) for s in (s0, s1) for z in (z0, z1))
    return max(0.04, min(want, 2 * hw))


def inner_ring(s, inset=SKIN + 0.01):
    """站位 s 的内表面多边形（整圈，世界坐标），框和量空间用。"""
    R = ring(s)
    c = Vector((0, (R["R0"][1] + R["R3"][1]) / 2))
    pts = []
    for y, z in (R["R0"], R["R1"], R["R2"], R["R3"], (-R["R3"][0], R["R3"][1]), (-R["R2"][0], R["R2"][1]), (-R["R1"][0], R["R1"][1])):
        v = Vector((y, z))
        d = c - v
        v = v + d.normalized() * inset if d.length > inset else c
        pts.append(at(s, v.x, v.y))
    return pts


def collect(acc, item):
    """kit 函数返回 (obj, lines) / [(obj, lines)…] / (obj, lines, extra)，统一收进 acc。"""
    if isinstance(item, list):
        for it in item:
            collect(acc, it)
    elif len(item) == 3:
        acc.append(item[:2])
        for it in item[2]:
            acc.append(it)
    else:
        acc.append(item)


def kbox(acc, name, x0, y0, x1, y1, want=0.3, dy=0.0, mapper=None, **kw):
    """K1 上一个矩形（像素）→ 设备箱：中心按 mapper 映射，长、高按 220 px/m，宽按 fit()。"""
    m = mapper or k1
    c = m((x0 + x1) / 2, (y0 + y1) / 2, dy)
    L, H = kl(x1 - x0), kl(y1 - y0)
    s = S(c)
    w = fit(s - L / 2, s + L / 2, c.z - H / 2, c.z + H / 2, want)
    collect(acc, box(name, c, (L, w, H), props=P, **kw))
    return c, (L, w, H)


X = Vector((1, 0, 0))  # 朝机头
Y = Vector((0, 1, 0))  # 朝左（剖视时朝观众）
Z = Vector((0, 0, 1))


# —— 结构：隔框每约 0.5 m（K1 零件表的框站位 + 补齐）、远侧桁条、中线上下纵梁 ————————————————
FRAME_S = [0.56, 0.99, 1.51, 2.21, 2.65, 3.08, 3.49, 3.9, 4.03, 4.43, 4.84, 5.3, 5.8, 6.3, 6.67, 7.04, 7.4]  # K1 零件表里提到的框：2.19、3.10、4.06、4.84、5.75、7.04
CANOPY_OPEN = (4.84, 7.0)  # 座舱开口：这一段的隔框不封顶（U 形）


def frame_at(acc, s, tag):
    """一道隔框：沿内表面内缩的一圈板（剖视时近侧一半切掉，切口是实心剖面）；座舱开口段只做 U 形（不过屋面）；
    框缘上下各一排螺栓；中线处（背脊、龙骨）各一块横跨剖切面的连接块，剖开后露出框的实心截面。"""
    w = 0.05 if s > 1.2 else 0.03
    ring_ = list(reversed(inner_ring(s)))
    skip = set()
    if CANOPY_OPEN[0] - 0.01 <= s <= CANOPY_OPEN[1]:
        # reversed 顺序：[−R1, −R2, −R3, R3, R2, R1, R0]；边 k 连 k → k+1，R0 两侧的边（5、6）不做
        skip = {5, 6}
    pieces = frame(f"int.frame.{tag}", ring_, depth=0.03 if s > 1 else 0.02, width=w, material="structure", props=PC, skip=skip)
    collect(acc, pieces)
    ri = inner_ring(s, SKIN + 0.01 + w * 0.5)
    # 远侧（y < 0）框缘螺栓：下切面与外上切面两段
    for k, (i, j) in enumerate(((4, 5), (5, 6))):
        a, b = ri[i] + X * 0.016, ri[j] + X * 0.016
        n = max(2, int((b - a).length / 0.08))
        collect(acc, bolts(f"int.frame.{tag}.bolts{k}", a, b, n, 0.006, X, props=P))
    R = ring(s)
    zk = R["R3"][1] + SKIN
    collect(acc, hull(f"int.frame.{tag}.keel", [at(s + ds, dy, z) for ds in (-0.02, 0.02) for dy in (-0.05, 0.05) for z in (zk, zk + 0.07)], "structure", PC, bevel=0.004))
    if not skip:
        # 屋面是脊（金字塔前机身）：块的上表面顺着屋面坡度
        r0, r1 = inner_ring(s, SKIN + 0.004)[:2]
        slope = (r0.z - r1.z) / max(1e-6, r1.y - r0.y)
        collect(acc, hull(f"int.frame.{tag}.spine", [at(s + ds, dy, z) for ds in (-0.02, 0.02) for dy in (-0.05, 0.0, 0.05) for z in (r0.z - 0.07, r0.z - slope * abs(dy))], "structure", PC, bevel=0.004))


def structure(acc):
    for k, s in enumerate(FRAME_S):
        frame_at(acc, s, f"f{k}")
    # 远侧桁条（y < 0，贴着内表面）：朱红脊线角、棱线角、下切面中、腹缘角；座舱段的屋面桁条就是窗槛纵梁
    for k, (pick, t) in enumerate((("R1", None), ("R2", None), ("mid", None), ("R3", None))):
        pts = []
        for s in (0.75, S_FLAT_I, S_END - 0.02):
            ri = inner_ring(s, SKIN + 0.012)
            # ri 顺序 [R0, R1, R2, R3, −R3, −R2, −R1]
            if pick == "R1":
                p = ri[6]
            elif pick == "R2":
                p = ri[5]
            elif pick == "R3":
                p = ri[4]
            else:
                p = (ri[5] + ri[4]) / 2
            pts.append(p)
        for j, (a, b) in enumerate(zip(pts, pts[1:])):
            collect(acc, beam(f"int.stringer.{k}.{j}", a, b, 0.035, 0.03, Vector((0, 1, 0.4)), kind="angle", props=P))
    # 远侧内壁壁板（K1 的浅灰内衬）：每两道框之间、每个切面（远侧屋面、外上切面、下切面、腹底远侧半边）一块，
    # 离框 2.5 cm、离棱 2 cm，贴着内表面（离蒙皮内表面 6 mm）、厚 4 mm（不加螺钉：远侧压暗后看不见，省 2 千三角形守住模块预算；不烘顶点 AO（aoFlat）：八个顶点的板被前面的件一挡就整块发黑）。座舱开口段的屋面不做（那里是座舱盖）
    # ri 顺序 [R0, R1, R2, R3, −R3, −R2, −R1]：远侧的四个切面 = (−R1, R0)、(−R2, −R1)、(−R3, −R2)、(底中, −R3)
    for k, (sa, sb) in enumerate(zip(FRAME_S, FRAME_S[1:])):
        sa, sb = sa + 0.025, sb - 0.025
        if sb - sa < 0.15:
            continue
        ra, rb = inner_ring(sa, SKIN + 0.006), inner_ring(sb, SKIN + 0.006)
        bot = lambda r: Vector((r[3].x, 0.0, r[3].z))  # noqa: E731
        for j, (i0, i1) in enumerate(((6, 0), (5, 6), (4, 5), ("b", 4))):
            if j == 0 and sb > CANOPY_OPEN[0] - 0.05:
                continue
            q = []
            for r in (ra, rb):
                p0 = bot(r) if i0 == "b" else r[i0]
                p1 = r[i1]
                d = (p1 - p0).normalized()
                q.append((p0 + d * 0.02, p1 - d * 0.02))
            (a0, a1), (b0, b1) = q
            c = (a0 + a1 + b0 + b1) / 4
            n = (Vector((c.x, 0.0, (ring(XN - c.x)["R0"][1] + ring(XN - c.x)["R3"][1]) / 2)) - c).normalized()
            pts = [p + n * dd for p in (a0, a1, b0, b1) for dd in (0.0, 0.004)]
            collect(acc, hull(f"int.liner.{k}.{j}", pts, "liner", {**P, "lineLevel": "secondary", "aoFlat": True}, bevel=0.002))
    # 中线纵梁：龙骨（全长）与背脊（到座舱开口前），横跨剖切面，剖开后是实心截面
    for name, f, s0, s1, dz in (("keel", lambda s: ring(s)["R3"][1] + SKIN + 0.02, 0.8, S_END - 0.02, 1), ("spine", lambda s: ring(s)["R0"][1] - SKIN - 0.025, 0.8, CANOPY_OPEN[0] - 0.02, -1)):
        pts = [at(s, 0, f(s)) for s in (s0, min(S_FLAT_I, s1), s1)]
        for j, (a, b) in enumerate(zip(pts, pts[1:])):
            if (b - a).length > 0.05:
                collect(acc, beam(f"int.longeron.{name}.{j}", a, b, 0.06, 0.045, Z, kind="I", props=PC, holes=int((b - a).length / 0.15)))
    # 机柜舱上下横梁（K1 y 370 / 500）与眉骨后的斜撑
    collect(acc, beam("int.rack.top", k1(708, 371), k1(911, 368), 0.06, 0.04, Z, kind="channel", props=P, holes=6))
    collect(acc, beam("int.rack.shelf", k1(714, 501), k1(907, 501), 0.06, 0.035, Z, kind="channel", props=P, holes=6))
    collect(acc, beam("int.brow.strut", k1(1003, 358), k1(1080, 404), 0.06, 0.05, Y, kind="box", props=PC))
    # 起落架舱顶（地板梁，s 4.03～6.5）：中线一根长工字梁（剖开）+ 每道框一根横梁
    collect(acc, beam("int.gear.roof", at(ks(911), 0, Z_GEAR + 0.02), at(ks(1460), 0, Z_GEAR + 0.02), 0.08, 0.04, Z, kind="I", props=PC, holes=18))
    for k, s in enumerate(f for f in FRAME_S if ks(911) < f < ks(1460)):
        hw = half_width(s, Z_GEAR) - 0.01
        collect(acc, beam(f"int.gear.roofrib.{k}", at(s, -hw, Z_GEAR), at(s, hw, Z_GEAR), 0.04, 0.05, Z, kind="channel", props=PC))


def harness(acc):
    """线束：上下两根主干（远侧，沿桁条），每道隔框处一根支线沿框下到下干；两端都落在接线盒上（不悬空）。"""
    tops, bots = [], []
    for s in FRAME_S:
        if s < 0.9 or s > S_END - 0.1:
            continue
        ri = inner_ring(s, SKIN + 0.06)
        tops.append((s, ri[6] + Vector((0, 0.01, -0.03))))
        bots.append((s, ri[4] + Vector((0, 0.01, 0.04))))
    for name, pts, r in (("top", tops, 0.016), ("bot", bots, 0.018)):
        P3 = [p for _, p in pts]
        collect(acc, pipe(f"int.harness.{name}", P3, r, bend=0.1, sides=8, material="cable", props=P))
        # 两端接线盒
        for k, (s, p) in enumerate((pts[0], pts[-1])):
            collect(acc, box(f"int.harness.{name}.jbox{k}", p + Vector((0.04 if k == 0 else -0.04, 0.0, 0.0)), (0.08, 0.06, 0.06), material="avionics", face="+y", panel=False, handles=False, plugs=1, props=P, corner_bolts=True))
    for k, ((s, a), (_, b)) in enumerate(zip(tops, bots)):
        ri = inner_ring(s, SKIN + 0.07)
        mid = (ri[5] + Vector((0, 0.01, 0))) if s < CANOPY_OPEN[0] else (ri[5] + Vector((0, 0.03, 0)))
        collect(acc, pipe(f"int.harness.drop.{k}", [a + X * 0.04, mid + X * 0.04, b + X * 0.04], 0.008, bend=0.08, sides=6, material="cable", props=P))
        # 支线两端的插头、中间两只卡在框上的卡箍（轻量 8 边件，合成一个对象）
        fits = []
        for j, p in enumerate((a + X * 0.04, b + X * 0.04)):
            fits.append(cylinder(f"int.harness.drop.{k}.c{j}", p - X * 0.012, p + X * 0.012, 0.013, 8, "metal", P, bevel=0.0))
        for j, f in enumerate((0.33, 0.66)):
            p = (a.lerp(mid, f * 2) if f < 0.5 else mid.lerp(b, f * 2 - 1)) + X * 0.04
            d = ((mid - a) if f < 0.5 else (b - mid)).normalized()
            fits.append(cylinder(f"int.harness.drop.{k}.clip{j}", p - d * 0.006, p + d * 0.006, 0.0105, 8, "metal", P, bevel=0.0))
        collect(acc, merge(f"int.harness.drop.{k}.fittings", fits, material="metal", props={**P, "lineLevel": "secondary"}))


# —— 机头尖：眼珠座、传感器组 ② ——————————————————————————————————————
def nose_bay(acc):
    c = at(EYE["s"], 0, Z_TIP + EYE["z"])
    s_m = ks(130)
    # 眼珠后座：八角环座 + 驱动短轴（K1：眼后面的多边形座与伸出的短轴）
    collect(acc, frame("int.eye.mount", list(reversed(inner_ring(s_m, SKIN + 0.008))), depth=0.018, width=0.022, material="structure", props=P))
    collect(acc, cylinder("int.eye.shaft", at(EYE["s"] + 0.07, 0, c.z), at(ks(133), 0, c.z), 0.016, 14, "chrome", P))
    collect(acc, drum("int.eye.motor", at(ks(122), 0, c.z), at(ks(140), 0, c.z), 0.03, bands=1, material="avionics", props=P))
    collect(acc, bolts("int.eye.motor.bolts", at(ks(122) - 0.002, 0.02, c.z + 0.02), at(ks(122) - 0.002, -0.02, c.z - 0.02), 2, 0.004, -X, props=P))
    # 接线簇（K1 x 153～185）：小盒 + 两圈线
    cc, _ = kbox(acc, "int.nose.junction", 155, 437, 185, 458, want=0.1, face="+y", panel=False, handles=False, plugs=2)
    for k, dz in enumerate((0.03, -0.035)):
        collect(acc, pipe(f"int.nose.loom.{k}", [at(ks(135), 0.02 * (k - 0.5), c.z + dz * 0.5), at(ks(150), 0.03, cc.z + dz), at(ks(170), 0.04, cc.z + dz * 1.2), at(ks(195), 0.02, cc.z + dz * 0.4)], 0.006, material="cable", props=P))
    # ② 传感器组（K1 x 193～233）：侧面一个方窗 + 透镜；后面是处理盒（x 258～318，侧面圆镜头）
    c2, (L, w, H) = kbox(acc, "int.sensor.stack", 193, 432, 233, 463, want=0.16, face="+y", handles=False, plugs=0, corner_bolts=True)
    collect(acc, hull("int.sensor.stack.window", [c2 + Y * (w / 2 + d) + X * a * L * 0.22 + Z * b * H * 0.22 for a in (-1, 1) for b in (-1, 1) for d in (-0.002, 0.004)], "glass", {**P, "glass": True}, bevel=0.0015))
    collect(acc, cylinder("int.sensor.stack.lens", c2 + Y * (w / 2 + 0.004), c2 + Y * (w / 2 + 0.011), 0.011, 16, "glass", {**P, "glass": True}))
    c3, (L, w, H) = kbox(acc, "int.sensor.proc", 258, 433, 318, 463, want=0.18, face="+y", handles=False, plugs=0, corner_bolts=True)
    lens = c3 + X * (S(c3) - ks(282)) + Y * (w / 2)
    collect(acc, cylinder("int.sensor.proc.ring", lens - Y * 0.002, lens + Y * 0.012, kl(9), 24, "metal", P, bevel=0.002))
    collect(acc, cylinder("int.sensor.proc.lens", lens + Y * 0.008, lens + Y * 0.016, kl(6.5), 24, "glass", {**P, "glass": True}))
    # 框上的托架（K1 x 237～248 的竖向角码，x 320～343 的竖轨）
    for k, (x, y) in enumerate(((242, 436), (242, 462), (331, 438), (331, 461))):
        p = k1(x, y)
        collect(acc, bracket(f"int.nose.bracket.{k}", p, X if k < 2 else -X, Z, size=(0.04, 0.035, 0.03), props=P))
    collect(acc, beam("int.nose.rail", k1(331, 432), k1(331, 466), 0.02, 0.018, X, kind="channel", props=P))
    collect(acc, pipe("int.nose.bend", [k1(318, 445, 0.03), k1(330, 445, 0.03), k1(338, 455, 0.03), k1(338, 470, 0.03)], 0.007, props=P))


# —— ③ 姿控推进器组：2×2 推进剂罐、汇流管、阀、通往六个喷口的支管 ————————————————
def rcs_bay(acc):
    from .nose import facet_normal, surface

    tanks = []
    for k, y in enumerate((433.5, 463.5)):
        for j, dy in enumerate((0.062, -0.062)):
            a, b = k1(368, y, dy), k1(425, y, dy)
            collect(acc, tank(f"int.rcs.tank.{k}{j}", a, b, kl(11.5), bands=2, props=P))
            tanks.append((a, b))
    # 罐箍（两道扁带把四只罐捆在框上）
    for k, x in enumerate((380, 413)):
        s = ks(x)
        zc = (k1(x, 433.5).z + k1(x, 463.5).z) / 2
        rr = kl(11.5)
        pts = [at(s + ds, dy * (0.062 + rr + 0.006), zc + dz * (0.068 + rr + 0.006)) for ds in (-0.012, 0.012) for dy in (-1, 1) for dz in (-1, 1)]
        collect(acc, hull(f"int.rcs.strap.{k}", pts + [at(s + ds, 0, zc + dz * (0.068 + rr + 0.012)) for ds in (-0.012, 0.012) for dz in (-1, 1)], "metal", P, bevel=0.003))
    # 汇流管：四只罐前端的出口汇到一根横管，横管两端各一只阀，再分三路到每侧三个喷口
    s_m = ks(362)
    zc = (k1(362, 433.5).z + k1(362, 463.5).z) / 2
    for k, (a, _) in enumerate(tanks):
        collect(acc, pipe(f"int.rcs.out.{k}", [a + X * 0.002, a + X * 0.03, at(s_m, a.y * 0.6, zc)], 0.008, props=P))
    collect(acc, cylinder("int.rcs.manifold", at(s_m, 0.17, zc), at(s_m, -0.17, zc), 0.014, 12, "metal", P))
    for side in (1, -1):
        tag = "lr"[side < 0]
        collect(acc, valve(f"int.rcs.valve.{tag}", at(s_m, 0.12 * side, zc), Y * side, 0.012, props=P))
        for k, (facet, s, t) in enumerate((("outer", 1.38, 0.5), ("outer", 1.56, 0.5), ("lower", 1.47, 0.35))):
            port, n = surface(s, facet, t, side)
            port = port - n * 0.03
            collect(acc, pipe(f"int.rcs.feed.{k}.{tag}", [at(s_m, 0.17 * side, zc), at(s_m - 0.04, 0.2 * side, zc + (0.03 if facet == "outer" else -0.04)), port - n * 0.06, port], 0.008, props=P))
            collect(acc, box(f"int.rcs.thruster.{k}.{tag}", port - n * 0.03, (0.06, 0.05, 0.05), material="metal", face="+z", panel=False, handles=False, plugs=0, props=P))
    # K1 罐后：上罐出口弯管上行、下罐出口斜管下行，竖管 + 十字接头，T 形阀组（x 425～505）
    collect(acc, pipe("int.rcs.riser.up", [k1(425, 433.5, 0.03), k1(440, 433.5, 0.03), k1(452, 414, 0.03), k1(470, 405, 0.03), k1(520, 402, 0.03)], 0.009, props=P))
    collect(acc, pipe("int.rcs.riser.down", [k1(425, 463.5, -0.03), k1(440, 470, -0.03), k1(458, 490, -0.03), k1(520, 497, -0.03)], 0.009, props=P))
    collect(acc, pipe("int.rcs.vert", [k1(443, 421), k1(443, 491)], 0.008, props=P))
    collect(acc, connector("int.rcs.cross", k1(443, 460), Y, 0.011, length=0.03, props=P))
    for k, y in enumerate((425, 441, 460, 470)):
        collect(acc, pipe(f"int.rcs.run.{k}", [k1(400 if k in (1, 2) else 428, y, 0.05 - 0.03 * k), k1(505, y, 0.05 - 0.03 * k)], 0.0075 if k in (1, 2) else 0.009, props=P))
    collect(acc, drum("int.rcs.tvalve.body", k1(473, 475), k1(473, 421), 0.016, bands=2, props=P))
    collect(acc, valve("int.rcs.tvalve", k1(473, 431), Y, 0.011, props=P))
    collect(acc, valve("int.rcs.tvalve.low", k1(473, 468), X, 0.01, props=P, top=Y))


# —— ④ 航电舱前段：泵、主机箱、上下引管、阀组 ————————————————————————————
def avionics_fwd(acc):
    # 框 511 上下的托架盒（K1 x 505～518）
    kbox(acc, "int.f3.clip.top", 505, 384, 518, 419, want=0.08, face="+y", panel=False, handles=False, plugs=0, corner_bolts=True)
    kbox(acc, "int.f3.clip.bot", 505, 475, 518, 498, want=0.08, face="+y", panel=False, handles=False, plugs=0, corner_bolts=True)
    # 竖泵（x 525～536）+ 盘式泵（x 538～554，轴沿机身）
    collect(acc, tank("int.av.pump.v", k1(530, 483), k1(530, 421), kl(6), bands=2, material="metal", props=P))
    collect(acc, pump("int.av.pump", k1(546, 446), -X, kl(26), props=P))
    # 主机箱 ④（x 562～656，y 419～477）：铭牌、四角螺栓、三只插头、下部格栅
    c, (L, w, H) = kbox(acc, "int.av.main", 562, 419, 656, 477, want=0.28, face="+y", handles=True, plugs=3, label=True, corner_bolts=True, grille=3)
    # 中腰一道横向分缝（K1 y 450）
    collect(acc, hull("int.av.main.groove", [c + Y * (w / 2 + d) + X * a * L * 0.47 + Z * (k1(600, 450).z - c.z + b * 0.002) for a in (-1, 1) for b in (-1, 1) for d in (-0.001, 0.0015)], "void", {**P, "lineLevel": "secondary"}, bevel=0.0))
    # 上三根引管到上纵梁、下三根到下管排
    for k, x in enumerate((605, 625, 645)):
        top = k1(x, 392)
        collect(acc, pipe(f"int.av.up.{k}", [k1(x, 419, 0.06 - 0.06 * k), k1(x, 400, 0.06 - 0.06 * k), top + Y * (0.06 - 0.06 * k)], 0.008, props=P))
        collect(acc, connector(f"int.av.up.{k}.nut", k1(x, 419, 0.06 - 0.06 * k), Z, 0.009, length=0.025, props=P))
        collect(acc, pipe(f"int.av.down.{k}", [k1(x, 477, 0.06 - 0.06 * k), k1(x, 505, 0.06 - 0.06 * k)], 0.008, props=P))
        collect(acc, connector(f"int.av.down.{k}.nut", k1(x, 477, 0.06 - 0.06 * k), -Z, 0.009, length=0.025, props=P))
    # 阀组（x 657～692）：竖管 + 阀体 + 侧接头
    collect(acc, pipe("int.av.stack.pipe", [k1(668, 388), k1(668, 498)], 0.009, props=P))
    collect(acc, drum("int.av.stack.body", k1(668, 456), k1(668, 431), kl(10), bands=1, props=P))
    collect(acc, cylinder("int.av.stack.cap", k1(668, 433), k1(668, 428), kl(12), 16, "metal", P))
    collect(acc, connector("int.av.stack.side", k1(678, 445), -X, 0.012, length=0.035, props=P))
    collect(acc, pipe("int.av.stack.out", [k1(690, 445), k1(700, 445), k1(712, 455)], 0.008, props=P))


# —— 航电舱后段（机柜，s 3.1～3.95）与眉骨下 ————————————————————————————
def avionics_aft(acc):
    kbox(acc, "int.rack.a", 722, 410, 771, 470, want=0.6, face="+y", handles=True, plugs=3, label=True, corner_bolts=True)
    kbox(acc, "int.rack.b", 779, 398, 848, 469, want=0.6, face="+y", handles=True, plugs=4, label=True, corner_bolts=True, split=1)
    kbox(acc, "int.rack.a.low", 722, 476, 775, 498, want=0.5, face="+y", handles=False, plugs=2, label=True)
    kbox(acc, "int.rack.b.low", 801, 475, 851, 499, want=0.5, face="+y", handles=False, plugs=2, label=True)
    collect(acc, pump("int.rack.pump", k1(788, 486, 0.12), Y, kl(10), props=P))
    # 竖管 + 顶阀（x 857～870）
    collect(acc, pipe("int.rack.vpipe", [k1(863, 397), k1(863, 466), k1(870, 480), k1(870, 505)], 0.01, props=P))
    collect(acc, valve("int.rack.vvalve", k1(863, 386), Z, 0.012, props=P, top=Y))
    # 眉骨前框上的托架盒（x 903～918）
    kbox(acc, "int.f6.box", 903, 408, 918, 451, want=0.12, face="+y", panel=False, handles=False, plugs=0, corner_bolts=True)
    # 眉骨下的前设备箱（x 934～997）与两只遮光盾驱动作动筒（竖立，x 1018～1061）
    kbox(acc, "int.brow.box", 934, 408, 997, 451, want=0.35, face="+y", handles=True, plugs=3, label=True, corner_bolts=True)
    for k, x in enumerate((1027, 1051)):
        collect(acc, actuator(f"int.shield.drive.{k}", k1(x, 451, 0.1 - 0.2 * k), k1(x, 401, 0.1 - 0.2 * k), kl(8.5), ext=0.4, props=P))
        collect(acc, bracket(f"int.shield.drive.{k}.foot", k1(x, 455, 0.1 - 0.2 * k), Z, X, size=(0.06, 0.03, 0.05), props=P))
    collect(acc, pipe("int.brow.pipe", [k1(1003, 460), k1(1072, 460), k1(1085, 470)], 0.009, props=P))
    collect(acc, valve("int.brow.valve", k1(1017, 460), X, 0.01, props=P))
    collect(acc, pipe("int.brow.hyd.0", [k1(1027, 451, 0.1), k1(1027, 462, 0.1), k1(1040, 462, 0.05)], 0.006, props=P))
    collect(acc, pipe("int.brow.hyd.1", [k1(1051, 451, -0.1), k1(1051, 462, -0.1), k1(1040, 462, -0.05)], 0.006, props=P))


# —— ⑭ 前起落架舱（收起，机轮朝前）——————————————————————————————————————
def gear_bay(acc):
    wheel = kg(1084, 537)
    r = kl(33)
    collect(acc, lathe("int.gear.tyre", wheel - Y * 0.065, wheel + Y * 0.065, [(0.0, r * 0.62), (0.08, r * 0.9), (0.25, r), (0.75, r), (0.92, r * 0.9), (1.0, r * 0.62)], 32, "rubber", P))
    collect(acc, cylinder("int.gear.hub", wheel - Y * 0.07, wheel + Y * 0.07, kl(15), 24, "metal", P))
    collect(acc, cylinder("int.gear.hubcap", wheel + Y * 0.07, wheel + Y * 0.078, kl(9), 18, "chrome", P))
    collect(acc, bolts("int.gear.hub.bolts", wheel + Y * 0.072 + Z * kl(12), wheel + Y * 0.072 - Z * kl(12), 2, 0.005, Y, props=P))
    pivot = kg(1200, 552)
    collect(acc, cylinder("int.gear.strut", pivot, wheel + (pivot - wheel).normalized() * kl(12), 0.045, 18, "metal", P))
    collect(acc, cylinder("int.gear.oleo", wheel + (pivot - wheel).normalized() * kl(14), wheel + (pivot - wheel).normalized() * kl(40), 0.034, 16, "chrome", P))
    collect(acc, cylinder("int.gear.trunnion", pivot - Y * 0.11, pivot + Y * 0.11, 0.035, 16, "metal", P))
    for k, (a, b) in enumerate(((kg(1118, 490), kg(1160, 528)), (kg(1122, 497), kg(1200, 552)))):
        collect(acc, cylinder(f"int.gear.brace.{k}", a + Y * (0.05 - 0.1 * k), b + Y * (0.05 - 0.1 * k), 0.018, 12, "metal", P))
    collect(acc, actuator("int.gear.retract", kg(1003, 534, -0.06), wheel + X * 0.0 - Y * 0.06 + (pivot - wheel).normalized() * 0.1, kl(8), ext=0.2, props=P))
    collect(acc, bracket("int.gear.retract.foot", kg(1003, 534, -0.06) + X * 0.02, -X, Z, size=(0.05, 0.05, 0.04), props=P))
    # 液压与阀组（x 930～990）、舱顶横管
    collect(acc, pipe("int.gear.vpipe", [kg(934, 489), kg(934, 520), kg(945, 528)], 0.009, props=P))
    kbox(acc, "int.gear.valvebox", 945, 510, 968, 528, want=0.1, mapper=kg, face="+y", panel=False, handles=False, plugs=2, corner_bolts=True)
    kbox(acc, "int.gear.hydunit", 968, 522, 988, 539, want=0.12, mapper=kg, face="+y", panel=False, handles=False, plugs=0, label=True)
    collect(acc, pipe("int.gear.roofpipe", [kg(949, 500), kg(1072, 500), kg(1100, 504)], 0.009, props=P))
    collect(acc, pipe("int.gear.lowpipe", [kg(941, 531), kg(1003, 531)], 0.008, props=P))
    collect(acc, tank("int.gear.accumulator", kg(1150, 510, -0.12), kg(1215, 510, -0.12), 0.045, bands=1, props=P))
    # 舱门作动筒（舱底两侧，收起）
    for k, x in enumerate((1260, 1400)):
        collect(acc, actuator(f"int.gear.door.{k}", kg(x, 575, -0.1), kg(x + 60, 560, -0.1), 0.018, ext=0.1, props=P))


# —— 座舱（真人尺寸）——————————————————————————————————————————————————
def cockpit(acc):
    s_b = ks(1090)
    # 地板（s 5.3～7.0）+ 地板下三根横梁 + 脚踏斜板（前壁上沿斜到地板，K1 的斜地板）
    w = 0.8
    collect(acc, hull("int.cp.floor", [at(s, y, ZF + dz) for s in (5.3, 6.98) for y in (w / 2, -w / 2) for dz in (0, -0.02)], "structure", PC, bevel=0.004))
    for k, s in enumerate((5.6, 6.1, 6.6)):
        collect(acc, beam(f"int.cp.floorbeam.{k}", at(s, 0.36, ZF - 0.07), at(s, -0.36, ZF - 0.07), 0.05, 0.1, Z, kind="I", props=P))
    for k, s in enumerate((5.4, 5.9, 6.4, 6.9)):
        collect(acc, beam(f"int.cp.subpost.{k}", at(s, -0.3, Z_GEAR + 0.04), at(s, -0.3, ZF - 0.12), 0.03, 0.03, X, kind="angle", props=P))
    collect(acc, hull("int.cp.footwell", [at(s, y, z + dz) for s, z in ((s_b + 0.04, Z_TIP + 0.42), (5.34, ZF)) for y in (0.36, -0.36) for dz in (0, -0.02)], "structure", PC, bevel=0.004))
    # 座舱远侧侧壁（K1 驾驶员身后那片深色舱壁）：按框分成四块壁板，每块内缩 1 cm、四角螺钉，中间一道横向加强筋
    edges = [5.4, 5.8, 6.3, 6.67, 6.96]  # 屏幕墙（s 5.07～5.4）之后才开始，不挡屏幕
    zt = Z_TIP + 0.9
    for k, (sa, sb_) in enumerate(zip(edges, edges[1:])):
        hw = min(half_width(ss, zz) for ss in (sa, sb_) for zz in (ZF + 0.01, zt))
        yw = -min(0.41, hw - 0.012)
        pts = [at(ss, yw + d, zz) for ss in (sa + 0.012, sb_ - 0.012) for zz in (ZF + 0.012, zt) for d in (0.0, -0.01)]
        collect(acc, hull(f"int.cp.wall.{k}", pts, "liner", {**P, "aoFlat": True}, bevel=0.003))
        collect(acc, beam(f"int.cp.wall.{k}.rib", at(sa + 0.03, yw + 0.012, Z_TIP + 0.47), at(sb_ - 0.03, yw + 0.012, Z_TIP + 0.47), 0.024, 0.03, Y, kind="angle", props=P))
        for zz in (ZF + 0.04, zt - 0.03):
            collect(acc, bolts(f"int.cp.wall.{k}.bolts{int(zz > Z_TIP + 0.5)}", at(sa + 0.03, yw + 0.001, zz), at(sb_ - 0.03, yw + 0.001, zz), 2, 0.005, Y, props=P))
    # 前仪表：⑪ 环形屏幕墙（五块，圆心在 s 5.55、半径 0.48，后仰 10°）+ 遮光罩 + ⑩ 平视显示器
    R, sc = 0.48, 5.55
    z0, z1 = Z_TIP + 0.5, Z_TIP + 0.92
    for k in range(5):
        a0, a1 = math.radians(-64 + 25.6 * k + 0.6), math.radians(-64 + 25.6 * (k + 1) - 0.6)
        pts_bezel, pts_face = [], []
        for a in (a0, a1):
            for z, tilt in ((z0, 0.0), (z1, (z1 - z0) * math.tan(math.radians(10)))):
                for d, lst in ((0.0, pts_face), (0.012, pts_face), (0.012, pts_bezel), (0.05, pts_bezel)):
                    rr = R + d - tilt
                    lst.append(at(sc - rr * math.cos(a), rr * math.sin(a), z))
        collect(acc, hull(f"int.cp.display.{k}.case", pts_bezel, "interior", PC, bevel=0.004))
        # 屏面比外框内缩 1.5 cm
        mid = sum(pts_face, Vector()) / len(pts_face)
        face = [mid + (p - mid) * Vector((1.0, 0.86, 0.9)) for p in pts_face]
        collect(acc, hull(f"int.cp.display.{k}", face, "screen", {**PC, "glow": {"key": "cockpit", "color": "#7bdbec"}}, bevel=0.0015))
    collect(acc, hull("int.cp.coaming", [at(sc - (R + 0.06) * math.cos(a), (R + 0.06) * math.sin(a), z) for a in (math.radians(-48), 0.0, math.radians(48)) for z in (z1, z1 + 0.04)] + [at(sc - (R - 0.06) * math.cos(a), (R - 0.06) * math.sin(a), z1 + 0.035) for a in (math.radians(-40), 0.0, math.radians(40))], "interior", PC, bevel=0.008))
    hs = sc - R + 0.08
    collect(acc, box("int.cp.hud.projector", at(hs, 0, z1 + 0.06), (0.12, 0.16, 0.05), material="interior", face="+z", panel=False, handles=False, plugs=0, props=P))
    collect(acc, hull("int.cp.hud", [at(hs + 0.02 + t * 0.06, y, z1 + 0.09 + t * 0.12 + d) for t in (0, 1) for y in (0.075, -0.075) for d in (0, 0.004)], "glass", {**P, "glass": True, "glow": {"key": "cockpit.hud", "color": "#7bdbec"}}, bevel=0.001))
    collect(acc, hull("int.cp.hud.frame", [at(hs + 0.015 + t * 0.06, y, z1 + 0.085 + t * 0.12) for t in (0, 1) for y in (0.08, -0.08)] + [at(hs + 0.015 + t * 0.06 - 0.008, y, z1 + 0.085 + t * 0.12) for t in (0, 1) for y in (0.08, -0.08)], "frame", P, bevel=0.0015))
    # 脚下的红灯单元（K1 屏幕下那块红色格栅）
    collect(acc, box("int.cp.redunit", at(5.2, 0.25, ZF + 0.2), (0.12, 0.07, 0.07), material="vermilion", face="+y", panel=False, handles=False, plugs=0, ears=False, props={**P, "glow": {"key": "cockpit.red", "color": "#c8412c"}}, grille=2))
    # 两侧操纵台（左油门、右侧杆），台面两块小面板 + 侧杆 / 油门柄
    for side, name in ((-1, "stick"), (1, "throttle")):
        y0 = 0.33 * side
        if side < 0:  # 近侧（左）操纵台剖视时挡住驾驶员，只做远侧这一台；左边只留扶手和油门座
            collect(acc, box(f"int.cp.console.{name}", at(5.95, y0 + 0.04 * side, Z_TIP + 0.42), (0.9, 0.12, 0.2), material="interior", face="+z", handles=False, plugs=0, props=P, split=1, corner_bolts=True))
        else:
            collect(acc, box(f"int.cp.console.{name}", at(6.0, y0 + 0.04 * side, Z_TIP + 0.51), (0.36, 0.1, 0.06), material="interior", face="+z", panel=False, handles=False, plugs=0, props=P))
        collect(acc, beam(f"int.cp.armrest.{name}", at(6.42, y0, Z_TIP + 0.56), at(6.1, y0, Z_TIP + 0.56), 0.07, 0.03, Z, kind="box", props=P))
    base = GRIPS["R"] - Z * 0.16 - X * 0.02
    collect(acc, cylinder("int.cp.stick.boot", base, base + Z * 0.04, 0.03, 14, "rubber", P, r2=0.018))
    collect(acc, cylinder("int.cp.stick", base + Z * 0.03, base + Z * 0.12 + X * 0.01, 0.011, 10, "metal", P))
    collect(acc, hull("int.cp.stick.grip", [base + Z * (0.11 + dz) + X * (0.01 + dx) + Y * dy for dx in (-0.025, 0.02) for dy in (-0.018, 0.018) for dz in (0, 0.1)] + [base + Z * 0.215 + X * 0.03 + Y * dy for dy in (-0.012, 0.012)], "rubber", P, bevel=0.008))
    base = GRIPS["L"] - Z * 0.10 + X * 0.025
    collect(acc, hull("int.cp.throttle.slot", [base + X * dx + Y * dy + Z * dz for dx in (-0.12, 0.12) for dy in (-0.012, 0.012) for dz in (-0.004, 0.003)], "void", {**P, "lineLevel": "secondary"}, bevel=0.0))
    collect(acc, cylinder("int.cp.throttle", base, base + Z * 0.08 - X * 0.02, 0.01, 10, "metal", P))
    collect(acc, hull("int.cp.throttle.grip", [base + Z * (0.07 + dz) - X * (0.02 + dx) + Y * dy for dx in (-0.03, 0.04) for dy in (-0.025, 0.02) for dz in (0, 0.06)], "rubber", P, bevel=0.008))
    # ⑬ 头顶开关板：挂在座舱盖弓形框下（s 5.85）
    collect(acc, box("int.cp.overhead", at(5.85, 0, Z_TIP + 1.17), (0.16, 0.36, 0.035), material="interior", face="+z", panel=True, handles=False, plugs=0, ears=False, props=P, split=2))
    # 开关板下沿一排指示灯（只有这一条发青光）
    collect(acc, hull("int.cp.overhead.lamps", [at(5.85 + dx, y, Z_TIP + 1.17 - 0.0175 - dz) for dx in (-0.05, -0.04) for y in (-0.14, 0.14) for dz in (0.0, 0.003)], "screen", {**P, "glow": {"key": "cockpit", "color": "#7bdbec"}}, bevel=0.0))
    return seat_and_pilot(acc)


def _sz(s, z, y=0.0):
    return at(s, y, z)


def seat_and_pilot(acc):
    """⑨ 弹射座椅与 ⑧ 驾驶员（真人尺寸）。坐标系：b 沿椅背向后上，n 朝前上（垂直椅背），y 朝左。"""
    s0, z0 = SRP
    sb, cb = math.sin(BACK), math.cos(BACK)

    def p(along, normal, y=0.0):
        """椅背坐标（沿椅背 along、离椅背 normal）→ 机体点。"""
        return at(s0 + along * sb - normal * cb, y, z0 + along * cb + normal * sb)

    def pan(fwd, up, y=0.0):
        """椅面坐标（向前 fwd、向上 up，椅面前沿上翘 8°）→ 机体点。"""
        a = math.radians(8)
        return at(s0 - fwd * math.cos(a) + up * math.sin(a) * 0.0, y, z0 + fwd * math.sin(a) + up)

    # 椅盆（坐垫 + 底壳）、两侧板、椅背垫、头靠箱（伞包）、头枕、两根导轨、弹射筒、背后装甲板、拉环
    collect(acc, hull("int.seat.cushion", [pan(f, u, y) for f in (0.02, 0.44) for u in (-0.01, 0.06) for y in (0.2, -0.2)], "seat", P, bevel=0.025))
    collect(acc, hull("int.seat.pan", [pan(f, u, y) for f in (-0.02, 0.48) for u in (-0.09, -0.01) for y in (0.23, -0.23)], "metal", P, bevel=0.01))
    for side in (1, -1):
        y = 0.245 * side
        # 近侧（剖视朝观众的一侧）侧板只到坐垫上沿，不挡驾驶员
        top = 0.42 if side < 0 else 0.12
        pts = [pan(f, u, y + d) for f in (-0.02, 0.4) for u in (-0.09, 0.08 if side < 0 else 0.03) for d in (0, -0.012 * side)] + [p(a, n, y + d) for a in (0.0, top) for n in (0.0, 0.14) for d in (0, -0.012 * side)]
        collect(acc, hull(f"int.seat.side.{'lr'[side < 0]}", pts, "seat", P, bevel=0.006))
    collect(acc, hull("int.seat.back", [p(a, n, y) for a in (0.04, 0.7) for n in (0.0, 0.07) for y in (0.2, -0.2)], "seat", P, bevel=0.025))
    collect(acc, hull("int.seat.backshell", [p(a, n, y) for a in (-0.02, 0.74) for n in (-0.06, 0.0) for y in (0.23, -0.23)], "metal", P, bevel=0.008))
    collect(acc, box("int.seat.headbox", p(0.87, -0.02), (0.11, 0.38, 0.24), rot=_rot_back(), material="seat", face="+y", panel=True, handles=False, plugs=0, props=P, label=True, corner_bolts=True))
    collect(acc, hull("int.seat.headrest", [p(a, n, y) for a in (0.76, 0.95) for n in (0.04, 0.1) for y in (0.11, -0.11)], "seat", P, bevel=0.02))
    for side in (1, -1):
        collect(acc, beam(f"int.seat.rail.{'lr'[side < 0]}", p(-0.38, -0.2, 0.19 * side), p(1.0, -0.2, 0.19 * side), 0.05, 0.04, Vector((-cb, 0, sb)) * -1, kind="channel", props=P, holes=7))
        # 椅背到导轨的连接耳（上中下三对）
        for k, a in enumerate((0.1, 0.45, 0.8)):
            collect(acc, hull(f"int.seat.lug.{k}.{'lr'[side < 0]}", [p(a + da, n, 0.19 * side + dy) for da in (-0.04, 0.04) for n in (-0.06, -0.18) for dy in (-0.012, 0.012)], "metal", P, bevel=0.004))
    collect(acc, tank("int.seat.catapult", p(-0.3, -0.13), p(0.82, -0.13), 0.045, bands=3, material="metal", props=P))
    collect(acc, hull("int.seat.armour", [p(a, -0.36, y) for a in (0.15, 1.0) for y in (0.26, -0.26)] + [p(a, -0.4, y) for a in (0.15, 1.0) for y in (0.26, -0.26)], "structure", P, bevel=0.006))
    collect(acc, hull("int.seat.armour.slot", [p(a, -0.355 + d, y) for a in (0.45, 0.85) for y in (0.06, -0.06) for d in (0.0, 0.004)], "void", {**P, "lineLevel": "secondary"}, bevel=0.0))
    for side in (1, -1):
        collect(acc, beam(f"int.seat.armour.strut.{'lr'[side < 0]}", p(0.3, -0.22, 0.2 * side), p(0.3, -0.36, 0.2 * side), 0.03, 0.03, _v(sb, cb), kind="box", props=P))
        collect(acc, beam(f"int.seat.armour.strut2.{'lr'[side < 0]}", p(0.9, -0.22, 0.2 * side), p(0.9, -0.36, 0.2 * side), 0.03, 0.03, _v(sb, cb), kind="box", props=P))
    # 座椅底架到地板的两根支腿（K1 椅下的斜撑）
    for side in (1, -1):
        collect(acc, beam(f"int.seat.leg.{'lr'[side < 0]}", pan(0.3, -0.09, 0.18 * side), at(s0 - 0.2, 0.18 * side, ZF + 0.005), 0.04, 0.03, X, kind="box", props=P))
    collect(acc, pipe("int.seat.handle", [pan(0.46, -0.02, 0.07), pan(0.5, 0.06, 0.07), pan(0.5, 0.06, -0.07), pan(0.46, -0.02, -0.07)], 0.009, bend=0.02, material="hazard", props=P))

    # —— ⑧ 驾驶员「銜燭」软态：开源人体基础网格摆姿 + 服装（blender/zl/pilot.py）——
    t8 = math.radians(8)
    seat = {
        "srp": np.array(at(s0, 0, z0)), "back": BACK, "back_n": 0.07, "pan_h": 0.06, "knee": math.radians(112),
        "feet": {"L": np.array(at(5.32, 0.14, Z_TIP + 0.2)), "R": np.array(at(5.32, -0.14, Z_TIP + 0.2))},
        "foot_dir": np.array([0.75, 0.0, 0.66]),
        "grips": {s_: np.array(GRIPS[s_]) for s_ in "LR"},
        "hand_dir": {"R": np.array([0.92, 0.18, -0.3]), "L": np.array([0.92, -0.18, -0.25])},
        "knuckles": {"R": np.array([0.0, 0.0, -1.0]), "L": np.array([0.0, 0.0, -1.0])},
        "palm": {"R": np.array([0.0, 1.0, 0.0]), "L": np.array([0.0, -1.0, 0.0])},
        "seat_side": {"L": pan(0.12, 0.08, 0.235), "R": pan(0.12, 0.08, -0.235)},
    }
    parts, J, seams = pilot.build(seat, P)
    collect(acc, parts)
    SEAMS.extend(seams)
    # 脚蹬：贴在两只脚掌下（踏板随人调），踏板臂落到脚蹬斜板上
    f = Vector(seat["foot_dir"]).normalized()
    n = Vector((f.z, 0.0, -f.x))  # 脚底朝向（前下）
    for side in "LR":
        ank = J[f"ankle.{side}"]
        c = ank + f * 0.08 + n * 0.085
        tag = side.lower()
        collect(acc, hull(f"int.cp.pedal.{tag}", [c + f * a + Y * b + n * d for a in (-0.11, 0.11) for b in (-0.05, 0.05) for d in (0.0, 0.022)], "metal", P, bevel=0.004))
        collect(acc, beam(f"int.cp.pedal.{tag}.arm", c + n * 0.02, Vector((c.x, c.y, ZF + 0.01)), 0.03, 0.025, X, kind="box", material="metal", props=P))
    head = J["head"]
    # 头盔顶离座舱盖内表面（玻璃厚 1.2 cm）
    from .nose import CANOPY

    top = J["helmet_top"]
    st = S(top)
    for a_, b_ in zip(CANOPY, CANOPY[1:]):
        if a_[0] <= st <= b_[0]:
            zc = Z_TIP + lerp(a_[1], b_[1], (st - a_[0]) / (b_[0] - a_[0])) - 0.012
            print(f"  头盔顶 s {st:.2f} z {top.z:.3f} · 离座舱盖内表面 {100 * (zc - top.z):.1f} cm")
    return head, p(0.87, -0.02)


def _v(a, b):
    """(沿 s, 沿 z) 方向 → 机体向量（s 向后 = −x）。"""
    return Vector((-a, 0, b)).normalized()


def _rot_back():
    """box() 的旋转：箱子 x 轴取椅背法向（朝前上），z 轴沿椅背。"""
    from mathutils import Matrix

    sb, cb = math.sin(BACK), math.cos(BACK)
    xa = Vector((cb, 0, sb))  # 朝前上（−s 方向为 +x）
    za = Vector((-sb, 0, cb))
    ya = za.cross(xa)
    return Matrix((xa, ya, za)).transposed()


# —— 座椅后：斜撑作动筒、头顶软管、竖管、横管、斜隔板；座舱下后设备舱 ——————————————————
def aft_bay(acc):
    collect(acc, actuator("int.aft.canopy.act", kc(1600, 330, -0.12), kc(1672, 268, -0.12), 0.022, ext=0.5, props=P))
    collect(acc, pipe("int.aft.hose", [kc(1496, 300, -0.16), kc(1540, 284, -0.16), kc(1580, 276, -0.16), kc(1579, 310, -0.16)], 0.014, bend=0.04, material="cable", props=P))
    for k, x in enumerate((1655, 1668, 1684)):
        collect(acc, pipe(f"int.aft.vpipe.{k}", [kc(x, 385, -0.2 + 0.06 * k), kc(x, 302 + 8 * k, -0.2 + 0.06 * k)], 0.01, props=P))
        collect(acc, connector(f"int.aft.vpipe.{k}.nut", kc(x, 330 + 10 * k, -0.2 + 0.06 * k), Z, 0.011, length=0.03, props=P))
    collect(acc, pipe("int.aft.hpipe", [kc(1575, 400, -0.28), kc(1696, 400, -0.28)], 0.016, props=P))
    for k, x in enumerate((1600, 1630, 1660)):
        collect(acc, clamp(f"int.aft.hpipe.c{k}", kc(x, 400, -0.28), X, 0.016, props=P))
    collect(acc, hull("int.aft.deck", [kc(x, y, yy) + Z * dz for x, y in ((1525, 493), (1696, 434)) for yy in (0.36, -0.36) for dz in (0, -0.02)], "structure", PC, bevel=0.004))  # 跨剖切面：要切开（否则近侧半块悬在剖切面外）
    # 地板下后设备舱（s 6.4～7.6）：两只箱 + 一排线束
    for k, (x0, x1) in enumerate(((1440, 1530), (1580, 1680))):
        kbox(acc, f"int.aft.box.{k}", x0, 515, x1, 580, want=0.4, mapper=kg, face="+y", handles=True, plugs=3, label=True, corner_bolts=True, split=k)
    collect(acc, pipe("int.aft.loom", [kg(1420, 505, -0.1), kg(1696, 505, -0.1)], 0.018, material="cable", props=P))


def build():
    acc = []
    SEAMS.clear()
    structure(acc)
    harness(acc)
    nose_bay(acc)
    rcs_bay(acc)
    avionics_fwd(acc)
    avionics_aft(acc)
    gear_bay(acc)
    head, headbox = cockpit(acc)
    aft_bay(acc)
    # K1 零件表里几何母版还没有的件（管线按表的路径重铺，原来的近似管排已删）
    n = k1table.build(acc, sys.modules[__name__])
    print(f"K1 零件表补建 {n} 件")
    # 小件（螺栓、接头、卡箍、铭牌……）的线一律降为次级线：三级线宽读得出来
    for o, _ in acc:
        if o.get("lineLevel") == "structure":
            d = o.dimensions
            if max(d) < 0.05:
                o["lineLevel"] = "secondary"
    # 只要 S_END 以内的（K1 画得比机头段长）
    empty = [o.name for o, _ in acc if not len(o.data.vertices)]
    if empty:
        print("  空对象（丢掉）:", " ".join(empty))
    acc = [(o, l) for o, l in acc if len(o.data.vertices) and min(XN - v.co.x for v in o.data.vertices) < S_END - 0.01]
    callouts = [
        {"n": 2, "label": "传感器组（光电 / 红外 / 射频 / 激光雷达）", "at": list(k1(213, 447))},
        {"n": 3, "label": "机头姿控推进器组", "at": list(k1(396, 433.5, 0.06))},
        {"n": 4, "label": "航电舱", "at": list(k1(609, 432))},
        {"n": 8, "label": "驾驶员（压力服，半躺约 30°）", "at": list(head)},
        {"n": 9, "label": "弹射座椅（导轨）", "at": list(headbox)},
        {"n": 10, "label": "平视显示器", "at": list(at(5.55 - 0.48 + 0.12, 0, Z_TIP + 1.05))},
        {"n": 11, "label": "环形屏幕墙", "at": list(at(5.2, 0.3, Z_TIP + 0.72))},
        {"n": 12, "label": "侧杆（右）/ 油门（左）", "at": list(at(5.84, 0.33, Z_TIP + 0.66))},
        {"n": 13, "label": "头顶开关板", "at": list(at(5.85, 0, Z_TIP + 1.16))},
        {"n": 14, "label": "前起落架舱", "at": list(kg(1280, 504))},
    ]
    return acc, callouts
