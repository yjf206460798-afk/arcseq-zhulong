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

from mathutils import Vector

from kit.parts import actuator, beam, bolts, box, bracket, clamp, connector, cylinder, ellipsoid, frame, hull, lathe, merge, pipe, pump, tank, valve

from .nose import EYE, S_END, Z_TIP, at, ring, top_profile
from .util import XN, lerp

SKIN = 0.035  # 蒙皮厚（剖面带的宽）
P = {"module": "interior", "lineLevel": "structure"}
PC = {**P, "cut": True}  # 剖切面上被切开的内部件（屏幕墙、地板……K1 里近侧一半是剖掉的）

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
SRP = (6.15, Z_TIP + 0.31)  # 座椅参考点（椅面与椅背交线中点）：s、z
BACK = math.radians(33)  # 椅背后倾


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


# —— 结构 ——————————————————————————————————————————————————————————
INNER_FRAMES = [  # (K1 x, 板宽, 名) K1 里的竖向舱壁 / 框
    (148, 0.025, "f0"), (242, 0.03, "f1"), (356, 0.035, "f2"), (511, 0.045, "f3"), (701, 0.05, "f4"),
    (882, 0.05, "f5"), (910, 0.05, "f6"), (1090, 0.06, "f7"),
]


def structure(acc):
    for x, w, tag in INNER_FRAMES:
        s = ks(x)
        collect(acc, frame(f"int.frame.{tag}", list(reversed(inner_ring(s))), depth=0.03 if s > 1 else 0.02, width=w, material="structure", props=P))
        # 框缘一圈螺栓（只在上下两段，K1 里看得见的那几排）
        ri = inner_ring(s, SKIN + 0.01 + w * 0.5)
        for k, (i, j) in enumerate(((0, 1), (3, 4))):
            a, b = ri[i] + X * 0.016, ri[j] + X * 0.016
            n = max(2, int((b - a).length / 0.07))
            collect(acc, bolts(f"int.frame.{tag}.bolts{k}", a, b, n, 0.006, X, props=P))
    # 上纵梁（K1：机头段顶上一根工字梁，s 0.9 起沿顶线到眉骨前框）与下纵梁（龙骨内侧）
    pts = [k1(x, y) for x, y in ((250, 418), (511, 393), (701, 373), (882, 353))]
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        collect(acc, beam(f"int.longeron.top.{k}", a, b, 0.05, 0.05, Z, kind="I", props=P, holes=int((b - a).length / 0.12)))
    pts = [k1(x, y) for x, y in ((250, 476), (511, 503), (701, 528), (882, 543))]
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        collect(acc, beam(f"int.longeron.bot.{k}", a, b, 0.05, 0.045, Z, kind="channel", props=P, holes=int((b - a).length / 0.14)))
    # 机柜舱上下横梁（K1 y 370 / 500，s 3.1～3.95）与眉骨后的斜撑（座舱前风挡框下的斜梁）
    collect(acc, beam("int.rack.top", k1(708, 371), k1(911, 368), 0.06, 0.04, Z, kind="channel", props=P, holes=6))
    collect(acc, beam("int.rack.shelf", k1(714, 501), k1(907, 501), 0.06, 0.035, Z, kind="channel", props=P, holes=6))
    collect(acc, beam("int.brow.strut", k1(1003, 358), k1(1080, 404), 0.06, 0.05, Y, kind="box", props=P))
    # 起落架舱顶（地板梁，K1 y 478，s 4.03～6.5）：一根长工字梁 + 远侧舱壁板与斜撑
    collect(acc, beam("int.gear.roof", at(ks(911), 0, Z_GEAR + 0.02), at(ks(1460), 0, Z_GEAR + 0.02), 0.08, 0.04, Z, kind="I", props=P, holes=18))
    for k, (x0, x1) in enumerate(((911, 1226), (1226, 1460), (1460, 1690))):
        s0, s1 = ks(x0), ks(x1)
        zb = max(keel(s0), keel(s1)) + 0.04
        y = -min(half_width(s0, zb + 0.01), half_width(s1, zb + 0.01)) + 0.012
        collect(acc, hull(f"int.bay.wall.{k}", [at(s, y + d, z) for s in (s0 + 0.01, s1 - 0.01) for d in (0, -0.008) for z in (zb, Z_GEAR)], "backwall", P, bevel=0.003))
        # 板上的交叉斜撑（K1 舱壁上的 X）
        for j, (za, zb_) in enumerate(((zb + 0.02, Z_GEAR - 0.02), (Z_GEAR - 0.02, zb + 0.02))):
            collect(acc, beam(f"int.bay.brace.{k}.{j}", at(s0 + 0.03, y + 0.02, za), at(s1 - 0.03, y + 0.02, zb_), 0.03, 0.02, Y, kind="angle", props=P))
    for k, x in enumerate((1226, 1310, 1428, 1565)):
        s = ks(x)
        collect(acc, beam(f"int.bay.post.{k}", at(s, -0.05, keel(s) + 0.03), at(s, -0.05, Z_GEAR), 0.05, 0.04, X, kind="channel", props=P, holes=3))


