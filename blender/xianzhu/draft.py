"""Tripo 起稿 → 本作坐标（WORKFLOW「AI 起稿」第 5 步：缩放、站正、对称……）。

源 GLB 路径是参数：发布版在 Tripo 付费版按同输入、同参数重新生成后，换文件重跑即可（DRAFT_BODY / DRAFT_HELMET，或命令行
`--draft-body` / `--draft-helmet`）。重生成后零件编号可能变，所以零件按位置认（PART_RULES），不按编号认。

坐标：Tripo GLB 导入后人面朝 −Y、左手在 +X、Z 上；转到本作 x 前、y 左、z 上（绕 Z 转 +90°），按设定图米制标定
（盔顶 → 鞋底 1.80 m）等比缩放，脚底 z = 0，对称面 y = 0。
"""
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
DRAFT_BODY = os.path.join(ROOT, "refs", "ai_draft", "X1_软态正视_hd分件.glb")
DRAFT_HELMET = os.path.join(ROOT, "refs", "ai_draft", "X1_头盔闭眼_smartmesh.glb")
FIG_H = 1.80  # 设定图米制标定：盔顶 → 鞋底


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    # 把父级变换烘进网格，去掉空物体
    for o in meshes:
        M = o.matrix_world.copy()
        o.parent = None
        o.data.transform(M)
        o.matrix_world = Matrix()
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return meshes


def verts(o):
    V = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", V)
    return V.reshape(-1, 3)


def set_verts(o, V):
    o.data.vertices.foreach_set("co", np.asarray(V, float).ravel())
    o.data.update()


def transform_all(objs, M):
    for o in objs:
        o.data.transform(M)
        o.data.update()


# 零件按位置认：(名字, 判别函数(中心 c, 包围盒 lo, hi, 全身高 H))，本作坐标、缩放后
def classify_parts(objs):
    """返回 {名字: 对象}：helmet、face、torso、uarm.l/r、farm.l/r、hand.l/r、thigh.l/r、shin.l/r、boot.l/r。"""
    info = []
    for o in objs:
        V = verts(o)
        info.append((o, V.mean(0), V.min(0), V.max(0), len(V)))
    out = {}
    torso = max(info, key=lambda t: t[4] if 0.8 < t[1][2] < 1.3 else 0)
    out["torso"] = torso[0]
    rest = [t for t in info if t[0] is not torso[0]]
    for o, c, lo, hi, n in rest:
        side = "l" if c[1] > 0 else "r"
        z, y = c[2], abs(c[1])
        if z > 1.45:
            key = "helmet" if hi[2] > 1.7 else "face"
        elif z < 0.12:
            key = f"boot.{side}"
        elif z < 0.45:
            key = f"shin.{side}"
        elif z < 0.85 and y < 0.2:
            key = f"thigh.{side}"
        elif z < 0.97 and y > 0.22:
            key = f"hand.{side}"
        elif z < 1.17:
            key = f"farm.{side}"
        else:
            key = f"uarm.{side}"
        if key in out:
            raise RuntimeError(f"零件认重了：{key}（重生成后零件位置变了？改 classify_parts 的分界）")
        out[key] = o
    for k, o in out.items():
        o.name = f"draft.{k}"
    return out


def normalize(objs, fig_h=FIG_H):
    """转向（面朝 +x、左手 +y）、等比缩放到 fig_h、脚底着地、左右对中。返回缩放比。"""
    transform_all(objs, Matrix.Rotation(math.pi / 2, 4, "Z"))
    allV = np.concatenate([verts(o) for o in objs])
    lo, hi = allV.min(0), allV.max(0)
    s = fig_h / (hi[2] - lo[2])
    transform_all(objs, Matrix.Diagonal((s, s, s, 1.0)) @ Matrix.Translation(Vector((0, 0, -lo[2]))))
    return s


def symmetry_plane(V, iters=12, sample=20000):
    """对称面拟合：y = a + b·x（左右镜像后最近点距离最小，小角度 + 偏移，ICP 式迭代）。返回 (a, b, 残差 m)。"""
    rng = np.random.default_rng(0)
    P = V[rng.choice(len(V), min(sample, len(V)), replace=False)]
    kd = KDTree(len(P))
    for i, p in enumerate(P):
        kd.insert(Vector(p), i)
    kd.balance()
    a, b = float(np.median(P[:, 1])), 0.0
    for _ in range(iters):
        # 关于直线 y = a + b x 的镜像（竖直平面）
        n = np.array([-b, 1.0, 0.0]) / math.hypot(1.0, b)
        d = (P @ n) - a / math.hypot(1.0, b)
        Q = P - 2 * d[:, None] * n
        Mt = np.array([P[kd.find(Vector(q))[1]] for q in Q])
        # 对应点的中点应落在对称面上：最小二乘拟合 y = a + b x
        mid = (Mt + P) / 2  # 一对镜像对应点的中点在对称面上
        A = np.c_[np.ones(len(mid)), mid[:, 0]]
        a, b = np.linalg.lstsq(A, mid[:, 1], rcond=None)[0]
    n = np.array([-b, 1.0, 0.0]) / math.hypot(1.0, b)
    d = (P @ n) - a / math.hypot(1.0, b)
    Q = P - 2 * d[:, None] * n
    res = np.array([kd.find(Vector(q))[2] for q in Q])
    return float(a), float(b), float(np.median(res))


