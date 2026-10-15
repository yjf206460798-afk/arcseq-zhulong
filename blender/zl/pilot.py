"""⑧ 驾驶员「銜燭」软态（DESIGN 9.1.1、refs/concept/X1）：开源人体基础网格摆坐姿 + 服装（WORKFLOW：人体不用基本形拼）。

1. 读 blender/assets/makehuman/（CC0，见 THIRD_PARTY_NOTICES）：base.obj 只取 body 组；骨架关节 = 关节辅助体顶点的平均；权重按骨骼名。
   MakeHuman 坐标（x 左、y 上、z 前，分米）→ 机体（x 前、y 左、z 上，米），身高缩放到 HEIGHT。
2. 摆姿：肢体分段（躯干、颈头、大腿、小腿、脚、上臂、前臂、手），每段的旋转 = 静止标架 → 目标标架（段轴 + 铰链轴）；
   大腿 / 小腿、上臂 / 前臂共用一根铰链轴，膝、肘处不拧麻花。膝、肘位置用两段 IK 求（膝朝上，肘朝外下）。手指按节弯曲握拳。
   其余骨骼跟父骨走。线性蒙皮 v' = Σ w·(G v + t)。
3. 定位：躯干后仰 BACK；臀部贴坐垫、背贴椅背（按接触平移后重解 IK，迭代三次）。
4. 服装（软态）：整身外移 5 mm 成服装，按部位分片（左右前襟、上臂、前臂、大腿、小腿、手套、靴）——分片边界就是接缝线；
   腿腹分块气囊、护膝是外层贴片；脊背一条未点亮的暗朱红细线；挽具（肩带、胸扣、腰带、腿带）沿体表走，腰带两端扣在座椅侧板上；
   胸侧脐带接口。头部不建（头盔整个罩住）：头盔按 DESIGN 重做——盔顶前凸的眉骨、窄面罩、收起的暗琥珀遮光面罩、盔脊、面罩铰链、颈环。
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from kit.finish import finish
from kit.parts import box, cylinder, ellipsoid, hull, lathe, merge, new_object, pipe

HERE = os.path.dirname(os.path.abspath(__file__))
MH = os.path.join(os.path.dirname(HERE), "assets", "makehuman")
HEIGHT = 1.74  # 第 50 百分位左右的成年人
SUIT = 0.007  # 服装离（平滑后的）体表
X, Y, Z = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])


# —— 读入 ——————————————————————————————————————————————————————————————
def load():
    V, faces, g = [], [], None
    with open(os.path.join(MH, "base.obj")) as f:
        for line in f:
            if line.startswith("v "):
                V.append([float(t) for t in line.split()[1:4]])
            elif line.startswith("g "):
                g = line.split()[1]
            elif line.startswith("f ") and g == "body":
                faces.append([int(t.split("/")[0]) - 1 for t in line.split()[1:]])
    V = np.array(V)
    sk = json.load(open(os.path.join(MH, "default.mhskel")))
    wt = json.load(open(os.path.join(MH, "default_weights.mhw")))["weights"]
    used = np.unique(np.concatenate([np.array(f) for f in faces]))
    S = HEIGHT / (V[used, 1].max() - V[used, 1].min())
    P = np.stack([V[:, 2], V[:, 0], V[:, 1]], 1) * S
    P[:, 2] -= P[used, 2].min()  # 脚底 z = 0（静止站姿）
    return P, faces, used, sk, wt


def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def frame(axis, hinge):
    a = norm(np.asarray(axis, float))
    h = np.asarray(hinge, float)
    h = norm(h - a * h.dot(a))
    return np.stack([a, h, np.cross(a, h)], 1)


def rot(axis, ang):
    k = norm(np.asarray(axis, float))
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * K @ K


def ik(a, t, l1, l2, pole):
    """两段 IK：根 a、末端目标 t、两段长、极向 pole → 中间关节位置（够不着时伸直）。"""
    d = t - a
    L = min(np.linalg.norm(d), l1 + l2 - 1e-4)
    u = norm(d)
    w = norm(pole - u * pole.dot(u))
    ca = (l1 * l1 + L * L - l2 * l2) / (2 * l1 * L)
    ang = math.acos(max(-1.0, min(1.0, ca)))
    return a + l1 * (math.cos(ang) * u + math.sin(ang) * w)


# —— 骨架 ——————————————————————————————————————————————————————————————
class Rig:
    def __init__(self, P, sk, wt):
        self.P = P
        self.bones = sk["bones"]
        self.J = {k: P[v].mean(0) for k, v in sk["joints"].items()}
        self.W = {b: (np.array([i for i, _ in L], int), np.array([w for _, w in L])) for b, L in wt.items()}
        # 每个骨骼归哪一段：沿父链找到第一个列在 SEG 里的
        self.seg_of = {}
        for b in self.bones:
            c = b
            while c and c not in SEG_BONES:
                c = self.bones[c]["parent"]
            self.seg_of[b] = SEG_BONES.get(c, "torso")

    def h(self, b):
        return self.J[self.bones[b]["head"]]

    def t(self, b):
        return self.J[self.bones[b]["tail"]]


SEG = {
    "torso": ["root", "spine05", "spine04", "spine03", "spine02", "spine01", "pelvis.L", "pelvis.R", "clavicle.L", "clavicle.R", "shoulder01.L", "shoulder01.R"],
    "head": ["neck01", "neck02", "neck03", "head"],
}
for s in "LR":
    SEG.update({f"thigh.{s}": [f"upperleg01.{s}", f"upperleg02.{s}"], f"shin.{s}": [f"lowerleg01.{s}", f"lowerleg02.{s}"], f"foot.{s}": [f"foot.{s}"],
                f"uarm.{s}": [f"upperarm01.{s}", f"upperarm02.{s}"], f"farm.{s}": [f"lowerarm01.{s}", f"lowerarm02.{s}"], f"hand.{s}": [f"wrist.{s}"]})
SEG_BONES = {b: s for s, L in SEG.items() for b in L}


def pose(rig, seat, root):
    """root：躯干根（MakeHuman root 骨头部）的摆放位置。返回 {骨: (G, t)} 与关节位置。"""
    sb, cb = math.sin(seat["back"]), math.cos(seat["back"])
    T = {}
    # 躯干：后仰
    Gt = frame([-sb, 0, cb], Y) @ frame(rig.h("neck01") - rig.h("root"), Y).T
    Mt = (Gt, root - Gt @ rig.h("root"))
    T["torso"] = Mt
    ap = lambda M, p: M[0] @ p + M[1]  # noqa: E731
    # 颈、头：比躯干立起约 18°（看前方）
    hb = seat["back"] - math.radians(18)
    Gh = frame([-math.sin(hb), 0, math.cos(hb)], Y) @ frame(rig.t("head") - rig.h("neck01"), Y).T
    neck = ap(Mt, rig.h("neck01"))
    T["head"] = (Gh, neck - Gh @ rig.h("neck01"))
    joints = {"neck": neck}
    for s, sg in (("L", 1), ("R", -1)):
        # 腿：髋 → 脚踝目标（膝内角 KNEE），膝朝上
        hip = ap(Mt, rig.h(f"upperleg01.{s}"))
        l1 = np.linalg.norm(rig.h(f"lowerleg01.{s}") - rig.h(f"upperleg01.{s}"))
        l2 = np.linalg.norm(rig.h(f"foot.{s}") - rig.h(f"lowerleg01.{s}"))
        d = math.sqrt(l1 * l1 + l2 * l2 - 2 * l1 * l2 * math.cos(seat["knee"]))
        ankle = hip + norm(seat["feet"][s] - hip) * d
        knee = ik(hip, ankle, l1, l2, Z + X * 0.3)
        hinge = norm(np.cross(knee - hip, ankle - knee))
        G = frame(knee - hip, hinge) @ frame(rig.h(f"lowerleg01.{s}") - rig.h(f"upperleg01.{s}"), Y).T
        T[f"thigh.{s}"] = (G, hip - G @ rig.h(f"upperleg01.{s}"))
        G = frame(ankle - knee, hinge) @ frame(rig.h(f"foot.{s}") - rig.h(f"lowerleg01.{s}"), Y).T
        T[f"shin.{s}"] = (G, knee - G @ rig.h(f"lowerleg01.{s}"))
        toe = rig.h(f"toe3-1.{s}")
        G = frame(seat["foot_dir"], Y) @ frame(toe - rig.h(f"foot.{s}"), Y).T
        T[f"foot.{s}"] = (G, ankle - G @ rig.h(f"foot.{s}"))
        # 臂：肩 → 腕目标（握把后 7 cm），肘朝外下
        sh = ap(Mt, rig.h(f"upperarm01.{s}"))
        el_r, wr_r = rig.h(f"lowerarm01.{s}"), rig.h(f"wrist.{s}")
        l1, l2 = np.linalg.norm(el_r - rig.h(f"upperarm01.{s}")), np.linalg.norm(wr_r - el_r)
        hd = norm(seat["hand_dir"][s])
        wrist = seat["grips"][s] - hd * 0.075 - norm(seat["palm"][s]) * 0.025
        elbow = ik(sh, wrist, l1, l2, sg * Y * 0.55 - Z * 0.8 - X * 0.25)
        hinge_r = norm(np.cross(el_r - rig.h(f"upperarm01.{s}"), wr_r - el_r))
        hinge = norm(np.cross(elbow - sh, wrist - elbow))
        G = frame(elbow - sh, hinge) @ frame(el_r - rig.h(f"upperarm01.{s}"), hinge_r).T
        T[f"uarm.{s}"] = (G, sh - G @ rig.h(f"upperarm01.{s}"))
        G = frame(wrist - elbow, hinge) @ frame(wr_r - el_r, hinge_r).T
        T[f"farm.{s}"] = (G, elbow - G @ el_r)
        ax_r = rig.h(f"finger3-1.{s}") - wr_r
        side_r = rig.h(f"finger5-1.{s}") - rig.h(f"finger2-1.{s}")
        G = frame(hd, seat["knuckles"][s]) @ frame(ax_r, side_r).T
        T[f"hand.{s}"] = (G, wrist - G @ wr_r)
        joints.update({f"hip.{s}": hip, f"knee.{s}": knee, f"ankle.{s}": ankle, f"shoulder.{s}": sh, f"elbow.{s}": elbow, f"wrist.{s}": wrist})
    # 每根骨的变换：段的变换；手指再按节弯曲（绕“食指 → 小指”轴，弯向掌心）
    B = {}
    for b in rig.bones:
        B[b] = T[rig.seg_of[b]]
    for s in "LR":
        Gh_, th = T[f"hand.{s}"]
        side = norm(rig.h(f"finger5-1.{s}") - rig.h(f"finger2-1.{s}"))
        for n, curl in ((1, 0.35), (2, 1.05), (3, 1.1), (4, 1.15), (5, 1.2)):
            M = np.eye(4)
            for j in (1, 2, 3):
                b = f"finger{n}-{j}.{s}"
                if b not in rig.bones:
                    continue
                base = rig.h(b)
                fd = norm(rig.t(b) - base)
                palm = palm_dir(rig, s)
                k = norm(np.cross(fd, palm)) if n > 1 else norm(np.cross(fd, palm) + side * 0.3)
                R = rot(k, curl * (0.55 if j == 1 else 0.5))
                step = np.eye(4)
                step[:3, :3] = R
                step[:3, 3] = base - R @ base
                M = M @ step
                G = Gh_ @ M[:3, :3]
                B[b] = (G, Gh_ @ M[:3, 3] + th)
                for c in rig.bones:
                    if c.startswith(f"finger{n}-") and c.endswith(f".{s}") and int(c.split("-")[1][0]) > j:
                        B[c] = B[b]
    return B, joints


def palm_dir(rig, s):
    """掌心朝向（静止姿态）：中指三节的弯曲方向——指节凸向手背，所以掌心在凸出的反方向。"""
    a, m, t = rig.h(f"finger3-1.{s}"), rig.h(f"finger3-2.{s}"), rig.t(f"finger3-3.{s}")
    u = norm(t - a)
    off = (m - a) - u * (m - a).dot(u)
    if np.linalg.norm(off) > 1e-4:
        return -norm(off)
    ax = norm(rig.h(f"finger3-1.{s}") - rig.h(f"wrist.{s}"))
    side = norm(rig.h(f"finger5-1.{s}") - rig.h(f"finger2-1.{s}"))
    return norm(np.cross(side, ax)) * (1 if s == "L" else -1)


def skin(rig, B, idx):
    P = rig.P
    out = np.zeros((len(P), 3))
    tot = np.zeros(len(P))
    for b, (vi, w) in rig.W.items():
        if b not in B:
            continue
        G, t = B[b]
        out[vi] += w[:, None] * (P[vi] @ G.T + t)
        tot[vi] += w
    ok = tot > 1e-6
    out[ok] /= tot[ok, None]
    G, t = B["root"]
    out[~ok] = P[~ok] @ G.T + t
    return out


def solve(rig, seat):
    """摆姿 + 接触：臀贴坐垫、背贴椅背。"""
    sb, cb = math.sin(seat["back"]), math.cos(seat["back"])
    O = seat["srp"]
    nb = np.array([cb, 0, sb])  # 椅背法向（朝前上）
    t8 = math.tan(math.radians(8))
    dom = dominant(rig)
    torso = np.array([rig.seg_of.get(dom[i], "torso") == "torso" for i in range(len(rig.P))])
    root = O + nb * 0.12 + np.array([0, 0, 0.05])
    for _ in range(4):
        B, J = pose(rig, seat, root)
        Q = skin(rig, B, None)
        rel = Q - O
        along = rel @ np.array([-sb, 0, cb])
        n = rel @ nb
        back = torso & (along > 0.12) & (along < 0.62) & (np.abs(Q[:, 1]) < 0.16)
        fwd = (O[0] - Q[:, 0]) * -1 / math.cos(math.radians(8))  # 沿椅面向前（机体 +x）
        hgt = (Q[:, 2] - O[2]) - fwd * t8 * 0 - (Q[:, 0] - O[0]) * t8
        seatv = (fwd > 0.0) & (fwd < 0.4) & (np.abs(Q[:, 1]) < 0.17) & (along < 0.12)
        dn = (seat["back_n"] + 0.004) - n[back].min()
        dh = (seat["pan_h"] + 0.004) - hgt[seatv].min()
        A = np.array([[cb, sb], [-t8, 1.0]])
        dx, dz = np.linalg.solve(A, [dn, dh])
        root = root + np.array([dx, 0, dz])
        if abs(dx) < 5e-4 and abs(dz) < 5e-4:
            break
    B, J = pose(rig, seat, root)
    return skin(rig, B, None), B, J


def dominant(rig):
    best = np.full(len(rig.P), -1.0)
    who = [None] * len(rig.P)
    for b, (vi, w) in rig.W.items():
        m = w > best[vi]
        for i in vi[m]:
            who[i] = b
        best[vi[m]] = w[m]
    return who


# —— 服装 ——————————————————————————————————————————————————————————————
MATERIAL = {"torso": "suit", "shin": "suit", "sleeve": "suit", "forearm": "suit", "glove": "rubber", "boot": "rubber"}


def vertex_normals(Q, faces):
    N = np.zeros_like(Q)
    for f in faces:
        a, b, c = Q[f[0]], Q[f[1]], Q[f[2]]
        n = np.cross(b - a, c - a)
        if len(f) == 4:
            n = n + np.cross(c - a, Q[f[3]] - a)
        N[f] += n
    L = np.linalg.norm(N, axis=1)
    L[L < 1e-12] = 1
    return N / L[:, None]


def smooth_labels(faces, labels, keep=(), rounds=3):
    """面标签按相邻面（共边）多数决平滑几轮：分片边界不锯齿。keep 里的类别不动（领口、靴口是平面切的，本来就直）。"""
    edge_faces = {}
    for fi, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            edge_faces.setdefault((min(a, b), max(a, b)), []).append(fi)
    nb = [[] for _ in faces]
    for fs in edge_faces.values():
        for a in fs:
            nb[a] += [b for b in fs if b != a]
    lab = list(labels)
    for _ in range(rounds):
        new = list(lab)
        for fi, ns in enumerate(nb):
            if lab[fi][0] in keep or not ns:
                continue
            votes = [lab[j] for j in ns if lab[j][0] not in keep] + [lab[fi]]
            best = max(set(votes), key=votes.count)
            if votes.count(best) > len(votes) / 2:
                new[fi] = best
        lab = new
    return lab


def ribbon(name, pts, normals, width, thick, material, props):
    """织带：沿 pts 的扁带（宽 width、厚 thick），带面贴着各点的体表法线。"""
    bm = bmesh.new()
    rows = []
    for k, (p, n) in enumerate(zip(pts, normals)):
        t = (pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]).normalized()
        b = t.cross(n).normalized()
        n2 = b.cross(t).normalized()
        rows.append([bm.verts.new(p + b * sx * width / 2 + n2 * sz * thick) for sx, sz in ((-1, 0), (1, 0), (1, 1), (-1, 1))])
    for A, B in zip(rows, rows[1:]):
        for k in range(4):
            bm.faces.new((A[k], B[k], B[(k + 1) % 4], A[(k + 1) % 4]))
    bm.faces.new(list(reversed(rows[0])))
    bm.faces.new(rows[-1])
    o = new_object(name, bm, material, props)
    return o, finish(o, bevel=0.0, angle=40)


def mesh_object(name, verts, faces, material, props):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.update()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(bpy.data.materials.get(material) or bpy.data.materials.new(material))
    bpy.context.scene.collection.objects.link(o)
    for k, v in props.items():
        o[k] = v
    return o, finish(o, bevel=0.0, curved=True)


def piece(name, Q, faces, keep, material, props):
    """faces 里被 keep 选中的面 → 一个对象（顶点重新编号）。"""
    F = [f for f, k in zip(faces, keep) if k]
    if not F:
        return None
    ids = sorted({i for f in F for i in f})
    remap = {v: k for k, v in enumerate(ids)}
    return mesh_object(name, Q[ids], [[remap[i] for i in f] for f in F], material, props)


SEG_CODE = {"torso": 0, "head": 1, "thigh": 2, "shin": 3, "foot": 4, "uarm": 5, "farm": 6, "hand": 7}
SMOOTH_W = {"torso": 1.0, "thigh": 0.9, "uarm": 0.9, "farm": 0.7, "shin": 0.7}


def smooth_body(P, faces, seg, shrink_iters=40, restore_iters=80):
    """去掉解剖细节、保留大体积（服装壳由它外扩，不透出肌肉）：
    ① 按骨段权重做拉普拉斯平滑（躯干最强，胸肌、腹肌、臀部抹平；四肢减弱；手、脚、头不动），会整体缩一点；
    ② 每个顶点沿平滑后的法线缩了多少，把这张“缩量”场本身再平滑很多轮（只剩大尺度），沿法线加回去——
       大体积回来了，局部的鼓包（肌肉）没有回来。"""
    E = set()
    for f in faces:
        for x, y in zip(f, f[1:] + f[:1]):
            E.add((min(x, y), max(x, y)))
    E = np.array(sorted(E))
    w = np.array([SMOOTH_W.get(s.split(".")[0], 0.0) for s in seg])
    body = np.zeros(len(P), bool)
    body[E.ravel()] = True
    w = np.where(body, w, 0.0)[:, None]
    cnt = np.zeros(len(P))
    np.add.at(cnt, E[:, 0], 1)
    np.add.at(cnt, E[:, 1], 1)
    cnt = np.maximum(cnt, 1)[:, None]

    def avg(X):
        acc = np.zeros_like(X)
        np.add.at(acc, E[:, 0], X[E[:, 1]])
        np.add.at(acc, E[:, 1], X[E[:, 0]])
        return acc / cnt

    Q = P.copy()
    for _ in range(shrink_iters):
        Q = Q + w * 0.5 * (avg(Q) - Q)
    Nq = vertex_normals(Q, faces)
    D = ((P - Q) * Nq).sum(1)[:, None]  # 沿法线缩了多少（正 = 往里缩）
    for _ in range(restore_iters):
        D = D + 0.6 * (avg(D) - D)
    return Q + Nq * np.where(body[:, None], D, 0.0)


def plane_segments(V, faces, fnormals, sel, p, n, lift=0.0015):
    """网格与平面 (p, n) 的交线：sel 里的每个面与平面相交的那一段（两点），点沿面法线抬 lift。返回串好的折线 [(点列, 法线列)]。"""
    segs = []
    for fi in sel:
        f = faces[fi]
        d = [(V[i] - p).dot(n) for i in f]
        pts = []
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            da, db = d[k], d[(k + 1) % len(f)]
            if (da < 0) != (db < 0) and abs(da - db) > 1e-12:
                t = da / (da - db)
                pts.append(V[a] + (V[b] - V[a]) * t)
        if len(pts) == 2:
            nn = fnormals[fi]
            segs.append((pts[0] + nn * lift, pts[1] + nn * lift, nn))
    # 首尾相接的段串成折线
    key = lambda q: tuple(np.round(q, 5))  # noqa: E731
    ends = {}
    for k, (a, b, _) in enumerate(segs):
        ends.setdefault(key(a), []).append(k)
        ends.setdefault(key(b), []).append(k)
    used_ = set()
    lines = []
    for k0 in range(len(segs)):
        if k0 in used_:
            continue
        used_.add(k0)
        a, b, nn = segs[k0]
        chain, norms = [a, b], [nn, nn]
        for forward in (True, False):
            while True:
                tip = chain[-1] if forward else chain[0]
                nxt = [k for k in ends.get(key(tip), []) if k not in used_]
                if not nxt:
                    break
                k = nxt[0]
                used_.add(k)
                a2, b2, n2 = segs[k]
                q = b2 if key(a2) == key(tip) else a2
                if forward:
                    chain.append(q)
                    norms.append(n2)
                else:
                    chain.insert(0, q)
                    norms.insert(0, n2)
        lines.append((chain, norms))
    return lines


def inscription(name, text, centre, xdir, ydir, height, props, material="inscription"):
    """胸前小字：Blender 文字转网格（文泉驿正黑，只取字形），按 (xdir, ydir) 贴在 centre 处，字高 height。"""
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    cu.size = height / 0.72  # 字体的字面高约是字号的 0.72
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.0006
    tmp = bpy.data.objects.new(name + ".tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    xd, yd = Vector(xdir).normalized(), Vector(ydir).normalized()
    zd = xd.cross(yd).normalized()
    yd = zd.cross(xd).normalized()
    M = Matrix((xd, yd, zd)).transposed()
    for v in me.vertices:
        v.co = Vector(centre) + M @ v.co
    o = bpy.data.objects.new(name, me)
    o.data.materials.clear()
    o.data.materials.append(bpy.data.materials.get(material) or bpy.data.materials.new(material))
    bpy.context.scene.collection.objects.link(o)
    for k, v in {**props, "lineLevel": "secondary"}.items():
        o[k] = v
    return o, finish(o, bevel=0.0, angle=40)


FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def build(seat, props):
    """seat：srp、back、back_n、pan_h、knee、feet、foot_dir、grips、hand_dir、knuckles、palm、seat_side（腰带扣点）。
    返回 (零件列表, 关节, 服装接缝线)。"""
    P0, faces, used, sk, wt = load()
    rig = Rig(P0, sk, wt)
    dom = dominant(rig)
    seg = [rig.seg_of.get(dom[i], "torso") if dom[i] else "torso" for i in range(len(P0))]
    rig.P = smooth_body(P0, faces, seg)
    P = rig.P
    Q, B, J = solve(rig, seat)
    ankle_z = max(rig.h("foot.L")[2], rig.h("foot.R")[2])
    neck_z = rig.h("neck02")[2]
    N = vertex_normals(Q, faces)
    Nr = vertex_normals(P, faces)
    code = np.array([SEG_CODE[s.split(".")[0]] for s in seg])
    # —— 服装壳：整身外移 SUIT，一张连续的网格；材质边界（腕、靴口、领口）用平面真切开（切口是直的），头部与脚掌切掉 ——
    S = Q + N * SUIT
    ap = lambda M, v: M[0] @ v + M[1]  # noqa: E731
    apn = lambda M, v: norm(M[0] @ v)  # noqa: E731
    cuts = {}
    for sd in "LR":
        el, wr = rig.h(f"lowerarm01.{sd}"), rig.h(f"wrist.{sd}")
        d = norm(wr - el)
        cuts[f"wrist.{sd}"] = (ap(B[f"lowerarm01.{sd}"], wr), apn(B[f"lowerarm01.{sd}"], d), (6, 7), sd)
        kn, an = rig.h(f"lowerleg01.{sd}"), rig.h(f"foot.{sd}")
        up = norm(kn - an)
        for nm, h in (("boot", 0.16), ("shoe", 0.04)):
            t_ = (ankle_z + h - an[2]) / max(1e-6, (kn - an)[2])
            pr = an + (kn - an) * t_
            cuts[f"{nm}.{sd}"] = (ap(B[f"lowerleg01.{sd}"], pr), apn(B[f"lowerleg01.{sd}"], up), (3, 4), sd)
    nk, hd = rig.h("neck01"), rig.h("head")
    cuts["neck"] = (ap(B["neck01"], nk + norm(hd - nk) * 0.04), apn(B["neck01"], norm(hd - nk)), (0, 1), None)
    bm = bmesh.new()
    vmap = {}
    for i in used:
        vmap[i] = bm.verts.new(tuple(S[i]))
    lay_code = bm.faces.layers.int.new("seg")
    lay_side = bm.faces.layers.int.new("side")
    for f in faces:
        try:
            bf = bm.faces.new([vmap[i] for i in f])
        except ValueError:
            continue
        cs = [code[i] for i in f]
        bf[lay_code] = max(set(cs), key=cs.count)
        bf[lay_side] = 1 if P[f, 1].mean() >= 0 else -1
    bm.normal_update()
    for nm, (pc, pn, codes, sd) in cuts.items():
        sg = 0 if sd is None else (1 if sd == "L" else -1)
        geom_f = [f for f in bm.faces if f[lay_code] in codes and (sg == 0 or f[lay_side] == sg) and (f.calc_center_median() - Vector(pc)).length < 0.22]
        if not geom_f:
            continue
        geom_e = list({e for f in geom_f for e in f.edges})
        geom_v = list({v for f in geom_f for v in f.verts})
        bmesh.ops.bisect_plane(bm, geom=geom_f + geom_e + geom_v, dist=1e-7, plane_co=Vector(pc), plane_no=Vector(pn))
    side_of = lambda f, nm: (f.calc_center_median() - Vector(cuts[nm][0])).dot(Vector(cuts[nm][1]))  # noqa: E731
    cls = {}
    dead = []
    for f in bm.faces:
        c, sg = f[lay_code], f[lay_side]
        sd = "L" if sg > 0 else "R"
        k = "suit"
        if c in (0, 1) and side_of(f, "neck") > 0 and (f.calc_center_median() - Vector(cuts["neck"][0])).length < 0.25:
            k = None
        elif c == 1:
            k = None
        elif c in (3, 4) and side_of(f, f"shoe.{sd}") < 0:
            k = None
        elif c in (3, 4) and side_of(f, f"boot.{sd}") < 0:
            k = f"boot.{sd.lower()}"
        elif c in (6, 7) and side_of(f, f"wrist.{sd}") > 0:
            k = f"glove.{sd.lower()}"
        if k is None:
            dead.append(f)
        else:
            cls[f] = k
    bm.verts.index_update()
    V = np.array([tuple(v.co) for v in bm.verts])
    Fall = [([v.index for v in f.verts], cls[f], tuple(f.normal), f[lay_code], f[lay_side]) for f in bm.faces if f in cls]
    bm.free()
    out = []
    for k, mat in (("suit", "suit"), ("glove.l", "rubber"), ("glove.r", "rubber"), ("boot.l", "rubber"), ("boot.r", "rubber")):
        F = [f for f, kk, _, _, _ in Fall if kk == k]
        if not F:
            continue
        ids = sorted({i for f in F for i in f})
        remap = {v: n for n, v in enumerate(ids)}
        out.append(mesh_object(f"int.pilot.{k}", V[ids], [[remap[i] for i in f] for f in F], mat, props))
    # 靴头：脚的凸包（不出脚趾），再垫一块鞋底
    for sd in "LR":
        ids = np.array([i for i in used if P[i, 2] < ankle_z + 0.06 and (P[i, 1] >= 0) == (sd == "L")])
        shoe = Q[ids] + N[ids] * 0.012
        out.append(hull(f"int.pilot.boot.{sd.lower()}.shoe", [Vector(v.tolist()) for v in shoe[:: max(1, len(shoe) // 300)]], "rubber", props, bevel=0.006))
        fd = Vector(seat["foot_dir"].tolist()).normalized()
        down = Vector((fd.z, 0.0, -fd.x))
        d = shoe @ np.array(down)
        low = shoe[d > np.percentile(d, 82)]
        sole = [Vector(v.tolist()) + down * dd for v in low[:: max(1, len(low) // 60)] for dd in (0.0, 0.015)]
        out.append(hull(f"int.pilot.boot.{sd.lower()}.sole", sole, "strap", props, bevel=0.004))
    # —— 接缝线（次级线）：服装壳与平面的交线——袖根、肘、前中拉链、腰线；平面在静止姿态里定，随所在骨段摆到位 ——
    suitF = [(f, n_, c_, s_) for f, kk, n_, c_, s_ in Fall if kk == "suit"]
    SF = [f for f, _, _, _ in suitF]
    SN = [np.array(n_) for _, n_, _, _ in suitF]
    SC = np.array([V[f].mean(0) for f in SF])
    seams = []

    def add(lines):
        for pts, ns in lines:
            if len(pts) >= 2:
                seams.append({"points": [[round(float(x), 4) for x in q] for q in pts], "normals": [[round(float(x), 3) for x in q] for q in ns], "level": "secondary", "cut": False})

    for sd in "LR":
        sh, el, wr = rig.h(f"upperarm01.{sd}"), rig.h(f"lowerarm01.{sd}"), rig.h(f"wrist.{sd}")
        u = norm(el - sh)
        pc, pn = ap(B[f"upperarm01.{sd}"], sh + u * 0.035), apn(B[f"upperarm01.{sd}"], u)
        ea = ap(B[f"upperarm01.{sd}"], el)
        axis = norm(ea - pc)
        near_arm = lambda q: np.linalg.norm((q - pc) - axis * (q - pc).dot(axis)) < 0.075  # noqa: E731
        add(plane_segments(V, SF, SN, [i for i in range(len(SF)) if np.linalg.norm(SC[i] - pc) < 0.11 and near_arm(SC[i])], pc, pn))
        u2 = norm(wr - el)
        pc, pn = ap(B[f"lowerarm01.{sd}"], el + u2 * 0.02), apn(B[f"lowerarm01.{sd}"], u2)
        add(plane_segments(V, SF, SN, [i for i in range(len(SF)) if np.linalg.norm(SC[i] - pc) < 0.08], pc, pn))
    # 前中拉链：静止姿态的 y = 0 平面，只取躯干前面、胯以上领口以下
    crotch = min(rig.h("upperleg01.L")[2], rig.h("upperleg01.R")[2])
    sel = [i for i, (f, n_, c_, s_) in enumerate(suitF) if c_ == 0 and Nr[f].mean(0)[0] > 0.25 and crotch + 0.04 < P[f, 2].mean() < neck_z - 0.03]
    add(plane_segments(V, SF, SN, sel, ap(B["spine03"], np.zeros(3) + rig.h("spine03") * np.array([1, 0, 1])), apn(B["spine03"], Y)))
    # 腰线
    wz = rig.h("spine05") + np.array([0, 0, 0.07])
    sel = [i for i, (f, n_, c_, s_) in enumerate(suitF) if c_ == 0 and abs(P[f, 2].mean() - wz[2]) < 0.05]
    add(plane_segments(V, SF, SN, sel, ap(B["spine05"], wz), apn(B["spine05"], Z)))
    # —— 外层贴片：护膝、大腿 / 小腿 / 腹部分块气囊（比服装再高 8～16 mm）——
    face_c = np.array([P[f].mean(0) for f in faces])
    face_n = np.array([norm(Nr[f].sum(0)) for f in faces])
    face_code = [max(set(code[f].tolist()), key=code[f].tolist().count) for f in faces]
    face_side = ["L" if c[1] >= 0 else "R" for c in face_c]
    fk = [(c, sd) for c, sd in zip(face_code, face_side)]

    def along(i, a, b):
        d = b - a
        return float((face_c[i] - a).dot(d) / d.dot(d))

    pads = []
    for sd in "LR":
        knee = rig.h(f"lowerleg01.{sd}")
        hip, ank = rig.h(f"upperleg01.{sd}"), rig.h(f"foot.{sd}")
        pads.append((f"kneepad.{sd}", 0.02, lambda i, knee=knee: np.linalg.norm(face_c[i] - knee) < 0.065 and face_n[i][0] > 0.2))
        for k, (t0, t1) in enumerate(((0.22, 0.47), (0.5, 0.78))):
            pads.append((f"bladder.thigh{k}.{sd}", 0.012, lambda i, t0=t0, t1=t1, hip=hip, knee=knee, sd=sd: fk[i] in ((0, sd), (2, sd)) and face_n[i][0] > 0.35 and t0 < along(i, hip, knee) < t1 and np.linalg.norm(np.cross(face_c[i] - hip, norm(knee - hip))) < 0.11))
        pads.append((f"bladder.shin.{sd}", 0.011, lambda i, knee=knee, ank=ank, sd=sd: fk[i] == (3, sd) and face_n[i][0] > 0.3 and 0.22 < along(i, knee, ank) < 0.7))
        w0, w1 = rig.h("spine05")[2] + 0.02, rig.h("spine03")[2] - 0.01
        pads.append((f"bladder.abdomen.{sd}", 0.012, lambda i, w0=w0, w1=w1, sd=sd: fk[i] == (0, sd) and face_n[i][0] > 0.55 and w0 < face_c[i][2] < w1 and abs(face_c[i][1]) > 0.012))
    for name, extra, pred in pads:
        keep = [pred(i) for i in range(len(faces))]
        it = piece(f"int.pilot.{name.lower()}", Q + N * (SUIT + extra), faces, keep, "pad" if name.startswith("bladder") else "rubber", props)
        if it:
            out.append(it)
    # 脊背暗朱红细线（未点亮）
    keep = [fk[i][0] == 0 and face_n[i][0] < -0.5 and abs(face_c[i][1]) < 0.011 and rig.h("spine05")[2] < face_c[i][2] < rig.h("neck01")[2] for i in range(len(faces))]
    it = piece("int.pilot.spine", Q + N * (SUIT + 0.003), faces, keep, "vermilion", props)
    if it:
        out.append(it)

    # —— 挽具：沿体表的带子（锚点在静止姿态里找体表顶点，摆姿后沿法线外移）——
    torso_ids = np.array([i for i in used if code[i] == 0 and P[i, 2] < neck_z])
    thigh_ids = np.array([i for i in used if code[i] == 2])

    def vid(y, z, front=True, ids=torso_ids):
        """静止姿态里 (y, z) 处躯干前（后）表面的顶点号。"""
        c = ids[(np.abs(P[ids, 2] - z) < 0.02) & (np.abs(P[ids, 1] - y) < 0.02)]
        if not len(c):
            c = ids[np.argsort(np.abs(P[ids, 2] - z) + np.abs(P[ids, 1] - y))[:5]]
        return c[np.argmax(P[c, 0])] if front else c[np.argmin(P[c, 0])]

    def surf(y, z, front=True, ids=torso_ids, out_=0.004):
        i = vid(y, z, front, ids)
        return Vector((Q[i] + N[i] * (SUIT + out_)).tolist())

    def top(y, z0):
        c = torso_ids[(np.abs(P[torso_ids, 1] - y) < 0.02) & (P[torso_ids, 2] > z0)]
        i = c[np.argmax(P[c, 2])]
        return Vector((Q[i] + N[i] * (SUIT + 0.004)).tolist())

    def drape(pts, ids=torso_ids, step=0.025):
        """折线加密后每点投到最近的几个体表顶点（只在躯干 / 大腿上找，不吸到手臂上），沿平均法线外移，再平滑几轮：
        带子贴着身体走、不打折。返回 (点, 法线)。"""
        dense = []
        for a, b in zip(pts, pts[1:]):
            n = max(1, int((b - a).length / step))
            dense += [a.lerp(b, k / n) for k in range(n)]
        dense.append(pts[-1])
        base = Q[ids]
        P_, N_ = [], []
        for p in dense:
            d = np.linalg.norm(base - np.array(p), axis=1)
            near = np.argsort(d)[:6]
            w = 1.0 / (d[near] + 1e-3)
            q = (base[near] * w[:, None]).sum(0) / w.sum()
            n = norm((N[ids[near]] * w[:, None]).sum(0))
            P_.append(q + n * (SUIT + 0.01))  # 离服装 1 cm：平滑后的折线在胸前凸面上也不陷进去
            N_.append(n)
        P_, N_ = np.array(P_), np.array(N_)
        for _ in range(2):
            P_[1:-1] = 0.5 * P_[1:-1] + 0.25 * (P_[:-2] + P_[2:])
            N_[1:-1] = 0.5 * N_[1:-1] + 0.25 * (N_[:-2] + N_[2:])
        return [Vector(v.tolist()) for v in P_], [Vector(norm(v).tolist()) for v in N_]

    sh_z = rig.h("clavicle.L")[2]
    chest = rig.h("spine02")[2]
    belly = rig.h("spine04")[2]
    hipz = rig.h("spine05")[2] - 0.02
    buckle = surf(0.0, chest - 0.06)
    lap = surf(0.0, hipz)
    for sd, sg in (("l", 1), ("r", -1)):
        # 肩带：背后 → 肩顶 → 胸前 → 胸扣
        pts, ns = drape([surf(sg * 0.08, sh_z - 0.14, False), top(sg * 0.1, sh_z - 0.05), surf(sg * 0.09, chest + 0.06), surf(sg * 0.05, chest - 0.03), buckle])
        out.append(ribbon(f"int.pilot.strap.shoulder.{sd}", pts, ns, 0.045, 0.005, "strap", props))
        # 腰带：腰扣 → 胯侧 → 扣在座椅侧板上
        side_pt = Vector(seat["seat_side"][sd.upper()])
        pts, ns = drape([lap, surf(sg * 0.1, hipz + 0.01), surf(sg * 0.16, hipz + 0.02)])
        pts.append(side_pt)
        ns.append(ns[-1])
        out.append(ribbon(f"int.pilot.strap.lap.{sd}", pts, ns, 0.05, 0.005, "strap", props))
        # 腿带：腰扣 → 绕大腿根前侧 → 外侧
        tz = rig.h(f"upperleg01.{sd.upper()}")[2] - 0.12
        pts, ns = drape([lap] + [surf(sg * a, tz, True, thigh_ids) for a in (0.04, 0.09, 0.14)] + [surf(sg * 0.17, tz + 0.05)], ids=np.concatenate([torso_ids, thigh_ids]))
        out.append(ribbon(f"int.pilot.strap.leg.{sd}", pts, ns, 0.04, 0.005, "strap", props))
    # 胸扣、腰扣（扣面朝外）
    for nm, p, w in (("buckle.chest", buckle, 0.07), ("buckle.lap", lap, 0.08)):
        n = Vector(N[used[np.argmin(np.linalg.norm(Q[used] - np.array(p), axis=1))]].tolist()).normalized()
        xa = n
        za = (Vector((0, 0, 1)) - n * n.z).normalized()
        R = Matrix((xa, za.cross(xa), za)).transposed()
        out.append(box(f"int.pilot.{nm}", p + n * 0.006, (0.016, w, 0.045), rot=R, material="metal", face="+x", panel=False, handles=False, plugs=0, ears=False, corner_bolts=True, props=props))
    # 脐带接口（左胸侧，氧 / 冷 / 电 / 数）：小盒 + 四个插头，软管接到座椅左侧
    port = surf(0.13, chest - 0.02, out_=0.03)
    out.append(box("int.pilot.umbilical", port, (0.06, 0.04, 0.07), material="avionics", face="+y", panel=False, handles=False, plugs=0, ears=False, corner_bolts=True, props=props))
    out.append(pipe("int.pilot.hose", [port + Vector((0, 0.02, -0.03)), port + Vector((-0.08, 0.08, -0.12)), Vector(seat["seat_side"]["L"]) + Vector((0.12, 0.0, 0.05))], 0.014, bend=0.06, sides=10, material="cable", props=props))

    # 胸前铭文「銜燭」（左胸上方，繁体，浅灰小字；从正面读，字行朝驾驶员的左手方向）
    Gc = B["spine02"][0]
    anchor = surf(0.04, chest + 0.06, out_=0.0)
    i0 = used[np.argmin(np.linalg.norm(Q[used] - np.array(anchor), axis=1))]
    nrm = Vector(N[i0].tolist())
    out.append(inscription("int.pilot.inscription", "銜燭", anchor + nrm * 0.004, Vector((Gc @ Y).tolist()), Vector((Gc @ Z).tolist()), 0.018, props))

    # —— 头盔（DESIGN 9.1.1 重做）：蛋形盔壳 + 盔顶前凸的眉骨（与机身眉骨同一语言）+ 窄面罩（透明，睁眼态）+ 面罩上沿收起的
    # 暗琥珀遮光面罩 + 下颌护条 + 盔脊 + 两侧面罩铰链 + 颈环。各件分开建、材质分开，转台全景里也读得出来 ——
    head_ids = np.array([i for i in used if code[i] == 1 and P[i, 2] > neck_z])
    G, t = B["head"]
    f, l, u = (Vector(G @ v) for v in (X, Y, Z))
    c = Vector(Q[head_ids].mean(0)) + u * 0.02 - f * 0.005
    R = (0.138, 0.126, 0.146)
    axes = (f, l, u)
    out.append(ellipsoid("int.pilot.helmet", c, R, axes, u=40, v=20, material="helmet", props=props))

    def on(az, el, k=1.0):
        a, e = math.radians(az), math.radians(el)
        return c + f * (R[0] * k * math.cos(e) * math.cos(a)) + l * (R[1] * k * math.cos(e) * math.sin(a)) + u * (R[2] * k * math.sin(e))

    def patch(name, az0, az1, el0, el1, k, material, extra=None, step=6):
        pts = [on(a, e, k) for a in np.arange(az0, az1 + 0.1, step) for e in np.arange(el0, el1 + 0.1, step)]
        pts += [on(a, e, 0.94) for a in (az0, (az0 + az1) / 2, az1) for e in (el0, el1)]
        return hull(name, pts, material, {**props, **(extra or {})}, bevel=0.002)

    # 面罩框（暗金属，比玻璃大一圈）→ 窄面罩：方位 ±40°、俯仰 −30°～+8°
    out.append(patch("int.pilot.visor.frame", -45, 45, -35, 11, 1.022, "frame"))
    out.append(patch("int.pilot.visor", -40, 40, -30, 8, 1.04, "glass", {"glass": True}, step=5))
    # 收起的遮光面罩：面罩上沿、眉骨下一条暗琥珀
    out.append(patch("int.pilot.sunvisor", -40, 40, 10, 17, 1.05, "visor", step=4))
    # 下颌护条：面罩下沿
    out.append(patch("int.pilot.helmet.chin", -38, 38, -44, -33, 1.035, "helmet", step=5))
    # 眉骨：盔顶前沿一道前凸的楔，中间最凸（约 3.5 cm），两端收进盔壳
    brow = []
    for a in range(-50, 51, 5):
        w = math.cos(math.radians(a) * 1.4) ** 2 if abs(a) < 64 else 0.0
        brow += [on(a, 15, 1.0), on(a, 31, 0.995), on(a, 20, 1.0 + 0.25 * w), on(a, 25, 1.0 + 0.18 * w)]
    out.append(hull("int.pilot.helmet.brow", brow, "frame", props, bevel=0.003))
    # 盔脊：眉骨后沿顶中线到后脑，一条凸起 1 cm 的窄脊（分三段凸体）
    for k, (e0, e1) in enumerate(((30, 70), (70, 115), (115, 150))):
        pts = []
        for e in (e0, e1):
            for a in (-8, 8):
                ang = math.radians(e)
                base = c + f * (R[0] * math.cos(ang)) + u * (R[2] * math.sin(ang))
                n = (base - c).normalized()
                pts += [base + l * (R[1] * math.sin(math.radians(a))) + n * d for d in (-0.004, 0.01)]
        out.append(hull(f"int.pilot.helmet.ridge{k}", pts, "helmet", props, bevel=0.002))
    # 面罩铰链（两侧圆盘 + 中心螺栓）、颈环（镀铬，带两只锁扣）
    for sd, sg in (("l", 1), ("r", -1)):
        p = on(90 * sg, 2, 1.0)
        out.append(cylinder(f"int.pilot.helmet.hinge.{sd}", p - l * sg * 0.004, p + l * sg * 0.014, 0.034, 20, "metal", props, bevel=0.002))
        out.append(cylinder(f"int.pilot.helmet.hinge.{sd}.bolt", p + l * sg * 0.012, p + l * sg * 0.02, 0.009, 6, "chrome", props, bevel=0.0))
    neck = Vector(J["neck"])
    ax = Vector(G @ Z)
    out.append(lathe("int.pilot.neckring", neck - ax * 0.012, neck + ax * 0.04, [(0, 0.092), (0.25, 0.104), (0.75, 0.104), (1, 0.096)], 32, "chrome", props))
    for sd, sg in (("l", 1), ("r", -1)):
        p = neck + ax * 0.014 + l * sg * 0.104
        out.append(box(f"int.pilot.neckring.latch.{sd}", p, (0.03, 0.016, 0.022), material="metal", face="+y", panel=False, handles=False, plugs=0, ears=False, props=props))
    return out, {k: Vector(v) for k, v in J.items()} | {"head": c, "helmet_top": c + u * R[2]}, seams
