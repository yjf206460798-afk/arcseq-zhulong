"""参数化零件（arcseq-kit 候选）。每个函数建一个对象（世界坐标），返回 (对象, 线数据)；线数据由 finish() 给出。

  pipe(name, pts, r, bend=…)            管线：沿折线的圆管，拐角按 bend 半径倒圆弯头，两端可加接头
  box(name, centre, size, …)            设备箱：倒角长方体 + 正面内凹面板 + 两只把手 + 一排插头（可关）
  connector(name, pos, axis, r, …)      接头：短圆柱 + 六角螺母 + 法兰
  actuator(name, p0, p1, r, ext)        作动筒：缸筒 + 活塞杆 + 两端耳环；ext 为伸出比例（0…1）
  clamp(name, pos, axis, r)             卡箍：套在管上的扁环 + 耳片
  frame(name, ring, depth, width)       框：沿截面外形内缩的一圈板（舱壁环），ring 为截面多边形（世界坐标、同一 x）
  cylinder(name, a, b, r, sides)        圆柱（缸体、罐、轴）
  hull(name, pts)                       点集凸包（托架、整流块）
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .finish import finish


def _material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    return m


def new_object(name, bm, material="interior", props=None, collection=None):
    me = bpy.data.meshes.new(name)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(_material(material))
    (collection or bpy.context.scene.collection).objects.link(obj)
    for k, v in (props or {}).items():
        obj[k] = v
    return obj


def _frame_of(axis):
    """以 axis 为 z 的正交基 (u, v, w)。"""
    w = Vector(axis).normalized()
    u = Vector((0, 0, 1)).cross(w)
    if u.length < 1e-6:
        u = Vector((0, 1, 0)).cross(w)
    u.normalize()
    v = w.cross(u)
    return u, v, w


def _ring(bm, centre, axis, r, sides, phase=0.0):
    u, v, _ = _frame_of(axis)
    return [bm.verts.new(centre + (u * math.cos(phase + 2 * math.pi * k / sides) + v * math.sin(phase + 2 * math.pi * k / sides)) * r) for k in range(sides)]


def _bridge(bm, A, B):
    n = len(A)
    for k in range(n):
        bm.faces.new((A[k], A[(k + 1) % n], B[(k + 1) % n], B[k]))


def _cap(bm, ring, flip=False):
    bm.faces.new(list(reversed(ring)) if flip else ring)


def _fillet(pts, bend, steps=5):
    """折线拐角倒圆：每个内点换成一段半径 bend 的圆弧（取样 steps 段）。"""
    P = [Vector(p) for p in pts]
    if bend <= 0 or len(P) < 3:
        return P
    out = [P[0]]
    for a, b, c in zip(P, P[1:], P[2:]):
        d1 = (b - a).normalized()
        d2 = (c - b).normalized()
        theta = d1.angle(d2, 0.0)
        if theta < 1e-3:
            out.append(b)
            continue
        t = min(bend * math.tan(theta / 2), (b - a).length * 0.45, (c - b).length * 0.45)
        p1 = b - d1 * t
        p2 = b + d2 * t
        n = max(1, min(steps, math.ceil(theta / math.radians(22))))  # 取样按转角：小弯一两段就够（面数）
        for i in range(n + 1):
            f = i / n
            # 二次贝塞尔近似圆弧
            out.append(p1 * (1 - f) ** 2 + b * 2 * f * (1 - f) + p2 * f * f)
    out.append(P[-1])
    return out


def pipe(name, pts, r, bend=None, sides=10, material="pipe", props=None, ends=True):
    """管线：中心线折线 pts，半径 r；拐角倒圆（默认弯曲半径 3r）。曲面件（网页取曲面轮廓线）。"""
    path = _fillet(pts, 3 * r if bend is None else bend)
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(path):
        if i == 0:
            t = path[1] - path[0]
        elif i == len(path) - 1:
            t = path[-1] - path[-2]
        else:
            t = (path[i + 1] - path[i - 1])
        rings.append(_ring(bm, p, t, r, sides))
    # 相邻两圈对齐（按投影最近的起点），避免扭转
    for A, B in zip(rings, rings[1:]):
        _bridge(bm, A, B)
    _cap(bm, rings[0], flip=True)
    _cap(bm, rings[-1])
    obj = new_object(name, bm, material, {"curved": True, **(props or {})})
    lines = finish(obj, bevel=min(0.004, r * 0.25), curved=True)
    return obj, lines


def cylinder(name, a, b, r, sides=16, material="interior", props=None, bevel=0.006, r2=None):
    a, b = Vector(a), Vector(b)
    bm = bmesh.new()
    A = _ring(bm, a, b - a, r, sides)
    B = _ring(bm, b, b - a, r if r2 is None else r2, sides)
    _bridge(bm, A, B)
    _cap(bm, A, flip=True)
    _cap(bm, B)
    obj = new_object(name, bm, material, {"curved": True, **(props or {})})
    return obj, finish(obj, bevel=min(bevel, r * 0.3), curved=True)


def hull(name, pts, material="interior", props=None, bevel=0.015):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts, edges=bm.edges)
    obj = new_object(name, bm, material, props)
    return obj, finish(obj, bevel=bevel)


def _cuboid(bm, centre, size, rot=None):
    sx, sy, sz = (s / 2 for s in size)
    R = rot or Matrix.Identity(3)
    corners = [Vector((x, y, z)) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    vs = [bm.verts.new(Vector(centre) + R @ c) for c in corners]
    bmesh.ops.convex_hull(bm, input=vs)


def box(name, centre, size, rot=None, material="avionics", face="+x", panel=True, handles=True, plugs=4, props=None, bevel=0.012, split=0, label=False, corner_bolts=False, grille=0, ears=True):
    """设备箱：size = (长 x, 宽 y, 高 z)；face 为正面朝向（"+x" "-x" "+y" "-y" "+z"）。
    正面：内凹 8 mm 的面板（四周留 14% 边；split=n 时横向分成 n+1 扇门）、两只把手（细横杆 + 两个支脚）、下沿一排插头（圆柱）；
    label：左上角一块浅色铭牌；corner_bolts：四角螺栓；grille=n：面板下部 n 条横向散热格栅。"""
    centre = Vector(centre)
    R = rot or Matrix.Identity(3)
    bm = bmesh.new()
    _cuboid(bm, centre, size, R)
    obj = new_object(name, bm, material, props)
    lines = finish(obj, bevel=min(bevel, min(size) * 0.12))
    extra = []
    axis = {"+x": Vector((1, 0, 0)), "-x": Vector((-1, 0, 0)), "+y": Vector((0, 1, 0)), "-y": Vector((0, -1, 0)), "+z": Vector((0, 0, 1))}[face]
    n = R @ axis
    i = {"+x": 0, "-x": 0, "+y": 1, "-y": 1, "+z": 2}[face]
    half = size[i] / 2
    # 正面的两条边方向
    dims = [k for k in range(3) if k != i]
    e1 = R @ Vector([1 if k == dims[0] else 0 for k in range(3)])
    e2 = R @ Vector([1 if k == dims[1] else 0 for k in range(3)])
    w1, w2 = size[dims[0]], size[dims[1]]
    up = e2 if abs(e2.z) >= abs(e1.z) else e1
    side = e1 if up is e2 else e2
    wu, ws = (w2, w1) if up is e2 else (w1, w2)
    fc = centre + n * half
    if panel and min(w1, w2) > 0.06:
        doors = split + 1
        gap = 0.006
        for k in range(doors):
            s0 = -0.36 + 0.72 * k / doors + (gap / ws if k else 0)
            s1 = -0.36 + 0.72 * (k + 1) / doors - (gap / ws if k < doors - 1 else 0)
            bm = bmesh.new()
            pts = []
            for a in (s0, s1):
                for b in (-1, 1):
                    for d in (0.002, -0.008):
                        pts.append(fc + side * a * ws + up * b * wu * 0.36 + n * d)
            vs = [bm.verts.new(p) for p in pts]
            bmesh.ops.convex_hull(bm, input=vs)
            o = new_object(name + f".panel{k}", bm, "panel", props)
            extra.append((o, finish(o, bevel=0.002)))
    if label and min(w1, w2) > 0.05:
        # 小铭牌：约 4 × 1.5 cm，左上角（不抢眼：小、低饱和）
        lw, lh = min(0.045, ws * 0.12), min(0.016, wu * 0.06)
        c = fc + side * (-ws * 0.28 + lw) + up * (wu * 0.3) + n * 0.0025
        pts = [c + side * a * lw + up * b * lh + n * d for a in (-1, 1) for b in (-1, 1) for d in (-0.001, 0.0008)]
        extra.append(hull(name + ".label", pts, "label", {**(props or {}), "lineLevel": "secondary"}, bevel=0.0))
    if ears and min(w1, w2) > 0.05:
        # 固定耳：底边两侧各一片带螺栓的耳板（往两侧伸出 2.5 cm），把箱子固定到托架 / 框上
        bottom = centre - up * wu / 2
        for a in (-1, 1):
            base = bottom + side * a * (ws / 2 + 0.0125) - n * (size[i] * 0.25)
            pts = [base + side * da + n * dn + up * dz for da in (-0.0125, 0.0125) for dn in (-0.02, 0.02) for dz in (0.0, 0.006)]
            extra.append(hull(name + f".ear{'lr'[a > 0]}", pts, material, props, bevel=0.0015))
            extra.append(bolts(name + f".ear{'lr'[a > 0]}.bolt", base + up * 0.006, base + up * 0.006, 1, 0.0045, up, props=props))
    if corner_bolts and min(w1, w2) > 0.05:
        rb = max(0.0035, min(ws, wu) * 0.025)
        for b in (-1, 1):
            extra.append(bolts(name + f".bolts{'bt'[b > 0]}", fc + side * -ws * 0.43 + up * b * wu * 0.43, fc + side * ws * 0.43 + up * b * wu * 0.43, 2, rb, n, props=props))
    for k in range(grille):
        c = fc + up * (-wu * 0.3 + k * 0.022) + side * ws * 0.15 + n * 0.0015
        pts = [c + side * a * ws * 0.15 + up * b * 0.004 + n * d for a in (-1, 1) for b in (-1, 1) for d in (-0.002, 0.001)]
        extra.append(hull(name + f".grille{k}", pts, "void", {**(props or {}), "lineLevel": "secondary"}, bevel=0.0))
    if handles and ws > 0.12:
        for a in (-1, 1):
            p = fc + side * a * ws * 0.42
            o, l = pipe(name + f".handle{'lr'[a > 0]}", [p + up * wu * 0.22, p + up * wu * 0.22 + n * 0.025, p - up * wu * 0.22 + n * 0.025, p - up * wu * 0.22], 0.004, bend=0.008, sides=6, material="metal", props=props)
            extra.append((o, l))
    for k in range(plugs if wu > 0.08 else 0):
        p = fc + side * ((k + 0.5) / plugs - 0.5) * ws * 0.6 - up * wu * 0.4
        o, l = connector(name + f".plug{k}", p, n, min(0.012, ws / plugs * 0.3), length=0.03, props=props)
        extra.append((o, l))
    return obj, lines, extra


def connector(name, pos, axis, r, length=0.04, material="metal", props=None):
    """接头：圆柱身 + 六角螺母（r × 1.35，长 0.35） + 法兰（r × 1.6，薄）。"""
    pos, w = Vector(pos), Vector(axis).normalized()
    bm = bmesh.new()
    A = _ring(bm, pos, w, r * 1.6, 12)
    B = _ring(bm, pos + w * 0.004, w, r * 1.6, 12)
    _bridge(bm, A, B)
    _cap(bm, A, flip=True)
    C = _ring(bm, pos + w * 0.004, w, r * 1.35, 6, math.pi / 6)
    D = _ring(bm, pos + w * (0.004 + length * 0.35), w, r * 1.35, 6, math.pi / 6)
    _bridge(bm, C, D)
    _cap(bm, C, flip=True)
    _cap(bm, D)
    E = _ring(bm, pos + w * (0.004 + length * 0.35), w, r, 12)
    F = _ring(bm, pos + w * length, w, r, 12)
    _bridge(bm, E, F)
    _cap(bm, E, flip=True)
    _cap(bm, F)
    obj = new_object(name, bm, material, props)
    return obj, finish(obj, bevel=0.0015)


def actuator(name, p0, p1, r, ext=0.5, material="metal", props=None):
    """作动筒：p0 端缸筒（全长的 55%）、p1 端活塞杆（半径 0.45r），两端耳环（扁圆柱，横穿销孔方向取与连线垂直、水平）。"""
    p0, p1 = Vector(p0), Vector(p1)
    L = (p1 - p0).length
    w = (p1 - p0).normalized()
    out = []
    barrel_end = p0 + w * L * (0.55 + 0.1 * (1 - ext))
    o, l = cylinder(name + ".barrel", p0 + w * r * 1.2, barrel_end, r, 16, material, props)
    out.append((o, l))
    o, l = cylinder(name + ".gland", barrel_end - w * 0.01, barrel_end + w * 0.012, r * 1.12, 16, material, props)
    out.append((o, l))
    o, l = cylinder(name + ".rod", barrel_end, p1 - w * r * 1.2, r * 0.45, 12, "chrome", props)
    out.append((o, l))
    side = w.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((0, 1, 0))
    side.normalize()
    for k, p in enumerate((p0, p1)):
        o, l = cylinder(name + f".eye{k}", p - side * r * 0.6, p + side * r * 0.6, r * 1.1, 14, material, props)
        out.append((o, l))
    return out


def clamp(name, pos, axis, r, material="metal", props=None):
    pos, w = Vector(pos), Vector(axis).normalized()
    bm = bmesh.new()
    A = _ring(bm, pos - w * 0.006, w, r * 1.25, 12)
    B = _ring(bm, pos + w * 0.006, w, r * 1.25, 12)
    _bridge(bm, A, B)
    _cap(bm, A, flip=True)
    _cap(bm, B)
    obj = new_object(name, bm, material, props)
    return obj, finish(obj, bevel=0.001, curved=True)


def frame(name, ring, depth=0.04, width=0.06, material="structure", props=None, skip=()):
    """框（舱壁环）：截面多边形 ring（同一 x 的世界坐标点，逆时针）沿内法线内缩 width，前后厚 depth。凹的环拆成每边一块凸板；
    skip：不做的边（序号 k 连 ring[k] → ring[k+1]，开口框用）。"""
    ring = [Vector(p) for p in ring]
    c = sum(ring, Vector()) / len(ring)
    out = []
    n = len(ring)
    for k in range(n):
        if k in skip:
            continue
        a, b = ring[k], ring[(k + 1) % n]
        ai = a + (c - a).normalized() * width
        bi = b + (c - b).normalized() * width
        pts = []
        for p in (a, b, ai, bi):
            pts += [p + Vector((depth / 2, 0, 0)), p - Vector((depth / 2, 0, 0))]
        o, l = hull(f"{name}.{k}", pts, material, {"skin": name, **(props or {})}, bevel=0.004)
        out.append((o, l))
    return out


# —— 第二批（复刻样板 K1 内部）：合并、螺栓排、型材梁、阀、泵、罐、回转体、椭球、角码 ——————————————


def merge(name, items, material=None, props=None):
    """把多个 (对象, 线) 合成一个对象（同材质的成排小件：螺栓、卡箍、筋……），线数据拼接。对象都是单位变换、世界坐标。"""
    items = [it for it in items if it and it[0] is not None]
    bm = bmesh.new()
    for o, _ in items:
        bm.from_mesh(o.data)
    mat = material or (items[0][0].data.materials[0].name if items[0][0].data.materials else "interior")
    lines = [x for _, l in items for x in l]
    curved = any(o.get("curved") for o, _ in items)
    for o, _ in items:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.data.materials.append(_material(mat))
    bpy.context.scene.collection.objects.link(obj)
    for k, v in (props or {}).items():
        obj[k] = v
    if curved:
        obj["curved"] = True
    return obj, lines


def bolts(name, a, b, n, r, normal, material="metal", props=None, h=None, ends=True):
    """一排六角螺栓头：a→b 上等距 n 个（ends=False 时两端各让半格），头朝 normal、外接圆半径 r、高 h（默认 0.6r）。合成一个对象。"""
    a, b, w = Vector(a), Vector(b), Vector(normal).normalized()
    h = 0.6 * r if h is None else h
    bm = bmesh.new()
    for k in range(n):
        f = (k / (n - 1) if n > 1 else 0.5) if ends else (k + 0.5) / n
        p = a.lerp(b, f)
        A = _ring(bm, p - w * 0.001, w, r, 6, math.pi / 6)
        B = _ring(bm, p + w * h, w, r, 6, math.pi / 6)
        _bridge(bm, A, B)
        _cap(bm, A, flip=True)
        _cap(bm, B)
    obj = new_object(name, bm, material, {"lineLevel": "secondary", **(props or {})})
    return obj, finish(obj, bevel=0.0, angle=40)


def beam(name, a, b, w, h, up, kind="I", t=None, material="structure", props=None, holes=0, bolt_r=0.006):
    """型材梁 a→b：截面宽 w（沿 side）、高 h（沿 up）、壁厚 t（默认 0.12·min(w, h)）。
    kind：I（工字）、channel（槽，开口朝 −side）、angle（角材，两肢朝 −up、−side）、box（矩形管）。holes>0 时上翼缘一排螺栓。返回 [(obj, lines)…]。"""
    a, b = Vector(a), Vector(b)
    d = (b - a).normalized()
    up = Vector(up)
    up = (up - d * up.dot(d)).normalized()
    side = d.cross(up).normalized()
    t = t or 0.12 * min(w, h)
    out = []

    def slab(tag, c0, c1, s0, s1):
        """截面里一块矩形（side 方向 s0…s1，up 方向 c0…c1）沿梁拉伸。"""
        pts = [p + side * s + up * c for p in (a, b) for s in (s0, s1) for c in (c0, c1)]
        o, l = hull(f"{name}.{tag}", pts, material, props, bevel=min(0.003, t * 0.3))
        out.append((o, l))

    if kind == "I":
        slab("web", -h / 2 + t, h / 2 - t, -t / 2, t / 2)
        slab("top", h / 2 - t, h / 2, -w / 2, w / 2)
        slab("bot", -h / 2, -h / 2 + t, -w / 2, w / 2)
    elif kind == "channel":
        slab("web", -h / 2, h / 2, w / 2 - t, w / 2)
        slab("top", h / 2 - t, h / 2, -w / 2, w / 2 - t)
        slab("bot", -h / 2, -h / 2 + t, -w / 2, w / 2 - t)
    elif kind == "angle":
        slab("v", -h / 2, h / 2, w / 2 - t, w / 2)
        slab("h", h / 2 - t, h / 2, -w / 2, w / 2 - t)
    else:
        slab("box", -h / 2, h / 2, -w / 2, w / 2)
    if holes:
        L = (b - a).length
        out.append(bolts(f"{name}.bolts", a + d * L * 0.04 + up * h / 2, b - d * L * 0.04 + up * h / 2, holes, bolt_r, up, props=props))
    return out


def lathe(name, a, b, profile, sides=20, material="interior", props=None, bevel=0.0):
    """回转体：轴 a→b，profile 为 [(t, r)…]（t 0…1 沿轴，r 半径；r=0 处收成尖点）。曲面件。"""
    a, b = Vector(a), Vector(b)
    axis = b - a
    bm = bmesh.new()
    rings = []
    for t, r in profile:
        c = a + axis * t
        rings.append([bm.verts.new(c)] if r <= 1e-6 else _ring(bm, c, axis, r, sides))
    for A, B in zip(rings, rings[1:]):
        if len(A) == 1 and len(B) == 1:
            continue
        if len(A) == 1:
            for k in range(sides):
                bm.faces.new((A[0], B[k], B[(k + 1) % sides]))
        elif len(B) == 1:
            for k in range(sides):
                bm.faces.new((A[k], A[(k + 1) % sides], B[0]))
        else:
            _bridge(bm, A, B)
    if len(rings[0]) > 1:
        _cap(bm, rings[0], flip=True)
    if len(rings[-1]) > 1:
        _cap(bm, rings[-1])
    obj = new_object(name, bm, material, {"curved": True, **(props or {})})
    return obj, finish(obj, bevel=bevel, curved=True)


def ellipsoid(name, centre, radii, axes=None, u=24, v=12, material="interior", props=None):
    """椭球：半轴 radii = (a, b, c) 沿 axes 的三根轴（默认世界 x、y、z）。曲面件。"""
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    ax = axes or (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    M = Matrix((Vector(ax[0]) * radii[0], Vector(ax[1]) * radii[1], Vector(ax[2]) * radii[2])).transposed()
    for vv in bm.verts:
        vv.co = Vector(centre) + M @ vv.co
    obj = new_object(name, bm, material, {"curved": True, **(props or {})})
    return obj, finish(obj, bevel=0, curved=True)


def tank(name, a, b, r, bands=2, material="tank", props=None, sides=24):
    """罐：圆柱身 + 两端椭球封头（高 0.45r）+ bands 道箍带（半径 1.04r、宽 0.25r）。返回 [(obj, lines)…]。"""
    a, b = Vector(a), Vector(b)
    L = (b - a).length
    e = 0.45 * r / L
    prof = [(0.0, 0.0), (e * 0.35, r * 0.62), (e * 0.7, r * 0.88), (e, r), (1 - e, r), (1 - e * 0.7, r * 0.88), (1 - e * 0.35, r * 0.62), (1.0, 0.0)]
    out = [lathe(name, a, b, prof, sides, material, props)]
    for k in range(bands):
        f = (k + 1) / (bands + 1)
        c = a.lerp(b, f)
        d = (b - a).normalized()
        out.append(cylinder(f"{name}.band{k}", c - d * 0.125 * r, c + d * 0.125 * r, r * 1.04, sides, "metal", props, bevel=0.002))
    return out


def valve(name, pos, axis, r, material="metal", props=None, top=None):
    """球阀：阀体（球，半径 1.5r）+ 两端法兰（半径 2r、厚 0.35r）+ 阀杆 + 执行器方盒（top 方向，默认朝上）。axis 为管线方向。"""
    pos, w = Vector(pos), Vector(axis).normalized()
    top = Vector(top or (0, 0, 1))
    top = (top - w * top.dot(w)).normalized()
    out = [ellipsoid(f"{name}.body", pos, (1.5 * r, 1.5 * r, 1.5 * r), u=16, v=8, material=material, props=props)]
    for k, sgn in enumerate((-1, 1)):
        c = pos + w * sgn * 1.55 * r
        out.append(cylinder(f"{name}.flange{k}", c - w * 0.18 * r, c + w * 0.18 * r, 2.0 * r, 12, material, props, bevel=0.001))
    out.append(cylinder(f"{name}.stem", pos + top * 1.3 * r, pos + top * 2.4 * r, 0.35 * r, 8, "chrome", props))
    side = w.cross(top)
    s = 1.2 * r
    pts = [pos + top * (2.4 * r + dz) + w * dx + side * dy for dx in (-s, s) for dy in (-s, s) for dz in (0, 1.8 * r)]
    out.append(hull(f"{name}.actuator", pts, "avionics", props, bevel=min(0.004, 0.2 * r)))
    return out


def pump(name, pos, axis, r, material="metal", props=None):
    """泵：蜗壳圆盘（半径 r、厚 0.45r）+ 电机（半径 0.62r、长 1.5r，四道散热筋）+ 出口短管（沿蜗壳切向）。axis 为电机轴向。"""
    pos, w = Vector(pos), Vector(axis).normalized()
    out = [cylinder(f"{name}.volute", pos - w * 0.225 * r, pos + w * 0.225 * r, r, 28, material, props, bevel=0.004)]
    m0 = pos + w * 0.225 * r
    out.append(cylinder(f"{name}.motor", m0, m0 + w * 1.5 * r, 0.62 * r, 20, "avionics", props, bevel=0.003))
    for k in range(4):
        c = m0 + w * (0.25 + 0.3 * k) * r
        out.append(cylinder(f"{name}.fin{k}", c - w * 0.04 * r, c + w * 0.04 * r, 0.7 * r, 20, "avionics", props, bevel=0.0))
    u, v, _ = _frame_of(w)
    p = pos + v * 0.8 * r
    out.append(cylinder(f"{name}.outlet", p, p + u * 1.3 * r, 0.22 * r, 10, "pipe", props))
    out.append(cylinder(f"{name}.inlet", pos - w * 0.225 * r, pos - w * 0.75 * r, 0.3 * r, 12, "pipe", props))
    return out


def bracket(name, base, normal, along, size=(0.06, 0.05, 0.04), t=0.005, material="structure", props=None):
    """L 形角码：底板贴在 base（法线 normal）上，沿 along 长 size[0]、宽 size[2]，立板高 size[1]；底板上两只螺栓。返回 [(obj, lines)…]。"""
    base, n = Vector(base), Vector(normal).normalized()
    d = Vector(along)
    d = (d - n * d.dot(n)).normalized()
    s = n.cross(d)
    L, H, W = size
    out = []
    pts = [base + d * x + s * y + n * z for x in (-L / 2, L / 2) for y in (-W / 2, W / 2) for z in (0, t)]
    out.append(hull(f"{name}.foot", pts, material, props, bevel=0.0012))
    pts = [base + d * x + s * y + n * z for x in (-L / 2, L / 2) for y in (W / 2 - t, W / 2) for z in (0, H)]
    out.append(hull(f"{name}.leg", pts, material, props, bevel=0.0012))
    out.append(bolts(f"{name}.bolts", base - d * L * 0.3 + n * t - s * W * 0.1, base + d * L * 0.3 + n * t - s * W * 0.1, 2, max(0.003, W * 0.12), n, props=props))
    return out


def drum(name, a, b, r, bands=2, material="metal", props=None, sides=20):
    """圆柱件（电机、缸体、蓄压器）：筒身 + 两端端盖（略大一圈的薄盘 + 中心凸台）+ bands 道箍带。返回 [(obj, lines)…]。"""
    a, b = Vector(a), Vector(b)
    w = (b - a).normalized()
    L = (b - a).length
    out = [cylinder(name, a + w * 0.006, b - w * 0.006, r, sides, material, props, bevel=min(0.004, r * 0.15))]
    for k, (p, d) in enumerate(((a, w), (b, -w))):
        out.append(cylinder(f"{name}.cap{k}", p, p + d * 0.008, r * 1.06, sides, "metal", props, bevel=0.0015))
        out.append(cylinder(f"{name}.boss{k}", p - d * 0.006, p + d * 0.002, r * 0.35, 12, "chrome", props, bevel=0.001))
    for k in range(bands):
        c = a.lerp(b, (k + 1) / (bands + 1))
        out.append(cylinder(f"{name}.band{k}", c - w * min(0.008, L * 0.04), c + w * min(0.008, L * 0.04), r * 1.04, sides, "metal", props, bevel=0.001))
    return out
