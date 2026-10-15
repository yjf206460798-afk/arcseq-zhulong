"""烛龙机头段内部（对 refs/layout/K1 的机头部分叠图对位；剖视模式按需加载的模块）。

K1 → 机体坐标：s = (x − 95) / 202，z = Z_TIP + (445 − y) / 202（K1 的机头尖在 (95, 445)，前段深度与 C2 一致，见 SUMMARY）。
有意不同（README：K1 的座舱盖画得太低、外部关系以几何母版为准）：座舱一组（地板、座椅、驾驶员、仪表、操纵杆）整体抬高 COCKPIT_LIFT，
让头盔落在 C2 的座舱盖下面。全部零件用 blender/kit 参数化零件库生成。
"""
import math

from mathutils import Matrix, Vector

from kit.parts import actuator, box, clamp, connector, cylinder, frame, hull, pipe

from .nose import BROW, EYE, FRAMES, S_END, Z_TIP, at, ring, spine_z, surface
from .util import XN

COCKPIT_LIFT = 0.42
SKIN = 0.035  # 蒙皮厚（剖面带的宽）
P = {"module": "interior", "lineLevel": "structure"}


def k1(x, y):
    """K1 像素 → (s, z)。"""
    return (x - 95) / 202, Z_TIP + (445 - y) / 202


def inner_ring(s, inset=SKIN + 0.01):
    """站位 s 的内表面多边形（整圈，世界坐标），框和量空间用。"""
    R = ring(s)
    c = Vector((0, (R["R0"][1] + R["R3"][1]) / 2))
    pts = []
    for y, z in (R["R0"], R["R1"], R["R2"], R["R3"], (-R["R3"][0], R["R3"][1]), (-R["R2"][0], R["R2"][1]), (-R["R1"][0], R["R1"][1])):
        v = Vector((y, z))
        d = (c - v)
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