# —— 机头尖：眼珠座、传感器组 ② ——————————————————————————————————————
def nose_bay(acc):
    c = at(EYE["s"], 0, Z_TIP + EYE["z"])
    s_m = ks(130)
    # 眼珠后座：八角环座 + 驱动短轴（K1：眼后面的多边形座与伸出的短轴）
    collect(acc, frame("int.eye.mount", list(reversed(inner_ring(s_m, SKIN + 0.008))), depth=0.018, width=0.022, material="structure", props=P))
    collect(acc, cylinder("int.eye.shaft", at(EYE["s"] + 0.07, 0, c.z), at(ks(133), 0, c.z), 0.016, 14, "chrome", P))
    collect(acc, cylinder("int.eye.motor", at(ks(122), 0, c.z), at(ks(140), 0, c.z), 0.03, 18, "avionics", P))
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
    collect(acc, cylinder("int.rcs.tvalve.body", k1(473, 475), k1(473, 421), 0.016, 14, "metal", P))
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
    collect(acc, cylinder("int.av.stack.body", k1(668, 456), k1(668, 431), kl(10), 16, "metal", P))
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


# —— 管排：顶上两根、底下两根，贯穿机头段（K1 的长横管），卡箍每 0.4 m ————————————————
def pipe_runs(acc):
    runs = [
        ("top.0", [(160, 440), (255, 427), (440, 425), (510, 404), (650, 397), (880, 380), (1000, 372)], 0.04, 0.011, "pipe"),
        ("top.1", [(345, 409), (440, 409), (520, 398), (700, 383), (880, 366)], -0.05, 0.009, "pipe"),
        ("top.2", [(200, 434), (440, 420), (700, 392), (880, 374)], -0.08, 0.013, "cable"),
        ("bot.0", [(155, 467), (345, 467), (546, 495), (800, 500), (911, 505)], 0.03, 0.01, "pipe"),
        ("bot.1", [(600, 510), (669, 510), (692, 514), (1000, 516)], -0.05, 0.009, "pipe"),
        ("bot.2", [(230, 468), (500, 496), (800, 518), (1000, 520)], -0.09, 0.012, "cable"),
    ]
    for name, pts, dy, r, mat in runs:
        P3 = [k1(x, y, dy) for x, y in pts]
        collect(acc, pipe(f"int.run.{name}", P3, r, material=mat, props=P))
        L = sum((b - a).length for a, b in zip(P3, P3[1:]))
        n = int(L / 0.4)
        clamps = []
        for k in range(1, n + 1):
            f = k / (n + 1) * L
            for a, b in zip(P3, P3[1:]):
                seg = (b - a).length
                if f <= seg:
                    p = a.lerp(b, f / seg)
                    clamps.append(clamp(f"int.run.{name}.c{k}", p, b - a, r, props=P))
                    break
                f -= seg
        if clamps:
            collect(acc, merge(f"int.run.{name}.clamps", clamps, props=P))


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
    # 脚蹬（两块踏板，斜板上）
    for side in (1, -1):
        collect(acc, hull(f"int.cp.pedal.{'lr'[side < 0]}", [at(s, 0.13 * side + dy, z + dz) for s, z in ((5.08, Z_TIP + 0.27), (5.2, Z_TIP + 0.16)) for dy in (-0.05, 0.05) for dz in (0.0, 0.025)], "metal", P, bevel=0.004))
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
    collect(acc, hull("int.cp.hud", [at(hs + 0.02 + t * 0.06, y, z1 + 0.09 + t * 0.12 + d) for t in (0, 1) for y in (0.075, -0.075) for d in (0, 0.004)], "glass", {**P, "glass": True, "glow": {"key": "cockpit", "color": "#7bdbec"}}, bevel=0.001))
    collect(acc, hull("int.cp.hud.frame", [at(hs + 0.015 + t * 0.06, y, z1 + 0.085 + t * 0.12) for t in (0, 1) for y in (0.08, -0.08)] + [at(hs + 0.015 + t * 0.06 - 0.008, y, z1 + 0.085 + t * 0.12) for t in (0, 1) for y in (0.08, -0.08)], "frame", P, bevel=0.0015))
    # 脚下的红灯单元（K1 屏幕下那块红色格栅）
    collect(acc, box("int.cp.redunit", at(5.22, 0.25, ZF + 0.16), (0.2, 0.1, 0.12), material="vermilion", face="+y", panel=False, handles=False, plugs=0, props={**P, "glow": {"key": "cockpit.red", "color": "#ff5a32"}}, grille=4))
    # 两侧操纵台（左油门、右侧杆），台面两块小面板 + 侧杆 / 油门柄
    for side, name in ((-1, "stick"), (1, "throttle")):
        y0 = 0.33 * side
        if side < 0:  # 近侧（左）操纵台剖视时挡住驾驶员，只做远侧这一台；左边只留扶手和油门座
            collect(acc, box(f"int.cp.console.{name}", at(5.95, y0 + 0.04 * side, Z_TIP + 0.42), (0.9, 0.12, 0.2), material="interior", face="+z", handles=False, plugs=0, props=P, split=1, corner_bolts=True))
        else:
            collect(acc, box(f"int.cp.console.{name}", at(5.82, y0 + 0.04 * side, Z_TIP + 0.49), (0.32, 0.1, 0.06), material="interior", face="+z", panel=False, handles=False, plugs=0, props=P))
        collect(acc, beam(f"int.cp.armrest.{name}", at(6.35, y0, Z_TIP + 0.56), at(5.62, y0, Z_TIP + 0.56), 0.07, 0.03, Z, kind="box", props=P))
    base = at(5.72, -0.33, Z_TIP + 0.53)
    collect(acc, cylinder("int.cp.stick.boot", base, base + Z * 0.04, 0.03, 14, "rubber", P, r2=0.018))
    collect(acc, cylinder("int.cp.stick", base + Z * 0.03, base + Z * 0.12 + X * 0.01, 0.011, 10, "metal", P))
    collect(acc, hull("int.cp.stick.grip", [base + Z * (0.11 + dz) + X * (0.01 + dx) + Y * dy for dx in (-0.025, 0.02) for dy in (-0.018, 0.018) for dz in (0, 0.1)] + [base + Z * 0.215 + X * 0.03 + Y * dy for dy in (-0.012, 0.012)], "rubber", P, bevel=0.008))
    base = at(5.82, 0.33, Z_TIP + 0.53)
    collect(acc, hull("int.cp.throttle.slot", [base + X * dx + Y * dy + Z * dz for dx in (-0.12, 0.12) for dy in (-0.012, 0.012) for dz in (-0.004, 0.003)], "void", {**P, "lineLevel": "secondary"}, bevel=0.0))
    collect(acc, cylinder("int.cp.throttle", base, base + Z * 0.08 - X * 0.02, 0.01, 10, "metal", P))
    collect(acc, hull("int.cp.throttle.grip", [base + Z * (0.07 + dz) - X * (0.02 + dx) + Y * dy for dx in (-0.03, 0.04) for dy in (-0.025, 0.02) for dz in (0, 0.06)], "rubber", P, bevel=0.008))
    # ⑬ 头顶开关板：挂在座舱盖弓形框下（s 5.85）
    collect(acc, box("int.cp.overhead", at(5.85, 0, Z_TIP + 1.17), (0.16, 0.36, 0.035), material="interior", face="-z" if False else "+z", panel=True, handles=False, plugs=0, props={**P, "glow": {"key": "cockpit", "color": "#7bdbec"}}, split=2))
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

    # —— ⑧ 驾驶员：压力服、半躺 33°。尺寸取成年人第 50 百分位（坐高约 0.91 m，大腿 0.55，小腿 0.5）——
    hip = p(0.08, 0.13)
    sh_l = p(0.52, 0.12, 0.2)
    head = p(0.75, 0.15)
    collect(acc, ellipsoid("int.pilot.pelvis", hip, (0.15, 0.19, 0.11), (_v(sb, cb), Vector((0, 1, 0)), _v(-cb, sb)), material="suit", props=P))
    collect(acc, ellipsoid("int.pilot.abdomen", p(0.25, 0.13), (0.14, 0.17, 0.11), (_v(sb, cb), Vector((0, 1, 0)), _v(-cb, sb)), material="suit", props=P))
    collect(acc, ellipsoid("int.pilot.chest", p(0.45, 0.13), (0.15, 0.21, 0.13), (_v(sb, cb), Vector((0, 1, 0)), _v(-cb, sb)), material="suit", props=P))
    collect(acc, box("int.pilot.chestpack", p(0.42, 0.26), (0.08, 0.22, 0.16), rot=_rot_back(), material="avionics", face="-x", panel=True, handles=False, plugs=2, props=P))
    collect(acc, lathe("int.pilot.neckring", p(0.6, 0.14), p(0.65, 0.15), [(0, 0.09), (0.3, 0.1), (1, 0.095)], 24, "metal", P))
    collect(acc, ellipsoid("int.pilot.helmet", head, (0.135, 0.125, 0.14), (_v(sb, cb), Vector((0, 1, 0)), _v(-cb, sb)), u=32, v=16, material="helmet", props=P))
    collect(acc, ellipsoid("int.pilot.visor", head + _v(-cb, sb) * 0.035 + _v(sb, cb) * 0.0, (0.085, 0.112, 0.11), (_v(sb, cb), Vector((0, 1, 0)), _v(-cb, sb)), u=24, v=12, material="glass", props={**P, "glass": True}))
    collect(acc, lathe("int.pilot.helmet.rim", head - _v(sb, cb) * 0.07, head - _v(sb, cb) * 0.05, [(0, 0.118), (1, 0.124)], 28, "metal", P))
    # 肩、上臂、肘、前臂、手（右手握侧杆、左手握油门）
    grips = {1: at(5.86, 0.33, Z_TIP + 0.64), -1: at(5.76, -0.33, Z_TIP + 0.7)}
    for side in (1, -1):
        tag = "lr"[side < 0]
        sh = p(0.52, 0.12, 0.2 * side)
        collect(acc, ellipsoid(f"int.pilot.shoulder.{tag}", sh, (0.08, 0.08, 0.08), material="suit", props=P))
        hand = grips[side]
        el = p(0.24, 0.24, 0.27 * side)
        collect(acc, lathe(f"int.pilot.upperarm.{tag}", sh, el, [(0, 0.06), (0.5, 0.058), (1, 0.05)], 16, "suit", P))
        collect(acc, ellipsoid(f"int.pilot.elbow.{tag}", el, (0.055, 0.055, 0.055), material="suit", props=P))
        collect(acc, lathe(f"int.pilot.forearm.{tag}", el, hand + (el - hand).normalized() * 0.06, [(0, 0.05), (0.6, 0.045), (1, 0.04)], 16, "suit", P))
        collect(acc, ellipsoid(f"int.pilot.glove.{tag}", hand, (0.06, 0.04, 0.05), material="rubber", props=P))
        # 大腿、膝、小腿、靴
        h = hip + Y * 0.1 * side + _v(-cb, sb) * 0.02
        knee = at(5.62, 0.12 * side, Z_TIP + 0.5)
        ankle = at(5.27, 0.13 * side, Z_TIP + 0.15)
        toe = at(5.11, 0.13 * side, Z_TIP + 0.3)
        collect(acc, lathe(f"int.pilot.thigh.{tag}", h, knee, [(0, 0.085), (0.4, 0.08), (1, 0.06)], 18, "suit", P))
        collect(acc, ellipsoid(f"int.pilot.knee.{tag}", knee + Vector((0.01, 0, 0.02)), (0.065, 0.06, 0.06), material="avionics", props=P))
        collect(acc, lathe(f"int.pilot.shin.{tag}", knee, ankle, [(0, 0.055), (0.3, 0.058), (1, 0.042)], 16, "suit", P))
        collect(acc, hull(f"int.pilot.boot.{tag}", [ankle + Vector((dx, dy, dz)) for dx, dz in ((0.06, -0.06), (0.06, 0.08), (-0.05, -0.06), (-0.05, 0.06)) for dy in (-0.045, 0.045)] + [toe + Vector((dx, dy, dz)) for dx, dz in ((0.0, -0.035), (0.0, 0.03)) for dy in (-0.04, 0.04)], "rubber", P, bevel=0.015))
    # 背带（两条斜带）与氧气管（胸前接头 → 座椅左侧）
    for side in (1, -1):
        collect(acc, pipe(f"int.pilot.strap.{'lr'[side < 0]}", [p(0.6, 0.2, 0.12 * side), p(0.45, 0.27, 0.06 * side), p(0.2, 0.25, 0.02 * side), p(0.05, 0.22, 0.08 * side)], 0.012, bend=0.08, sides=6, material="cable", props=P))
    collect(acc, pipe("int.pilot.hose", [p(0.38, 0.27, 0.08), p(0.3, 0.33, 0.2), p(0.12, 0.25, 0.27), pan(0.1, 0.02, 0.27)], 0.016, bend=0.06, sides=10, material="cable", props=P))
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
    collect(acc, hull("int.aft.deck", [kc(x, y, yy) + Z * dz for x, y in ((1525, 493), (1696, 434)) for yy in (0.36, -0.36) for dz in (0, -0.02)], "structure", P, bevel=0.004))
    # 地板下后设备舱（s 6.4～7.6）：两只箱 + 一排线束
    for k, (x0, x1) in enumerate(((1440, 1530), (1580, 1680))):
        kbox(acc, f"int.aft.box.{k}", x0, 515, x1, 580, want=0.4, mapper=kg, face="+y", handles=True, plugs=3, label=True, corner_bolts=True, split=k)
    collect(acc, pipe("int.aft.loom", [kg(1420, 505, -0.1), kg(1696, 505, -0.1)], 0.018, material="cable", props=P))


def build():
    acc = []
    structure(acc)
    nose_bay(acc)
    rcs_bay(acc)
    avionics_fwd(acc)
    avionics_aft(acc)
    pipe_runs(acc)
    gear_bay(acc)
    head, headbox = cockpit(acc)
    aft_bay(acc)
    # 只要 S_END 以内的（K1 画得比机头段长）
    acc = [(o, l) for o, l in acc if min(XN - v.co.x for v in o.data.vertices) < S_END - 0.01]
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
