"""烛龙机头段（Z1 look-dev，s 0～7.2 m）：烛光窗眼珠、针状机头、切面前机身、眉骨、座舱盖、遮光盾滑轨、鸭翼、棱线、鳞片瓦样片。

切面做法（写进 PATTERNS「切面机身」）：前机身每一段的截面都是后端截面绕同一个“顶点”的缩放（位似），所以每条棱线都是直线、
且同一段里所有棱线汇向一点——每张切面都是严格的平面（大块精确切面，平面着色不出斜纹）。段与段之间换顶点，形成折线。
  针段 s 0.16～1.1：顶点在机头尖 (s 0, z 1.45)；
  前机身 s 1.1～7.2：顶点在机头前方 (s −1.24, z 1.43)。
截面（半边，从背脊顺时针）：R0 背脊、R1 肩线、R2 棱线（最宽、锐边、朱红线）、R3 腹缘、R4 龙骨（腹底平面，与 R3 同高）。
"""
import math

import bmesh
import bpy
from mathutils import Vector

from .util import XN, at, boolean, hull_object, lerp, mesh_object, mirror_object

# 后端截面（s = 7.2）：(y, z)
REAR = {"R0": (0.0, 2.18), "R1": (0.56, 2.08), "R2": (1.08, 1.52), "R3": (0.55, 0.87)}
S_END = 7.2
FORE_APEX = (-1.24, 1.43)  # (s, z)
NEEDLE = (1.1, (0.0, 1.45))  # 针段后端站位与顶点 (s, z)
BALL = {"s": 0.11, "z": 1.45, "r": 0.11}


def ring(s):
    """站位 s 的半截面棱点 {R0…R3: (y, z)}。"""
    sa, za = FORE_APEX
    if s >= NEEDLE[0] - 1e-9:
        k = (s - sa) / (S_END - sa)
        return {key: (y * k, za + (z - za) * k) for key, (y, z) in REAR.items()}
    base = ring(NEEDLE[0])
    s0, z0 = NEEDLE[1]
    k = (s - s0) / (NEEDLE[0] - s0)
    return {key: (y * k, z0 + (z - z0) * k) for key, (y, z) in base.items()}


# 每张切面的横向细分数（顶点 AO 要有足够的顶点；切面是平面，细分不改形状）
FACETS = [("R0", "R1", 3, "hull"), ("R1", "R2", 4, "hull"), ("R2", "R3", 4, "belly")]


def section(s):
    """整圈截面点（从右侧腹缘经龙骨……按逆时针看机头方向的顺序），返回 [(y, z, facet 名)]。"""
    R = ring(s)
    half = []  # 左侧：R0 → R1 → R2 → R3
    for a, b, n, mat in FACETS:
        for i in range(n):
            t = i / n
            half.append(((lerp(R[a][0], R[b][0], t), lerp(R[a][1], R[b][1], t)), mat))
    half.append((R["R3"], "belly"))
    # 右侧镜像（R3' → … → R0 之前），腹底 R3 → R3' 中间加 5 点
    pts = [p for p, _ in half]
    belly = [((lerp(R["R3"][0], -R["R3"][0], i / 6), R["R3"][1]), "belly") for i in range(1, 6)]
    right = [((-y, z), m) for (y, z), m in reversed(half[1:])]
    return [(p, m) for p, m in half] + belly + right


def surface_point(s, facet, t, lift=0.0, side=1):
    """切面上的点：facet = ("R1", "R2") 这样的两条棱线，t 为两棱线之间的比例；lift 沿切面法线抬起（米）。返回 (点, 法线)。"""
    a, b = facet
    R = ring(s)
    y = lerp(R[a][0], R[b][0], t) * side
    z = lerp(R[a][1], R[b][1], t)
    n = facet_normal(s, facet, side)
    p = at(s, y, z) + n * lift
    return p, n