def build():
    acc = []
    # —— 结构框（K1 的竖杆：s 0.67、1.25、2.05、3.1、3.9、4.75 的舱壁环）与上下纵梁 ——
    for k, s in enumerate(FRAMES[:-1]):
        collect(acc, frame(f"int.frame.{k}", list(reversed(inner_ring(s))), depth=0.03, width=0.045 if s > 1 else 0.03, material="structure", props=P))
    for k, (pick, dz) in enumerate((("R0", -0.06), ("R3", 0.06))):
        a = at(FRAMES[0], 0, ring(FRAMES[0])[pick][1] + dz * 0.5)
        b = at(BROW[2], 0, ring(BROW[2])[pick][1] + dz)
        collect(acc, hull(f"int.longeron.{k}", [a + Vector((0, dy, dz2)) for dy in (-0.02, 0.02) for dz2 in (-0.02, 0.02)] + [b + Vector((0, dy, dz2)) for dy in (-0.02, 0.02) for dz2 in (-0.02, 0.02)], "structure", P, bevel=0.004))
    # —— ② 传感器组（s 0.47～1.16）：主传感器盒 + 云台驱动筒 + 光纤束 ——
    s0, z0 = k1(190, 445)
    collect(acc, box("int.sensor.stack", at(0.58, 0, Z_TIP), (0.2, 0.09, 0.1), material="avionics", face="+x", plugs=2, props=P))
    collect(acc, cylinder("int.sensor.gimbal", at(0.82, 0, Z_TIP), at(1.12, 0, Z_TIP), 0.07, 20, "avionics", P))
    collect(acc, box("int.sensor.drive", at(0.97, 0, Z_TIP - 0.1), (0.22, 0.12, 0.06), material="avionics", face="+y", handles=False, plugs=0, props=P))
    collect(acc, pipe("int.sensor.fibre", [at(0.48, 0, Z_TIP + 0.03), at(0.3, 0, Z_TIP + 0.02), at(0.16, 0, Z_TIP)], 0.008, material="cable", props=P))
    # —— ③ 机头姿控推进器组（s 1.34～1.6）：两只推进剂小罐上下叠 + 汇流管 + 通往三个喷口的支管 + 电磁阀 ——
    for k, z in enumerate((0.11, -0.02)):
        collect(acc, cylinder(f"int.rcs.tank.{k}", at(1.33, 0, Z_TIP + z), at(1.62, 0, Z_TIP + z), 0.045, 18, "tank", P))
    collect(acc, cylinder("int.rcs.manifold", at(1.47, -0.09, Z_TIP + 0.045), at(1.47, 0.09, Z_TIP + 0.045), 0.018, 12, "metal", P))
    for side in (1, -1):
        for k, (facet, s, t) in enumerate((("outer", 1.38, 0.5), ("outer", 1.56, 0.5), ("lower", 1.47, 0.35))):
            port, n = surface(s, facet, t, side)
            port = port - n * 0.03
            collect(acc, pipe(f"int.rcs.feed.{k}.{'lr'[side < 0]}", [at(1.47, 0.08 * side, Z_TIP + 0.045), at(s, 0.08 * side, Z_TIP + 0.045 + (0.04 if facet == "outer" else -0.05)), port], 0.009, props=P))
            collect(acc, box(f"int.rcs.valve.{k}.{'lr'[side < 0]}", port - n * 0.035, (0.05, 0.04, 0.04), material="metal", face="+z", panel=False, handles=False, plugs=0, props=P))
    # —— ④ 航电舱（s 2.05～4.75）：主机箱、两联机柜、下层小箱、冷却管与线束 ——
    sa, za = k1(560, 418)
    sb, zb = k1(655, 475)
    collect(acc, box("int.avionics.main", at((sa + sb) / 2, 0, (za + zb) / 2), (sb - sa, 0.34, za - zb), material="avionics", face="+y", plugs=5, props=P))
    for k, (x0, x1) in enumerate(((725, 788), (792, 855))):
        s0_, zt = k1(x0, 395)
        s1_, zb_ = k1(x1, 478)
        collect(acc, box(f"int.avionics.rack.{k}", at((s0_ + s1_) / 2, 0, (zt + zb_) / 2), (s1_ - s0_ - 0.01, 0.42, zt - zb_), material="avionics", face="+y", plugs=4, props=P))
        s0_, zt = k1(x0, 480)
        s1_, zb_ = k1(x1, 502)
        collect(acc, box(f"int.avionics.lower.{k}", at((s0_ + s1_) / 2, 0, (zt + zb_) / 2), (s1_ - s0_ - 0.02, 0.3, zt - zb_), material="avionics", face="+y", handles=False, plugs=3, props=P))
    sa, za = k1(935, 405)
    sb, zb = k1(1000, 445)
    collect(acc, box("int.avionics.fwd", at((sa + sb) / 2, 0, (za + zb) / 2), (sb - sa, 0.3, za - zb), material="avionics", face="+y", plugs=3, props=P))
    for k, (x0, x1, y) in enumerate(((505, 560, 440), (660, 720, 455), (860, 905, 430))):
        sa, z = k1(x0, y)
        sb, _ = k1(x1, y)
        collect(acc, box(f"int.avionics.small.{k}", at((sa + sb) / 2, -0.05, z), (sb - sa, 0.14, 0.11), material="avionics", face="+y", handles=False, plugs=2, props=P))
    # 管线：上层冷却管三根（沿上纵梁）、下层液压管两根、线束一捆；卡箍每 0.5 m
    for k, (dy, dz, r, mat) in enumerate(((-0.06, -0.09, 0.012, "pipe"), (0.0, -0.11, 0.01, "pipe"), (0.06, -0.09, 0.012, "pipe"), (-0.1, -0.05, 0.016, "cable"))):
        pts = [at(s, dy, spine_z(s) + dz - 0.03 * (s < 1.6)) for s in (0.75, 1.3, 2.0, 3.1, 4.0, 4.7)]
        pts.insert(0, at(0.62, dy * 0.5, Z_TIP + 0.06))
        collect(acc, pipe(f"int.pipe.top.{k}", pts, r, material=mat, props=P))
        for s in (1.0, 1.5, 2.5, 3.5, 4.3):
            collect(acc, clamp(f"int.clamp.top.{k}.{int(s * 10)}", at(s, dy, spine_z(s) + dz - 0.03 * (s < 1.6)), Vector((1, 0, (spine_z(s + 0.1) - spine_z(s)) / 0.1)), r, props=P))
    for k, (dy, r) in enumerate(((-0.08, 0.011), (0.08, 0.011))):
        pts = [at(s, dy, ring(s)["R3"][1] + 0.1) for s in (1.0, 2.0, 3.1, 3.9, 4.6)]
        pts.append(at(4.9, dy, ring(4.9)["R3"][1] + 0.25))
        collect(acc, pipe(f"int.pipe.low.{k}", pts, r, material="pipe", props=P))
    # 机柜之间的竖向连接管（K1 里机柜两侧的弯管）
    for k, s in enumerate((2.2, 3.05, 3.85)):
        collect(acc, pipe(f"int.pipe.riser.{k}", [at(s, -0.18, spine_z(s) - 0.12), at(s, -0.18, Z_TIP + 0.05), at(s + 0.08, -0.18, Z_TIP - 0.1), at(s + 0.08, -0.12, ring(s)["R3"][1] + 0.12)], 0.01, props=P))
        collect(acc, connector(f"int.pipe.riser.end.{k}", at(s + 0.08, -0.12, ring(s)["R3"][1] + 0.12), (0, 0, 1), 0.012, props=P))
    # —— ⑭ 前起落架舱（s 4.13～5.72）：舱壁、支柱（收起，向前）、机轮、收放作动筒、液压单元 ——
    sa, _ = k1(930, 0)
    sb, _ = k1(1250, 0)
    zf = ring(sb)["R3"][1]
    for side in (1, -1):
        collect(acc, hull(f"int.gear.wall.{'lr'[side < 0]}", [at(s, 0.24 * side + d, z) for s in (sa, sb) for d in (0, 0.012 * side) for z in (ring(s)["R3"][1] + 0.01, Z_TIP + COCKPIT_LIFT - 0.2)], "structure", P, bevel=0.004))
    sw, zw = k1(1060, 545)
    wheel = at(sw, 0, zw + 0.05)
    collect(acc, cylinder("int.gear.wheel", wheel + Vector((0, -0.09, 0)), wheel + Vector((0, 0.09, 0)), 0.17, 28, "rubber", P))
    collect(acc, cylinder("int.gear.hub", wheel + Vector((0, -0.1, 0)), wheel + Vector((0, 0.1, 0)), 0.08, 18, "metal", P))
    pivot = at(5.55, 0, Z_TIP + COCKPIT_LIFT - 0.26)
    collect(acc, cylinder("int.gear.strut", pivot, wheel + Vector((0, 0, 0.12)), 0.045, 16, "metal", P))
    collect(acc, cylinder("int.gear.oleo", wheel + Vector((0.05, 0, 0.12)), wheel + Vector((0.32, 0, 0.17)), 0.032, 14, "chrome", P))
    collect(acc, actuator("int.gear.retract", at(5.3, -0.12, Z_TIP + COCKPIT_LIFT - 0.3), wheel + Vector((0.12, -0.12, 0.1)), 0.026, 0.3, props=P))
    sh, zh = k1(1080, 520)
    collect(acc, box("int.gear.hydraulic", at(5.0, 0.13, zh), (0.3, 0.12, 0.14), material="metal", face="+y", handles=False, plugs=3, props=P))
    collect(acc, cylinder("int.gear.accumulator", at(4.4, 0.14, zh - 0.02), at(4.75, 0.14, zh - 0.02), 0.05, 18, "tank", P))
    # —— 座舱（整体抬高 COCKPIT_LIFT）：地板、⑪ 环形屏幕墙、⑩ 平视显示器、⑫ 侧杆 / 油门、⑬ 头顶开关板、⑨ 弹射座椅与导轨、⑧ 驾驶员 ——
    L = COCKPIT_LIFT
    sf0, zf0 = k1(1085, 470)
    sf1, _ = k1(1600, 470)
    floor_z = zf0 + L
    collect(acc, hull("int.cockpit.floor", [at(s, y, floor_z + dz) for s in (sf0, sf1) for y in (0.34, -0.34) for dz in (0, -0.03)], "structure", P, bevel=0.006))
    # 屏幕墙：前方一圈弧形（五块平板拼成，向座位方向内倾），屏面一层发青光的薄片
    sw0, zw0 = k1(1110, 445)
    sw1, zw1 = k1(1180, 375)
    for k in range(5):
        a0 = math.radians(-70 + 28 * k)
        a1 = math.radians(-70 + 28 * (k + 1))
        R = 0.36
        cx = sw0 + 0.32
        pts = []
        for a in (a0, a1):
            for zz, back in ((zw0 + L, 0.0), (zw1 + L + 0.05, 0.08)):
                pts += [at(cx - R * math.cos(a) + back, R * math.sin(a), zz), at(cx - R * math.cos(a) - 0.03 + back, R * math.sin(a), zz)]
        collect(acc, hull(f"int.cockpit.display.{k}", pts, "screen", {**P, "glow": {"key": "cockpit", "color": "#7bdbec"}}, bevel=0.003))
    sh_, zh_ = k1(1165, 395)
    collect(acc, hull("int.cockpit.hud", [at(sh_ + ds, y, zh_ + L + dz) for ds, dz in ((0.0, -0.05), (0.04, 0.1)) for y in (-0.09, 0.09) for _ in (0,)] + [at(sh_ + 0.006 + ds, y, zh_ + L + dz) for ds, dz in ((0.0, -0.05), (0.04, 0.1)) for y in (-0.09, 0.09)], "glass", {**P, "glass": True, "glow": {"key": "cockpit", "color": "#7bdbec"}}, bevel=0.001))
    ss_, zs_ = k1(1265, 440)
    for k, (y, name) in enumerate(((-0.2, "stick"), (0.2, "throttle"))):
        base = at(ss_ + (0.05 if k else 0), y, floor_z + 0.12)
        collect(acc, box(f"int.cockpit.{name}.console", base - Vector((0, 0, 0.06)), (0.34, 0.08, 0.12), material="interior", face="+z", handles=False, plugs=0, props=P))
        collect(acc, cylinder(f"int.cockpit.{name}", base, base + Vector((-0.03, 0, 0.14)), 0.014, 12, "metal", P))
        collect(acc, hull(f"int.cockpit.{name}.grip", [base + Vector((-0.03 + dx, dy, 0.13 + dz)) for dx in (-0.025, 0.025) for dy in (-0.02, 0.02) for dz in (0, 0.08)], "rubber", P, bevel=0.008))
    so, zo = k1(1405, 300)
    collect(acc, box("int.cockpit.overhead", at(6.35, 0, Z_TIP + 1.17), (0.3, 0.26, 0.04), material="interior", face="+z", handles=False, plugs=0, props={**P, "glow": {"key": "cockpit", "color": "#7bdbec"}}))
    # 座椅：坐垫、后倾 30° 的椅背、头枕、两根导轨、弹射筒
    seat_p = at(6.95, 0, floor_z + 0.18)
    back_dir = Vector((-math.sin(math.radians(60)), 0, math.cos(math.radians(60))))  # 向后上
    back_dir = Vector((-0.5, 0, 0.866)) if False else Vector((-math.cos(math.radians(60)), 0, math.sin(math.radians(60))))
    collect(acc, hull("int.seat.pan", [seat_p + Vector((dx, dy, dz)) for dx in (-0.22, 0.22) for dy in (-0.22, 0.22) for dz in (-0.06, 0.04)], "seat", P, bevel=0.02))
    bb = seat_p + Vector((-0.24, 0, 0.0))
    collect(acc, hull("int.seat.back", [bb + back_dir * t + Vector((dx, dy, 0)) for t in (0.0, 0.72) for dx in (-0.05, 0.03) for dy in (-0.23, 0.23)], "seat", P, bevel=0.02))
    hr = bb + back_dir * 0.82
    collect(acc, hull("int.seat.headrest", [hr + back_dir * t + Vector((dx, dy, 0)) for t in (0.0, 0.18) for dx in (-0.08, 0.02) for dy in (-0.13, 0.13)], "seat", P, bevel=0.015))
    for side in (1, -1):
        collect(acc, hull(f"int.seat.rail.{'lr'[side < 0]}", [bb + Vector((-0.09, 0.26 * side + dy, 0)) + back_dir * t for t in (-0.25, 1.0) for dy in (-0.015, 0.015) for _ in (0,)] + [bb + Vector((-0.13, 0.26 * side + dy, 0)) + back_dir * t for t in (-0.25, 1.0) for dy in (-0.015, 0.015)], "metal", P, bevel=0.004))
    collect(acc, cylinder("int.seat.catapult", bb + Vector((-0.16, 0, 0)), bb + Vector((-0.16, 0, 0)) + back_dir * 0.9, 0.035, 14, "metal", P))
    # 驾驶员（压力服、半躺约 30°）：胸、腹、大腿、小腿、手臂、头盔（凸体与圆柱拼）
    torso0 = bb + back_dir * 0.08 + Vector((0.13, 0, 0))
    torso1 = bb + back_dir * 0.6 + Vector((0.12, 0, 0))
    collect(acc, cylinder("int.pilot.torso", torso0, torso1, 0.15, 18, "suit", P, r2=0.17))
    helmet = bb + back_dir * 0.8 + Vector((0.12, 0, 0))
    collect(acc, hull("int.pilot.helmet", [helmet + Vector((math.cos(a) * 0.12, math.sin(a) * 0.11 * math.cos(b), math.sin(b) * 0.13)) for a in [i * math.pi / 6 for i in range(12)] for b in (-0.9, -0.3, 0.3, 0.9)], "helmet", P, bevel=0.0))
    collect(acc, hull("int.pilot.visor", [helmet + Vector((0.07 + math.cos(a) * 0.055, math.sin(a) * 0.09, dz)) for a in (-0.8, 0, 0.8) for dz in (-0.04, 0.05)] + [helmet + Vector((0.12, 0, 0.0))], "glass", {**P, "glass": True}, bevel=0.0))
    knee = seat_p + Vector((0.38, 0, 0.12))
    foot = at(sf0 + 0.18, 0, floor_z + 0.08)
    for side in (1, -1):
        hip = seat_p + Vector((-0.08, 0.1 * side, 0.08))
        k_ = knee + Vector((0, 0.1 * side, 0))
        f_ = foot + Vector((0, 0.11 * side, 0))
        collect(acc, cylinder(f"int.pilot.thigh.{'lr'[side < 0]}", hip, k_, 0.075, 14, "suit", P, r2=0.06))
        collect(acc, cylinder(f"int.pilot.shin.{'lr'[side < 0]}", k_, f_, 0.055, 14, "suit", P, r2=0.05))
        sh0 = torso1 + Vector((-0.02, 0.17 * side, -0.05))
        hand = at(ss_ + 0.0, 0.2 * side, floor_z + 0.3)
        el = (sh0 + hand) / 2 + Vector((-0.05, 0.03 * side, -0.12))
        collect(acc, cylinder(f"int.pilot.upperarm.{'lr'[side < 0]}", sh0, el, 0.05, 12, "suit", P))
        collect(acc, cylinder(f"int.pilot.forearm.{'lr'[side < 0]}", el, hand, 0.042, 12, "suit", P))
    # 座舱侧的管线（K1：座椅后面的竖管与线束）
    for k, dy in enumerate((-0.3, 0.3)):
        collect(acc, pipe(f"int.cockpit.duct.{k}", [at(7.5, dy, floor_z - 0.05), at(7.4, dy, floor_z + 0.4), at(7.05, dy * 0.9, floor_z + 0.75), at(6.6, dy * 0.85, floor_z + 0.85)], 0.02, material="cable", props=P))
    callouts = [
        {"n": 2, "label": "传感器组（光电 / 红外 / 射频 / 激光雷达）", "at": list(at(0.58, 0, Z_TIP + 0.05))},
        {"n": 3, "label": "机头姿控推进器组", "at": list(at(1.47, 0, Z_TIP + 0.16))},
        {"n": 4, "label": "航电舱", "at": list(at(2.55, 0, Z_TIP + 0.15))},
        {"n": 8, "label": "驾驶员（压力服，半躺约 30°）", "at": list(helmet)},
        {"n": 9, "label": "弹射座椅（导轨）", "at": list(bb + back_dir * 0.45 - Vector((0.05, 0, 0)))},
        {"n": 10, "label": "平视显示器", "at": list(at(sh_ + 0.02, 0, zh_ + L + 0.05))},
        {"n": 11, "label": "环形屏幕墙", "at": list(at(sw0 + 0.05, -0.2, zw0 + L + 0.15))},
        {"n": 12, "label": "侧杆（右）/ 油门（左）", "at": list(at(ss_, -0.2, floor_z + 0.3))},
        {"n": 13, "label": "头顶开关板", "at": list(at(6.35, 0, Z_TIP + 1.17))},
        {"n": 14, "label": "前起落架舱", "at": list(wheel)},
    ]
    return acc, callouts
