"""人体底模：MakeHuman CC0 基础网格 → Blender 网格 + 骨架（默认骨架、默认权重）→ 平滑去解剖细节 → 摆姿。

- 平滑（X1 定）：Blender 内置 Laplacian Smooth 修改器，按骨段加权（躯干 1、大腿 / 上臂 0.9、前臂 / 小腿 0.7，头、手、脚 0）
  在静止姿态里应用掉——胸、腹、臀的解剖起伏抹平，大体积保留；摆姿后再挂 Corrective Smooth（静止形 = 平滑后的形）
  抹掉线性蒙皮在肩、腋、胯的鼓包与折棱。身体只是服装的绑定靶面，衣服底下的部分最后被 delete group 删掉。
- 摆姿：世界坐标里按“骨头指向”摆（aim：最小旋转把骨头转到目标方向；twist：绕骨轴自转），父骨先、子骨后。
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from mh import MH

SMOOTH_W = {"torso": 1.0, "thigh": 0.9, "uarm": 0.9, "farm": 0.7, "shin": 0.7}
SEG = {
    "torso": ["root", "spine05", "spine04", "spine03", "spine02", "spine01", "pelvis.L", "pelvis.R", "clavicle.L", "clavicle.R",
              "shoulder01.L", "shoulder01.R", "breast.L", "breast.R"],
    "head": ["neck01", "neck02", "neck03", "head"],
}
for _s in "LR":
    SEG.update({f"thigh.{_s}": [f"upperleg01.{_s}", f"upperleg02.{_s}"], f"shin.{_s}": [f"lowerleg01.{_s}", f"lowerleg02.{_s}"],
                f"foot.{_s}": [f"foot.{_s}"], f"uarm.{_s}": [f"upperarm01.{_s}", f"upperarm02.{_s}"],
                f"farm.{_s}": [f"lowerarm01.{_s}", f"lowerarm02.{_s}"], f"hand.{_s}": [f"wrist.{_s}"]})
SEG_BONES = {b: s for s, L in SEG.items() for b in L}


class Body:
    def __init__(self, mh: MH):
        self.mh = mh
        P, faces, ids = mh.piece("body")
        self.ids = ids  # 局部 → 全局顶点号
        self.faces = faces
        self.rest = P
        # 每个顶点的主骨与骨段
        best = np.full(len(mh.P), -1.0)
        who = np.full(len(mh.P), "", dtype=object)
        for b, L in mh.weights.items():
            vi = np.array([i for i, _ in L], int)
            w = np.array([w for _, w in L])
            m = w > best[vi]
            who[vi[m]] = b
            best[vi[m]] = w[m]
        self.bone_of = who  # 全局
        self.seg_g = np.array([seg_of(mh, b) for b in who], dtype=object)
        self.seg = self.seg_g[ids]
        self.obj = self._mesh()
        self.rig = None

    def rigged(self):
        """平滑之后再挂骨架与 Corrective Smooth（修改器顺序：骨架 → 校正平滑）。"""
        self.rig = self._rig()
        return self

    # —— 网格与权重 ——
    def _mesh(self):
        me = bpy.data.meshes.new("xz.body")
        me.from_pydata([tuple(v) for v in self.rest], [], self.faces)
        me.update()
        o = bpy.data.objects.new("xz.body", me)
        bpy.context.scene.collection.objects.link(o)
        loc = {g: k for k, g in enumerate(self.ids)}
        for b, L in self.mh.weights.items():
            vg = o.vertex_groups.new(name=b)
            for gi, w in L:
                k = loc.get(gi)
                if k is not None:
                    vg.add([k], w, "REPLACE")
        sm = o.vertex_groups.new(name="smooth")
        for k, s in enumerate(self.seg):
            w = SMOOTH_W.get(s.split(".")[0], 0.0)
            if w > 0:
                sm.add([k], w, "REPLACE")
        for p in me.polygons:
            p.use_smooth = True
        return o

    def smooth(self, shrink=40, restore=80):
        """顶点组加权的 Laplacian 平滑，在静止姿态里抹平解剖细节（胸、腹、臀的起伏），大体积保留：
        ① 按骨段权重做 Laplacian 收缩 shrink 轮（局部起伏消失，整体也缩一圈）；② 每个顶点沿法线缩了多少，这张“缩量”场
        再做 restore 轮 Laplacian 低通（只剩大尺度），沿法线加回去——体积回来，局部鼓包不回来。权重场本身先抹匀 10 轮，
        骨段交界（前臂 → 手）不出台阶。
        X1 实测：Blender 的 Laplacian Smooth 修改器在顶点组权重不全为 1 时把四肢拉成细杆，“保体积”还把整个网格
        （含权重 0 的头）一起放大；Taubin λ|μ 留得住乳房这类低频起伏。所以同一个 Laplacian 算子在 numpy 里做；
        摆姿后的 Corrective Smooth 仍用 Blender 内置修改器。"""
        P0 = self.rest.copy()
        E = set()
        for f in self.faces:
            for a, b in zip(f, f[1:] + f[:1]):
                E.add((min(a, b), max(a, b)))
        E = np.array(sorted(E))
        cnt = np.zeros(len(P0))
        np.add.at(cnt, E[:, 0], 1)
        np.add.at(cnt, E[:, 1], 1)
        cnt = np.maximum(cnt, 1)[:, None]

        def avg(X):
            acc = np.zeros_like(X)
            np.add.at(acc, E[:, 0], X[E[:, 1]])
            np.add.at(acc, E[:, 1], X[E[:, 0]])
            return acc / cnt

        w = np.array([SMOOTH_W.get(sg.split(".")[0], 0.0) for sg in self.seg])[:, None]
        for _ in range(10):
            w = 0.5 * w + 0.5 * avg(w)
        Q = P0.copy()
        for _ in range(shrink):
            Q = Q + w * 0.5 * (avg(Q) - Q)
        N = normals(Q, self.faces)
        D = ((P0 - Q) * N).sum(1)[:, None]
        for _ in range(restore):
            D = D + 0.6 * (avg(D) - D)
        P = Q + N * D * np.minimum(w * 4, 1.0)
        self.rest = P
        me = self.obj.data
        me.vertices.foreach_set("co", P.ravel())
        me.update()

    # —— 骨架 ——
    def _rig(self):
        arm = bpy.data.armatures.new("xz.rig")
        rig = bpy.data.objects.new("xz.rig", arm)
        bpy.context.scene.collection.objects.link(rig)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        B = self.mh.skel["bones"]
        eb = {}
        for name in B:
            e = arm.edit_bones.new(name)
            e.head = Vector(self.mh.head(name))
            e.tail = Vector(self.mh.tail(name))
            if (e.tail - e.head).length < 1e-5:
                e.tail = e.head + Vector((0, 0, 0.01))
            eb[name] = e
        for name, b in B.items():
            if b["parent"]:
                eb[name].parent = eb[b["parent"]]
        bpy.ops.object.mode_set(mode="OBJECT")
        mod = self.obj.modifiers.new("armature", "ARMATURE")
        mod.object = rig
        cs = self.obj.modifiers.new("corrective", "CORRECTIVE_SMOOTH")
        cs.iterations = 12
        cs.smooth_type = "LENGTH_WEIGHTED"
        cs.rest_source = "ORCO"
        cs.vertex_group = "smooth"
        return rig

    def pb(self, name):
        return self.rig.pose.bones[name]

    def bone_dir(self, name):
        p = self.pb(name)
        return (self.rig.matrix_world @ p.tail - self.rig.matrix_world @ p.head).normalized()

    def bone_head(self, name):
        return self.rig.matrix_world @ self.pb(name).head

    def rotate(self, name, R):
        """骨头绕自己的头（世界坐标）转 R（3×3）。"""
        p = self.pb(name)
        h = p.head.copy()
        M = Matrix.Translation(h) @ R.to_4x4() @ Matrix.Translation(-h)
        p.matrix = M @ p.matrix
        bpy.context.view_layer.update()

    def aim(self, name, direction):
        d = Vector(direction).normalized()
        q = self.bone_dir(name).rotation_difference(d)
        self.rotate(name, q.to_matrix())

    def twist(self, name, angle):
        self.rotate(name, Quaternion(self.bone_dir(name), angle).to_matrix())

    def reset_pose(self):
        for p in self.rig.pose.bones:
            p.matrix_basis = Matrix()
        bpy.context.view_layer.update()

    def evaluated(self):
        """当前姿态下的身体顶点（修改器全算：骨架 + Corrective Smooth）。"""
        dg = bpy.context.evaluated_depsgraph_get()
        e = self.obj.evaluated_get(dg)
        me = e.to_mesh()
        V = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", V)
        e.to_mesh_clear()
        return V.reshape(-1, 3)


def normals(V, faces):
    N = np.zeros_like(V)
    for f in faces:
        a, b, c = V[f[0]], V[f[1]], V[f[2]]
        n = np.cross(b - a, c - a)
        if len(f) == 4:
            n = n + np.cross(c - a, V[f[3]] - a)
        N[f] += n
    return N / np.maximum(np.linalg.norm(N, axis=1), 1e-12)[:, None]


def seg_of(mh, bone):
    c = bone
    while c and c not in SEG_BONES:
        c = mh.skel["bones"][c]["parent"]
    return SEG_BONES.get(c, "torso") if c else "torso"


def apply(obj, name):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=name)


def stand(body: Body):
    """X1 设定图的站姿：手臂自然下垂（外展约 10°、肘微屈、掌心朝大腿），两脚略收（护膝中心 ±0.14、靴中心 ±0.20）。"""
    body.reset_pose()
    for s, sg in (("L", 1), ("R", -1)):
        # 腿：髋 → 踝目标（y ±0.19），膝在两者连线上
        hip = body.bone_head(f"upperleg01.{s}")
        ank = body.bone_head(f"foot.{s}")
        tgt = Vector((ank.x, sg * 0.19, ank.z))
        q = (ank - hip).normalized().rotation_difference((tgt - hip).normalized())
        body.rotate(f"upperleg01.{s}", q.to_matrix())
        # 脚掌回正（朝前略外八 6°）
        f = body.bone_dir(f"foot.{s}")
        want = Vector((math.cos(math.radians(6)), sg * math.sin(math.radians(6)), f.z)).normalized()
        q = Vector((f.x, f.y, 0)).normalized().rotation_difference(Vector((want.x, want.y, 0)).normalized())
        body.rotate(f"foot.{s}", q.to_matrix())
        # 上臂：外展 10°、略向后 3°
        a = math.radians(10)
        body.aim(f"upperarm01.{s}", (-0.05, sg * math.sin(a), -math.cos(a)))
        # 前臂：肘微屈 12°（前臂向前），外展跟上臂
        b = math.radians(12)
        body.aim(f"lowerarm01.{s}", (math.sin(b), sg * math.sin(math.radians(6)), -math.cos(b)))
        # 掌心朝大腿：转前臂，使“食指 → 小指”方向朝后（拇指朝前）
        hand_twist(body, s)
        body.aim(f"wrist.{s}", body.bone_dir(f"lowerarm01.{s}") + Vector((0.08, 0, 0)))
        curl(body, s, 0.42)


def hand_twist(body, s):
    """绕前臂轴转，使手掌侧向（食指根 → 小指根）指向身后（−x）。"""
    for _ in range(3):
        a = body.bone_head(f"finger2-1.{s}")
        b = body.bone_head(f"finger5-1.{s}")
        side = (b - a)
        ax = body.bone_dir(f"lowerarm01.{s}")
        side = (side - ax * side.dot(ax)).normalized()
        want = Vector((-1, 0, 0))
        want = (want - ax * want.dot(ax)).normalized()
        ang = side.angle(want)
        sgn = 1 if ax.dot(side.cross(want)) > 0 else -1
        body.twist(f"lowerarm01.{s}", sgn * ang)


def curl(body, s, amount):
    """手指自然微屈：每节绕“食指 → 小指”轴弯 amount 弧度（拇指一半）。"""
    side = (body.bone_head(f"finger5-1.{s}") - body.bone_head(f"finger2-1.{s}")).normalized()
    for n in range(1, 6):
        for j in (1, 2, 3):
            b = f"finger{n}-{j}.{s}"
            if b not in body.rig.pose.bones:
                continue
            k = 0.5 if n == 1 else 1.0
            d = body.bone_dir(b)
            axis = d.cross(side).normalized()
            # 弯向掌心：掌心法向 = 侧向 × 指向（左右手相反）
            sgn = 1 if s == "L" else -1
            body.rotate(b, Quaternion(axis, -sgn * amount * k).to_matrix())


def head_parts(body, rest_V, BV, collar_top, props):
    """delete group 之后留下的身体：头面部（皮肤）+ 通讯帽（盖住头发、耳朵、颈部，只露脸）+ 两只眼球。
    返回 (件列表, 删除掩码)。删除掩码 = 被服装盖住的身体顶点（mhclo 的 delete_verts）：颈部以下、手、脚全删。"""
    import geo
    from bind import Binding

    seg = body.seg
    keep = np.array([seg[i] == "head" and BV[i, 2] > collar_top - 0.012 for i in range(len(BV))])
    F = [f for f in body.faces if all(keep[i] for i in f)]
    N = normals(BV, body.faces)
    eyeL, eyeR = np.array(body.bone_head("eye.L")), np.array(body.bone_head("eye.R"))
    ec = (eyeL + eyeR) / 2
    out = []

    # 脸部开口：前视 (y, z) 里的八边形（额头、两颊、下巴下），平面平行于 x 轴切开通讯帽，开口边是直的
    ez = float(ec[2])
    hole = [(0.0, ez + 0.05), (0.045, ez + 0.044), (0.066, ez + 0.018), (0.066, ez - 0.04), (0.05, ez - 0.09), (0.022, ez - 0.118),
            (-0.022, ez - 0.118), (-0.05, ez - 0.09), (-0.066, ez - 0.04), (-0.066, ez + 0.018), (-0.045, ez + 0.044)]

    cy, cz = sum(y for y, _ in hole) / len(hole), sum(z_ for _, z_ in hole) / len(hole)
    edges = []
    for (y0, z0), (y1, z1) in zip(hole, hole[1:] + hole[:1]):
        ny, nz = z1 - z0, -(y1 - y0)
        L = math.hypot(ny, nz)
        ny, nz = ny / L, nz / L
        if (cy - y0) * ny + (cz - z0) * nz > 0:  # 法线朝外
            ny, nz = -ny, -nz
        edges.append((y0, z0, ny, nz))

    def inside(p, grow=0.0):
        return all((p[1] - y0) * ny + (p[2] - z0) * nz <= grow for y0, z0, ny, nz in edges)

    front = lambda i: BV[i, 0] > ec[0] - 0.035 and N[i][0] > 0.05  # noqa: E731
    face = [f for f in F if all(front(i) and inside(BV[i], 0.015) for i in f)]
    V, F2, _ = _sub(BV, face)
    out.append(("skin", geo.obj_from_arrays("xz.body.face", V, F2, "skin", props)))
    import bmesh
    from mathutils import Vector
    V, F2, _ = _sub(BV + N * 0.0035, F)
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(v)) for v in V]
    for f in F2:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    for y0, z0, ny, nz in edges:
        geom = [f for f in bm.faces if f.calc_center_median().x > ec[0] - 0.03]
        bmesh.ops.bisect_plane(bm, geom=geom + list({e for f in geom for e in f.edges}) + list({v for f in geom for v in f.verts}),
                               dist=1e-6, plane_co=Vector((0, y0, z0)), plane_no=Vector((0, ny, nz)).normalized())
    dead = [f for f in bm.faces if f.calc_center_median().x > ec[0] - 0.03 and inside(f.calc_center_median(), -1e-5)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    out.append(("cap", geo.obj_from_bm("xz.body.cap", bm, "cap", props)))
    for s in "lr":
        P, Fe, _ = body.mh.piece(f"helper-{s}-eye")
        b = Binding(rest_V, body.faces, P)
        out.append(("eye", geo.obj_from_arrays(f"xz.body.eye.{s}", b.apply(BV), Fe, "eye", props)))
    return out, ~keep


def _sub(V, F):
    ids = sorted({i for f in F for i in f})
    remap = {v: k for k, v in enumerate(ids)}
    return V[ids], [[remap[i] for i in f] for f in F], ids


def translate(body, name, d):
    p = body.pb(name)
    p.matrix = Matrix.Translation(Vector(d)) @ p.matrix
    bpy.context.view_layer.update()


def aim_between(body, bone, a, b, direction):
    """转 bone（绕它的头），使关节 a → 关节 b 的连线指向 direction（a、b 是骨名，取其头）。"""
    v = body.bone_head(b) - body.bone_head(a)
    q = v.normalized().rotation_difference(Vector(direction).normalized())
    body.rotate(bone, q.to_matrix())


def ik(a, t, l1, l2, pole):
    d = t - a
    L = min(d.length, l1 + l2 - 1e-4)
    u = d.normalized()
    w = (pole - u * pole.dot(u)).normalized()
    ca = (l1 * l1 + L * L - l2 * l2) / (2 * l1 * L)
    ang = math.acos(max(-1.0, min(1.0, ca)))
    return a + (u * math.cos(ang) + w * math.sin(ang)) * l1


def sit(body, S, iters=4):
    """坐姿（座椅局部坐标，原点 = SRP）：躯干后仰 S["back"]、头比躯干立起 18°、大腿顺坐垫、膝内角 S["knee"]、
    脚掌朝 foot_dir、两手两段 IK 握住握把（肘朝外下）；再按“臀贴坐垫、背贴椅背”平移，重解手臂，迭代。"""
    body.reset_pose()
    sb, cb = math.sin(S["back"]), math.cos(S["back"])
    aim_between(body, "root", "root", "neck01", (-sb, 0, cb))
    hb = S["back"] - math.radians(18)
    aim_between(body, "neck01", "neck01", "head", (-math.sin(hb), 0, math.cos(hb)))
    mid = (body.bone_head("upperleg01.L") + body.bone_head("upperleg01.R")) / 2
    translate(body, "root", Vector((0.13, 0, 0.14)) - mid)
    rest = {s: (np.linalg.norm(body.mh.head(f"lowerarm01.{s}") - body.mh.head(f"upperarm01.{s}")),
                np.linalg.norm(body.mh.head(f"wrist.{s}") - body.mh.head(f"lowerarm01.{s}"))) for s in "LR"}
    t8 = math.tan(S["pan_tilt"])
    nb = Vector((cb, 0, sb))

    def limbs():
        for s, sg in (("L", 1), ("R", -1)):
            a = S["pan_tilt"] + math.radians(4)
            dth = Vector((math.cos(a), sg * 0.07, math.sin(a))).normalized()
            aim_between(body, f"upperleg01.{s}", f"upperleg01.{s}", f"lowerleg01.{s}", dth)
            dsh = Matrix.Rotation(math.pi - S["knee"], 3, "Y") @ dth
            aim_between(body, f"lowerleg01.{s}", f"lowerleg01.{s}", f"foot.{s}", dsh)
            aim_between(body, f"foot.{s}", f"foot.{s}", f"toe3-1.{s}", Vector(S["foot_dir"].tolist()))
            hd = Vector(S["hand_dir"][s].tolist()).normalized()
            wrist = Vector(S["grips"][s].tolist()) - hd * 0.075 - Vector(S["palm"][s].tolist()).normalized() * 0.025
            sh = body.bone_head(f"upperarm01.{s}")
            l1, l2 = rest[s]
            elbow = ik(sh, wrist, l1, l2, Vector((-0.25, sg * 0.55, -0.8)))
            aim_between(body, f"upperarm01.{s}", f"upperarm01.{s}", f"lowerarm01.{s}", elbow - sh)
            aim_between(body, f"lowerarm01.{s}", f"lowerarm01.{s}", f"wrist.{s}", wrist - elbow)
            # 手：转前臂使“食指根 → 小指根”朝 knuckles，再把手指向 hand_dir，握拳
            kn = Vector(S["knuckles"][s].tolist())
            for _ in range(3):
                side = body.bone_head(f"finger5-1.{s}") - body.bone_head(f"finger2-1.{s}")
                ax = body.bone_dir(f"lowerarm01.{s}")
                side = (side - ax * side.dot(ax)).normalized()
                want = (kn - ax * kn.dot(ax)).normalized()
                ang = side.angle(want)
                sgn = 1 if ax.dot(side.cross(want)) > 0 else -1
                body.twist(f"lowerarm01.{s}", sgn * ang)
            aim_between(body, f"wrist.{s}", f"wrist.{s}", f"finger3-1.{s}", hd)

    for _ in range(iters):
        limbs()
        V = body.evaluated()
        tor = np.array([sg_ == "torso" for sg_ in body.seg])
        along = V @ np.array([-sb, 0, cb])
        n = V @ np.array(nb)
        back = tor & (along > 0.12) & (along < 0.62) & (np.abs(V[:, 1]) < 0.16)
        hgt = V[:, 2] - V[:, 0] * t8
        pan = tor & (V[:, 0] > -0.02) & (V[:, 0] < 0.4) & (np.abs(V[:, 1]) < 0.17) & (along < 0.2)
        dn = (S["back_n"] + 0.004) - n[back].min()
        dh = (S["pan_h"] + 0.004) - hgt[pan].min()
        dx, dz = np.linalg.solve(np.array([[cb, sb], [-t8, 1.0]]), [dn, dh])
        translate(body, "root", Vector((dx, 0, dz)))
        if abs(dx) < 5e-4 and abs(dz) < 5e-4:
            break
    limbs()
    for s in "LR":
        curl(body, s, 0.95)
    return body.evaluated()