def facet_normal(s, facet, side=1):
    a, b = facet
    s0, s1 = (s - 0.05, s + 0.05)
    R0, R1 = ring(max(s0, 0.16)), ring(min(s1, S_END))
    p00 = at(max(s0, 0.16), R0[a][0] * side, R0[a][1])
    p01 = at(max(s0, 0.16), R0[b][0] * side, R0[b][1])
    p10 = at(min(s1, S_END), R1[a][0] * side, R1[a][1])
    n = (p01 - p00).cross(p10 - p00).normalized()
    # 朝外：远离机身中轴（y = 0, z ≈ 1.5）
    mid = (p00 + p01) / 2
    if n.dot(mid - Vector((mid.x, 0, 1.45))) < 0:
        n = -n
    return n


def top_z(s, y):
    """上表面（R0–R1 切面，|y| ≤ 肩线）的高度。"""
    R = ring(s)
    y = abs(y)
    if y <= R["R1"][0]:
        return lerp(R["R0"][1], R["R1"][1], y / R["R1"][0])
    return lerp(R["R1"][1], R["R2"][1], (y - R["R1"][0]) / (R["R2"][0] - R["R1"][0]))


def stations():
    s = [0.16]
    x = 0.2
    while x < S_END - 1e-6:
        s.append(round(x, 3))
        x += 0.1
    s += [NEEDLE[0], S_END]
    return sorted(set(round(v, 4) for v in s))


def body():
    """前机身蒙皮：按站位放样，切面上的细分只为顶点 AO；前端封口藏在眼珠里，后端是剖切面（look-dev 段的断面）。"""
    bm = bmesh.new()
    rings = []
    mats = []
    for s in stations():
        sec = section(s)
        rings.append([bm.verts.new(at(s, y, z)) for (y, z), _ in sec])
        mats = [m for _, m in sec]
    n = len(rings[0])
    for A, B in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((A[i], A[j], B[j], B[i]))
    front = bm.faces.new(list(reversed(rings[0])))
    rear = bm.faces.new(rings[-1])
    rear.material_index = 2
    front.material_index = 2
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = False
    # 肩线（R1）到棱线（R2）之间的格子归上表面；R2 以下归机腹：按格子形心高度与棱线高度比较
    for f in bm.faces:
        if f.material_index == 2:
            continue
        c = f.calc_center_median()
        s = XN - c.x
        R = ring(min(max(s, 0.16), S_END))
        f.material_index = 1 if c.z < R["R2"][1] - 1e-4 else 0
    return mesh_object("nose.body", bm, mats=("hull", "belly", "interior"), props={"skin": "skin"})


