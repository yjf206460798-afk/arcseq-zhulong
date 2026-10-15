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
DRAFT_HELMET = os.path.join(ROOT, "refs", "ai_draft", "X1_头盔闭眼修正_smartmesh.glb")  # 早先那顶 X1_头盔闭眼_smartmesh 作废
DRAFT_CONNECTOR = os.path.join(ROOT, "refs", "ai_draft", "X1_脐带接头_smartmesh.glb")
FIG_H = 1.80  # 设定图米制标定：盔顶 → 鞋底


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    # 把父级变换烘进网格，去掉空物体
    for o in meshes:
        M = o.matrix_world.copy()
        o["src_file"] = os.path.relpath(path, ROOT)
        o["src_name"] = o.name  # GLB 里的原名：原样对照渲染（asis.py）按它配对
        o["xform"] = flat(M)  # 原样导入 → 当前网格的累计变换（只含刚体 + 等比缩放）
        o.parent = None
        o.data.transform(M)
        o.matrix_world = Matrix()
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return meshes


# —— 保法线（PATTERNS「外部模型的导入、检查与保法线」）——————————————————————————————————————
# Tripo 的平面与硬棱全靠 GLB 自带的自定义法线（导入后 sharp_edge / sharp_face 全是 0）。自定义法线按“角空间”编码，
# 刚体变换、等比缩放之后仍然有效（Mesh.transform 会一起转），但任何改拓扑的操作（bmesh 切开、镜像、删面）之后就错位。
# 做法：改拓扑之前把每个角的世界法线存进角属性 NORMAL_ATTR（bmesh 切开时插值、复制时照抄），改完再写回自定义法线；
# 镜像出来的那一半把 y 分量取反。
NORMAL_ATTR = "tripo_n"


def keep_normals(o):
    """当前每个角的法线（含自定义法线）→ 角属性 NORMAL_ATTR。"""
    me = o.data
    N = np.empty(len(me.loops) * 3)
    me.corner_normals.foreach_get("vector", N)
    at = me.attributes.get(NORMAL_ATTR) or me.attributes.new(NORMAL_ATTR, "FLOAT_VECTOR", "CORNER")
    at.data.foreach_set("vector", N)


def restore_normals(o, flip=None):
    """角属性 NORMAL_ATTR → 自定义法线。flip(面中心) 为真的面（镜像出来的一半）y 取反；属性坏掉（长度≈0）的角用面法线。"""
    me = o.data
    at = me.attributes.get(NORMAL_ATTR)
    if at is None:
        return 0
    N = np.empty(len(me.loops) * 3)
    at.data.foreach_get("vector", N)
    N = N.reshape(-1, 3)
    if flip is not None:
        for p in me.polygons:
            if flip(p.center):
                N[p.loop_start:p.loop_start + p.loop_total, 1] *= -1
    L = np.linalg.norm(N, axis=1)
    bad = L < 0.5
    if bad.any():
        FN = np.empty(len(me.polygons) * 3)
        me.polygons.foreach_get("normal", FN)
        FN = FN.reshape(-1, 3)
        own = np.empty(len(me.loops), int)
        for p in me.polygons:
            own[p.loop_start:p.loop_start + p.loop_total] = p.index
        N[bad] = FN[own[bad]]
        L[bad] = 1.0
    N = N / L[:, None]
    for p in me.polygons:
        p.use_smooth = True
    me.normals_split_custom_set([tuple(n) for n in N])
    return int(bad.sum())


def mark_hard(o, angle=25.0):
    """线条（L2 边标记）只取“硬棱”：Tripo 网格两侧面的角法线在这条边上断开（夹角 > angle）的边；我们自己建的件
    （没有自定义法线）取 use_edge_sharp 的边。Freestyle 的折痕检测在三十万面的起稿网格上满身都是线，不用。返回标记边数。"""
    me = o.data
    n_e = len(me.edges)
    if not n_e:
        return 0
    flags = np.zeros(n_e, bool)
    if me.has_custom_normals:
        N = np.empty(len(me.loops) * 3)
        me.corner_normals.foreach_get("vector", N)
        N = N.reshape(-1, 3)
        LV = np.empty(len(me.loops), int)
        me.loops.foreach_get("vertex_index", LV)
        LE = np.empty(len(me.loops), int)
        me.loops.foreach_get("edge_index", LE)
        own = np.empty(len(me.loops), int)
        for p in me.polygons:
            own[p.loop_start:p.loop_start + p.loop_total] = p.index
        corner = {}
        for li in range(len(LV)):
            corner[(own[li], LV[li])] = li
        ef = {}
        for li in range(len(LE)):
            ef.setdefault(LE[li], set()).add(own[li])
        cth = math.cos(math.radians(angle))
        EV = np.empty(n_e * 2, int)
        me.edges.foreach_get("vertices", EV)
        EV = EV.reshape(-1, 2)
        for e, fs in ef.items():
            if len(fs) != 2:
                continue
            fa, fb = fs
            for v in EV[e]:
                if N[corner[(fa, v)]] @ N[corner[(fb, v)]] < cth:
                    flags[e] = True
                    break
    else:
        sh = me.attributes.get("sharp_edge")
        if sh is not None:
            sh.data.foreach_get("value", flags)
    seam = np.zeros(n_e, bool)
    me.edges.foreach_get("use_seam", seam)
    flags |= seam
    at = me.attributes.get("freestyle_edge") or me.attributes.new("freestyle_edge", "BOOLEAN", "EDGE")
    at.data.foreach_set("value", flags)
    return int(flags.sum())


