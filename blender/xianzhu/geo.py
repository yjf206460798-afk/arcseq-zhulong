"""銜燭 建模用的几何小工具（只依赖 bpy / bmesh / mathutils / numpy）。

烛龙分支的 `blender/kit/`（参数化零件库）合入 main 后，这里的 box / tube 可以换成 kit 版本；接口保持“世界坐标直接建、
对象变换为单位阵、自定义属性随 glTF extras 导出”，与 kit 相同。
"""
import math

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
    return m


def obj_from_bm(name, bm, mat, props=None, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(material(mat))
    bpy.context.scene.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = smooth
    for k, v in (props or {}).items():
        o[k] = v
    return o


def obj_from_arrays(name, V, F, mat, props=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [tuple(f) for f in F])
    me.update()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(material(mat))
    bpy.context.scene.collection.objects.link(o)
    for p in me.polygons:
        p.use_smooth = smooth
    for k, v in (props or {}).items():
        o[k] = v
    return o


def verts_of(o):
    V = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", V)
    return V.reshape(-1, 3)


def bvh_of(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.transform(o.matrix_world)
    t = BVHTree.FromBMesh(bm)
    bm.free()
    return t


def project(tree, p, lift=0.0):
    """最近表面点 + 法线（沿法线抬 lift）。"""
    lo, n, _, _ = tree.find_nearest(Vector(p))
    return lo + n * lift, n


def drape(tree, pts, lift, step=0.02, smooth=2):
    """折线加密 → 每点投到表面最近点、沿法线抬 lift → 平滑几轮。返回 (点列, 法线列)。"""
    pts = [Vector(p) for p in pts]
    dense = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, int((b - a).length / step))
        dense += [a.lerp(b, k / n) for k in range(n)]
    dense.append(pts[-1])
    P, N = [], []
    for p in dense:
        q, n = project(tree, p, lift)
        P.append(np.array(q))
        N.append(np.array(n))
    P, N = np.array(P), np.array(N)
    # 法线离群（切缝处的细条面、凹槽壁）：偏离前后邻居平均 40° 以上的换成邻居平均
    for k in range(len(N)):
        nb = N[max(0, k - 3):k + 4].sum(0) - N[k]
        nb /= max(np.linalg.norm(nb), 1e-9)
        if N[k].dot(nb) < math.cos(math.radians(40)):
            N[k] = nb
    for _ in range(smooth):
        P[1:-1] = 0.5 * P[1:-1] + 0.25 * (P[:-2] + P[2:])
        N[1:-1] = 0.5 * N[1:-1] + 0.25 * (N[:-2] + N[2:])
    # 平滑后再贴回一次，保证不陷进表面；去掉挤在一起的点（投影吸到同一条边上时会重合，带子会翻折）
    out = []
    for p, n in zip(P, N):
        q, _ = project(tree, p - n * lift * 0.0, 0.0)
        q = q + Vector(n) * lift
        if out and (q - out[-1][0]).length < step * 0.35:
            continue
        out.append((q, Vector(n)))
    return [q for q, _ in out], [n for _, n in out]


def ribbon(name, pts, normals, width, thick, mat, props=None, closed=False):
    """扁带（织带、嵌条）：沿 pts，带面贴着各点法线，宽 width、厚 thick（向外）。"""
    bm = bmesh.new()
    rows = []
    n_ = len(pts)
    for k in range(n_):
        p, n = Vector(pts[k]), Vector(normals[k]).normalized()
        if closed:
            t = Vector(pts[(k + 1) % n_]) - Vector(pts[k - 1])
        else:
            t = Vector(pts[min(k + 1, n_ - 1)]) - Vector(pts[max(k - 1, 0)])
        t.normalize()
        b = t.cross(n).normalized()
        n2 = b.cross(t).normalized()
        rows.append([bm.verts.new(p + b * sx * width / 2 + n2 * sz * thick) for sx, sz in ((-1, 0), (1, 0), (1, 1), (-1, 1))])
    pairs = list(zip(rows, rows[1:])) + ([(rows[-1], rows[0])] if closed else [])
    for A, B in pairs:
        for k in range(4):
            bm.faces.new((A[k], B[k], B[(k + 1) % 4], A[(k + 1) % 4]))
    if not closed:
        bm.faces.new(list(reversed(rows[0])))
        bm.faces.new(rows[-1])
    o = obj_from_bm(name, bm, mat, props, smooth=False)
    mark_sharp(o, 40)
    return o


def tube(name, pts, radius, mat, props=None, sides=12, closed=False, caps=True):
    bm = bmesh.new()
    rows = []
    pts = [Vector(p) for p in pts]
    prev = None
    for k, p in enumerate(pts):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        if prev is None:
            a = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            u = t.cross(a).normalized()
        else:
            u = (prev - t * prev.dot(t)).normalized()
        prev = u
        v = t.cross(u)
        rows.append([bm.verts.new(p + (u * math.cos(2 * math.pi * i / sides) + v * math.sin(2 * math.pi * i / sides)) * radius) for i in range(sides)])
    pairs = list(zip(rows, rows[1:])) + ([(rows[-1], rows[0])] if closed else [])
    for A, B in pairs:
        for i in range(sides):
            bm.faces.new((A[i], A[(i + 1) % sides], B[(i + 1) % sides], B[i]))
    if caps and not closed:
        bm.faces.new(list(reversed(rows[0])))
        bm.faces.new(rows[-1])
    return obj_from_bm(name, bm, mat, props, smooth=True)


def box(name, centre, size, R, mat, props=None, bevel=0.0):
    """长方体：中心 centre，尺寸 (sx, sy, sz) 沿 R 的三列。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    S = Matrix.Diagonal((*size, 1.0))
    M = Matrix.Translation(Vector(centre)) @ R.to_4x4() @ S
    bm.transform(M)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
    o = obj_from_bm(name, bm, mat, props, smooth=False)
    mark_sharp(o, 40)
    return o


def hull(name, pts, mat, props=None, bevel=0.0):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(p)) for p in pts]
    bmesh.ops.convex_hull(bm, input=vs)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=bm.verts, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=bm.edges[:], offset=bevel, segments=1, profile=0.5, affect="EDGES", clamp_overlap=True)
    o = obj_from_bm(name, bm, mat, props, smooth=False)
    mark_sharp(o, 40)
    return o


def mark_sharp(o, angle):
    """折角大于 angle 的边标锐边（导出时法线在此断开；网页线条层取特征边）。"""
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    thr = math.radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0.0) > thr:
            e.smooth = False
    bm.to_mesh(me)
    bm.free()


def frame_from(x, z):
    """以 x 为第一轴、z 为大致第三轴的旋转矩阵（列）。"""
    x = Vector(x).normalized()
    z = Vector(z)
    z = (z - x * z.dot(x)).normalized()
    y = z.cross(x)
    return Matrix((x, y, z)).transposed()