def sensor():
    """烛光窗（机头尖的眼珠）：金属球体 + 前半球光窗（通电发琥珀光）+ 六片虹膜遮片 + 窗框环。"""
    c = at(BALL["s"], 0, BALL["z"])
    r = BALL["r"]
    objs = []
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=r)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "Y"))
    bmesh.ops.translate(bm, verts=bm.verts, vec=c)
    for f in bm.faces:
        f.smooth = True
    objs.append(mesh_object("sensor.ball", bm, mats=("carbon",), props={"skin": "sensor.ball"}))
    # 光窗：前半球（与 +x 夹角 < 34°）的球冠，略大一点盖在球上；虹膜在它外面
    WIN = math.radians(34)
    APER = math.radians(13)

    def cap(radius, a0, a1, n_az=48, n_el=6, name="", mats=("sensor",), props=None, az0=0.0, az1=2 * math.pi, hexagon=False):
        bm = bmesh.new()
        rows = []
        for i in range(n_el + 1):
            a = lerp(a0, a1, i / n_el)
            row = []
            for k in range(n_az + 1):
                phi = lerp(az0, az1, k / n_az)
                aa = a
                if hexagon and i == 0:
                    # 虹膜的内沿是正六边形：光圈半角 a0 / cos(到最近一条边法线的夹角)
                    sector = (phi % (math.pi / 3)) - math.pi / 6
                    aa = math.atan(math.tan(a0) / math.cos(sector))
                d = Vector((math.cos(aa), math.sin(aa) * math.cos(phi), math.sin(aa) * math.sin(phi)))
                row.append(bm.verts.new(c + d * radius))
            rows.append(row)
        for A, B in zip(rows, rows[1:]):
            for k in range(n_az):
                bm.faces.new((A[k], B[k], B[k + 1], A[k + 1]))
        # 整圈时首尾两列重合：合并
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        for f in bm.faces:
            f.smooth = True
        return mesh_object(name, bm, mats=mats, props=props)

    objs.append(cap(r * 1.004, 0.0001, WIN, n_el=6, name="sensor.window", mats=("sensor",), props={"skin": "sensor.window", "glow": {"key": "sensor", "color": "#ffb060"}}))
    for b in range(6):
        az0 = b * math.pi / 3
        objs.append(cap(r * 1.03, APER, WIN, n_az=8, n_el=4, name=f"sensor.iris.{b}", mats=("carbon",), props={"skin": f"sensor.iris.{b}", "lineLevel": "secondary"}, az0=az0, az1=az0 + math.pi / 3, hexagon=True))
    # 窗框环：光窗边缘一圈（截面 6 mm 的圆环）
    rr = r * math.sin(WIN) * 1.03
    xx = r * math.cos(WIN) * 1.03
    bm = bmesh.new()
    segs, sides, minor = 48, 8, 0.007
    grid = []
    for i in range(segs):
        phi = 2 * math.pi * i / segs
        rowv = []
        for k in range(sides):
            th = 2 * math.pi * k / sides
            radial = Vector((0, math.cos(phi), math.sin(phi)))
            p = Vector((xx + minor * math.sin(th), 0, 0)) + radial * (rr + minor * math.cos(th))
            rowv.append(bm.verts.new(c + p))
        grid.append(rowv)
    for i in range(segs):
        for k in range(sides):
            a, b2 = grid[i], grid[(i + 1) % segs]
            bm.faces.new((a[k], b2[k], b2[(k + 1) % sides], a[(k + 1) % sides]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True
    objs.append(mesh_object("sensor.bezel", bm, mats=("carbon",), props={"skin": "sensor.bezel", "lineLevel": "secondary"}))
    return objs


def brow():
    """眉骨：座舱前方一道切削的 V 形脊（俯视像向前的箭头），里面是遮光盾的收纳槽；比座舱盖前缘高约 6 cm。并进机身（布尔并），交线成为真实的折边。"""
    pts = []
    s0, s1, s2 = 4.05, 5.18, 5.24
    for s, y, dz in [(s0, 0, 0.0), (4.6, 0.19, 0.06), (s1, 0.0, None), (s2, 0.0, None), (s1, 0.40, 0.12), (s2, 0.40, 0.12), (4.9, 0.33, 0.09)]:
        for side in (1, -1):
            if dz is None:
                pts.append(at(s, 0, 2.31 if s == s1 else 2.30))
            else:
                pts.append(at(s, y * side, top_z(s, y) + dz))
    for s in (s0, 4.6, s1, s2):
        for y in (0, 0.2, 0.40):
            yy = min(y, ring(s)["R1"][0] * 0.98)
            for side in (1, -1):
                pts.append(at(s, yy * side, top_z(s, yy) - 0.06))
    return hull_object("brow", pts, mats=("hull",))


def canopy():
    """座舱盖：俯视长六边形的切面“宝石”，前端藏在眉骨后面；中间一道金属框（座舱盖弓形框）；后端没入背部整流。"""
    def glass_points(stations):
        pts = []
        for s, ridge, (ys, zs), (yb) in stations:
            pts.append(at(s, 0, ridge))
            for side in (1, -1):
                pts.append(at(s, ys * side, zs))
                pts.append(at(s, yb * side, top_z(s, yb) - 0.0))
                pts.append(at(s, yb * side, top_z(s, yb) - 0.03))
            pts.append(at(s, 0, top_z(s, 0) - 0.05))
        return pts
    front = [(5.22, 2.24, (0.22, 2.17), 0.33), (5.65, 2.42, (0.24, 2.34), 0.36), (6.13, 2.42, (0.24, 2.34), 0.36)]
    rear = [(6.17, 2.42, (0.24, 2.34), 0.36), (6.35, 2.42, (0.24, 2.34), 0.36), (6.95, 2.20, (0.14, 2.15), 0.20)]
    g1 = hull_object("canopy.glass.front", glass_points(front), mats=("glass",), props={"skin": "glass", "glass": True})
    g2 = hull_object("canopy.glass.rear", glass_points(rear), mats=("glass",), props={"skin": "glass", "glass": True})
    bow = hull_object("canopy.bow", glass_points([(6.125, 2.43, (0.245, 2.35), 0.365), (6.175, 2.43, (0.245, 2.35), 0.365)]), mats=("carbon",), props={"skin": "canopy.frame"})
    return [g1, g2, bow]


def aft_fairing():
    """座舱后的背部整流（并进机身）：座舱盖后端没入它的前端面。"""
    pts = []
    for s, ridge, (ys, zs), yb in [(6.85, 2.30, (0.17, 2.21), 0.25), (7.2, 2.31, (0.2, 2.24), 0.3)]:
        pts.append(at(s, 0, ridge))
        for side in (1, -1):
            pts.append(at(s, ys * side, zs))
            pts.append(at(s, yb * side, top_z(s, yb) - 0.04))
        pts.append(at(s, 0, top_z(s, 0) - 0.06))
    return hull_object("fairing", pts, mats=("hull",))


def rails():
    """遮光盾滑轨：座舱盖两侧各一条（眉骨后缘到背部整流），遮光盾沿它从眉骨里滑出盖住座舱（化剑 / 入轨时“闭眼”）。"""
    out = []
    for side, tag in ((1, "l"), (-1, "r")):
        pts = []
        for s in (5.24, 6.88):
            y0 = 0.375
            for dy in (0, 0.028):
                y = (y0 + dy) * side
                z = top_z(s, y0 + dy)
                pts += [at(s, y, z - 0.01), at(s, y, z + 0.026)]
        out.append(hull_object(f"shield.rail.{tag}", pts, mats=("carbon",), props={"skin": f"shield.rail.{tag}"}))
    return out


def canard():
    """鸭翼（左）：棱线下方 5 cm，根部插进棱线槽；收纳时沿槽缩进机身（Z4 机构）。"""
    pts = []
    zc = None

    def chine_z(s):
        return ring(s)["R2"][1]

    def side_y(s, z):
        R = ring(s)
        t = (R["R2"][1] - z) / (R["R2"][1] - R["R3"][1])
        return lerp(R["R2"][0], R["R3"][0], t)

    for s_le, s_te, span, th in [(5.45, 6.55, 0.0, 0.04), (6.58, 6.86, 0.95, 0.015)]:
        z0 = chine_z(5.9) - 0.05
        yr = side_y(6.0, z0) - 0.03
        y = yr + span
        mid = (s_le + s_te) / 2
        pts += [at(s_le, y, z0), at(s_te, y, z0), at(mid, y, z0 + th / 2), at(mid, y, z0 - th / 2)]
    return hull_object("canard.l", pts, mats=("hull",), props={"skin": "canard.l", "joint": "canard.l"})


def rcs_ports():
    """机头姿态推进器（左）：上外切面上三个小方口（空腔着色）。"""
    out = []
    bm = bmesh.new()
    for k, s in enumerate((1.55, 1.68, 1.81)):
        quad = []
        for ds, dt in ((-0.035, -0.12), (0.035, -0.12), (0.035, 0.12), (-0.035, 0.12)):
            p, n = surface_point(s + ds, ("R1", "R2"), 0.5 + dt, lift=0.003)
            quad.append(bm.verts.new(p))
        bm.faces.new(quad)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.dot(facet_normal(1.7, ("R1", "R2"))) < 0:
            f.normal_flip()
    out.append(mesh_object("rcs.nose.l", bm, mats=("void",), props={"system": "void", "skin": "rcs.nose.l", "shadow": False}))
    return out


def scale_patch():
    """鳞片防热瓦样片（左，下切面 s 3.3～5.3）：菱形错排、后端圆，每片后缘翘起 5 mm（前后错叠的读法），片间留 6 mm 缝。
    只做这一小片几何，其余机腹的鳞片走烘焙贴图（对照两种做法在 4× 下的可读性）。"""
    bm = bmesh.new()
    facet = ("R2", "R3")
    p, w = 0.085, 0.15  # 行距（沿 s）与列宽（沿切面斜向）
    gap = 0.006
    s_from, s_to = 3.3, 5.3
    row = 0
    s = s_from
    count = 0
    while s < s_to:
        R = ring(s)
        slant = math.hypot(R["R2"][0] - R["R3"][0], R["R2"][1] - R["R3"][1])
        v = 0.10 + (w / 2 if row % 2 else 0.0)
        while v + w / 2 < slant * 0.9:
            outline = []
            # 菱形：前尖 (−p, 0)、两侧 (0, ±w/2)、后端圆弧（两侧到后尖 (+p, 0) 之间 5 段）
            pts2 = [(-p + gap, 0.0), (0.0, -w / 2 + gap)]
            for i in range(1, 6):
                a = -math.pi / 2 + math.pi * i / 6
                pts2.append((0.0 + (p - gap) * 0.95 * math.cos(a) * 1.0, (w / 2 - gap) * math.sin(a)))
            pts2.append((0.0, w / 2 - gap))
            for du, dv in pts2:
                ss = s + du
                rr = ring(ss)
                sl = math.hypot(rr["R2"][0] - rr["R3"][0], rr["R2"][1] - rr["R3"][1])
                t = (v + dv) / sl
                rise = 0.002 + 0.005 * max(0.0, (du + p) / (2 * p))
                top, n = surface_point(ss, facet, t, lift=rise)
                bot, _ = surface_point(ss, facet, t, lift=-0.003)
                outline.append((top, bot))
            verts = [bm.verts.new(a) for a, _ in outline] + [bm.verts.new(b) for _, b in outline]
            bmesh.ops.convex_hull(bm, input=verts)
            count += 1
            v += w
        s += p
        row += 1
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # 凸包会留下零散的内部元素：删掉不在面上的点
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    for f in bm.faces:
        f.smooth = False
    obj = mesh_object("scale.patch.l", bm, mats=("belly",), props={"skin": "scale", "lineLevel": "secondary", "shadow": False, "aoOccluder": False})
    return obj, count


def stand():
    """展示支架（look-dev 段专用）：一根收分的立柱 + 托板，托住 s 4.6 处的腹底。"""
    s = 4.6
    zb = ring(s)["R3"][1]
    pts = []
    for ds, dy, z in [(0.11, 0.11, 0.0), (0.06, 0.06, zb - 0.05)]:
        for a in (1, -1):
            for b in (1, -1):
                pts.append(at(s + ds * a, dy * b, z))
    post = hull_object("stand.post", pts, mats=("interior",), props={"skin": "stand.post"})
    pts = []
    for ds in (0.26, -0.26):
        for dy in (0.2, -0.2):
            for z in (zb - 0.05, zb - 0.002):
                pts.append(at(s + ds, dy, z))
    plate = hull_object("stand.cradle", pts, mats=("interior",), props={"skin": "stand.cradle"})
    return [post, plate]


def seams():
    """次级工艺线（L2）与一级结构线（L1）、朱红棱线（accent），贴在切面上抬 2 mm；返回引擎坐标的折线与逐点法线。"""
    out = []

    def line(points_normals, level="secondary", closed=False, **extra):
        out.append({"points": [list(map(lambda v: round(v, 4), p)) for p, _ in points_normals], "normals": [list(map(lambda v: round(v, 4), n)) for _, n in points_normals], "level": level, "closed": closed, **extra})

    def around(s, lift=0.002):
        """绕机身一圈（上表面与两侧切面，不含腹底）。"""
        pts = []
        for side in (1, -1):
            seq = [(("R0", "R1"), 0), (("R0", "R1"), 0.5), (("R1", "R2"), 0), (("R1", "R2"), 0.5), (("R2", "R3"), 0), (("R2", "R3"), 0.5), (("R2", "R3"), 1)]
            run = [surface_point(s, f, t, lift, side) for f, t in seq]
            pts.append(run if side == 1 else run)
        left, right = pts
        return list(reversed(left)) + right[1:]

    # 针段接缝、前机身口盖环（俯视 C2 在 s≈1.1、3.0 处的横缝）
    line(around(1.1))
    line(around(3.05))
    # 上外切面的检修口盖（左右）、下切面的口盖
    for side in (1, -1):
        rect = [(2.35, 0.22), (3.85, 0.22), (3.85, 0.72), (2.35, 0.72)]
        line([surface_point(s, ("R1", "R2"), t, 0.002, side) for s, t in rect], closed=True)
        rect = [(1.3, 0.25), (2.8, 0.25), (2.8, 0.6), (1.3, 0.6)]
        line([surface_point(s, ("R0", "R1"), t, 0.002, side) for s, t in rect], closed=True)
        # 鸭翼收纳槽：棱线下方一条一级结构线（鸭翼沿它缩进机身）
        def slot(s, side=side):
            R = ring(s)
            z = R["R2"][1] - 0.05
            t = (R["R2"][1] - z) / (R["R2"][1] - R["R3"][1])
            return surface_point(s, ("R2", "R3"), t, 0.002, side)
        line([slot(s) for s in (5.25, 6.95)], level="structure")
        # 朱红棱线：从光窗后 s 0.6 沿棱线到段末（整机里一直到翼前缘转折处）
        def chine(s, side=side):
            R = ring(s)
            p = at(s, R["R2"][0] * side, R["R2"][1])
            n = (facet_normal(s, ("R1", "R2"), side) + facet_normal(s, ("R2", "R3"), side)).normalized()
            return p + n * 0.004, n
        line([chine(s) for s in (0.6, NEEDLE[0], S_END)], level="accent", accent="chine", u0=0.0, u1=1.0)
    return out


def ball_mask(c, r):
    planes = []
    dirs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    k = 1 / math.sqrt(3)
    dirs += [(a * k, b * k, d * k) for a in (1, -1) for b in (1, -1) for d in (1, -1)]
    for n in dirs:
        n = Vector(n)
        planes.append([round(n.x, 4), round(n.y, 4), round(n.z, 4), round(n.dot(c) + r, 4)])
    return planes


def build():
    objs = [body()]
    objs += sensor()
    b = brow()
    boolean(objs[0], b)
    f = aft_fairing()
    boolean(objs[0], f)
    objs += canopy()
    objs += rails()
    c = canard()
    objs += [c, mirror_object(c, "canard.r")]
    objs[-1]["joint"] = "canard.r"
    objs[-1]["skin"] = "canard.r"
    rcs = rcs_ports()[0]
    objs += [rcs, mirror_object(rcs, "rcs.nose.r")]
    objs[-1]["skin"] = "rcs.nose.r"
    patch, n_tiles = scale_patch()
    objs += [patch, mirror_object(patch, "scale.patch.r")]
    objs += stand()
    S = seams()
    sensor_c = at(BALL["s"], 0, BALL["z"])
    meta = {
        "offset": [-(XN - S_END / 2), 0, 0],
        "seams": S,
        "landmarks": {
            "sensor": list(sensor_c),
            "canopy": list(at(5.9, 0, 2.3)),
            "chine.start.l": list(at(0.6, ring(0.6)["R2"][0], ring(0.6)["R2"][1])),
            "rcs.nose.l": list(surface_point(1.68, ("R1", "R2"), 0.5)[0]),
        },
        "joints": [],
        # 遮线区：眼珠里面（内切半径 8 cm 的 14 面体，顶点都在球面 11 cm 以内，不吃掉球的外轮廓）。针段前端藏在球里，它的棱线离球面不到 20 cm，会被外轮廓的深度让出量透出来
        "masks": [ball_mask(sensor_c, 0.08)],
        "focus": {"nose": list(sensor_c), "canopy": list(at(5.6, 0, 2.2))},
        "tiles": n_tiles,
    }
    return objs, meta