def verts(o):
    V = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", V)
    return V.reshape(-1, 3)


def set_verts(o, V):
    o.data.vertices.foreach_set("co", np.asarray(V, float).ravel())
    o.data.update()


def flat(M):
    return [float(x) for r in M for x in r]


def unflat(L):
    return Matrix([L[0:4], L[4:8], L[8:12], L[12:16]])


def transform_all(objs, M):
    for o in objs:
        o.data.transform(M)
        o.data.update()
        if "xform" in o:
            o["xform"] = flat(M @ unflat(list(o["xform"])))


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
    keep = (lambda c: c.y > 0) if keep_negative else (lambda c: c.y < 0)
    restore_normals(o, flip=keep)


def mirror_copy(src, dst):
    """dst 的网格换成 src 关于 y = 0 的镜像（左右肢体成对时用一侧替另一侧）。"""
    me = src.data.copy()
    me.transform(Matrix.Diagonal((1, -1, 1, 1)))
    me.flip_normals()
    old = dst.data
    dst.data = me
    bpy.data.meshes.remove(old)
    restore_normals(dst, flip=lambda c: True)


def outside_parts(orig, sym, side=1, core_d=0.012, grow_d=0.002, grow=6, min_faces=150, exclude=()):
    """orig（对称前的网格）里在 side 一侧（y·side > 0.02）、离对称后的表面 sym 很远（> core_d，软管与接口离服装 2～4 cm，
    左右不对称的织带只差 1 cm 左右）的面做核，再沿网格往外长 grow 圈（只长到离面 > grow_d 的地方，把软管根部带上），
    按连通块取出，面数够大的块才要；exclude：[(lo, hi)] 包围盒内的不要。返回 (块列表 [orig 的面号], 每点带符号距离)。"""
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
    keep_i = [k for k, f in enumerate(F) if all(out_v[i] for i in f)]
    keep = [F[k] for k in keep_i]
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
    for k in keep_i:
        comps.setdefault(find(F[k][0]), []).append(k)
    out = [fs for fs in comps.values() if len(fs) >= min_faces]
    return out, sd


def extract_faces(src, face_ids, name):
    """src 的一部分面复制成新对象（保住角属性，所以法线能写回）。"""
    import bmesh

    o = src.copy()
    o.data = src.data.copy()
    o.name = name
    o.data.name = name
    bpy.context.scene.collection.objects.link(o)
    want = set(face_ids)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in want], context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    restore_normals(o)
    return o


def build_body(props, path=DRAFT_BODY):
    """起稿身体 → 对称、单侧件分出来、起稿自带的头盔丢掉。返回 (零件 {名字: 对象}, 单侧附件对象列表, 日志)。"""
    import geo

    objs = import_glb(path)
    s = normalize(objs)
    parts = classify_parts(objs)
    log = {"source": os.path.relpath(path, ROOT), "scale": round(s, 5)}
    log["straighten"] = stand_straight(objs, [o for k, o in parts.items() if k not in ("helmet", "face")])
    for o in objs:
        keep_normals(o)
    log["helmet_src"] = parts["helmet"]["src_name"]  # 原样对照时把它藏掉
    bpy.data.objects.remove(parts.pop("helmet"))  # 换成 Smart Mesh 修正版（helmet_tripo.py）
    torso = parts["torso"]
    orig = torso.copy()
    orig.data = torso.data.copy()
    bpy.context.scene.collection.objects.link(orig)
    mirror_half(torso)
    for a in ("uarm", "farm", "hand", "thigh", "shin", "boot"):
        mirror_copy(parts[f"{a}.r"], parts[f"{a}.l"])
    comps, _ = outside_parts(orig, torso, side=1)
    att = [extract_faces(orig, fs, f"xz.suit.hose{k}") for k, fs in enumerate(comps)]
    bpy.data.objects.remove(orig)
    for o in att:
        o.data.materials.clear()
        o.data.materials.append(geo.material("hose"))
        for kk, v in props.items():
            o[kk] = v
    log["attachments"] = [len(fs) for fs in comps]
    for k, o in parts.items():
        o.data.materials.clear()
        o.data.materials.append(geo.material("skin" if k == "face" else "suit"))
        for kk, v in props.items():
            o[kk] = v
    return parts, att, log