def stand_straight(objs, refs):
    """按 refs（躯干 + 四肢，不含头盔）合起来的对称面把整体转正（绕 z）、移到 y = 0，迭代到转角 < 0.05°。"""
    log = []
    for _ in range(12):
        a, b, m = symmetry_plane(np.concatenate([verts(o) for o in refs]))
        ang = math.atan(b)
        transform_all(objs, Matrix.Rotation(-ang, 4, "Z") @ Matrix.Translation(Vector((0, -a, 0))))
        log.append((round(math.degrees(ang), 3), round(a, 4), round(m, 4)))
        if abs(math.degrees(ang)) < 0.05 and abs(a) < 2e-4:
            break
    return log


# —— 对称：服装底形左右对称，单侧件（左胸脐带接口、软管）保留单侧 ——————————————————————
def mirror_half(o, keep_negative=True):
    """把网格沿 y = 0 切开，只留一侧（默认着装者右侧 y < 0），镜像补出另一侧，中线焊上。"""
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(o.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6, plane_co=(0, 0, 0), plane_no=(0, 1, 0), clear_outer=keep_negative, clear_inner=not keep_negative)
    bmesh.ops.mirror(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], axis="Y", merge_dist=2e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def mirror_copy(src, dst):
    """dst 的网格换成 src 关于 y = 0 的镜像（左右肢体成对时用一侧替另一侧）。"""
    me = src.data.copy()
    me.transform(Matrix.Diagonal((1, -1, 1, 1)))
    me.flip_normals()
    old = dst.data
    dst.data = me
    bpy.data.meshes.remove(old)


def outside_parts(orig, sym, side=1, core_d=0.012, grow_d=0.002, grow=6, min_faces=150, exclude=()):
    """orig（对称前的网格）里在 side 一侧（y·side > 0.02）、离对称后的表面 sym 很远（> core_d，软管与接口离服装 2～4 cm，
    左右不对称的织带只差 1 cm 左右）的面做核，再沿网格往外长 grow 圈（只长到离面 > grow_d 的地方，把软管根部带上），
    按连通块取出，面数够大的块才要；exclude：[(lo, hi)] 包围盒内的不要。返回 (块列表 [(顶点, 面)], 每点带符号距离)。"""
    import bmesh
    from mathutils.bvhtree import BVHTree

    bm = bmesh.new()
    bm.from_mesh(sym.data)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    V = verts(orig)
    d = np.empty(len(V))
    sgn = np.empty(len(V))
    for i, p in enumerate(V):
        lo, n, _, dist = tree.find_nearest(Vector(p))
        d[i] = dist
        sgn[i] = 1.0 if (Vector(p) - lo).dot(n) >= 0 else -1.0
    sd = d * sgn
    zone = V[:, 1] * side > 0.02
    for lo, hi in exclude:
        zone &= ~np.all((V >= np.array(lo)) & (V <= np.array(hi)), axis=1)
    sel = zone & (sd > core_d)
    F = [list(p.vertices) for p in orig.data.polygons]
    ok = zone & (sd > grow_d)
    for _ in range(grow):
        nxt = sel.copy()
        for f in F:
            if any(sel[i] for i in f):
                for i in f:
                    if ok[i]:
                        nxt[i] = True
        sel = nxt
    out_v = sel
    keep = [f for f in F if all(out_v[i] for i in f)]
    # 连通块
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for f in keep:
        for a, b in zip(f, f[1:]):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
    comps = {}
    for f in keep:
        comps.setdefault(find(f[0]), []).append(f)
    out = []
    for fs in comps.values():
        if len(fs) < min_faces:
            continue
        ids = sorted({i for f in fs for i in f})
        remap = {v: k for k, v in enumerate(ids)}
        out.append((V[ids], [[remap[i] for i in f] for f in fs]))
    return out, sd


def build_body(props, path=DRAFT_BODY):
    """起稿身体 → 对称、单侧件分出来、起稿自带的头盔丢掉。返回 (零件 {名字: 对象}, 单侧附件对象列表, 日志)。"""
    import geo

    objs = import_glb(path)
    s = normalize(objs)
    parts = classify_parts(objs)
    log = {"source": os.path.relpath(path, ROOT), "scale": round(s, 5)}
    log["straighten"] = stand_straight(objs, [o for k, o in parts.items() if k not in ("helmet", "face")])
    bpy.data.objects.remove(parts.pop("helmet"))  # 换成 Smart Mesh 那顶（helmet_draft.py）
    torso = parts["torso"]
    orig = torso.copy()
    orig.data = torso.data.copy()
    bpy.context.scene.collection.objects.link(orig)
    mirror_half(torso)
    for a in ("uarm", "farm", "hand", "thigh", "shin", "boot"):
        mirror_copy(parts[f"{a}.r"], parts[f"{a}.l"])
    comps, _ = outside_parts(orig, torso, side=1)
    bpy.data.objects.remove(orig)
    att = [geo.obj_from_arrays(f"xz.suit.hose{k}", V, F, "hose", props) for k, (V, F) in enumerate(comps)]
    log["attachments"] = [len(F) for _, F in comps]
    for k, o in parts.items():
        o.data.materials.clear()
        o.data.materials.append(geo.material("skin" if k == "face" else "suit"))
        for kk, v in props.items():
            o[kk] = v
        for p in o.data.polygons:
            p.use_smooth = True
    return parts, att, log
