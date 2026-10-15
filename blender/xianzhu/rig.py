"""骨架（作者 2026-10-15：用已有的人体骨架，把权重传到新网格上，摆进座椅）。

1. 对位：MakeHuman CC0 人体（body.py：平滑、默认骨架、默认权重）先摆设定图站姿（body.stand），再按段 ICP 贴到 Tripo
   底稿上：躯干只平移（x、z），四肢每段绕父关节转（大腿 → 小腿、上臂 → 前臂 → 手、脚），每段皮肤顶点找底稿对应零件上的
   最近点，Kabsch 求转角，迭代几轮。底稿零件按关节分好了，但零件分界环是斜的，不能直接当关节位置——关节仍取人体骨架的，
   只是转到底稿的姿态里。
2. 新静止姿态：人体皮肤按当前姿态应用，骨架的当前姿态设为静止姿态（底稿站姿 = 骨架静止姿态）。
3. 权重：Data Transfer（顶点组，最近面插值）从人体皮肤传到底稿各件，再按零件限定允许的骨头（上臂件只认肩、上臂、肘
   附近的骨头……）、归一化；手套整件跟腕骨、靴整件跟脚骨（手指一体，不弯）；扣件、护膝、软管这些后加的件从已上好权重
   的底稿件再传一次；头盔、脸、通讯帽刚体跟头骨。
4. 坐姿：body.sit（座椅局部坐标，原点 SRP）。接触（臀贴坐垫、背贴椅背）用底稿躯干的外表面量，不用人体皮肤。
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

import body as B
import draft

# 人体骨段（body.SEG）→ 底稿零件、绕哪个骨头转
LIMBS = [  # (人体骨段, 底稿零件, 转的骨头)
    ("thigh.{S}", "thigh.{s}", "upperleg01.{S}"),
    ("shin.{S}", "shin.{s}", "lowerleg01.{S}"),
    ("foot.{S}", "boot.{s}", "foot.{S}"),
    ("uarm.{S}", "uarm.{s}", "upperarm01.{S}"),
    ("farm.{S}", "farm.{s}", "lowerarm01.{S}"),
    ("hand.{S}", "hand.{s}", "wrist.{S}"),
]

# 每个底稿零件允许的骨头（前缀匹配，{S} = L / R）；不在里面的权重清零
ALLOW = {
    "torso": ["root", "spine", "pelvis", "clavicle", "shoulder01", "breast", "neck", "upperarm01.", "upperleg01."],
    "uarm": ["clavicle.{S}", "shoulder01.{S}", "upperarm01.{S}", "upperarm02.{S}", "lowerarm01.{S}"],
    "farm": ["upperarm02.{S}", "lowerarm01.{S}", "lowerarm02.{S}", "wrist.{S}"],
    "thigh": ["pelvis.{S}", "spine05", "root", "upperleg01.{S}", "upperleg02.{S}", "lowerleg01.{S}"],
    "shin": ["upperleg02.{S}", "lowerleg01.{S}", "lowerleg02.{S}", "foot.{S}"],
}
RIGID = {"hand": "wrist.{S}", "boot": "foot.{S}", "face": "head"}


def tree_of(V):
    kd = KDTree(len(V))
    for i, p in enumerate(V):
        kd.insert(p, i)
    kd.balance()
    return kd


def kabsch(P, Q, c):
    """绕定点 c 的最优转动 R：R(P − c) ≈ Q − c。"""
    A = P - c
    Bq = Q - c
    H = A.T @ Bq
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    return Vt.T @ D @ U.T


def fit(body, parts, iters=6, log=None):
    """人体按段 ICP 贴到底稿上。返回每段的残差（中位最近距离，米）。"""
    log = {} if log is None else log
    seg = body.seg
    # 躯干：平移 x、z
    T = draft.verts(parts["torso"])
    kd = tree_of(T)
    for _ in range(iters):
        V = body.evaluated()
        P = V[seg == "torso"]
        Q = np.array([kd.find(p)[0] for p in P])
        d = np.median(Q - P, axis=0)
        B.translate(body, "root", Vector((d[0], 0.0, d[2])))
    log["torso"] = float(np.median([kd.find(p)[2] for p in body.evaluated()[seg == "torso"]]))
    for S, s in (("L", "l"), ("R", "r")):
        for sg, part, bone in LIMBS:
            sg, part, bone = sg.format(S=S), part.format(s=s), bone.format(S=S)
            D = draft.verts(parts[part])
            kd = tree_of(D)
            for _ in range(iters):
                V = body.evaluated()
                P = V[seg == sg]
                Q = np.array([kd.find(p)[0] for p in P])
                c = np.array(body.bone_head(bone))
                R = kabsch(P, Q, c)
                ang = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2))))
                body.rotate(bone, Matrix(R.tolist()))
                if ang < 0.2:
                    break
            V = body.evaluated()
            log[sg] = round(float(np.median([kd.find(p)[2] for p in V[seg == sg]])), 4)
    return log


def rest_from_pose(body):
    """当前姿态设为新的静止姿态：人体皮肤按姿态应用（骨架 + 校正平滑），骨架 pose → rest，重挂骨架修改器。"""
    o = body.obj
    for m in list(o.modifiers):
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier=m.name)
    rig = body.rig
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    mod = o.modifiers.new("armature", "ARMATURE")
    mod.object = rig
    body.rest = draft.verts(o)


class RestJoints:
    """sit() 里取上臂 / 前臂长度用（body.mh.head）：换成新静止姿态里的骨头头部。"""

    def __init__(self, rig):
        self.H = {b.name: np.array(rig.matrix_world @ b.head_local) for b in rig.data.bones}

    def head(self, name):
        return self.H[name]


def allowed(part):
    kind, _, side = part.partition(".")
    S = side.upper()
    return [p.format(S=S) for p in ALLOW.get(kind, [])]


def transfer(src, dst, groups=None, rigid=None):
    """Data Transfer 顶点组：src → dst（最近面插值），只保留 groups（前缀）里的骨头，归一化。rigid：整件只跟一根骨头。"""
    for vg in list(dst.vertex_groups):
        dst.vertex_groups.remove(vg)
    if rigid:
        vg = dst.vertex_groups.new(name=rigid)
        vg.add(list(range(len(dst.data.vertices))), 1.0, "REPLACE")
        return 1
    m = dst.modifiers.new("weights", "DATA_TRANSFER")
    m.object = src
    m.use_vert_data = True
    m.data_types_verts = {"VGROUP_WEIGHTS"}
    m.vert_mapping = "POLYINTERP_NEAREST"
    m.layers_vgroup_select_src = "ALL"
    m.layers_vgroup_select_dst = "NAME"
    bpy.context.view_layer.objects.active = dst
    bpy.ops.object.datalayout_transfer(modifier=m.name)
    # 修改器挂在最前、应用（网格没改，自定义法线不受影响）
    while dst.modifiers.find(m.name) > 0:
        bpy.ops.object.modifier_move_up(modifier=m.name)
    bpy.ops.object.modifier_apply(modifier=m.name)
    names = [vg.name for vg in dst.vertex_groups]
    keep = [n for n in names if groups is None or any(n.startswith(g) for g in groups)]
    n_v = len(dst.data.vertices)
    W = np.zeros((n_v, len(keep)))
    idx = {n: k for k, n in enumerate(keep)}
    for v in dst.data.vertices:
        for g in v.groups:
            nm = dst.vertex_groups[g.group].name
            if nm in idx:
                W[v.index, idx[nm]] = g.weight
    tot = W.sum(1)
    # 允许的骨头一点权重都没有的顶点（零件边上）：给最近的有权重顶点的
    bad = tot < 1e-4
    if bad.any() and (~bad).any():
        P = draft.verts(dst)
        kd = tree_of(P[~bad])
        good = np.nonzero(~bad)[0]
        for i in np.nonzero(bad)[0]:
            W[i] = W[good[kd.find(P[i])[1]]]
        tot = W.sum(1)
    W = W / np.maximum(tot, 1e-9)[:, None]
    for vg in list(dst.vertex_groups):
        dst.vertex_groups.remove(vg)
    cnt = 0
    for n, k in idx.items():
        col = W[:, k]
        ids = np.nonzero(col > 1e-3)[0]
        if not len(ids):
            continue
        vg = dst.vertex_groups.new(name=n)
        for i in ids:
            vg.add([int(i)], float(col[i]), "REPLACE")
        cnt += 1
    return cnt


def weight_parts(body, parts):
    """底稿各件上权重。返回 {件名: 骨头数}。"""
    out = {}
    for k, o in parts.items():
        kind, _, side = k.partition(".")
        if kind in RIGID:
            out[k] = transfer(None, o, rigid=RIGID[kind].format(S=side.upper()))
        else:
            out[k] = transfer(body.obj, o, groups=allowed(k))
    return out


def weight_extras(parts, extras):
    """后加的件（扣件、护膝、靴底、软管、接头、铭文、脊线、颈封）：从已上好权重的底稿件（合成一个临时源）再传。"""
    src_objs = [o for k, o in parts.items()]
    tmp = []
    for o in src_objs:
        c = o.copy()
        c.data = o.data.copy()
        bpy.context.scene.collection.objects.link(c)
        tmp.append(c)
    bpy.ops.object.select_all(action="DESELECT")
    for c in tmp:
        c.select_set(True)
    bpy.context.view_layer.objects.active = tmp[0]
    bpy.ops.object.join()
    src = bpy.context.view_layer.objects.active
    src.name = "tmp.weights"
    out = {}
    for o in extras:
        if o.name.startswith("xz.boot."):
            side = o.name.split(".")[2]
            out[o.name] = transfer(None, o, rigid=f"foot.{side.upper()}")
        else:
            out[o.name] = transfer(src, o)
    bpy.data.objects.remove(src)
    return out


def attach(objs, rig):
    for o in objs:
        if o.modifiers.get("armature") is None:
            m = o.modifiers.new("armature", "ARMATURE")
            m.object = rig


class Draped:
    """给 body.sit 用：骨架、骨头操作照旧（Body 的方法），接触面换成底稿躯干的外表面。"""

    def __init__(self, body, torso):
        self.body = body
        self.torso = torso
        self.rig = body.rig
        self.mh = RestJoints(body.rig)
        self.seg = None

    def __getattr__(self, k):
        return getattr(self.body, k)

    def evaluated(self):
        dg = bpy.context.evaluated_depsgraph_get()
        e = self.torso.evaluated_get(dg)
        me = e.to_mesh()
        V = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", V)
        e.to_mesh_clear()
        V = V.reshape(-1, 3)
        self.seg = np.array(["torso"] * len(V), dtype=object)
        return V


def head_matrix(rig):
    """头骨当前姿态相对静止姿态的世界变换（头盔、脸刚体跟它走）。"""
    pb = rig.pose.bones["head"]
    return rig.matrix_world @ pb.matrix @ (rig.matrix_world @ pb.bone.matrix_local).inverted()
