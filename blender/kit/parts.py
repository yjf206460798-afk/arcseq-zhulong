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
        for i in range(steps + 1):
            f = i / steps
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


def box(name, centre, size, rot=None, material="avionics", face="+x", panel=True, handles=True, plugs=4, props=None, bevel=0.012):
    """设备箱：size = (长 x, 宽 y, 高 z)；face 为正面朝向（"+x" "-x" "+y" "-y" "+z"）。
    正面：内凹 8 mm 的面板（四周留 14% 边）、两只把手（细横杆 + 两个支脚）、下沿一排插头（圆柱）。"""
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
        bm = bmesh.new()
        pts = []
        for a in (-1, 1):
            for b in (-1, 1):
                for d in (0.002, -0.008):
                    pts.append(fc + side * a * ws * 0.36 + up * b * wu * 0.36 + n * d)
        vs = [bm.verts.new(p) for p in pts]
        bmesh.ops.convex_hull(bm, input=vs)
        o = new_object(name + ".panel", bm, "panel", props)
        extra.append((o, finish(o, bevel=0.002)))
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


def frame(name, ring, depth=0.04, width=0.06, material="structure", props=None):
    """框（舱壁环）：截面多边形 ring（同一 x 的世界坐标点，逆时针）沿内法线内缩 width，前后厚 depth。凹的环拆成每边一块凸板。"""
    ring = [Vector(p) for p in ring]
    c = sum(ring, Vector()) / len(ring)
    out = []
    n = len(ring)
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]
        ai = a + (c - a).normalized() * width
        bi = b + (c - b).normalized() * width
        pts = []
        for p in (a, b, ai, bi):
            pts += [p + Vector((depth / 2, 0, 0)), p - Vector((depth / 2, 0, 0))]
        o, l = hull(f"{name}.{k}", pts, material, {"skin": name, **(props or {})}, bevel=0.004)
        out.append((o, l))
    return out
